package M1Progress;
use strict;
use warnings;

# Pure contract for P5 character progress: raising a stat or a skill and
# equipping or taking off an item. The plugin supplies observed state and the
# server's acknowledgement packets; nothing here touches game globals.
# Success is only claimed from the matching server packet (PACKETVER 20130807).
use constant {MIN_TIMEOUT => 5, MAX_TIMEOUT => 30, MAX_STAT => 99};

our @STATS = qw(str agi vit int dex luk);
# OpenKore jobID -> rAthena job name, as in config/p5-equipment.json.
my %JOB = (0 => 'Novice', 1 => 'Swordman', 2 => 'Mage', 3 => 'Archer',
    4 => 'Acolyte', 5 => 'Merchant', 6 => 'Thief');
my %KEYS = (stat_up => 'stat,timeout_s,type', skill_up => 'skill,timeout_s,type',
    equip => 'name_id,timeout_s,type', unequip => 'name_id,timeout_s,type');
my %FIELD = (stat_up => qr/^(?:str|agi|vit|int|dex|luk)$/, skill_up => qr/^[A-Z][A-Z0-9_]{1,31}$/,
    equip => qr/^[1-9]\d{0,5}$/, unequip => qr/^[1-9]\d{0,5}$/);

sub job_name { defined $_[0] ? $JOB{$_[0]} : undef }

sub _common {
    my ($a, $ctx) = @_;
    my $type = $a->{type} // '';
    my ($field) = $KEYS{$type} ? grep { $_ ne 'timeout_s' && $_ ne 'type' } split /,/, $KEYS{$type} : ();
    return "invalid_$type" unless $KEYS{$type} && join(',', sort keys %$a) eq $KEYS{$type} &&
        defined($a->{$field}) && !ref($a->{$field}) && $a->{$field} =~ $FIELD{$type} &&
        defined($a->{timeout_s}) && !ref($a->{timeout_s}) && $a->{timeout_s} =~ /^\d{1,2}$/;
    return 'invalid_timeout' if $a->{timeout_s} < MIN_TIMEOUT || $a->{timeout_s} > MAX_TIMEOUT;
    return 'executor_not_native' unless $ctx->{manual_ai};
    return 'dead' if $ctx->{dead} || !$ctx->{hp} || $ctx->{hp} <= 0;
    return 'recovering' if $ctx->{recovering};
    return undef;
}

# ctx->{stats}: undef until the server's status packet arrived, else
# {str => {value, cost}, ...}; ctx->{points_free} from the same packet.
sub validate_stat {
    my ($a, $ctx) = @_;
    my $r = _common($a, $ctx);
    return $r if $r;
    my $s = $ctx->{stats} && $ctx->{stats}{$a->{stat}} or return 'stats_not_observed';
    return 'stat_at_max' if $s->{value} >= MAX_STAT;
    return 'insufficient_stat_points' if !$s->{cost} || ($ctx->{points_free} // 0) < $s->{cost};
    return undef;
}

# ctx->{skills}: {handle => {lv, up}} from the server's skill list, where up
# is the server's own "can be raised" flag (prerequisites and max level).
sub validate_skill {
    my ($a, $ctx) = @_;
    my $r = _common($a, $ctx);
    return $r if $r;
    my $s = $ctx->{skills} && $ctx->{skills}{$a->{skill}} or return 'skill_not_available';
    return 'skill_not_upgradable' unless $s->{up};
    return 'insufficient_skill_points' if ($ctx->{points_skill} // 0) < 1;
    return undef;
}

# ctx->{inventory}: [{name_id, equipped, identified, equippable}];
# ctx->{requirements}: config/p5-equipment.json entry for name_id or undef;
# ctx->{job_id}, ctx->{base_level}, ctx->{sex} (0 female, 1 male).
sub validate_equip {
    my ($a, $ctx) = @_;
    my $r = _common($a, $ctx);
    return $r if $r;
    return 'inventory_not_ready' unless $ctx->{inventory_ready};
    my @held = grep { $_->{name_id} == $a->{name_id} } @{$ctx->{inventory}};
    return 'item_not_in_inventory' unless @held;
    my @free = grep { !$_->{equipped} } @held or return 'already_equipped';
    return 'item_not_equippable' unless grep { $_->{equippable} } @free;
    return 'item_unidentified' unless grep { $_->{equippable} && $_->{identified} } @free;
    my $req = $ctx->{requirements} or return 'equipment_requirements_unknown';
    my $job = job_name($ctx->{job_id}) or return 'job_unknown';
    return 'job_cannot_equip' unless grep { $_ eq $job } @{$req->{jobs}};
    return 'level_too_low' if ($ctx->{base_level} // 0) < $req->{min_level};
    my $gender = $req->{gender} // 'Both';
    return 'gender_cannot_equip' if $gender ne 'Both' && $gender ne (($ctx->{sex} // -1) == 1 ? 'Male' : 'Female');
    return undef;
}

sub validate_unequip {
    my ($a, $ctx) = @_;
    my $r = _common($a, $ctx);
    return $r if $r;
    return 'inventory_not_ready' unless $ctx->{inventory_ready};
    return 'item_not_equipped' unless grep { $_->{name_id} == $a->{name_id} && $_->{equipped} } @{$ctx->{inventory}};
    return undef;
}

# Acknowledgement flags by packet switch. For PACKETVER >= 20110824 rAthena
# sends 0 for success in 0999/08D0 (equip) and 099A/08D1 (take off); the old
# 00AA/00AC carry 1 for success.
sub ack_ok {
    my ($switch, $flag) = @_;
    $switch = uc($switch // '');
    return $flag == 0 ? 1 : 0 if $switch =~ /^(0999|08D0|099A|08D1)$/;
    return $flag == 1 ? 1 : 0 if $switch =~ /^(00AA|00AC)$/;
    return 0;
}

# o: {self_dead, expired, ack => undef | {ok, value}, before}. 00BC always
# answers a status-up request; ok with the raised value is the only success.
sub stat_outcome {
    my ($o) = @_;
    if (my $ack = $o->{ack}) {
        return ('failed', 'server_refused') unless $ack->{ok};
        return ('completed', 'stat_raised') if $ack->{value} == $o->{before} + 1;
        return ('unknown', 'stat_mismatch');
    }
    return ('unknown', 'result_not_confirmed') if $o->{expired};
    return ();
}

# o: {expired, level => undef | level from 010E for this skill, before}.
# The server sends nothing when it ignores a skill-up, so silence is unknown.
sub skill_outcome {
    my ($o) = @_;
    if (defined $o->{level}) {
        return ('completed', 'skill_raised') if $o->{level} == $o->{before} + 1;
        return ('unknown', 'skill_mismatch') if $o->{level} != $o->{before};
    }
    return ('unknown', 'result_not_confirmed') if $o->{expired};
    return ();
}

# o: {expired, ack => undef | {ok, location}} for equip or unequip.
sub equip_outcome {
    my ($o, $done) = @_;
    if (my $ack = $o->{ack}) {
        return ('failed', 'server_refused') unless $ack->{ok};
        return ('completed', $done) if $ack->{location};
        return ('unknown', 'no_location');
    }
    return ('unknown', 'result_not_confirmed') if $o->{expired};
    return ();
}
1;
