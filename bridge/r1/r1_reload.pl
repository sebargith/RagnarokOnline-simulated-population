# R1: the single sync point for policy refits. When the supervisor writes
# $R1_OBSERVER_DIR/reload.request (one request id), reload this profile's four
# generated control files with OpenKore's own reload and record the result as an
# event. It sends no packets and runs no console commands.
package R1Reload;
use strict;
use warnings;
use JSON::PP;
use Time::HiRes qw(time);
use Globals qw(%config);
use Plugins;
use Misc ();

use constant POLL_S => 2;
use constant FILES => 'config\.txt$|mon_control\.txt$|items_control\.txt$|routeweights\.txt$';

my $dir = $ENV{R1_OBSERVER_DIR} or die "R1_OBSERVER_DIR is not set\n";
my $json = JSON::PP->new->canonical;
my ($last, $hooks) = (0, undef);

Plugins::register('r1_reload', 'R1 profile reload on supervisor request', \&unload);
$hooks = Plugins::addHooks(['AI_pre', \&tick]);

sub tick {
    return if time - $last < POLL_S;
    $last = time;
    my $path = "$dir/reload.request";
    return unless -e $path;
    open(my $in, '<', $path) or return;
    my $id = <$in> // '';
    close $in;
    unlink $path;
    $id =~ s/\s+//g;
    my $ok = eval { Misc::parseReload(FILES); 1 };
    open(my $fh, '>>', "$dir/events.jsonl") or return;
    print $fh $json->encode({t => 0 + sprintf('%.3f', time), type => 'reloaded', id => $id, ok => $ok ? 1 : 0,
        error => $ok ? '' : "$@", lockMap => $config{lockMap} // '',
        sell_weight => 0 + ($config{itemsMaxWeight_sellOrStore} // 0)}) . "\n";
    close $fh;
}

sub unload {
    Plugins::delHooks($hooks) if $hooks;
}

1;
