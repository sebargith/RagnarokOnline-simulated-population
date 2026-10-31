# Project-owned restricted control plugin for the pinned OpenKore revision.
package M1Bridge;
use strict;
use warnings;
use IO::Socket::INET;
use IO::Select;
use JSON::PP;
use Time::HiRes qw(time);
use Globals qw($net $char $field $messageSender $playersList $monstersList $itemsList $accountID %currentDeal %incomingDeal %outgoingDeal %config $quit $conState_tries);
use Misc ();
use Plugins;
use Network;
use AI ();
use Task ();
use Utils ();
use M4RequestWindow;
use M1Navigation;

my ($server, $client, $cfg, $hooks, $pending);
my ($input, $output, $authorized, $auth_time) = ('', '', 0, 0);
my ($seq, $epoch, $in_game, $last_snapshot, $last_action) = (0, 0, 0, 0, 0);
my %seen;
my $serial_window = M4RequestWindow->new(128);
my ($trade_offered, $trade_used) = (0, 0);
my ($attempts, $recovery_deadline, $stopping) = (0, 0, 0);
my $json = JSON::PP->new->utf8->canonical;
my $boot = sprintf('%x-%x-%x', time * 1000, $$, rand(2**30));

Plugins::register('m1_bridge', 'Bounded loopback observation/action bridge', \&unload);
$hooks = Plugins::addHooks(
    ['start3', \&start], ['mainLoop_pre', \&tick],
    ['packet/character_moves', \&moved],
    ['packet_selfChat', \&self_chat], ['packet_pubMsg', \&public_chat],
    ['packet_attack', \&combat], ['monster_disappeared', \&monster_gone],
    ['packet/inventory_item_added', \&inventory_added],
    ['engaged_deal', \&trade_engaged], ['incoming_deal', \&trade_incoming],
    ['packet/deal_add_you', \&trade_added], ['packet/deal_finalize', \&trade_locked],
    ['complete_deal', \&trade_complete], ['cancelled_deal', \&trade_cancelled],
    ['Network::serverConnect/master', \&reconnecting], ['checkConnection', \&check_connection],
);

sub start {
    open my $fh, '<:raw', $ENV{M1_BRIDGE_CONFIG} or die "M1_BRIDGE_CONFIG required: $!";
    local $/; $cfg = $json->decode(<$fh>); close $fh;
    die 'Invalid bridge configuration' unless $cfg->{port} =~ /^(876[567]|8770)$/ && length($cfg->{token}) >= 20;
    # Native profiles have exactly one movement owner: OpenKore's route task.
    die 'Native navigation requires --ai=manual' if $cfg->{native_navigation} && AI::state() != AI::MANUAL();
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
        $s->{executor} = $cfg->{native_navigation} ? 'openkore_route' : 'bridge_steps';
        $s->{navigation} = $pending && $pending->{task} ? $pending->{id} : undef;
        $s->{hp} = 0 + ($char->{hp} // 0); $s->{hp_max} = 0 + ($char->{hp_max} // 0);
        $s->{zeny} = 0 + ($char->{zeny} // 0);
        my $own_items = $currentDeal{you} // {};
        my $other_items = $currentDeal{other} // {};
        $s->{deal} = {name => $currentDeal{name} // '', incoming => $incomingDeal{name} // '',
            you_zeny => 0 + ($currentDeal{you_zeny} // 0), other_zeny => 0 + ($currentDeal{other_zeny} // 0),
            you_item => 0 + (($own_items->{909} // {})->{amount} // 0), other_item => 0 + (($other_items->{909} // {})->{amount} // 0),
            you_locked => $currentDeal{you_finalize} ? 1 : 0, other_locked => $currentDeal{other_finalize} ? 1 : 0};
        $s->{inventory_ready} = $char->inventory->isReady ? 1 : 0;
        $s->{field} = {width => $field->width, height => $field->height};
        my @inventory = map {{name => $_->{name}, name_id => 0 + $_->{nameID}, amount => 0 + $_->{amount}}}
            @{$char->inventory->getItems};
        $s->{inventory} = [@inventory[0 .. ($#inventory > 31 ? 31 : $#inventory)]];
        my @players = map {{name => $_->{name} // '', id => unpack('H*', $_->{ID}),
            x => 0 + $_->{pos_to}{x}, y => 0 + $_->{pos_to}{y}}} @{$playersList->getItems};
        $s->{players} = [@players[0 .. ($#players > 31 ? 31 : $#players)]];
        my @monsters = map {{id => unpack('H*', $_->{ID}), name => $_->{name}, name_id => 0 + $_->{nameID},
            x => 0 + $_->{pos_to}{x}, y => 0 + $_->{pos_to}{y}}} @{$monstersList->getItems};
        $s->{monsters} = [@monsters[0 .. ($#monsters > 15 ? 15 : $#monsters)]];
        my @items = map {{id => unpack('H*', $_->{ID}), name_id => 0 + $_->{nameID}, amount => 0 + $_->{amount},
            x => 0 + $_->{pos}{x}, y => 0 + $_->{pos}{y}}} @{$itemsList->getItems};
        $s->{ground_items} = [@items[0 .. ($#items > 15 ? 15 : $#items)]];
    }
    emit('snapshot', $s);
}

sub result {
    my ($id, $status, $reason, $evidence) = @_;
    my $r = {request_id => $id, status => $status, reason => $reason};
    $r->{evidence} = $evidence if $evidence;
    $seen{$id} = $r if exists $seen{$id};
    $serial_window->finish($id, $r);
    emit('action_result', $r);
}

sub finish {
    my ($status, $reason, $evidence) = @_;
    return unless $pending;
    result($pending->{id}, $status, $reason, $evidence);
    undef $pending;
}

sub nav_evidence {
    return {} unless connected();
    my $calc = Utils::calcPosFromPathfinding($field, $char);
    {map => $field->baseName, position => {x => 0 + $calc->{x}, y => 0 + $calc->{y}},
        pos_to => {x => 0 + $char->{pos_to}{x}, y => 0 + $char->{pos_to}{y}},
        elapsed_ms => int((time - $pending->{started}) * 1000)};
}

# Removes the route task and halts at the predicted cell; never resumes later.
sub stop_route {
    AI::clear(qw/move route mapRoute/);
    $char->sendAttackStop if connected();
}

sub navigation_tick {
    my $task = $pending->{task};
    my $state = !grep({ ref($_) && $_ == $task } @AI::ai_seq_args) ? 'missing' :
        $task->getStatus() == Task::DONE() ? 'done' : $task->getStatus() == Task::STOPPED() ? 'stopped' : 'running';
    # processTask dequeues a DONE task in the same AI pass, so a finished task
    # is usually 'missing' here; its retained status still tells us the outcome.
    $state = 'done' if $state eq 'missing' && $task->getStatus() == Task::DONE();
    if (AI::state() != AI::MANUAL()) {
        stop_route(); finish('unknown', 'executor_mode_changed', nav_evidence()); return;
    }
    my $a = $pending->{action};
    my $evidence = nav_evidence();
    # Task::getError asserts DONE; a running task has no error to read.
    my $error = $state eq 'done' ? $task->getError() : undef;
    my ($status, $reason) = M1Navigation::outcome($state, $error,
        {map => $evidence->{map}, dest_map => $a->{map}, pos_to => $evidence->{pos_to},
         calc => $evidence->{position}, dest => {x => $a->{x}, y => $a->{y}}});
    if ($status) {
        # Any non-arrival halts at the predicted cell instead of coasting on.
        stop_route() unless $status eq 'completed';
        $evidence->{route_error} = $error->{message} if $error;
        finish($status, $reason, $evidence); return;
    }
    if (time >= $pending->{deadline}) { stop_route(); finish('failed', 'timeout', $evidence); return }
    if (time - $pending->{progress} >= 1) {
        $pending->{progress} = time;
        emit('navigation_progress', {request_id => $pending->{id}, %$evidence,
            destination => {x => 0 + $a->{x}, y => 0 + $a->{y}},
            distance => M1Navigation::distance($evidence->{position}, $a)});
    }
}

sub request {
    my ($r) = @_;
    unless (ref($r) eq 'HASH') { emit('protocol_error', {reason => 'object_required'}); return }
    my $id = $r->{id};
    unless (defined($id) && !ref($id) && $id =~ /^[A-Za-z0-9_-]{1,64}$/) {
        emit('protocol_error', {reason => 'invalid_request_id'}); return;
    }
    if ($id =~ /^c_(\d{1,15})$/) {
        my ($state, $cached) = $serial_window->admit($id);
        if ($state eq 'cached') { emit('action_result', {%$cached, replay => 1}); return }
        # A boot-lifetime high-water mark rejects evicted IDs forever. A new
        # controller learns the next sequence at auth; it never resends intents.
        if ($state eq 'retired') { result($id, 'rejected', 'retired_request'); return }
    } else {
        if (exists $seen{$id}) { emit('action_result', {%{$seen{$id}}, replay => 1}); return }
        # Preserve the original UUID/demo contract without unsafe eviction.
        if (keys(%seen) >= 128) { result($id, 'rejected', 'session_action_limit'); return }
        $seen{$id} = {};
    }
    unless (join(',', sort keys %$r) eq 'action,deadline_ms,id,session,v' &&
        !ref($r->{v}) && $r->{v} == 1 && !ref($r->{session}) &&
        defined($r->{deadline_ms}) && !ref($r->{deadline_ms}) && $r->{deadline_ms} =~ /^\d{13}$/) {
        result($id, 'rejected', 'invalid_envelope'); return;
    }
    if ($r->{session} ne session()) { result($id, 'rejected', 'stale_session'); return }
    if (!connected()) { result($id, 'rejected', 'disconnected'); return }
    my $remaining = $r->{deadline_ms} - time * 1000;
    if ($remaining <= 0 || $remaining > 5000) { result($id, 'rejected', 'invalid_deadline'); return }
    my $a = $r->{action};
    unless (ref($a) eq 'HASH' && defined($a->{type}) && !ref($a->{type})) {
        result($id, 'rejected', 'invalid_action'); return;
    }
    # Cancel is exempt from busy/rate limits: it only ends the active route.
    if ($a->{type} eq 'cancel') {
        unless (join(',', sort keys %$a) eq 'target,type' && defined($a->{target}) && !ref($a->{target}) &&
            $pending && $pending->{task} && $a->{target} eq $pending->{id}) {
            result($id, 'rejected', 'no_matching_navigation'); return;
        }
        stop_route();
        finish('cancelled', 'cancel_requested', nav_evidence());
        result($id, 'completed', 'navigation_cancelled');
        return;
    }
    if ($pending) { result($id, 'rejected', 'busy'); return }
    if (time - $last_action < 1) { result($id, 'rejected', 'rate_limited'); return }
    if ($a->{type} eq 'navigate') {
        my $reason = M1Navigation::validate($a, {manual_ai => $cfg->{native_navigation} && AI::state() == AI::MANUAL(),
            hp => $char->{hp}, map => $field->baseName, width => $field->width, height => $field->height,
            walkable => sub { $field->isWalkable(@_) }, pos_to => $char->{pos_to}});
        if ($reason) { result($id, 'rejected', $reason); return }
        AI::clear(qw/move route mapRoute/);
        $char->route($field->baseName, $a->{x}, $a->{y}, noMapRoute => 1, maxRouteTime => $a->{timeout_s},
            attackOnRoute => 0, noSitAuto => 1);
        my $task = AI::action() eq 'route' ? $AI::ai_seq_args[0] : undef;
        unless ($task) { result($id, 'rejected', 'route_not_queued'); return }
        my $now = time;
        $pending = {id => $id, action => $a, task => $task, started => $now, progress => 0,
            deadline => $now + $a->{timeout_s} + M1Navigation::GRACE};
        $last_action = $now;
        result($id, 'accepted', 'route_queued');
        return;
    }
    if ($a->{type} eq 'move' && $cfg->{native_navigation}) { result($id, 'rejected', 'legacy_executor_disabled'); return }
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
    } elsif ($a->{type} eq 'attack' || $a->{type} eq 'take') {
        unless ($cfg->{m4_fixture} && join(',', sort keys %$a) eq 'target,type' &&
            defined($a->{target}) && !ref($a->{target}) && $a->{target} =~ /^[a-f0-9]{8}$/ &&
            $field->baseName eq 'prontera' && $char->{hp} > 0) {
            result($id, 'rejected', 'invalid_pve'); return;
        }
        my $target = ($a->{type} eq 'attack' ? $monstersList : $itemsList)->getByID(pack('H*', $a->{target}));
        my $pos = $target ? ($a->{type} eq 'attack' ? $target->{pos_to} : $target->{pos}) : undef;
        unless ($target && $pos && abs($pos->{x} - $char->{pos_to}{x}) <= 1 &&
            abs($pos->{y} - $char->{pos_to}{y}) <= 1 &&
            ($a->{type} eq 'attack' ? ($target->{nameID} == 1002 && !$target->{dead}) : $target->{nameID} == 909)) {
            result($id, 'rejected', 'target_not_visible_nearby_or_allowed'); return;
        }
        $pending = {id => $id, action => $a, deadline => $r->{deadline_ms}/1000};
        if ($a->{type} eq 'attack') { $messageSender->sendAction($target->{ID}, 0) }
        else { $messageSender->sendTake($target->{ID}) }
    } elsif ($a->{type} =~ /^trade_(request|accept|offer|lock|commit)$/) {
        unless ($cfg->{m4_fixture} && $cfg->{trade_role} && join(',', sort keys %$a) eq 'type' &&
            $field->baseName eq 'prontera' && $char->{hp} > 0 && $char->inventory->isReady) {
            result($id, 'rejected', 'invalid_trade'); return;
        }
        my ($partner) = grep { ($_->{name} // '') eq $cfg->{trade_peer} } @{$playersList->getItems};
        unless ($partner && abs($partner->{pos_to}{x}-$char->{pos_to}{x}) <= 2 && abs($partner->{pos_to}{y}-$char->{pos_to}{y}) <= 2) {
            result($id, 'rejected', 'trade_peer_not_nearby'); return;
        }
        my $type = $a->{type};
        if ($type eq 'trade_request') {
            unless ($cfg->{trade_role} eq 'seller' && !$trade_used && !%currentDeal && !%incomingDeal && !%outgoingDeal) {
                result($id, 'rejected', 'trade_unavailable'); return;
            }
            $pending = {id => $id, action => $a, deadline => $r->{deadline_ms}/1000};
            $trade_used = 1;
            Misc::deal($partner);
        } elsif ($type eq 'trade_accept') {
            unless ($cfg->{trade_role} eq 'buyer' && !$trade_used && ($incomingDeal{name} // '') eq $cfg->{trade_peer} && !%currentDeal) {
                result($id, 'rejected', 'unexpected_incoming_trade'); return;
            }
            $pending = {id => $id, action => $a, deadline => $r->{deadline_ms}/1000};
            $trade_used = 1;
            $messageSender->sendDealReply(3);
        } else {
            unless (($currentDeal{name} // '') eq $cfg->{trade_peer}) {
                result($id, 'rejected', 'wrong_trade_peer'); return;
            }
            if ($type eq 'trade_offer') {
                if ($trade_offered || $currentDeal{you_finalize}) { result($id, 'rejected', 'offer_already_sent_or_locked'); return }
                my ($item) = grep { $_->{nameID} == 909 && $_->{amount} >= 1 && !$_->{equipped} } @{$char->inventory->getItems};
                unless ($cfg->{trade_role} eq 'seller' ? $item : $char->{zeny} >= 10) {
                    result($id, 'rejected', 'insufficient_trade_assets'); return;
                }
                $pending = {id => $id, action => $a, deadline => $r->{deadline_ms}/1000};
                $trade_offered = 1;
                if ($cfg->{trade_role} eq 'seller') { Misc::dealAddItem($item, 1) }
                else {
                    $currentDeal{you_zeny} = 10;
                    unless (trade_matches()) { undef $pending; result($id, 'rejected', 'buyer_offer_mismatch'); return }
                    # Legacy protocol acknowledges Zeny only to the OTHER side.
                    # Lock after the fixed offer; our lock ack confirms acceptance.
                    $messageSender->sendDealAddItem(pack('v',0), 10);
                    $messageSender->sendDealFinalize();
                }
            } else {
                unless (trade_matches() && $trade_offered && !$currentDeal{final} &&
                    ($type eq 'trade_lock' ? !$currentDeal{you_finalize} : ($currentDeal{you_finalize} && $currentDeal{other_finalize}))) {
                    result($id, 'rejected', 'trade_offer_or_lock_mismatch'); return;
                }
                $pending = {id => $id, action => $a, deadline => $r->{deadline_ms}/1000};
                if ($type eq 'trade_lock') { $messageSender->sendDealFinalize() }
                else { $currentDeal{final} = 1; $messageSender->sendDealTrade() }
            }
        }
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

sub combat {
    my (undef, $args) = @_;
    my $data = {source => unpack('H*', $args->{sourceID}), target => unpack('H*', $args->{targetID}),
        damage => 0 + $args->{dmg}, self => $args->{sourceID} eq $accountID ? 1 : 0};
    emit('combat', $data);
    if ($pending && $pending->{action}{type} eq 'attack' && $data->{self} && $data->{target} eq $pending->{action}{target}) {
        finish('completed', 'server_attack', $data);
    }
}

sub monster_gone {
    my (undef, $args) = @_;
    my $m = $args->{monster};
    emit('monster_departure', {target => unpack('H*', $m->{ID}), dead => $m->{dead} ? 1 : 0, name_id => 0 + $m->{nameID}});
}

sub inventory_added {
    my (undef, $args) = @_;
    return if $args->{fail};
    my $data = {name_id => 0 + $args->{nameID}, amount => 0 + $args->{amount}};
    emit('inventory_added', $data);
    if ($pending && $pending->{action}{type} eq 'take' && $data->{name_id} == 909 && $data->{amount} > 0) {
        finish('completed', 'server_inventory_add', $data);
    }
}

sub trade_matches {
    my $seller = $cfg->{trade_role} eq 'seller';
    return 0 unless ($currentDeal{name} // '') eq $cfg->{trade_peer};
    my $own = $currentDeal{you} // {};
    my $other = $currentDeal{other} // {};
    return 0 if grep { $_ != 909 && ($own->{$_}{amount} // 0) > 0 } keys %$own;
    return 0 if grep { $_ != 909 && ($other->{$_}{amount} // 0) > 0 } keys %$other;
    return ($own->{909}{amount} // 0) == ($seller ? 1 : 0) &&
        ($other->{909}{amount} // 0) == ($seller ? 0 : 1) &&
        ($currentDeal{you_zeny} // 0) == ($seller ? 0 : 10) &&
        ($currentDeal{other_zeny} // 0) == ($seller ? 10 : 0);
}

sub trade_incoming {
    my (undef, $args) = @_;
    emit('trade', {phase => 'incoming', name => $args->{name}});
}
sub trade_engaged {
    my (undef, $args) = @_;
    emit('trade', {phase => 'engaged', name => $args->{name}});
    if ($pending && $pending->{action}{type} =~ /^trade_(request|accept)$/ && $args->{name} eq $cfg->{trade_peer}) {
        finish('completed', 'server_trade_engaged', {name => $args->{name}});
    }
}
sub trade_added {
    my (undef, $args) = @_;
    return unless $pending && $pending->{action}{type} eq 'trade_offer';
    if ($args->{fail}) { finish('rejected', 'server_offer_rejected'); return }
    my $index = unpack('v', $args->{ID});
    if ($cfg->{trade_role} eq 'seller' ? ($index > 0 && $args->{item} && $args->{item}{nameID} == 909) : $index == 0) {
        finish('completed', 'server_offer_ack', {role => $cfg->{trade_role}});
    }
}
sub trade_locked {
    my (undef, $args) = @_;
    emit('trade', {phase => 'locked', side => $args->{type} == 1 ? 'other' : 'self'});
    if ($pending && ($pending->{action}{type} eq 'trade_lock' || ($pending->{action}{type} eq 'trade_offer' && $cfg->{trade_role} eq 'buyer')) && $args->{type} == 0) {
        finish('completed', 'server_trade_locked');
    }
}
sub trade_complete {
    emit('trade', {phase => 'complete'});
    if ($pending && $pending->{action}{type} eq 'trade_commit') { finish('completed', 'server_trade_complete') }
}
sub trade_cancelled {
    emit('trade', {phase => 'cancelled'});
    if ($pending && $pending->{action}{type} =~ /^trade_/) { finish('unknown', 'server_trade_cancelled_reconcile_inventory') }
}

sub tick {
    return unless $server;
    my $ready = connected() ? 1 : 0;
    if ($ready != $in_game) {
        unless ($ready) {
            # A route must not silently resume after reconnecting.
            AI::clear(qw/move route mapRoute/) if $pending && $pending->{task};
            finish('unknown', 'game_disconnected');
        }
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
    if ($pending && $pending->{task}) { navigation_tick() if $ready }
    elsif ($pending && time >= $pending->{deadline}) { finish('unknown', 'confirmation_timeout') }
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
                    next_serial => $serial_window->next_serial(),
                    limits => {frame_bytes => 4096, output_bytes => 65536, actions_per_session => 128, serial_results => 128}});
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
