# Project-owned restricted control plugin for the pinned OpenKore revision.
package M1Bridge;
use strict;
use warnings;
use IO::Socket::INET;
use IO::Select;
use JSON::PP;
use Time::HiRes qw(time);
use Globals qw($net $char $field $messageSender $playersList $monstersList $itemsList $accountID %monsters_old %currentDeal %incomingDeal %outgoingDeal %config $quit $conState_tries
    $npcsList $storeList %portals_lut %ai_v %talk);
use Misc ();
use Plugins;
use Network;
use AI ();
use Task ();
use Utils ();
use Settings ();
use M4RequestWindow;
use M1Navigation;
use M1Combat;
use M1Travel;
use M1Supply;

my ($server, $client, $cfg, $hooks, $pending);
my ($input, $output, $authorized, $auth_time) = ('', '', 0, 0);
my ($seq, $epoch, $in_game, $last_snapshot, $last_action) = (0, 0, 0, 0, 0);
my %seen;
my $serial_window = M4RequestWindow->new(128);
my ($trade_offered, $trade_used) = (0, 0);
my ($attempts, $recovery_deadline, $stopping) = (0, 0, 0);
my $json = JSON::PP->new->utf8->canonical;
# Local recovery policy state (native profile only); never driven by the model.
my %recovery = (phase => 'none', retreats => 0);
my ($last_hit_on_me, $last_hp_update, $was_dead) = (0, 0, 0);
my %item_weight;    # item_weights.txt (tenths), loaded on first purchase.
my $walk_graph;    # Built once from OpenKore's portals table on first travel.
my $boot = sprintf('%x-%x-%x', time * 1000, $$, rand(2**30));

Plugins::register('m1_bridge', 'Bounded loopback observation/action bridge', \&unload);
$hooks = Plugins::addHooks(
    ['start3', \&start], ['mainLoop_pre', \&tick],
    ['packet/character_moves', \&moved],
    ['packet_selfChat', \&self_chat], ['packet_pubMsg', \&public_chat],
    ['packet_attack', \&combat], ['monster_disappeared', \&monster_gone],
    ['npc_talk', \&npc_text], ['npc_autotalk', \&npc_autotalk], ['packet/npc_sell_list', \&shop_sell_list], ['buy_result', \&shop_buy_result], ['packet/sell_result', \&shop_sell_result], ['packet/inventory_item_added', \&inventory_added], ['packet/stat_info', \&stat_info],
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
        $s->{native_task} = $pending && $pending->{native} ? {id => $pending->{id}, kind => $pending->{native}} : undef;
        $s->{recovery} = $recovery{phase};
        $s->{dead} = $char->{dead} ? 1 : 0; $s->{sitting} = $char->{sitting} ? 1 : 0;
        $s->{sp} = 0 + ($char->{sp} // 0); $s->{sp_max} = 0 + ($char->{sp_max} // 0);
        $s->{level} = {base => 0 + ($char->{lv} // 0), job => 0 + ($char->{lv_job} // 0),
            exp => 0 + ($char->{exp} // 0), exp_max => 0 + ($char->{exp_max} // 0),
            job_exp => 0 + ($char->{exp_job} // 0), job_exp_max => 0 + ($char->{exp_job_max} // 0)};
        $s->{hp} = 0 + ($char->{hp} // 0); $s->{hp_max} = 0 + ($char->{hp_max} // 0);
        $s->{zeny} = 0 + ($char->{zeny} // 0);
        $s->{weight} = 0 + ($char->{weight} // 0); $s->{weight_max} = 0 + ($char->{weight_max} // 0);
        my $own_items = $currentDeal{you} // {};
        my $other_items = $currentDeal{other} // {};
        $s->{deal} = {name => $currentDeal{name} // '', incoming => $incomingDeal{name} // '',
            you_zeny => 0 + ($currentDeal{you_zeny} // 0), other_zeny => 0 + ($currentDeal{other_zeny} // 0),
            you_item => 0 + (($own_items->{909} // {})->{amount} // 0), other_item => 0 + (($other_items->{909} // {})->{amount} // 0),
            you_locked => $currentDeal{you_finalize} ? 1 : 0, other_locked => $currentDeal{other_finalize} ? 1 : 0};
        $s->{inventory_ready} = $char->inventory->isReady ? 1 : 0;
        $s->{field} = {width => $field->width, height => $field->height};
        my @inventory = map {{name => $_->{name}, name_id => 0 + $_->{nameID}, amount => 0 + $_->{amount},
            type => 0 + ($_->{type} // 0), equipped => $_->{equipped} ? 1 : 0}}
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
        my @npcs = map {{name => $_->{name} // '', x => 0 + $_->{pos}{x}, y => 0 + $_->{pos}{y}}} @{$npcsList->getItems};
        $s->{npcs} = [@npcs[0 .. ($#npcs > 15 ? 15 : $#npcs)]];
        $s->{ai_queue} = [@AI::ai_seq[0 .. ($#AI::ai_seq > 7 ? 7 : $#AI::ai_seq)]];
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

sub route_state {
    my ($task) = @_;
    my $state = !grep({ ref($_) && $_ == $task } @AI::ai_seq_args) ? 'missing' :
        $task->getStatus() == Task::DONE() ? 'done' : $task->getStatus() == Task::STOPPED() ? 'stopped' : 'running';
    # processTask dequeues a DONE task in the same AI pass, so a finished task
    # is usually 'missing' here; its retained status still tells us the outcome.
    $state eq 'missing' && $task->getStatus() == Task::DONE() ? 'done' : $state;
}

sub navigation_tick {
    my $task = $pending->{task};
    my $state = route_state($task);
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

sub stop_native {
    cancel_talk() if $pending && ($pending->{native} // '') eq 'npc_talk';
    AI::clear(qw/attack take move route mapRoute/);
    $char->sendAttackStop if connected() && !$char->{dead};
}

# Another player's damage or misses on it, or its attacks on them, mark a claim.
sub engaged_by_other {
    my ($m) = @_;
    for my $field (qw(dmgFromPlayer missedFromPlayer dmgToPlayer missedToPlayer)) {
        return 1 if grep { $_ ne $accountID && $m->{$field}{$_} } keys %{$m->{$field} || {}};
    }
    return 0;
}

sub native_request {
    my ($id, $a) = @_;
    my $now = time;
    if ($a->{type} eq 'respawn') {
        unless (join(',', sort keys %$a) eq 'type' && $char->{dead}) { result($id, 'rejected', 'not_dead'); return }
        $messageSender->sendRestart(0);
        $pending = {id => $id, action => $a, native => 'respawn', started => $now, deadline => $now + 20};
        $last_action = $now;
        result($id, 'accepted', 'respawn_sent');
        return;
    }
    my $attack = $a->{type} eq 'attack';
    my $bin = defined($a->{target}) && !ref($a->{target}) && $a->{target} =~ /^[a-f0-9]{8}$/ ? pack('H*', $a->{target}) : undef;
    my $actor = $bin ? ($attack ? $monstersList : $itemsList)->getByID($bin) : undef;
    my $ctx = {manual_ai => AI::state() == AI::MANUAL(), dead => $char->{dead}, hp => $char->{hp},
        hp_max => $char->{hp_max}, recovering => $recovery{phase} ne 'none',
        pos => Utils::calcPosFromPathfinding($field, $char)};
    if ($attack) {
        $ctx->{monster} = $actor && {dead => $actor->{dead}, pos => $actor->{pos_to}, engaged_by_other => engaged_by_other($actor)};
    } else {
        $ctx->{item} = $actor && {pos => $actor->{pos}};
    }
    my $reason = $attack ? M1Combat::validate_attack($a, $ctx) : M1Combat::validate_take($a, $ctx);
    if ($reason) { result($id, 'rejected', $reason); return }
    AI::clear(qw/attack take move route mapRoute/);
    if ($attack) { $char->attack($actor->{ID}) } else { AI::take($actor->{ID}) }
    unless (AI::action() eq $a->{type}) { result($id, 'rejected', 'task_not_queued'); return }
    $pending = {id => $id, action => $a, native => $a->{type}, target_bin => $actor->{ID},
        name_id => 0 + $actor->{nameID}, name => $actor->{name}, started => $now, progress => 0,
        hits => 0, damage => 0, deadline => $now + $a->{timeout_s}};
    $last_action = $now;
    result($id, 'accepted', 'task_queued');
}

sub native_tick {
    my $p = $pending;
    my $evidence = nav_evidence();
    $evidence->{hp} = 0 + $char->{hp}; $evidence->{hp_max} = 0 + $char->{hp_max};
    my ($status, $reason);
    if ($p->{native} eq 'respawn') {
        ($status, $reason) = ('completed', 'respawned') unless $char->{dead};
    } elsif ($p->{native} eq 'attack') {
        my $m = $monstersList->getByID($p->{target_bin});
        my $old = $monsters_old{$p->{target_bin}};
        my $dmg = $p->{dmg_from_you} // ($m ? $m->{dmgFromYou} : $old ? $old->{dmgFromYou} : 0);
        ($status, $reason) = M1Combat::attack_outcome({self_dead => $char->{dead} ? 1 : 0,
            in_queue => AI::inQueue('attack') ? 1 : 0,
            target_dead => $p->{target_dead} || ($old && $old->{dead}) || ($m && $m->{dead}) ? 1 : 0,
            dmg_from_you => $dmg // 0, gave_up => $m && ($m->{attack_failed} // 0) >= $p->{started} ? 1 : 0,
            target_visible => $m ? 1 : 0});
        @$evidence{qw(target_name first_hit_ms hits damage_dealt)} = ($p->{name}, $p->{first_hit_ms}, $p->{hits}, $p->{damage});
    } else {
        my $item = $itemsList->getByID($p->{target_bin});
        $p->{gone_at} //= time unless $item;
        ($status, $reason) = M1Combat::take_outcome({self_dead => $char->{dead} ? 1 : 0,
            inventory_added => $p->{added} ? 1 : 0, in_queue => AI::inQueue('take') ? 1 : 0,
            item_visible => $item ? 1 : 0, since_gone => $p->{gone_at} ? time - $p->{gone_at} : 0});
        $evidence->{item} = $p->{added} if $p->{added};
        $evidence->{item_name} = $p->{name};
    }
    if ($status) {
        stop_native() unless $status eq 'completed';
        finish($status, $reason, $evidence); return;
    }
    if (time >= $p->{deadline}) { stop_native(); finish('failed', 'timeout', $evidence); return }
    if (time - ($p->{progress} // 0) >= 1) {
        $p->{progress} = time;
        emit('task_progress', {request_id => $p->{id}, kind => $p->{native}, %$evidence});
    }
}

# Local, model-free survival: retreat when badly hurt, rest to regenerate,
# sit only when Basic Skill allows it. Decisions come from M1Combat.
sub recovery_tick {
    my $pos = Utils::calcPosFromPathfinding($field, $char);
    # Nearest monster that is attacking or targeting us.
    my ($threat) = sort { M1Navigation::distance($a, $pos) <=> M1Navigation::distance($b, $pos) }
        map { $_->{pos_to} } grep { $_ } map { $monstersList->getByID($_) } AI::ai_getAggressives();
    my $fighting = $pending && ($pending->{native} // '') eq 'attack' ? 1 : 0;
    if ($char->{dead} && !$was_dead) {
        emit('death', {map => $field->baseName, hp_max => 0 + $char->{hp_max}});
        %recovery = (phase => 'none', retreats => 0);
    }
    $was_dead = $char->{dead} ? 1 : 0;
    my ($step) = M1Combat::recovery_step({dead => $char->{dead}, hp => $char->{hp}, hp_max => $char->{hp_max},
        phase => $recovery{phase}, fighting => $fighting,
        threat_distance => $threat ? M1Navigation::distance($threat, $pos) : undef,
        retreat_elapsed => $recovery{retreat_since} ? time - $recovery{retreat_since} : 0, retreat_moving => AI::inQueue('route') ? 1 : 0,
        busy => $pending ? 1 : 0, can_sit => ($char->{skills}{NV_BASIC}{lv} // 0) >= 3, sitting => $char->{sitting}});
    return unless $step;
    my $hp = {hp => 0 + $char->{hp}, hp_max => 0 + $char->{hp_max}};
    if ($step eq 'retreat') {
        my $decided = time;
        $threat //= $fighting && $monstersList->getByID($pending->{target_bin}) ? $monstersList->getByID($pending->{target_bin})->{pos_to} : $pos;
        # Survival preempts any task in progress; its result says so.
        if ($pending && $pending->{native} && $pending->{native} ne 'respawn') {
            cancel_talk() if $pending->{native} eq 'npc_talk';
            AI::clear(qw/attack take/);
            finish('failed', 'retreat_low_hp', {%{nav_evidence()}, %$hp});
        }
        my $cell = M1Combat::retreat_cell($pos, $threat, sub { $field->isWalkable(@_) }, $field->width, $field->height);
        AI::clear(qw/move route mapRoute/);
        $char->route($field->baseName, $cell->{x}, $cell->{y}, noMapRoute => 1, maxRouteTime => 15,
            attackOnRoute => 0, noSitAuto => 1) if $cell;
        $recovery{since} //= $decided; $recovery{retreat_since} //= $decided;
        $recovery{phase} = 'retreat'; $recovery{retreats}++;
        emit('recovery', {phase => 'retreat', %$hp, from => $pos, threat => $threat, destination => $cell,
            retreats => $recovery{retreats},
            hit_to_decision_ms => $last_hit_on_me ? int(($decided - $last_hit_on_me) * 1000) : undef,
            hp_update_to_decision_ms => $last_hp_update ? int(($decided - $last_hp_update) * 1000) : undef});
    } elsif ($step eq 'rest') {
        $recovery{since} //= time;
        $recovery{phase} = 'rest';
        emit('recovery', {phase => 'rest', %$hp});
    } elsif ($step eq 'sit') {
        return if $recovery{sit_sent} && time - $recovery{sit_sent} < 3;
        $recovery{sit_sent} = time;
        AI::sit();
        emit('recovery', {phase => 'sit', %$hp});
    } elsif ($step eq 'exhausted') {
        $recovery{phase} = 'exhausted';
        emit('recovery', {phase => 'exhausted', %$hp, retreats => $recovery{retreats}});
    } elsif ($step eq 'recovered') {
        AI::stand() if $char->{sitting};
        emit('recovery', {phase => 'recovered', %$hp, retreats => $recovery{retreats},
            duration_s => int(time - ($recovery{since} // time))});
        %recovery = (phase => 'none', retreats => 0);
    }
}

# P2a travel: each leg is a same-map Task::Route to a free walk portal (or the
# destination); a hop counts only on the observed map change. Never MapRoute.
sub travel_evidence {
    my $p = $pending;
    return {%{nav_evidence()}, leg => $p->{leg} + 1, legs => scalar @{$p->{legs}}, hops => $p->{hops},
        zeny_delta => ($char->{zeny} // 0) - $p->{zeny}, map_route_seen => $p->{map_route_seen} ? 1 : 0};
}

sub start_leg {
    my $p = $pending;
    my $leg = $p->{legs}[$p->{leg}];
    my $final = !defined $leg->{to_map};
    if ($final) {
        my $reason = !($leg->{x} < $field->width && $leg->{y} < $field->height) ? 'out_of_bounds' :
            !$field->isWalkable($leg->{x}, $leg->{y}) ? 'destination_not_walkable' : undef;
        if ($reason) { finish('failed', $reason, travel_evidence()); return }
        if ($char->{pos_to}{x} == $leg->{x} && $char->{pos_to}{y} == $leg->{y}) {
            finish('completed', 'arrived', travel_evidence()); return;
        }
    }
    my $cell = $final ? $leg : M1Travel::approach_cell($leg, sub { $field->isWalkable(@_) });
    unless ($cell) { finish('failed', 'portal_unreachable', travel_evidence()); return }
    $p->{approach} = {x => $cell->{x}, y => $cell->{y}};
    my $remaining = int($p->{deadline} - time);
    AI::clear(qw/move route mapRoute/);
    $char->route($field->baseName, $cell->{x}, $cell->{y}, noMapRoute => 1, maxRouteTime => $remaining > 1 ? $remaining : 1,
        attackOnRoute => 0, noSitAuto => 1);
    $p->{task} = AI::action() eq 'route' ? $AI::ai_seq_args[0] : undef;
    $p->{phase} = 'route';
    unless ($p->{task}) { stop_route(); finish('failed', 'route_not_queued', travel_evidence()) }
}

sub travel_request {
    my ($id, $a) = @_;
    my $reason = M1Travel::validate($a, {manual_ai => $cfg->{native_navigation} && AI::state() == AI::MANUAL(),
        hp => $char->{hp}, map => $field->baseName});
    if ($reason) { result($id, 'rejected', $reason); return }
    $walk_graph //= M1Travel::walk_graph(\%portals_lut);
    my @legs = M1Travel::plan($walk_graph, $field->baseName, $char->{pos_to}, $a->{map}, $a);
    unless (@legs) { result($id, 'rejected', 'no_walk_route'); return }
    my $now = time;
    $pending = {id => $id, action => $a, native => 'travel', legs => \@legs, leg => 0, hops => [],
        zeny => $char->{zeny} // 0, started => $now, progress => 0, deadline => $now + $a->{timeout_s} + M1Navigation::GRACE};
    $last_action = $now;
    start_leg();
    result($id, 'accepted', 'walk_route_planned', {legs => \@legs}) if $pending && $pending->{id} eq $id;
}

sub travel_tick {
    my $p = $pending;
    if (AI::state() != AI::MANUAL()) { stop_route(); finish('unknown', 'executor_mode_changed', travel_evidence()); return }
    if ($char->{dead}) { stop_route(); finish('failed', 'died', travel_evidence()); return }
    $p->{map_route_seen} = 1 if AI::inQueue('mapRoute');
    if (time >= $p->{deadline}) { stop_route(); finish('failed', 'timeout', travel_evidence()); return }
    if ($p->{settle_until}) {
        # Let the client finish loading the new map before the next leg.
        return if time < $p->{settle_until};
        delete $p->{settle_until};
        start_leg(); return;
    }
    my $leg = $p->{legs}[$p->{leg}];
    my $task = $p->{task};
    my $state = $task ? route_state($task) : 'missing';
    my $calc = Utils::calcPosFromPathfinding($field, $char);
    my ($step, $status, $reason) = M1Travel::leg_step({map => $field->baseName, leg => $leg, phase => $p->{phase},
        task_state => $state, error => $state eq 'done' ? $task->getError() : undef,
        pos_to => $char->{pos_to}, calc => $calc, enter_elapsed => $p->{enter_since} ? time - $p->{enter_since} : 0});
    $step //= '';
    if ($step eq 'hopped') {
        AI::clear(qw/move route mapRoute/);
        my $hop = {from => $leg->{map}, to => $field->baseName, elapsed_ms => int((time - $p->{started}) * 1000),
            position => {x => 0 + $char->{pos_to}{x}, y => 0 + $char->{pos_to}{y}}};
        push @{$p->{hops}}, $hop;
        emit('travel_hop', {request_id => $p->{id}, %$hop});
        $p->{leg}++; undef $p->{task}; delete $p->{enter_since};
        $p->{settle_until} = time + .5;
        return;
    }
    if ($step eq 'final') {
        stop_route() unless $status eq 'completed';
        finish($status, $reason, travel_evidence()); return;
    }
    if ($step eq 'enter') { $p->{phase} = 'enter'; $p->{enter_since} = time; $p->{enter_sent} = 0 }
    if ($p->{phase} eq 'enter' && time - $p->{enter_sent} >= .5) {
        # Like MapRoute's 'Enter Distance' step: re-send the step into the warp area.
        $char->sendMove(@{$p->{approach}}{qw(x y)}); $p->{enter_sent} = time;
    }
    if (time - $p->{progress} >= 1) {
        $p->{progress} = time;
        emit('travel_progress', {request_id => $p->{id}, %{travel_evidence()}, phase => $p->{phase},
            target => {map => $leg->{map}, x => $leg->{x}, y => $leg->{y}}});
    }
}

# P2a dialog: continue, pre-declared exact menu labels and closing only.
sub talk_snapshot {
    return {map => $field->baseName, zeny => 0 + ($char->{zeny} // 0),
        inventory => join(',', sort map { "$_->{nameID}:$_->{amount}" } @{$char->inventory->getItems})};
}

sub cancel_talk { $messageSender->sendTalkCancel($pending->{npc_bin}) if connected() }

sub talk_request {
    my ($id, $a) = @_;
    my $at = sub { defined($_[0]) && !ref($_[0]) && $_[0] =~ /^\d{1,3}$/ };
    my ($npc) = $at->($a->{x}) && $at->($a->{y}) ?
        grep { $_->{pos}{x} == $a->{x} && $_->{pos}{y} == $a->{y} } @{$npcsList->getItems} : ();
    my $reason = M1Travel::validate_talk($a, {manual_ai => $cfg->{native_navigation} && AI::state() == AI::MANUAL(),
        hp => $char->{hp}, recovering => $recovery{phase} ne 'none', talking => %talk ? 1 : 0,
        npc => $npc && $npc->{pos}, pos => Utils::calcPosFromPathfinding($field, $char)});
    if ($reason) { result($id, 'rejected', $reason); return }
    AI::clear(qw/move route mapRoute/);
    my $now = time;
    $pending = {id => $id, action => $a, native => 'npc_talk', npc_bin => $npc->{ID}, npc_name => $npc->{name},
        choices => [@{$a->{choices}}], chosen => [], menus => [], transcript => [], pages => 0,
        before => talk_snapshot(), acted => $now, started => $now, progress => 0, deadline => $now + $a->{timeout_s}};
    $last_action = $now;
    $messageSender->sendTalk($npc->{ID});
    result($id, 'accepted', 'talk_sent');
}

sub talk_finish {
    my ($status, $reason) = @_;
    my $p = $pending;
    my $after = talk_snapshot();
    my ($final, $why, $changed) = M1Travel::talk_outcome($status, $reason, $p->{before}, $after);
    finish($final, $why, {%{nav_evidence()}, npc => $p->{npc_name}, transcript => $p->{transcript},
        menus => $p->{menus}, chosen => $p->{chosen}, pages => $p->{pages},
        autotalk_suppressed => $p->{autotalk_suppressed} // 0, npc_task_left => AI::inQueue('NPC') ? 1 : 0,
        dialog_result => $final eq $status ? undef : "$status/$reason", changed => $changed,
        before => $p->{before}, after => $after});
}

sub talk_tick {
    my $p = $pending;
    my $now = time;
    if ($p->{closing}) {
        # Like OpenKore's TalkNPC: acknowledge the close button after a short wait.
        return if $now < $p->{closing};
        cancel_talk(); talk_finish(@{$p->{close_result}}); return;
    }
    if ($char->{dead}) { cancel_talk(); talk_finish('failed', 'died'); return }
    if ($now >= $p->{deadline}) { cancel_talk(); talk_finish('failed', 'timeout'); return }
    my $v = $ai_v{npc_talk} || {};
    # Act once per new NPC packet, after a human-like pause, and only for our NPC.
    return unless ($v->{time} // 0) > $p->{acted} && $now - $v->{time} >= .5 &&
        (!defined $v->{ID} || $v->{ID} eq $p->{npc_bin});
    my ($act, $status, $reason) = M1Travel::dialog_step({state => $v->{talk}, choices => $p->{choices},
        pages => $p->{pages}, responses => $talk{responses}});
    return unless $act;
    $p->{acted} = $now;
    if (($v->{talk} // '') eq 'select') {
        my @menu = @{$talk{responses} || []}; pop @menu;
        push @{$p->{menus}}, [@menu[0 .. ($#menu > 15 ? 15 : $#menu)]] if @{$p->{menus}} < 8;
    }
    if ($act eq 'continue') { $p->{pages}++; $messageSender->sendTalkContinue($p->{npc_bin}) }
    elsif ($act eq 'respond') {
        push @{$p->{chosen}}, shift @{$p->{choices}};
        $messageSender->sendTalkResponse($p->{npc_bin}, $status);
    } elsif ($act eq 'close') { $p->{closing} = $now + .5; $p->{close_result} = [$status, $reason] }
    else { cancel_talk(); talk_finish($status, $reason) }
}

# P2b shops: talk -> buy/sell list from the server -> one bulk packet -> the
# server's result, then the trade is reconciled against Zeny and inventory.
sub item_totals {
    my %t;
    $t{$_->{nameID}} += $_->{amount} for @{$char->inventory->getItems};
    return {zeny => 0 + ($char->{zeny} // 0), items => \%t};
}

sub item_weights {
    unless (%item_weight) {
        open my $fh, '<', Settings::getTableFilename('item_weights.txt') or return \%item_weight;
        while (<$fh>) { $item_weight{$1} = $2 if /^(\d+)\s+(\d+)/ }
        close $fh;
    }
    \%item_weight;
}

sub shop_request {
    my ($id, $a) = @_;
    my $sell = $a->{type} eq 'npc_sell';
    my $at = sub { defined($_[0]) && !ref($_[0]) && $_[0] =~ /^\d{1,3}$/ };
    my ($npc) = $at->($a->{x}) && $at->($a->{y}) ?
        grep { $_->{pos}{x} == $a->{x} && $_->{pos}{y} == $a->{y} } @{$npcsList->getItems} : ();
    my $ctx = {manual_ai => $cfg->{native_navigation} && AI::state() == AI::MANUAL(), hp => $char->{hp},
        recovering => $recovery{phase} ne 'none', talking => %talk ? 1 : 0, npc => $npc && $npc->{pos},
        pos => Utils::calcPosFromPathfinding($field, $char), zeny => $char->{zeny} // 0,
        inventory => [map {{name_id => $_->{nameID}, amount => $_->{amount}, type => $_->{type} // 0,
            equipped => $_->{equipped} ? 1 : 0}} @{$char->inventory->getItems}]};
    my $reason = $sell ? M1Supply::validate_sell($a, $ctx) : M1Supply::validate_buy($a, $ctx);
    if ($reason) { result($id, 'rejected', $reason); return }
    AI::clear(qw/move route mapRoute/);
    my $now = time;
    $pending = {id => $id, action => $a, native => 'shop', mode => $sell ? 'sell' : 'buy', npc_bin => $npc->{ID},
        npc_name => $npc->{name}, phase => 'open', before => item_totals(), acted => $now,
        started => $now, progress => 0, deadline => $now + $a->{timeout_s}};
    $last_action = $now;
    $messageSender->sendTalk($npc->{ID});
    result($id, 'accepted', 'talk_sent');
}

sub shop_finish {
    my ($status, $reason, $extra) = @_;
    my $p = $pending;
    finish($status, $reason, {%{nav_evidence()}, npc => $p->{npc_name}, mode => $p->{mode},
        quote => $p->{quote}, sent => $p->{sent}, expected => $p->{expect}, server_result => $p->{server_result},
        autotalk_suppressed => $p->{autotalk_suppressed} // 0,
        before => $p->{before}, after => item_totals(), %{$extra || {}}});
}

sub shop_tick {
    my $p = $pending;
    my $now = time;
    my $sent = $p->{phase} eq 'sent' || $p->{phase} eq 'settle';
    if ($now >= $p->{deadline} || $char->{dead}) {
        # Once a trade packet left, only the observed state can say what happened.
        shop_finish($sent ? ('unknown', 'result_not_confirmed') : ('failed', $char->{dead} ? 'died' : 'timeout'));
        return;
    }
    my $v = $ai_v{npc_talk} || {};
    my $fresh = ($v->{time} // 0) > $p->{acted} && (!defined $v->{ID} || $v->{ID} eq $p->{npc_bin});
    if ($p->{phase} eq 'open') {
        return unless $fresh;
        $p->{acted} = $now;
        if (($v->{talk} // '') ne 'buy_or_sell') { cancel_talk(); shop_finish('failed', 'not_a_shop'); return }
        $messageSender->sendNPCBuySellList($p->{npc_bin}, $p->{mode} eq 'sell' ? 1 : 0);
        $p->{phase} = 'list';
    } elsif ($p->{phase} eq 'list') {
        my $a = $p->{action};
        if ($p->{mode} eq 'buy') {
            return unless $fresh && ($v->{talk} // '') eq 'store';
            my %store; $store{$_->{nameID}} //= 0 + $_->{price} for @{$storeList->getItems};
            $p->{quote} = {store => \%store};
            my ($why, $cost) = M1Supply::buy_quote($a->{items}, \%store, {max_zeny => $a->{max_zeny},
                zeny => $char->{zeny} // 0, weight => $char->{weight} // 0, weight_max => $char->{weight_max} // 0,
                item_weight => item_weights()});
            if ($why) { shop_finish('failed', $why); return }
            $p->{expect} = {zeny => -$cost, items => {map { $_->{name_id} => $_->{amount} } @{$a->{items}}}};
            $p->{sent} = [map {{itemID => 0 + $_->{name_id}, amount => 0 + $_->{amount}}} @{$a->{items}}];
            $messageSender->sendBuyBulk($p->{sent});
        } else {
            return unless $p->{offers};
            $p->{quote} = {offers => $p->{offers}};
            my ($why, $total) = M1Supply::sell_quote($a->{items}, $p->{offers});
            if ($why) { shop_finish('failed', $why); return }
            my @bulk;
            for my $i (@{$a->{items}}) {
                my $left = $i->{amount};
                for my $item (grep { $_->{nameID} == $i->{name_id} && !$_->{equipped} } @{$char->inventory->getItems}) {
                    last unless $left;
                    my $n = $item->{amount} < $left ? $item->{amount} : $left;
                    push @bulk, {ID => $item->{ID}, amount => $n}; $left -= $n;
                }
            }
            $p->{expect} = {zeny => $total, items => {map { $_->{name_id} => -$_->{amount} } @{$a->{items}}}};
            $p->{sent} = [map {{name_id => 0 + $_->{name_id}, amount => 0 + $_->{amount}}} @{$a->{items}}];
            $messageSender->sendSellBulk(\@bulk);
        }
        $p->{phase} = 'sent'; $p->{acted} = $now;
    } elsif ($p->{phase} eq 'sent') {
        return unless defined $p->{server_result};
        if ($p->{server_result}) {
            shop_finish($p->{mode} eq 'buy' ? M1Supply::buy_failure($p->{server_result}) : ('failed', 'server_sell_failed'));
            return;
        }
        # Zeny/inventory updates may trail the result packet; give them 2 s.
        $p->{phase} = 'settle'; $p->{settle_until} = $now + 2;
    }
    if ($p->{phase} eq 'settle') {
        my ($status, $reason, $observed) = M1Supply::reconcile($p->{mode} eq 'buy' ? 'bought' : 'sold',
            $p->{before}, item_totals(), $p->{expect});
        shop_finish($status, $reason, {observed => $observed}) if $status eq 'completed' || $now >= $p->{settle_until};
    }
}

# 00C7 rows: inventory index (a2), price, overcharge price (what is paid).
sub shop_sell_list {
    my (undef, $args) = @_;
    return unless $pending && ($pending->{native} // '') eq 'shop' && $pending->{mode} eq 'sell';
    my %offers;
    for (my $i = 0; $i + 10 <= length($args->{itemsdata} // ''); $i += 10) {
        my ($index, undef, $paid) = unpack('a2 V V', substr($args->{itemsdata}, $i, 10));
        my $item = $char->inventory->getByID($index) or next;
        $offers{$item->{nameID}} //= 0 + $paid;
    }
    $pending->{offers} = \%offers;
}

sub shop_buy_result {
    my (undef, $args) = @_;
    return unless $pending && ($pending->{native} // '') eq 'shop' && $pending->{mode} eq 'buy' && $pending->{phase} eq 'sent';
    $pending->{server_result} = 0 + ($args->{fail} // 0);
}

sub shop_sell_result {
    my (undef, $args) = @_;
    return unless $pending && ($pending->{native} // '') eq 'shop' && $pending->{mode} eq 'sell' && $pending->{phase} eq 'sent';
    $pending->{server_result} = $args->{fail} ? 1 : 0;
}

# OpenKore queues its own 'autotalk' TalkNPC (with autoTalkCont it would page
# on its own) when an NPC answers. During our dialog the bridge is the only
# speaker: drop that task before it ever iterates.
sub npc_autotalk {
    my (undef, $args) = @_;
    return unless $pending && ($pending->{native} // '') =~ /^(npc_talk|shop)$/;
    $args->{task}->delHooks if $args->{task};
    AI::clear('NPC');
    $pending->{autotalk_suppressed}++;
}

sub npc_text {
    my (undef, $args) = @_;
    return unless $pending && ($pending->{native} // '') eq 'npc_talk' && $args->{ID} eq $pending->{npc_bin};
    my $line = (split /\n/, $args->{msg} // '')[-1] // '';
    push @{$pending->{transcript}}, substr($line, 0, 120) if @{$pending->{transcript}} < 40;
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
    # Cancel is exempt from busy/rate limits: it only ends the active native task.
    if ($a->{type} eq 'cancel') {
        unless (join(',', sort keys %$a) eq 'target,type' && defined($a->{target}) && !ref($a->{target}) &&
            $pending && $pending->{native} && $pending->{native} ne 'respawn' && $a->{target} eq $pending->{id}) {
            result($id, 'rejected', 'no_matching_task'); return;
        }
        my $kind = $pending->{native};
        stop_native();
        finish('cancelled', 'cancel_requested', nav_evidence());
        result($id, 'completed', "${kind}_cancelled");
        return;
    }
    if ($pending) { result($id, 'rejected', 'busy'); return }
    if (time - $last_action < 1) { result($id, 'rejected', 'rate_limited'); return }
    if ($cfg->{native_navigation} && $a->{type} =~ /^(navigate|travel|npc_talk|npc_sell|npc_buy|attack|take)$/ && $recovery{phase} ne 'none') {
        result($id, 'rejected', 'recovering'); return;
    }
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
        $pending = {id => $id, action => $a, task => $task, native => 'navigation', started => $now, progress => 0,
            deadline => $now + $a->{timeout_s} + M1Navigation::GRACE};
        $last_action = $now;
        result($id, 'accepted', 'route_queued');
        return;
    }
    if ($a->{type} eq 'travel') { travel_request($id, $a); return }
    if ($a->{type} eq 'npc_talk') { talk_request($id, $a); return }
    if ($a->{type} =~ /^npc_(sell|buy)$/) { shop_request($id, $a); return }
    if ($cfg->{native_navigation} && $a->{type} =~ /^(attack|take|respawn)$/) { native_request($id, $a); return }
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
    $last_hit_on_me = time if $data->{target} eq unpack('H*', $accountID) && $data->{damage} > 0;
    if ($pending && ($pending->{native} // '') eq 'attack' && $data->{self} && $args->{targetID} eq $pending->{target_bin}) {
        $pending->{first_hit_ms} //= int((time - $pending->{started}) * 1000);
        $pending->{hits}++; $pending->{damage} += $data->{damage};
    }
    if ($pending && !$pending->{native} && $pending->{action}{type} eq 'attack' && $data->{self} && $data->{target} eq $pending->{action}{target}) {
        finish('completed', 'server_attack', $data);
    }
}

sub monster_gone {
    my (undef, $args) = @_;
    my $m = $args->{monster};
    emit('monster_departure', {target => unpack('H*', $m->{ID}), dead => $m->{dead} ? 1 : 0, name_id => 0 + $m->{nameID}});
    if ($pending && ($pending->{native} // '') eq 'attack' && $m->{ID} eq $pending->{target_bin}) {
        $pending->{target_dead} = $m->{dead} ? 1 : 0;
        $pending->{dmg_from_you} = 0 + ($m->{dmgFromYou} // 0);
    }
}

# VAR_HP (5): when the server's HP value reached us, to time our own reaction.
sub stat_info {
    my (undef, $args) = @_;
    $last_hp_update = time if ($args->{type} // -1) == 5;
}

sub inventory_added {
    my (undef, $args) = @_;
    return if $args->{fail};
    my $data = {name_id => 0 + $args->{nameID}, amount => 0 + $args->{amount}};
    emit('inventory_added', $data);
    if ($pending && ($pending->{native} // '') eq 'take' && $data->{name_id} == $pending->{name_id} && $data->{amount} > 0) {
        $pending->{added} = $data;
    }
    if ($pending && !$pending->{native} && $pending->{action}{type} eq 'take' && $data->{name_id} == 909 && $data->{amount} > 0) {
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
            AI::clear(qw/move route mapRoute attack take/) if $pending && $pending->{native};
            $recovery{phase} = 'rest' if $recovery{phase} eq 'retreat';
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
    my $native = $pending ? $pending->{native} // '' : '';
    if ($native eq 'travel') { travel_tick() if $ready }
    elsif ($native eq 'npc_talk') { talk_tick() if $ready }
    elsif ($native eq 'shop') { shop_tick() if $ready }
    elsif ($pending && $pending->{task}) { navigation_tick() if $ready }
    elsif ($pending && $pending->{native}) { native_tick() if $ready }
    elsif ($pending && time >= $pending->{deadline}) { finish('unknown', 'confirmation_timeout') }
    recovery_tick() if $ready && $cfg->{native_navigation};
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
