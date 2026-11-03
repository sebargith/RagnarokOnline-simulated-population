# Frozen (R2, 2026-11-03): off the main path; OpenKore auto (scripts/run_r1.py)
# replaces it. Kept for its tests and evidence; do not extend.
package M1Healing;
use strict;
use warnings;
use JSON::PP;

# Local recovery only: Apple (512), never arbitrary type-0 items or commands.
# A write-ahead record prevents replay after timeout, disconnect or restart.
sub new {
    my ($class, $path) = @_;
    my $self = bless {path => $path, state => {status => 'none'}}, $class;
    if (-e $path) {
        eval {
            open my $f, '<:raw', $path or die $!;
            local $/; my $s = decode_json(<$f>); close $f;
            die 'invalid ledger' unless ref($s) eq 'HASH' &&
                ($s->{status} // '') =~ /^(none|pending|confirmed|failed|unknown)$/;
            $self->{state} = $s;
            # A previous send may have reached the server. Never resend it.
            $s->{status} = 'unknown' if $s->{status} eq 'pending';
        };
        $self->{state} = {status => 'error'} if $@;
    }
    return $self;
}
sub state { $_[0]->{state} }
sub save {
    my ($self, $s) = @_;
    $self->{state} = $s;
    my $ok = eval {
        open my $f, '>:raw', $self->{path} or die $!;
        print {$f} encode_json($s) or die $!;
        close $f or die $!;
        1;
    };
    $self->{state} = {status => 'error'} unless $ok;
    return $ok;
}
sub eligible {
    my ($self, $o, $now) = @_;
    my $s = $self->state;
    return 0 unless $s->{status} eq 'none' ||
        ($s->{status} eq 'confirmed' && $now - ($s->{sent_at} // $now) >= 10);
    return 0 unless $o->{ready} && !$o->{dead} && !$o->{busy} && !$o->{threat} &&
        $o->{phase} eq 'rest' && $o->{hp_max} && $o->{hp} > 0 &&
        100 * $o->{hp} / $o->{hp_max} < 60;
    return 0 unless ($o->{name_id} // 0) == 512 && ($o->{type} // -1) == 0 &&
        !$o->{equipped} && ($o->{amount} // 0) >= 1;
    return 1;
}
sub begin {
    my ($self, $o, $now) = @_;
    return 0 unless $self->eligible($o, $now);
    return $self->save({status => 'pending', index => $o->{index}, name_id => 512,
        before => $o->{amount}, sent_at => $now});
}
sub observe {
    my ($self, $o) = @_;
    my $s = $self->state;
    return 0 unless $s->{status} eq 'pending' && $o->{own} &&
        ($o->{index} // '') eq $s->{index} && ($o->{name_id} // 0) == $s->{name_id};
    my $status = !$o->{success} ? 'failed' :
        $o->{remaining} == $s->{before} - 1 ? 'confirmed' : 'unknown';
    $self->save({%$s, status => $status, remaining => $o->{remaining}});
    return 1;
}
sub expire {
    my ($self, $now) = @_;
    my $s = $self->state;
    return 0 unless $s->{status} eq 'pending' && $now - $s->{sent_at} >= 5;
    $self->save({%$s, status => 'unknown'});
    return 1;
}
1;
