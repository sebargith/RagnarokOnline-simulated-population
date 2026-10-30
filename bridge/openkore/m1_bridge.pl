# Project-owned restricted control plugin for the pinned OpenKore revision.
package M1Bridge;
use strict;
use warnings;
use IO::Socket::INET;
use IO::Select;
use JSON::PP;
use Time::HiRes qw(time);
use Globals qw($net $char $field $messageSender $playersList %config $quit $conState_tries);
use Plugins;
use Network;

my ($server, $client, $cfg, $hooks, $pending);
my ($input, $output, $authorized, $auth_time) = ('', '', 0, 0);
my ($seq, $epoch, $in_game, $last_snapshot, $last_action) = (0, 0, 0, 0, 0);
my %seen;
my ($attempts, $recovery_deadline, $stopping) = (0, 0, 0);
my $json = JSON::PP->new->utf8->canonical;
my $boot = sprintf('%x-%x-%x', time * 1000, $$, rand(2**30));

Plugins::register('m1_bridge', 'Bounded loopback observation/action bridge', \&unload);
$hooks = Plugins::addHooks(
    ['start3', \&start], ['mainLoop_pre', \&tick],
    ['packet/character_moves', \&moved],
    ['packet_selfChat', \&self_chat], ['packet_pubMsg', \&public_chat],
    ['Network::serverConnect/master', \&reconnecting], ['checkConnection', \&check_connection],
);

sub start {
    open my $fh, '<:raw', $ENV{M1_BRIDGE_CONFIG} or die "M1_BRIDGE_CONFIG required: $!";
    local $/; $cfg = $json->decode(<$fh>); close $fh;
    die 'Invalid bridge configuration' unless $cfg->{port} =~ /^876[567]$/ && length($cfg->{token}) >= 20;
    $server = IO::Socket::INET->new(LocalAddr => '127.0.0.1', LocalPort => $cfg->{port},
        Listen => 1, Proto => 'tcp', ReuseAddr => 0) or die "Bridge listen: $!";
    $server->blocking(0);
    $recovery_deadline = time + 90;
    print "M1 bridge listening on 127.0.0.1:$cfg->{port}\n";
}

sub session { "$boot:$epoch" }
sub connected { $net && $net->getState() == Network::IN_GAME && $net->serverAlive() && $char && $field }

sub reconnecting {
    ++$attempts;
    emit('reconnect_attempt', {attempt => $attempts, max_attempts => 3});
}

sub check_connection {
    my (undef, $args) = @_;
    $args->{return} = 1 if $stopping;
}

sub drop_client {
    close $client if $client;
    undef $client; $authorized = 0; $input = ''; $output = '';
    # Pending game actions continue to their observation/deadline, never reissued.
}

sub emit {
    my ($kind, $data) = @_;
    return unless $client && $authorized;
    my $line = $json->encode({v => 1, agent_id => $cfg->{agent_id},
        source => 'openkore', id => "$boot:" . ++$seq, time_ms => int(time * 1000),
        session => session(), kind => $kind, data => $data}) . "\n";
    # Bounded output: close on overflow; next auth explicitly supplies resync snapshot.
    if (length($output) + length($line) > 65536) { drop_client(); return }
    $output .= $line;
}

sub snapshot {
    my $ready = connected() ? 1 : 0;
    my $s = {connected => $ready};
    if ($ready) {
        $s->{name} = $char->{name}; $s->{map} = $field->baseName;
        $s->{position} = {x => 0 + $char->{pos}{x}, y => 0 + $char->{pos}{y}};
        $s->{destination} = {x => 0 + $char->{pos_to}{x}, y => 0 + $char->{pos_to}{y}};
        $s->{hp} = 0 + ($char->{hp} // 0); $s->{hp_max} = 0 + ($char->{hp_max} // 0);
        $s->{inventory_ready} = $char->inventory->isReady ? 1 : 0;
        $s->{field} = {width => $field->width, height => $field->height};
        my @inventory = map {{name => $_->{name}, name_id => 0 + $_->{nameID}, amount => 0 + $_->{amount}}}
            @{$char->inventory->getItems};
        $s->{inventory} = [@inventory[0 .. ($#inventory > 31 ? 31 : $#inventory)]];
        my @players = map {{name => $_->{name} // '', id => unpack('H*', $_->{ID}),
            x => 0 + $_->{pos_to}{x}, y => 0 + $_->{pos_to}{y}}} @{$playersList->getItems};
        $s->{players} = [@players[0 .. ($#players > 31 ? 31 : $#players)]];
    }
    emit('snapshot', $s);
}

sub result {
    my ($id, $status, $reason, $evidence) = @_;
    my $r = {request_id => $id, status => $status, reason => $reason};
    $r->{evidence} = $evidence if $evidence;
    $seen{$id} = $r if exists $seen{$id};
    emit('action_result', $r);
}

sub finish {
    my ($status, $reason, $evidence) = @_;
    return unless $pending;
    result($pending->{id}, $status, $reason, $evidence);
    undef $pending;
}

sub request {
    my ($r) = @_;
    unless (ref($r) eq 'HASH') { emit('protocol_error', {reason => 'object_required'}); return }
    my $id = $r->{id};
    unless (defined($id) && !ref($id) && $id =~ /^[A-Za-z0-9_-]{1,64}$/) {
        emit('protocol_error', {reason => 'invalid_request_id'}); return;
    }
    if (exists $seen{$id}) { emit('action_result', {%{$seen{$id}}, replay => 1}); return }
    # Retain IDs for this game session; refuse further actions at capacity, never evict.
    if (keys(%seen) >= 128) { result($id, 'rejected', 'session_action_limit'); return }
    $seen{$id} = {};
    unless (join(',', sort keys %$r) eq 'action,deadline_ms,id,session,v' &&
        !ref($r->{v}) && $r->{v} == 1 && !ref($r->{session}) &&
        defined($r->{deadline_ms}) && !ref($r->{deadline_ms}) && $r->{deadline_ms} =~ /^\d{13}$/) {
        result($id, 'rejected', 'invalid_envelope'); return;
    }
    if ($r->{session} ne session()) { result($id, 'rejected', 'stale_session'); return }
    if (!connected()) { result($id, 'rejected', 'disconnected'); return }
    my $remaining = $r->{deadline_ms} - time * 1000;
    if ($remaining <= 0 || $remaining > 5000) { result($id, 'rejected', 'invalid_deadline'); return }
    if ($pending) { result($id, 'rejected', 'busy'); return }
    if (time - $last_action < 1) { result($id, 'rejected', 'rate_limited'); return }
    my $a = $r->{action};
    unless (ref($a) eq 'HASH' && defined($a->{type}) && !ref($a->{type})) {
        result($id, 'rejected', 'invalid_action'); return;
    }
    if ($a->{type} eq 'move') {
        unless (join(',', sort keys %$a) eq 'map,type,x,y' && !ref($a->{map}) && $a->{map} eq $field->baseName &&
            defined($a->{x}) && defined($a->{y}) && !ref($a->{x}) && !ref($a->{y}) &&
            $a->{x} =~ /^\d{1,3}$/ && $a->{y} =~ /^\d{1,3}$/ &&
            abs($a->{x} - $char->{pos_to}{x}) <= 1 && abs($a->{y} - $char->{pos_to}{y}) <= 1 &&
            $a->{x} < $field->width && $a->{y} < $field->height && $field->isWalkable($a->{x}, $a->{y}) &&
            ($a->{x} != $char->{pos_to}{x} || $a->{y} != $char->{pos_to}{y}) && $char->{hp} > 0) {
            result($id, 'rejected', 'invalid_move'); return;
        }
        $pending = {id => $id, action => $a, deadline => $r->{deadline_ms} / 1000};
        $messageSender->sendMove($a->{x}, $a->{y});
    } elsif ($a->{type} eq 'chat') {
        unless (join(',', sort keys %$a) eq 'text,type' && defined($a->{text}) && !ref($a->{text}) &&
            $a->{text} =~ /^[\x20-\x7e]{1,80}$/ && $a->{text} !~ /^\s*[@#\/;]/) {
            result($id, 'rejected', 'invalid_chat'); return;
        }
        $pending = {id => $id, action => $a, deadline => $r->{deadline_ms} / 1000};
        $messageSender->sendChat($a->{text});
    } else { result($id, 'rejected', 'action_not_allowed'); return }
    $last_action = time;
    result($id, 'accepted', 'packet_sent');
}

sub moved {
    my (undef, $args) = @_;
    return unless connected();
    my $dest = {x => 0 + $char->{pos_to}{x}, y => 0 + $char->{pos_to}{y}};
    emit('movement_ack', {destination => $dest, packet => $args->{switch}});
    if ($pending && $pending->{action}{type} eq 'move' &&
        $dest->{x} == $pending->{action}{x} && $dest->{y} == $pending->{action}{y}) {
        finish('completed', 'server_movement_ack', {destination => $dest, packet => $args->{switch}});
    }
}

sub self_chat {
    my (undef, $args) = @_;
    return unless defined($args->{user}) && defined($args->{msg});
    emit('chat', {speaker => $args->{user}, text => $args->{msg}, self => 1});
    if ($pending && $pending->{action}{type} eq 'chat' && defined($args->{msg}) && $args->{msg} eq $pending->{action}{text}) {
        finish('completed', 'server_chat_echo', {text => $args->{msg}});
    }
}

sub public_chat {
    my (undef, $args) = @_;
    emit('chat', {speaker => $args->{pubMsgUser}, text => $args->{pubMsg}, self => 0});
}

sub tick {
    return unless $server;
    my $ready = connected() ? 1 : 0;
    if ($ready != $in_game) {
        finish('unknown', 'game_disconnected') unless $ready;
        if ($ready) { ++$epoch; %seen = (); $attempts = 0; $recovery_deadline = 0 }
        else { $recovery_deadline = time + 90 }
        $in_game = $ready;
        emit('connection', {connected => $ready});
        snapshot();
    }
    if (!$ready && !$stopping && $recovery_deadline && (time >= $recovery_deadline ||
        ($attempts >= 3 && $net->getState() == Network::NOT_CONNECTED && !$conState_tries))) {
        finish('unknown', 'reconnect_exhausted');
        emit('reconnect_exhausted', {attempts => $attempts, deadline_seconds => 90});
        $stopping = time + .2;
    }
    $quit = 1 if $stopping && time >= $stopping;
    finish('unknown', 'confirmation_timeout') if $pending && time >= $pending->{deadline};
    if (!$client) {
        $client = $server->accept();
        if ($client) { $client->blocking(0); $auth_time = time }
    }
    return unless $client;
    if (!$authorized && time - $auth_time > 3) { drop_client(); return }
    my $select = IO::Select->new($client);
    if ($select->can_read(0)) {
        my $count = sysread($client, my $chunk, 4096);
        if (!defined($count) || !$count) { drop_client(); return }
        $input .= $chunk;
        if (length($input) > 4096) { drop_client(); return }
    }
    # Drain buffered frames even when no additional socket bytes arrive.
    # At most four frames per game tick; a bounded input buffer limits flooding.
    {
        for (1..4) {
            last unless $input =~ s/^([^\n]*)\n//;
            my $r = eval { $json->decode($1) };
            if ($@) { drop_client(); return }
            if (!$authorized) {
                unless (ref($r) eq 'HASH' && join(',', sort keys %$r) eq 'token,type' &&
                    !ref($r->{type}) && $r->{type} eq 'auth' && !ref($r->{token}) && $r->{token} eq $cfg->{token}) {
                    drop_client(); return;
                }
                $authorized = 1;
                emit('ready', {resync => 1, pending_request_id => $pending ? $pending->{id} : undef,
                    limits => {frame_bytes => 4096, output_bytes => 65536, actions_per_session => 128}});
                snapshot();
            } else { request($r) }
        }
    }
    if ($authorized && time - $last_snapshot >= 1) { snapshot(); $last_snapshot = time }
    if (length($output) && $select->can_write(0)) {
        my $sent = syswrite($client, $output, length($output) > 4096 ? 4096 : length($output));
        if (!defined($sent)) { drop_client(); return }
        substr($output, 0, $sent, '');
    }
}

sub unload {
    Plugins::delHooks($hooks) if $hooks;
    drop_client(); close $server if $server;
}
1;
