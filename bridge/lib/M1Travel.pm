package M1Travel;
use strict;
use warnings;
use M1Navigation;

# Pure contract for P2a: cross-map travel through walkable portals only, and a
# bounded NPC dialog. The plugin supplies observed state; nothing here touches
# the network, AI queue or game globals.
use constant {MAX_HOPS => 3, MAX_INNER => 4, MIN_TIMEOUT => 5, MAX_TIMEOUT => 300, ENTER_WAIT => 5,
    TALK_MIN_TIMEOUT => 5, TALK_MAX_TIMEOUT => 60, TALK_RANGE => 5, MAX_CHOICES => 4, MAX_PAGES => 12, APPROACH => 2,
    # P5 tutorial scripts (npc_script): long dialogs, warps and same-map portals.
    SCRIPT_MAX_CHOICES => 32, SCRIPT_MAX_PAGES => 160, SCRIPT_MAX_TIMEOUT => 240, WARP_SLACK => 2};

sub validate {
    my ($a, $ctx) = @_;
    return 'invalid_travel' unless join(',', sort keys %$a) eq 'map,timeout_s,type,x,y' &&
        !grep { !defined($a->{$_}) || ref($a->{$_}) } qw(map timeout_s x y);
    return 'invalid_travel' unless $a->{x} =~ /^\d{1,3}$/ && $a->{y} =~ /^\d{1,3}$/ &&
        $a->{timeout_s} =~ /^\d{1,3}$/ && $a->{map} =~ /^[a-z0-9_-]{1,24}$/;
    return 'invalid_timeout' if $a->{timeout_s} < MIN_TIMEOUT || $a->{timeout_s} > MAX_TIMEOUT;
    return 'executor_not_native' unless $ctx->{manual_ai};
    return 'dead' unless $ctx->{hp} > 0;
    return 'same_map_use_navigate' if $a->{map} eq $ctx->{map};
    return undef;
}

# Keeps only free, talk-less, permanently enabled portals from OpenKore's portals
# table: no Kafra, paid or scripted NPC warps, no dynamic groups, airships or warp
# items (those live in other tables). With a zone table (config/walk-zones.json,
# see zone_table) each edge carries the walk zone it is entered from and lands in,
# same-map walk portals are kept as edges, and portals the table lacks are left out.
# Without it, map-to-map portals only and every map is one zone (0).
sub walk_graph {
    my ($lut, $zones) = @_;
    my %g;
    for my $key (sort keys %$lut) {
        my $src = $lut->{$key}{source} or next;
        for my $d (sort keys %{$lut->{$key}{dest} || {}}) {
            my $e = $lut->{$key}{dest}{$d};
            next if ($e->{cost} // 0) || ($e->{steps} // '') ne '' || !$e->{enabled} ||
                defined $e->{dynamicPortalGroup} || defined $e->{dynamicPortalGroupBlock};
            my ($zf, $zt) = (0, 0);
            if ($zones) {
                ($zf, $zt) = @{$zones->{portals}{"$src->{map} $src->{x} $src->{y} $e->{map} $e->{x} $e->{y}"} || next};
            } else {
                next if $e->{map} eq $src->{map};
            }
            push @{$g{$src->{map}}}, {x => 0 + $src->{x}, y => 0 + $src->{y}, to_map => $e->{map},
                to => {x => 0 + $e->{x}, y => 0 + $e->{y}}, zone => $zf, to_zone => $zt};
        }
    }
    \%g;
}

# config/walk-zones.json as lookups: "map x y to tx ty" -> [zone, to_zone] and
# map -> {"x y" => zone} for the anchor cells.
sub zone_table {
    my ($doc) = @_;
    my (%portals, %anchors);
    $portals{join ' ', @{$_}[0 .. 5]} = [@{$_}[6, 7]] for @{$doc->{portals} || []};
    for my $map (keys %{$doc->{anchors} || {}}) {
        $anchors{$map}{"$_->[0] $_->[1]"} = $_->[2] for @{$doc->{anchors}{$map}};
    }
    return {portals => \%portals, anchors => \%anchors};
}

# Zone of a cell: from it (or the nearest walkable cell within APPROACH) walk the
# 4-neighbour walkable cells to the first anchor. undef when the component holds
# no portal. $walkable must reject cells outside the map; at most $limit cells.
sub zone_at {
    my ($anchors, $walkable, $pos, $limit) = @_;
    my $start = approach_cell($pos, $walkable) or return undef;
    my @queue = ([$start->{x}, $start->{y}]);
    my %seen = ("$start->{x} $start->{y}" => 1);
    $limit //= 250000;
    while (@queue && $limit-- > 0) {
        my ($x, $y) = @{shift @queue};
        my $zone = $anchors->{"$x $y"};
        return $zone if defined $zone;
        for my $c ([$x + 1, $y], [$x - 1, $y], [$x, $y + 1], [$x, $y - 1]) {
            next if $c->[0] < 0 || $c->[1] < 0 || $seen{"$c->[0] $c->[1]"}++ || !$walkable->(@$c);
            push @queue, $c;
        }
    }
    undef;
}

# Fewest map hops, then fewest same-map portals (at most MAX_HOPS and MAX_INNER),
# between walk zones; ties by map name, zone and portal cell. On each step the
# portal closest to where the character is or lands. $o: start_zone and dest_zone
# (undef = any zone of that map; with zones => 1 an undef zone means no walk route).
# Returns (\@legs) or (undef, reason): start_isolated, destination_unreachable,
# no_zone_path. Legs are portal legs plus the final leg to $dest.
sub route {
    my ($g, $from, $pos, $to, $dest, $o) = @_;
    $o //= {};
    if ($o->{zones}) {
        return (undef, 'start_isolated') unless defined $o->{start_zone};
        return (undef, 'destination_unreachable') unless defined $o->{dest_zone};
    }
    my @starts = defined $o->{start_zone} ? ("$from	$o->{start_zone}") :
        map { "$from	$_" } sort { $a <=> $b } keys %{{map { $_->{zone} => 1 } @{$g->{$from} || []}}};
    my $goal = sub { my ($m, $z) = split /	/, $_[0]; $m eq $to && (!defined $o->{dest_zone} || $z == $o->{dest_zone}) };
    my $span = MAX_INNER + 1;
    my (%cost, %prev, %buckets, $found);
    for (@starts) { $cost{$_} = [0, 0]; $prev{$_} = '' }
    $buckets{0} = [@starts];
    LEVEL: for my $level (0 .. (MAX_HOPS + 1) * $span - 1) {
        for my $node (@{$buckets{$level} || []}) {
            next if $cost{$node}[0] * $span + $cost{$node}[1] != $level;
            if ($goal->($node)) { $found = $node; last LEVEL }
            my ($map, $zone) = split /	/, $node;
            my ($hops, $inner) = @{$cost{$node}};
            for my $e (sort { $a->{to_map} cmp $b->{to_map} || $a->{to_zone} <=> $b->{to_zone} ||
                    $a->{x} <=> $b->{x} || $a->{y} <=> $b->{y} } grep { $_->{zone} == $zone } @{$g->{$map} || []}) {
                my @step = $e->{to_map} eq $map ? ($hops, $inner + 1) : ($hops + 1, $inner);
                next if $step[0] > MAX_HOPS || $step[1] > MAX_INNER;
                my $next = "$e->{to_map}	$e->{to_zone}";
                next if $cost{$next} && $cost{$next}[0] * $span + $cost{$next}[1] <= $step[0] * $span + $step[1];
                $cost{$next} = \@step; $prev{$next} = $node;
                push @{$buckets{$step[0] * $span + $step[1]}}, $next;
            }
        }
    }
    return (undef, $o->{zones} ? 'no_zone_path' : 'no_walk_route') unless $found;
    my @nodes = ($found);
    unshift @nodes, $prev{$nodes[0]} while $prev{$nodes[0]} ne '';
    my (@legs, $at);
    $at = $pos;
    for my $i (0 .. $#nodes - 1) {
        my ($map, $zone) = split /	/, $nodes[$i];
        my ($next, $next_zone) = split /	/, $nodes[$i + 1];
        my ($portal) = sort { M1Navigation::distance($a, $at) <=> M1Navigation::distance($b, $at) ||
            $a->{x} <=> $b->{x} || $a->{y} <=> $b->{y} }
            grep { $_->{zone} == $zone && $_->{to_map} eq $next && $_->{to_zone} == $next_zone } @{$g->{$map}};
        push @legs, {map => $map, x => $portal->{x}, y => $portal->{y}, to_map => $portal->{to_map},
            $portal->{to_map} eq $map ? (to => {%{$portal->{to}}}) : ()};
        $at = $portal->{to};
    }
    push @legs, {map => $to, x => 0 + $dest->{x}, y => 0 + $dest->{y}};
    (\@legs);
}

# Legs of route(), or () when there is no walk route.
sub plan {
    my ($legs) = route(@_);
    $legs ? @$legs : ();
}

# One travel tick. $o: map (observed), leg {map, to_map?}, phase route|enter,
# task_state/error (route task), enter_elapsed, plus M1Navigation observations
# for the final leg. Returns ('hopped'), ('enter'), ('final', status, reason)
# or () to keep waiting. A hop only counts on the server-confirmed map change.
sub leg_step {
    my ($o) = @_;
    my $leg = $o->{leg};
    if (defined $leg->{to_map} && $leg->{to_map} eq $leg->{map} && $o->{warped}) {
        # Same-map portal: only the server's map-change packet at the landing counts.
        return ('hopped') if $o->{map} eq $leg->{map} && M1Navigation::distance($o->{warped}, $leg->{to}) <= WARP_SLACK;
        return ('final', 'unknown', 'unexpected_warp');
    }
    if ($o->{map} ne $leg->{map}) {
        return ('hopped') if defined $leg->{to_map} && $o->{map} eq $leg->{to_map};
        return ('final', 'unknown', 'unexpected_map');
    }
    unless (defined $leg->{to_map}) {
        my @r = M1Navigation::outcome($o->{task_state}, $o->{error},
            {map => $o->{map}, dest_map => $leg->{map}, pos_to => $o->{pos_to}, calc => $o->{calc}, dest => $leg});
        return @r ? ('final', @r) : ();
    }
    if (($o->{phase} // 'route') eq 'enter') {
        return $o->{enter_elapsed} >= ENTER_WAIT ? ('final', 'failed', 'portal_not_taken') : ();
    }
    return () if $o->{task_state} eq 'running';
    return ('final', 'unknown', 'route_task_lost') if $o->{task_state} eq 'missing';
    return ('final', 'unknown', 'route_task_stopped') if $o->{task_state} eq 'stopped';
    if ($o->{error}) {
        my $code = $o->{error}{code} // -1;
        return ('final', 'failed', $code == 0 ? 'timeout' : $code == 1 ? 'unreachable' :
            $code == 2 ? 'blocked' : 'route_error');
    }
    # Route ended at the portal's approach cell without a map change: step in.
    return M1Navigation::distance($o->{pos_to}, $leg) <= APPROACH ? ('enter') : ('final', 'unknown', 'route_ended_off_target');
}

# Portal source cells are often unwalkable in the GAT although the server's
# warp area around them is; route to the nearest walkable cell within APPROACH.
sub approach_cell {
    my ($leg, $walkable) = @_;
    my @cells;
    for my $dx (-APPROACH() .. APPROACH) {
        for my $dy (-APPROACH() .. APPROACH) {
            my ($x, $y) = ($leg->{x} + $dx, $leg->{y} + $dy);
            push @cells, {x => $x, y => $y} if $x >= 0 && $y >= 0 && $walkable->($x, $y);
        }
    }
    my ($best) = sort { M1Navigation::distance($a, $leg) <=> M1Navigation::distance($b, $leg) ||
        abs($a->{x} - $leg->{x}) + abs($a->{y} - $leg->{y}) <=> abs($b->{x} - $leg->{x}) + abs($b->{y} - $leg->{y}) ||
        $a->{y} <=> $b->{y} || $a->{x} <=> $b->{x} } @cells;
    $best;
}

sub validate_talk {
    my ($a, $ctx) = @_;
    return 'invalid_npc_talk' unless join(',', sort keys %$a) eq 'choices,timeout_s,type,x,y' &&
        !grep { !defined($a->{$_}) || ref($a->{$_}) } qw(timeout_s x y);
    return 'invalid_npc_talk' unless $a->{x} =~ /^\d{1,3}$/ && $a->{y} =~ /^\d{1,3}$/ &&
        $a->{timeout_s} =~ /^\d{1,3}$/ && ref($a->{choices}) eq 'ARRAY' && @{$a->{choices}} <= MAX_CHOICES &&
        !grep { !defined($_) || ref($_) || !/^[\x20-\x7e]{1,40}$/ } @{$a->{choices}};
    return 'invalid_timeout' if $a->{timeout_s} < TALK_MIN_TIMEOUT || $a->{timeout_s} > TALK_MAX_TIMEOUT;
    talk_context($ctx);
}

# Only the approved first-job NPC and its six fixed destinations are exposed.
my %FIRST_JOB = (Swordman => 1, Mage => 2, Archer => 3, Acolyte => 4, Merchant => 5, Thief => 6);
sub first_job_id { $FIRST_JOB{$_[0] // ''} }
sub validate_first_job_precheck {
    my ($a, $ctx) = @_;
    return 'invalid_first_job' unless join(',', sort keys %$a) eq 'job,timeout_s,type' &&
        defined($a->{job}) && !ref($a->{job}) && first_job_id($a->{job}) &&
        defined($a->{timeout_s}) && !ref($a->{timeout_s}) && $a->{timeout_s} =~ /^\d{1,3}$/;
    return 'invalid_timeout' if $a->{timeout_s} < 10 || $a->{timeout_s} > 60;
    return 'wrong_map_or_npc' unless ($ctx->{map} // '') eq 'prontera';
    return 'not_eligible' unless defined($ctx->{job_id}) && $ctx->{job_id} == 0 &&
        defined($ctx->{job_level}) && $ctx->{job_level} >= 10 &&
        defined($ctx->{points_skill}) && $ctx->{points_skill} == 0;
    talk_context($ctx);
}
sub validate_first_job {
    my ($a, $ctx) = @_;
    return 'wrong_map_or_npc' unless ($ctx->{npc_name} // '') eq 'First Job Changer';
    validate_first_job_precheck($a, $ctx);
}
sub first_job_name_step {
    my ($same_actor, $name, $now, $deadline) = @_;
    return 'npc_actor_changed' unless $same_actor;
    return 'npc_name_timeout' if $now >= $deadline;
    return $name eq 'First Job Changer' ? 'resolved' : 'wrong_map_or_npc' if defined $name;
    return 'waiting';
}

# A matching own-character job-change packet is the only success evidence.
sub first_job_outcome {
    my ($selected, $expected, $observed, $reason) = @_;
    return ('completed', 'job_changed') if $selected && defined($observed) && $observed == $expected;
    return ('unknown', 'job_change_unconfirmed') if $selected || defined($observed);
    return ('failed', $reason);
}

# npc_script: a pre-declared tutorial dialog. The only text it may type is the
# character's own name (name_reply 1; the plugin supplies it, never the caller),
# and an optional expect {map, x, y} names the one warp that completes it.
sub validate_script {
    my ($a, $ctx) = @_;
    my $keys = join(',', grep { $_ ne 'expect' } sort keys %$a);
    return 'invalid_npc_script' unless $keys eq 'choices,name_reply,timeout_s,type,x,y' &&
        !grep { !defined($a->{$_}) || ref($a->{$_}) } qw(name_reply timeout_s x y);
    return 'invalid_npc_script' unless $a->{x} =~ /^\d{1,3}$/ && $a->{y} =~ /^\d{1,3}$/ &&
        $a->{timeout_s} =~ /^\d{1,3}$/ && $a->{name_reply} =~ /^[01]$/ && ref($a->{choices}) eq 'ARRAY' &&
        @{$a->{choices}} <= SCRIPT_MAX_CHOICES &&
        !grep { !defined($_) || ref($_) || !/^[\x20-\x7e]{1,64}$/ } @{$a->{choices}};
    if (exists $a->{expect}) {
        my $e = $a->{expect};
        return 'invalid_npc_script' unless ref($e) eq 'HASH' && join(',', sort keys %$e) eq 'map,x,y' &&
            !grep({ !defined($_) || ref($_) } values %$e) && $e->{map} =~ /^[a-z0-9_-]{1,24}$/ &&
            $e->{x} =~ /^\d{1,3}$/ && $e->{y} =~ /^\d{1,3}$/;
    }
    return 'invalid_timeout' if $a->{timeout_s} < TALK_MIN_TIMEOUT || $a->{timeout_s} > SCRIPT_MAX_TIMEOUT;
    talk_context($ctx);
}

sub talk_context {
    my ($ctx) = @_;
    return 'executor_not_native' unless $ctx->{manual_ai};
    return 'dead' unless $ctx->{hp} > 0;
    return 'recovering' if $ctx->{recovering};
    return 'already_talking' if $ctx->{talking};
    return 'npc_not_found' unless $ctx->{npc};
    return 'npc_too_far' if M1Navigation::distance($ctx->{npc}, $ctx->{pos}) > TALK_RANGE;
    return undef;
}

# One dialog decision from OpenKore's talk state (initiated|next|select|number|
# text|close|buy_or_sell). Returns ('continue'), ('respond', n) with n 1-based,
# ('cancel', status, reason), ('close', status, reason) or () to wait. Only
# continue, exact pre-declared menu labels and closing are ever sent.
# npc_script adds max_pages and name_reply/name_sent: ('name') types the own
# name once, only when the script declared it.
sub dialog_step {
    my ($o) = @_;
    my $state = $o->{state} // '';
    return () if $state eq '' || $state eq 'initiated';
    if ($state eq 'close') {
        return @{$o->{choices}} ? ('close', 'failed', 'closed_before_choices') : ('close', 'completed', 'conversation_closed');
    }
    return ('name') if $state eq 'text' && $o->{name_reply} && !$o->{name_sent};
    return ('cancel', 'failed', 'input_not_allowed') if $state eq 'number' || $state eq 'text';
    return ('cancel', 'failed', 'shop_not_allowed') if $state eq 'buy_or_sell';
    if ($state eq 'next') {
        return $o->{pages} >= ($o->{max_pages} // MAX_PAGES) ? ('cancel', 'failed', 'too_many_pages') : ('continue');
    }
    if ($state eq 'select') {
        my @r = @{$o->{responses} || []};
        pop @r;    # OpenKore appends a local 'Cancel Chat' entry that is not a menu item.
        my $want = $o->{choices}[0];
        my ($i) = defined $want ? grep { $r[$_] eq $want } 0 .. $#r : ();
        return defined $i ? ('respond', $i + 1) : ('cancel', 'failed', 'unexpected_menu');
    }
    ('cancel', 'failed', 'unexpected_dialog');
}

# A finished dialog is only reported as is when Zeny, inventory and map are
# unchanged; otherwise the change is surfaced instead of hidden.
sub talk_outcome {
    my ($status, $reason, $before, $after) = @_;
    my @changed = grep { $before->{$_} ne $after->{$_} } qw(map zeny inventory);
    return @changed ? ('unknown', 'state_changed', \@changed) : ($status, $reason, []);
}

# npc_script: a server warp completes it only at the declared destination; a
# warp nobody declared, or a declared one that never came, is never success.
# Inventory, Zeny and EXP changes are reported for the caller to check.
sub script_outcome {
    my ($status, $reason, $expect, $warp) = @_;
    if ($warp) {
        return ('unknown', 'unexpected_warp') unless $expect && $warp->{map} eq $expect->{map} &&
            M1Navigation::distance($warp, $expect) <= WARP_SLACK;
        return ('completed', 'warped');
    }
    return ('failed', $status eq 'completed' ? 'warp_not_observed' : $reason) if $expect;
    ($status, $reason);
}

# A post-warp inventory must be ready and unchanged for a full second. The
# caller owns the action deadline; a missing observation is never empty stock.
sub stable_warp_snapshot {
    my ($state, $snapshot, $now, $deadline) = @_;
    return 'timeout' if $now >= $deadline;
    unless ($snapshot->{inventory_ready}) {
        delete $state->{candidate}; delete $state->{since};
        return 'waiting';
    }
    my $key = join("\x1e", map { defined $snapshot->{$_} ? $snapshot->{$_} : '' } qw(map inventory zeny exp));
    if (!defined $state->{candidate} || $state->{candidate} ne $key) {
        $state->{candidate} = $key; $state->{since} = $now;
        return 'waiting';
    }
    return $now - $state->{since} >= 1 ? 'stable' : 'waiting';
}

# Same-map walk portals (the tutorial castle's inner doors): source cell to landing.
sub same_map_portals {
    my ($lut) = @_;
    my %p;
    for my $key (sort keys %$lut) {
        my $src = $lut->{$key}{source} or next;
        for my $d (sort keys %{$lut->{$key}{dest} || {}}) {
            my $e = $lut->{$key}{dest}{$d};
            next if ($e->{cost} // 0) || ($e->{steps} // '') ne '' || !$e->{enabled} || $e->{map} ne $src->{map};
            $p{"$src->{map} $src->{x} $src->{y}"} = {x => 0 + $e->{x}, y => 0 + $e->{y}};
        }
    }
    \%p;
}

sub validate_portal {
    my ($a, $ctx, $portals) = @_;
    return 'invalid_portal' unless join(',', sort keys %$a) eq 'map,timeout_s,type,x,y' &&
        !grep { !defined($a->{$_}) || ref($a->{$_}) } qw(map timeout_s x y);
    return 'invalid_portal' unless $a->{x} =~ /^\d{1,3}$/ && $a->{y} =~ /^\d{1,3}$/ &&
        $a->{timeout_s} =~ /^\d{1,3}$/ && $a->{map} =~ /^[a-z0-9_-]{1,24}$/;
    return 'invalid_timeout' if $a->{timeout_s} < MIN_TIMEOUT || $a->{timeout_s} > MAX_TIMEOUT;
    return 'executor_not_native' unless $ctx->{manual_ai};
    return 'dead' unless $ctx->{hp} > 0;
    return 'wrong_map' unless $a->{map} eq $ctx->{map};
    return 'not_a_same_map_portal' unless $portals->{"$a->{map} $a->{x} $a->{y}"};
    return undef;
}
1;
