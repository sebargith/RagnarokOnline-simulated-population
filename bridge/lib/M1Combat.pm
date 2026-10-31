package M1Combat;
use strict;
use warnings;
use M1Navigation;

# Pure contract for native attack/take and the local recovery policy. The
# plugin supplies observed state; nothing here touches game globals.
# Thresholds follow the first live death (docs/evidence/P1b-native-combat.md):
# one Drops hit (7-8 of 47 HP) jumped past a 25% retreat line, and stopping
# after a fixed number of short legs let a slower chaser catch up.
use constant {MIN_TIMEOUT => 5, MAX_TIMEOUT => 120, MAX_RANGE => 14,
    ENGAGE_MIN => 60, RETREAT_BELOW => 35, RECOVERED_AT => 90,
    SAFE_DISTANCE => 15, RETREAT_DISTANCE => 12, RETREAT_BUDGET => 60, PICKUP_GRACE => 1};

sub hp_pct { my ($o) = @_; $o->{hp_max} ? 100 * $o->{hp} / $o->{hp_max} : 0 }

sub _common {
    my ($a, $ctx) = @_;
    return 'invalid_target' unless join(',', sort keys %$a) eq 'target,timeout_s,type' &&
        defined($a->{target}) && !ref($a->{target}) && $a->{target} =~ /^[a-f0-9]{8}$/ &&
        defined($a->{timeout_s}) && !ref($a->{timeout_s}) && $a->{timeout_s} =~ /^\d{1,3}$/;
    return 'invalid_timeout' if $a->{timeout_s} < MIN_TIMEOUT || $a->{timeout_s} > MAX_TIMEOUT;
    return 'executor_not_native' unless $ctx->{manual_ai};
    return 'dead' if $ctx->{dead} || $ctx->{hp} <= 0;
    return 'recovering' if $ctx->{recovering};
    return undef;
}

# ctx->{monster}: undef when not visible, else {dead, pos, engaged_by_other}.
sub validate_attack {
    my ($a, $ctx) = @_;
    my $reason = _common($a, $ctx);
    return $reason if $reason;
    return 'hp_too_low' if hp_pct($ctx) < ENGAGE_MIN;
    my $m = $ctx->{monster} or return 'target_not_visible';
    return 'target_dead' if $m->{dead};
    return 'target_too_far' if M1Navigation::distance($m->{pos}, $ctx->{pos}) > MAX_RANGE;
    # Never steal a monster another player is already fighting.
    return 'target_engaged_by_other' if $m->{engaged_by_other};
    return undef;
}

# ctx->{item}: undef when not visible, else {pos}.
sub validate_take {
    my ($a, $ctx) = @_;
    my $reason = _common($a, $ctx);
    return $reason if $reason;
    my $item = $ctx->{item} or return 'item_not_visible';
    return 'item_too_far' if M1Navigation::distance($item->{pos}, $ctx->{pos}) > MAX_RANGE;
    return undef;
}

# Kill is only claimed when the server reported the target dead after our damage.
sub attack_outcome {
    my ($o) = @_;
    return ('failed', 'died') if $o->{self_dead};
    return () if $o->{in_queue};
    return ('completed', 'killed') if $o->{target_dead} && $o->{dmg_from_you} > 0;
    return ('failed', 'killed_by_other') if $o->{target_dead};
    return ('failed', 'cannot_reach_or_damage') if $o->{gave_up};
    return ('failed', 'target_lost') unless $o->{target_visible};
    return ('unknown', 'attack_ended');
}

# Pickup is only claimed from a matching inventory addition.
sub take_outcome {
    my ($o) = @_;
    return ('failed', 'died') if $o->{self_dead};
    return ('completed', 'picked_up') if $o->{inventory_added};
    return () if $o->{in_queue};
    return ('failed', 'take_gave_up') if $o->{item_visible};
    # The item may vanish a moment before the inventory packet arrives.
    return () if $o->{since_gone} < PICKUP_GRACE;
    return ('failed', 'item_lost');
}

# One recovery decision per tick: retreat, rest, sit, recovered, exhausted or
# nothing. A threat is an aggressive monster closer than SAFE_DISTANCE; while
# hurt and threatened we keep opening distance until the time budget runs out.
sub recovery_step {
    my ($o) = @_;
    return () if $o->{dead};
    my $pct = hp_pct($o);
    my $phase = $o->{phase} // 'none';
    if ($phase eq 'exhausted') { return $pct >= RECOVERED_AT ? ('recovered') : () }
    my $near = defined($o->{threat_distance}) && $o->{threat_distance} < SAFE_DISTANCE;
    my $hurt = $phase eq 'none' ? $pct < RETREAT_BELOW && ($o->{fighting} || $near) : $pct < RECOVERED_AT && $near;
    if ($hurt) {
        return () if $phase eq 'retreat' && $o->{retreat_moving};
        return ('exhausted') if ($o->{retreat_elapsed} // 0) >= RETREAT_BUDGET;
        return ('retreat');
    }
    return () if $phase eq 'retreat' && $o->{retreat_moving};
    return ('recovered') if $phase ne 'none' && $pct >= RECOVERED_AT;
    return ('rest') if $phase eq 'none' && $pct < ENGAGE_MIN && !$o->{busy};
    return ('rest') if $phase eq 'retreat';
    return ('sit') if $phase eq 'rest' && $o->{can_sit} && !$o->{sitting} && !$near;
    return ();
}

# First walkable cell about RETREAT_DISTANCE away from the threat, trying the
# direct escape direction first and widening the angle; undef if none.
sub retreat_cell {
    my ($pos, $threat, $walkable, $width, $height) = @_;
    my ($dx, $dy) = ($pos->{x} - $threat->{x}, $pos->{y} - $threat->{y});
    ($dx, $dy) = (1, 0) if !$dx && !$dy;
    my $base = atan2($dy, $dx);
    # Up to ~137 degrees off the escape line, so a cornered actor slides along
    # the wall instead of having no cell; never straight back at the threat.
    for my $offset (0, 0.4, -0.4, 0.8, -0.8, 1.2, -1.2, 1.6, -1.6, 2.0, -2.0, 2.4, -2.4) {
        for my $d (RETREAT_DISTANCE, RETREAT_DISTANCE - 3, RETREAT_DISTANCE + 3) {
            my $x = int($pos->{x} + $d * cos($base + $offset) + 0.5);
            my $y = int($pos->{y} + $d * sin($base + $offset) + 0.5);
            next if $x < 0 || $y < 0 || $x >= $width || $y >= $height;
            return {x => $x, y => $y} if $walkable->($x, $y);
        }
    }
    return undef;
}
1;
