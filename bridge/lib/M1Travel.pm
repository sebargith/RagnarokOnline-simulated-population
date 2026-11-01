package M1Travel;
use strict;
use warnings;
use M1Navigation;

# Pure contract for P2a: cross-map travel through walkable portals only, and a
# bounded NPC dialog. The plugin supplies observed state; nothing here touches
# the network, AI queue or game globals.
use constant {MAX_HOPS => 3, MIN_TIMEOUT => 5, MAX_TIMEOUT => 300, ENTER_WAIT => 5,
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

# Keeps only free, talk-less, permanently enabled map-to-map portals from
# OpenKore's portals table: no Kafra, paid or scripted NPC warps, no dynamic
# groups, airships or warp items (those live in other tables).
sub walk_graph {
    my ($lut) = @_;
    my %g;
    for my $key (sort keys %$lut) {
        my $src = $lut->{$key}{source} or next;
        for my $d (sort keys %{$lut->{$key}{dest} || {}}) {
            my $e = $lut->{$key}{dest}{$d};
            next if ($e->{cost} // 0) || ($e->{steps} // '') ne '' || !$e->{enabled} ||
                defined $e->{dynamicPortalGroup} || defined $e->{dynamicPortalGroupBlock} ||
                $e->{map} eq $src->{map};
            push @{$g{$src->{map}}}, {x => 0 + $src->{x}, y => 0 + $src->{y}, to_map => $e->{map},
                to => {x => 0 + $e->{x}, y => 0 + $e->{y}}};
        }
    }
    \%g;
}

# Fewest-hops map path (ties by map name), then on each map the portal closest
# to where the character is or lands. Returns portal legs plus the final leg,
# or () when no walkable path within MAX_HOPS exists.
sub plan {
    my ($g, $from, $pos, $to, $dest) = @_;
    my %prev = ($from => '');
    my @queue = ([$from, 0]);
    while (@queue) {
        my ($map, $hops) = @{shift @queue};
        last if exists $prev{$to};
        next if $hops >= MAX_HOPS;
        for my $next (sort { $a cmp $b } map { $_->{to_map} } @{$g->{$map} || []}) {
            next if exists $prev{$next};
            $prev{$next} = $map;
            push @queue, [$next, $hops + 1];
        }
    }
    return () unless exists $prev{$to};
    my @maps = ($to);
    unshift @maps, $prev{$maps[0]} while $prev{$maps[0]} ne '';
    my (@legs, $at);
    $at = $pos;
    for my $i (0 .. $#maps - 1) {
        my ($portal) = sort { M1Navigation::distance($a, $at) <=> M1Navigation::distance($b, $at) ||
            $a->{x} <=> $b->{x} || $a->{y} <=> $b->{y} } grep { $_->{to_map} eq $maps[$i + 1] } @{$g->{$maps[$i]}};
        push @legs, {map => $maps[$i], x => $portal->{x}, y => $portal->{y}, to_map => $portal->{to_map}};
        $at = $portal->{to};
    }
    push @legs, {map => $to, x => 0 + $dest->{x}, y => 0 + $dest->{y}};
    @legs;
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
