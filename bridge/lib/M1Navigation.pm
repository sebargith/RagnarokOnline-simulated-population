package M1Navigation;
use strict;
use warnings;

# Pure contract for native same-map navigation. The plugin supplies observed
# state; nothing here touches the network, AI queue or game globals.
use constant {MIN_TIMEOUT => 5, MAX_TIMEOUT => 300, GRACE => 5};

# Returns undef when the action is admissible, otherwise a rejection reason.
sub validate {
    my ($a, $ctx) = @_;
    return 'invalid_navigate' unless join(',', sort keys %$a) eq 'map,timeout_s,type,x,y' &&
        !grep { !defined($a->{$_}) || ref($a->{$_}) } qw(map timeout_s x y);
    return 'invalid_navigate' unless $a->{x} =~ /^\d{1,3}$/ && $a->{y} =~ /^\d{1,3}$/ &&
        $a->{timeout_s} =~ /^\d{1,3}$/ && $a->{map} =~ /^[a-z0-9_-]{1,24}$/;
    return 'invalid_timeout' if $a->{timeout_s} < MIN_TIMEOUT || $a->{timeout_s} > MAX_TIMEOUT;
    return 'executor_not_native' unless $ctx->{manual_ai};
    return 'dead' unless $ctx->{hp} > 0;
    # Cross-map routing may use paid NPC transport; it is not part of this slice.
    return 'cross_map_not_supported' unless $a->{map} eq $ctx->{map};
    return 'out_of_bounds' unless $a->{x} < $ctx->{width} && $a->{y} < $ctx->{height};
    return 'not_walkable' unless $ctx->{walkable}->($a->{x}, $a->{y});
    return 'already_at_destination' if $a->{x} == $ctx->{pos_to}{x} && $a->{y} == $ctx->{pos_to}{y};
    return undef;
}

sub distance {
    my ($p, $q) = @_;
    my ($dx, $dy) = (abs($p->{x} - $q->{x}), abs($p->{y} - $q->{y}));
    $dx > $dy ? $dx : $dy;
}

# Maps a finished or lost task to (status, reason). Task::Route error codes:
# 0 TOO_MUCH_TIME, 1 CANNOT_CALCULATE_ROUTE, 2 STUCK, others unexpected.
# 'done' without error is only success when the server-acked position matches.
sub outcome {
    my ($task, $error, $obs) = @_;
    return ('unknown', 'route_task_lost') if $task eq 'missing';
    return ('unknown', 'route_task_stopped') if $task eq 'stopped';
    return () unless $task eq 'done';
    if ($error) {
        my $code = $error->{code} // -1;
        return ('failed', 'timeout') if $code == 0;
        return ('failed', 'unreachable') if $code == 1;
        return ('failed', 'blocked') if $code == 2;
        return ('unknown', 'route_error');
    }
    return ('unknown', 'map_changed') unless $obs->{map} eq $obs->{dest_map};
    return ('completed', 'arrived') if distance($obs->{pos_to}, $obs->{dest}) == 0 &&
        distance($obs->{calc}, $obs->{dest}) <= 1;
    return ('unknown', 'route_ended_off_target');
}
1;
