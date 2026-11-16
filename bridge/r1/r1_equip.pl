# R1: wear the gear plan (docs/PROGRESSION_ECONOMY.md E2, agent/gear_plan.py).
# config.txt carries one key per slot, r1_equip_<slot> <item id>, written by
# scripts/build_r1_profile.py and refreshed by r1_reload. OpenKore's own equipAuto
# cannot be used for this: its gate (Actor::Item::scanConfigAndCheck) reads a
# number as an inventory index, and names come from the Korean kRO table. This
# plugin calls OpenKore's own Actor::Item::bulkEquip, which takes item ids and
# skips what is already worn. Only when idle, routing or fighting (as equipAuto),
# never during NPC, shop or storage steps. No packets of its own; each equip is an event.
package R1Equip;
use strict;
use warnings;
use JSON::PP;
use Time::HiRes qw(time);
use Globals qw($char $field $net %config %equipSlot_rlut);
use Plugins;
use Network;
use AI ();
use Actor::Item;

use constant {POLL_S => 2, RETRY_S => 30};

my $dir = $ENV{R1_OBSERVER_DIR} or die "R1_OBSERVER_DIR is not set\n";
my $json = JSON::PP->new->canonical;
my ($last, %tried, $hooks) = (0);

Plugins::register('r1_equip', 'R1 wear the gear plan by item id', \&unload);
$hooks = Plugins::addHooks(['AI_pre', \&tick]);

sub tick {
    return if time - $last < POLL_S;
    $last = time;
    return unless $net && $net->getState == Network::IN_GAME && $char && $field && !$char->{dead};
    return unless $char->inventory->isReady && $char->{equipment};
    return unless AI::isIdle || AI::is(qw(route mapRoute attack sitAuto items_take take));
    my %list;
    for my $slot (sort keys %equipSlot_rlut) {
        my $id = $config{"r1_equip_$slot"} // '';
        next unless $id =~ /^\d+$/;
        my $item = $char->inventory->getByNameID($id, 1) or next;
        next if $item->{equipped} || time - ($tried{"$slot:$id"} // 0) < RETRY_S;
        $tried{"$slot:$id"} = time;
        $list{$slot} = $id;
    }
    return unless %list;
    Actor::Item::bulkEquip(\%list);
    open(my $fh, '>>', "$dir/events.jsonl") or return;
    print $fh $json->encode({t => 0 + sprintf('%.3f', time), type => 'equip', items => {map { $_ => 0 + $list{$_} } keys %list},
        map => $field->baseName}) . "\n";
    close $fh;
}

sub unload {
    Plugins::delHooks($hooks) if $hooks;
}

1;
