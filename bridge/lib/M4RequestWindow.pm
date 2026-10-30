package M4RequestWindow;
use strict;
use warnings;

# One boot's monotonic IDs: bounded result retention without allowing replay
# after eviction. Legacy UUID requests retain their original separate limit.
sub new { bless {high => 0, cap => $_[1], results => {}, order => []}, $_[0] }
sub next_serial { $_[0]{high} + 1 }
sub admit {
    my ($self, $id) = @_;
    return ('cached', $self->{results}{$id}) if exists $self->{results}{$id};
    return ('retired') unless $id =~ /^c_(\d{1,15})$/ && $1 > $self->{high};
    $self->{high} = 0 + $1;
    $self->{results}{$id} = {};
    push @{$self->{order}}, $id;
    delete $self->{results}{shift @{$self->{order}}} while @{$self->{order}} > $self->{cap};
    return ('new');
}
sub finish {
    my ($self, $id, $result) = @_;
    $self->{results}{$id} = $result if exists $self->{results}{$id};
}
sub size { scalar keys %{$_[0]{results}} }
1;
