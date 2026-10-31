package M1Explore;
use strict;
use warnings;

# At most 48 straight, obstacle-free rays from the current position. The
# callbacks use OpenKore's loaded client field, not server-side entity state.
sub candidates {
    my ($pos, $width, $height, $walkable, $path_free) = @_;
    my @directions = ([1,0],[1,0.5],[1,1],[0.5,1],[0,1],[-0.5,1],[-1,1],[-1,0.5],
                      [-1,0],[-1,-0.5],[-1,-1],[-0.5,-1],[0,-1],[0.5,-1],[1,-1],[1,-0.5]);
    my @out;
    for my $radius (20, 35, 50) {
        for my $d (@directions) {
            my $x = int($pos->{x} + $radius * $d->[0]);
            my $y = int($pos->{y} + $radius * $d->[1]);
            # Stay away from map edges and accidental edge portals.
            next if $x < 8 || $y < 8 || $x >= $width - 8 || $y >= $height - 8;
            next unless $walkable->($x, $y);
            my $target = {x => $x, y => $y};
            next unless $path_free->($pos, $target);
            push @out, $target;
        }
    }
    return \@out;
}
1;
