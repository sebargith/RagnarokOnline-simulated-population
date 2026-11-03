# R1 trial: read-only observer for an OpenKore profile running --ai=auto.
# Appends JSON lines to $R1_OBSERVER_DIR/events.jsonl: game events from hooks and a
# compact state sample every few seconds. It never sends packets, commands or
# config changes; OpenKore's own AI owns every action.
package R1Observer;
use strict;
use warnings;
use JSON::PP;
use Time::HiRes qw(time);
use Globals qw($char $field $net @ai_seq);
use Plugins;
use Network;
use AI ();

use constant SAMPLE_S => 5;

my $dir = $ENV{R1_OBSERVER_DIR} or die "R1_OBSERVER_DIR is not set\n";
my $json = JSON::PP->new->canonical;
my ($last, $hooks) = (0, undef);

Plugins::register('r1_observer', 'R1 read-only observer', \&unload);
$hooks = Plugins::addHooks(
    ['AI_pre', \&tick],
    ['target_died', sub { my $m = $_[1]{monster} || {};
        event(kill => {name_id => 0 + ($m->{nameID} // 0), name => $m->{name} // ''}) }],
    ['self_died', sub { event(died => sample()) }],
    ['exp_gained', sub { event(exp => level()) }],
    ['base_level_changed', sub { event(level => level()) }],
    ['job_level_changed', sub { event(level => level()) }],
    ['zeny_change', sub { event(zeny => {zeny => 0 + ($_[1]{zeny} // 0), change => 0 + ($_[1]{change} // 0),
        map => map_name(), ai => [queue_view()]}) }],
    ['Network::Receive::map_changed', sub { event(map => {from => $_[1]{oldMap} // '', to => map_name(),
        zeny => zeny()}) }],
    ['npc_talk', sub { event(npc_talk => {name => $_[1]{name} // '', msg => $_[1]{msg} // '', map => map_name(),
        ai => [queue_view()]}) }],
    ['teleport_sent', sub { event(teleport => sample()) }],
    ['disconnected', sub { event(disconnected => {}) }],
    ['in_game', sub { event(in_game => {}) }],
);

sub in_game { $net && $net->getState == Network::IN_GAME && $char && $field }
sub map_name { in_game() ? $field->baseName : '' }
sub zeny { $char ? 0 + ($char->{zeny} // 0) : 0 }
sub queue_view { my $n = $#ai_seq > 5 ? 5 : $#ai_seq; @ai_seq[0 .. $n] }

sub level {
    return {} unless $char;
    return {base => 0 + ($char->{lv} // 0), exp => 0 + ($char->{exp} // 0), exp_max => 0 + ($char->{exp_max} // 0),
     job => 0 + ($char->{lv_job} // 0), job_exp => 0 + ($char->{exp_job} // 0),
     job_exp_max => 0 + ($char->{exp_job_max} // 0)}
}

sub sample {
    return {connected => 0} unless in_game();
    my %inventory;
    $inventory{$_->{nameID}} += $_->{amount} for @{$char->inventory->getItems};
    return {connected => 1, map => map_name(), x => 0 + $char->{pos_to}{x}, y => 0 + $char->{pos_to}{y},
     hp => 0 + ($char->{hp} // 0), hp_max => 0 + ($char->{hp_max} // 0), dead => $char->{dead} ? 1 : 0,
     sitting => $char->{sitting} ? 1 : 0, zeny => zeny(), weight => 0 + ($char->{weight} // 0),
     weight_max => 0 + ($char->{weight_max} // 0), points_free => 0 + ($char->{points_free} // 0),
     points_skill => 0 + ($char->{points_skill} // 0), job_id => 0 + ($char->{jobID} // 0),
     equipped => [sort { $a <=> $b } map { 0 + $_->{nameID} } grep { $_->{equipped} } @{$char->inventory->getItems}],
     stats => {map { $_ => 0 + ($char->{$_} // 0) } qw(str agi vit int dex luk)},
     level => level(), ai => [queue_view()], inventory => \%inventory}
}

sub tick {
    return if time - $last < SAMPLE_S;
    $last = time;
    event(sample => sample());
}

sub event {
    my ($type, $data) = @_;
    open(my $fh, '>>', "$dir/events.jsonl") or return;
    print $fh $json->encode({t => 0 + sprintf('%.3f', time), type => $type, %$data}) . "\n";
    close $fh;
}

sub unload {
    Plugins::delHooks($hooks) if $hooks;
}

1;
