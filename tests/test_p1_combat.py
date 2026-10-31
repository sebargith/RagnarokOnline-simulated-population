import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]

# Recorded states exercised against the real Perl contract module.
SCRIPT = r'''
use JSON::PP;
use M1Combat;
my $ctx = sub { my %o = @_; {manual_ai => 1, dead => 0, hp => 40, hp_max => 42, recovering => 0,
    pos => {x => 150, y => 250}, monster => {dead => 0, pos => {x => 155, y => 252}, engaged_by_other => 0},
    item => {pos => {x => 151, y => 250}}, %o} };
my $act = sub { my %o = @_; {type => 'attack', target => '0001a2b3', timeout_s => 30, %o} };
my $tk = sub { my %o = @_; {type => 'take', target => '0001a2b3', timeout_s => 30, %o} };
my %v = (
    attack_ok => M1Combat::validate_attack($act->(), $ctx->()),
    attack_extra => M1Combat::validate_attack({%{$act->()}, skill => 1}, $ctx->()),
    attack_bad_id => M1Combat::validate_attack($act->(target => 'zz'), $ctx->()),
    attack_timeout => M1Combat::validate_attack($act->(timeout_s => 121), $ctx->()),
    attack_legacy => M1Combat::validate_attack($act->(), $ctx->(manual_ai => 0)),
    attack_dead_self => M1Combat::validate_attack($act->(), $ctx->(dead => 1)),
    attack_recovering => M1Combat::validate_attack($act->(), $ctx->(recovering => 1)),
    attack_low_hp => M1Combat::validate_attack($act->(), $ctx->(hp => 24)),
    attack_invisible => M1Combat::validate_attack($act->(), $ctx->(monster => undef)),
    attack_corpse => M1Combat::validate_attack($act->(), $ctx->(monster => {dead => 1, pos => {x => 151, y => 250}})),
    attack_far => M1Combat::validate_attack($act->(), $ctx->(monster => {dead => 0, pos => {x => 165, y => 250}})),
    attack_ks => M1Combat::validate_attack($act->(), $ctx->(monster => {dead => 0, pos => {x => 151, y => 250}, engaged_by_other => 1})),
    take_ok => M1Combat::validate_take($tk->(), $ctx->(hp => 5)),
    take_invisible => M1Combat::validate_take($tk->(), $ctx->(item => undef)),
    take_far => M1Combat::validate_take($tk->(), $ctx->(item => {pos => {x => 150, y => 270}})),
);
my %a = (
    running => [M1Combat::attack_outcome({in_queue => 1, target_visible => 1})],
    killed => [M1Combat::attack_outcome({target_dead => 1, dmg_from_you => 12})],
    stolen => [M1Combat::attack_outcome({target_dead => 1, dmg_from_you => 0})],
    gave_up => [M1Combat::attack_outcome({gave_up => 1, target_visible => 1})],
    lost => [M1Combat::attack_outcome({target_visible => 0})],
    ended => [M1Combat::attack_outcome({target_visible => 1})],
    died => [M1Combat::attack_outcome({self_dead => 1, in_queue => 1})],
);
my %t = (
    running => [M1Combat::take_outcome({in_queue => 1, item_visible => 1})],
    picked => [M1Combat::take_outcome({inventory_added => 1})],
    awaiting_packet => [M1Combat::take_outcome({since_gone => 0.3})],
    lost => [M1Combat::take_outcome({since_gone => 1.5})],
    gave_up => [M1Combat::take_outcome({item_visible => 1})],
    died => [M1Combat::take_outcome({self_dead => 1})],
);
my $r = sub { my %o = @_; [M1Combat::recovery_step({dead => 0, hp => 47, hp_max => 47, phase => 'none',
    fighting => 0, threat_distance => undef, retreat_elapsed => 0, retreat_moving => 0, busy => 0,
    can_sit => 0, sitting => 0, %o})] };
my %rec = (
    healthy => $r->(),
    hurt_fighting => $r->(hp => 15, fighting => 1),
    hurt_threat_near => $r->(hp => 15, threat_distance => 3),
    hurt_threat_far => $r->(hp => 15, threat_distance => 20),
    low_idle => $r->(hp => 25),
    low_busy => $r->(hp => 25, busy => 1),
    retreating => $r->(hp => 6, phase => 'retreat', retreat_moving => 1, threat_distance => 2),
    # Regression: the first live death stood still after short legs while chased.
    leg_done_still_chased => $r->(hp => 6, phase => 'retreat', threat_distance => 5, retreat_elapsed => 4.4),
    leg_done_safe => $r->(hp => 6, phase => 'retreat', threat_distance => 16),
    rest_novice => $r->(hp => 20, phase => 'rest'),
    rest_can_sit => $r->(hp => 20, phase => 'rest', can_sit => 1),
    rest_threat_returns => $r->(hp => 30, phase => 'rest', can_sit => 1, threat_distance => 6),
    budget_spent => $r->(hp => 6, phase => 'rest', threat_distance => 4, retreat_elapsed => 60),
    exhausted_wait => $r->(hp => 6, phase => 'exhausted', threat_distance => 1),
    recovered => $r->(hp => 43, phase => 'rest'),
    dead => $r->(hp => 0, dead => 1, fighting => 1),
);
my $walk = sub { $_[0] != 162 };
my %cell = (
    away => M1Combat::retreat_cell({x => 150, y => 250}, {x => 145, y => 250}, sub { 1 }, 400, 400),
    blocked_direct => M1Combat::retreat_cell({x => 150, y => 250}, {x => 145, y => 250}, $walk, 400, 400),
    edge => M1Combat::retreat_cell({x => 1, y => 1}, {x => 5, y => 5}, sub { 1 }, 400, 400),
    none => M1Combat::retreat_cell({x => 150, y => 250}, {x => 145, y => 250}, sub { 0 }, 400, 400),
);
print JSON::PP->new->canonical->encode({validate => \%v, attack => \%a, take => \%t, recovery => \%rec, cell => \%cell});
'''


class CombatContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        perl = ROOT.parent/'vendor/strawberry-perl/perl/bin/perl.exe'
        perl = str(perl) if perl.exists() else shutil.which('perl')
        if not perl:
            raise unittest.SkipTest('Perl unavailable')
        result = subprocess.run([perl, '-I'+str(ROOT/'bridge/lib'), '-e', SCRIPT],
            capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.data = json.loads(result.stdout)

    def test_admission(self):
        self.assertEqual(self.data['validate'], {
            'attack_ok': None, 'attack_extra': 'invalid_target', 'attack_bad_id': 'invalid_target',
            'attack_timeout': 'invalid_timeout', 'attack_legacy': 'executor_not_native',
            'attack_dead_self': 'dead', 'attack_recovering': 'recovering', 'attack_low_hp': 'hp_too_low',
            'attack_invisible': 'target_not_visible', 'attack_corpse': 'target_dead',
            'attack_far': 'target_too_far', 'attack_ks': 'target_engaged_by_other',
            'take_ok': None, 'take_invisible': 'item_not_visible', 'take_far': 'item_too_far'})

    def test_kill_and_pickup_need_server_evidence(self):
        self.assertEqual(self.data['attack'], {
            'running': [], 'killed': ['completed', 'killed'], 'stolen': ['failed', 'killed_by_other'],
            'gave_up': ['failed', 'cannot_reach_or_damage'], 'lost': ['failed', 'target_lost'],
            'ended': ['unknown', 'attack_ended'], 'died': ['failed', 'died']})
        self.assertEqual(self.data['take'], {
            'running': [], 'picked': ['completed', 'picked_up'], 'awaiting_packet': [],
            'lost': ['failed', 'item_lost'], 'gave_up': ['failed', 'take_gave_up'], 'died': ['failed', 'died']})

    def test_recovery_policy(self):
        self.assertEqual(self.data['recovery'], {
            'healthy': [], 'hurt_fighting': ['retreat'], 'hurt_threat_near': ['retreat'],
            'hurt_threat_far': ['rest'], 'low_idle': ['rest'], 'low_busy': [],
            'retreating': [], 'leg_done_still_chased': ['retreat'], 'leg_done_safe': ['rest'],
            'rest_novice': [], 'rest_can_sit': ['sit'], 'rest_threat_returns': ['retreat'],
            'budget_spent': ['exhausted'], 'exhausted_wait': [], 'recovered': ['recovered'], 'dead': []})

    def test_retreat_moves_away_and_stays_on_map(self):
        cell = self.data['cell']
        self.assertEqual(cell['away'], {'x': 162, 'y': 250})
        self.assertNotEqual(cell['blocked_direct']['x'], 162)
        self.assertGreater(cell['blocked_direct']['x'], 150)
        self.assertTrue(all(v >= 0 for v in cell['edge'].values()))
        self.assertIsNone(cell['none'])


if __name__ == '__main__':
    unittest.main()
