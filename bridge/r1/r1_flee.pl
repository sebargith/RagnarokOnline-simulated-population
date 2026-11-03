# R1: flee without a Fly Wing (policy rule leave_pack_no_wings). With the same
# thresholds OpenKore uses for teleportAuto (teleportAuto_hp with aggressives,
# teleportAuto_minAggressives, teleportAuto_minAggressivesInLock in the lockMap),
# when the character has no Fly Wing it clears the fight and takes OpenKore's own
# route to the supply town without attacking or sitting on the way; leaving the
# map ends the fight, and lockMap brings it back later. Reversible movement only:
# no packets, NPC dialogs or console commands of its own. Each flee is an event.
package R1Flee;
use strict;
use warnings;
use JSON::PP;
use Time::HiRes qw(time);
use Globals qw($char $field $net %config);
use Plugins;
use Network;
use AI ();
use Misc qw(percent_hp);

use constant {POLL_S => 0.5, COOLDOWN_S => 30, FLY_WING => 601};

my $dir = $ENV{R1_OBSERVER_DIR} or die "R1_OBSERVER_DIR is not set\n";
my $json = JSON::PP->new->canonical;
my ($last, $fled, $hooks) = (0, 0, undef);

Plugins::register('r1_flee', 'R1 flee without Fly Wing', \&unload);
$hooks = Plugins::addHooks(['AI_pre', \&tick]);

sub tick {
    return if time - $last < POLL_S;
    $last = time;
    return unless $net && $net->getState == Network::IN_GAME && $char && $field;
    return if $char->{dead} || $field->isCity || time - $fled < COOLDOWN_S;
    return if $char->inventory->getByNameID(FLY_WING);
    my $aggressives = scalar(AI::ai_getAggressives());
    return unless $aggressives;
    my $in_lock = $field->baseName eq ($config{lockMap} // '');
    my $pack = $in_lock && $config{teleportAuto_minAggressivesInLock}
        ? $config{teleportAuto_minAggressivesInLock} : $config{teleportAuto_minAggressives};
    my $low = $config{teleportAuto_hp} && percent_hp($char) <= $config{teleportAuto_hp};
    return unless $low || ($pack && $aggressives >= $pack);
    my ($town) = split ' ', ($config{sellAuto_npc} // '');
    return unless $town;
    $fled = time;
    AI::clear(qw(attack route move mapRoute sitAuto sitting items_take take));
    $char->route($town, undef, undef, attackOnRoute => 0, noSitAuto => 1, isEscape => 1);
    open(my $fh, '>>', "$dir/events.jsonl") or return;
    print $fh $json->encode({t => 0 + sprintf('%.3f', time), type => 'flee', map => $field->baseName, to => $town,
        hp => 0 + ($char->{hp} // 0), hp_max => 0 + ($char->{hp_max} // 0), aggressives => $aggressives,
        why => $low ? 'low_hp' : 'pack'}) . "\n";
    close $fh;
}

sub unload {
    Plugins::delHooks($hooks) if $hooks;
}

1;
