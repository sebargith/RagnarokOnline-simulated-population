package Interface::M1Headless;
use strict;
use warnings;
use base 'Interface';

# The stock Windows console interface requires real console screen/input handles.
# This interface keeps the normal OpenKore loop and fails on missing configuration.
sub new { $| = 1; bless {}, shift }
sub getInput { undef }
sub writeOutput { print STDOUT $_[2] }
sub query { die "Headless configuration requires input: $_[1]\n" }
sub title { }
sub beep { }
1;
