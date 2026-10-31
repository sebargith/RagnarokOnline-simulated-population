import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]

# Recorded states exercised against the real Perl contract module.
SCRIPT = r'''
use JSON::PP;
use M1Progress;
my $base = sub { my %o = @_; {manual_ai => 1, dead => 0, hp => 40, recovering => 0, %o} };
my $stats = {str => {value => 5, cost => 2}, agi => {value => 99, cost => 0}, vit => {value => 5, cost => 2},
    int => {value => 1, cost => 2}, dex => {value => 5, cost => 2}, luk => {value => 1, cost => 2}};
my $st = sub { my %o = @_; $base->(stats => $stats, points_free => 3, %o) };
my $sk = sub { my %o = @_; $base->(skills => {NV_BASIC => {lv => 1, up => 1}, SM_BASH => {lv => 0, up => 0}}, points_skill => 2, %o) };
my $req = {jobs => ['Novice', 'Swordman'], min_level => 2, gender => 'Both'};
my $inv = [{name_id => 1201, equipped => 2, identified => 1, equippable => 1},
    {name_id => 1101, equipped => 0, identified => 1, equippable => 1},
    {name_id => 1102, equipped => 0, identified => 0, equippable => 1},
    {name_id => 512, equipped => 0, identified => 1, equippable => 0}];
my $eq = sub { my %o = @_; $base->(inventory_ready => 1, inventory => $inv, requirements => $req,
    job_id => 0, base_level => 4, sex => 1, %o) };
my $a = sub { my ($type, $field, $value, %o) = @_; {type => $type, $field => $value, timeout_s => 10, %o} };
my %v = (
    stat_ok => M1Progress::validate_stat($a->('stat_up', stat => 'str'), $st->()),
    stat_extra => M1Progress::validate_stat($a->('stat_up', stat => 'str', amount => 2), $st->()),
    stat_bad_name => M1Progress::validate_stat($a->('stat_up', stat => 'hp'), $st->()),
    stat_timeout => M1Progress::validate_stat($a->('stat_up', stat => 'str', timeout_s => 31), $st->()),
    stat_legacy => M1Progress::validate_stat($a->('stat_up', stat => 'str'), $st->(manual_ai => 0)),
    stat_dead => M1Progress::validate_stat($a->('stat_up', stat => 'str'), $st->(dead => 1)),
    stat_recovering => M1Progress::validate_stat($a->('stat_up', stat => 'str'), $st->(recovering => 1)),
    stat_unobserved => M1Progress::validate_stat($a->('stat_up', stat => 'str'), $st->(stats => undef)),
    stat_max => M1Progress::validate_stat($a->('stat_up', stat => 'agi'), $st->()),
    stat_poor => M1Progress::validate_stat($a->('stat_up', stat => 'str'), $st->(points_free => 1)),
    skill_ok => M1Progress::validate_skill($a->('skill_up', skill => 'NV_BASIC'), $sk->()),
    skill_bad_handle => M1Progress::validate_skill($a->('skill_up', skill => 'nv basic'), $sk->()),
    skill_unlisted => M1Progress::validate_skill($a->('skill_up', skill => 'AC_OWL'), $sk->()),
    skill_locked => M1Progress::validate_skill($a->('skill_up', skill => 'SM_BASH'), $sk->()),
    skill_no_points => M1Progress::validate_skill($a->('skill_up', skill => 'NV_BASIC'), $sk->(points_skill => 0)),
    equip_ok => M1Progress::validate_equip($a->('equip', name_id => 1101), $eq->()),
    equip_string_id => M1Progress::validate_equip($a->('equip', name_id => 'x1'), $eq->()),
    equip_not_ready => M1Progress::validate_equip($a->('equip', name_id => 1101), $eq->(inventory_ready => 0)),
    equip_missing => M1Progress::validate_equip($a->('equip', name_id => 2301), $eq->()),
    equip_worn => M1Progress::validate_equip($a->('equip', name_id => 1201), $eq->()),
    equip_consumable => M1Progress::validate_equip($a->('equip', name_id => 512), $eq->()),
    equip_unidentified => M1Progress::validate_equip($a->('equip', name_id => 1102), $eq->()),
    equip_unknown => M1Progress::validate_equip($a->('equip', name_id => 1101), $eq->(requirements => undef)),
    equip_job_unknown => M1Progress::validate_equip($a->('equip', name_id => 1101), $eq->(job_id => 4001)),
    equip_wrong_job => M1Progress::validate_equip($a->('equip', name_id => 1101), $eq->(job_id => 3)),
    equip_low_level => M1Progress::validate_equip($a->('equip', name_id => 1101), $eq->(base_level => 1)),
    equip_gender => M1Progress::validate_equip($a->('equip', name_id => 1101),
        $eq->(requirements => {%$req, gender => 'Female'})),
    unequip_ok => M1Progress::validate_unequip($a->('unequip', name_id => 1201), $eq->()),
    unequip_not_worn => M1Progress::validate_unequip($a->('unequip', name_id => 1101), $eq->()),
);
my %ack = (
    v5_equip_ok => M1Progress::ack_ok('0999', 0), v5_equip_fail => M1Progress::ack_ok('0999', 2),
    v5_unequip_ok => M1Progress::ack_ok('099A', 0), v5_unequip_fail => M1Progress::ack_ok('099A', 1),
    old_equip_ok => M1Progress::ack_ok('00AA', 1), old_equip_fail => M1Progress::ack_ok('00AA', 0),
    other => M1Progress::ack_ok('0001', 0),
);
my %o = (
    stat_wait => [M1Progress::stat_outcome({before => 5})],
    stat_raised => [M1Progress::stat_outcome({before => 5, ack => {ok => 1, value => 6}})],
    stat_refused => [M1Progress::stat_outcome({before => 5, ack => {ok => 0, value => 5}})],
    stat_mismatch => [M1Progress::stat_outcome({before => 5, ack => {ok => 1, value => 8}})],
    stat_silent => [M1Progress::stat_outcome({before => 5, expired => 1})],
    skill_wait => [M1Progress::skill_outcome({before => 1})],
    skill_raised => [M1Progress::skill_outcome({before => 1, level => 2})],
    skill_same => [M1Progress::skill_outcome({before => 1, level => 1})],
    skill_jump => [M1Progress::skill_outcome({before => 1, level => 4})],
    skill_silent => [M1Progress::skill_outcome({before => 1, expired => 1})],
    equip_wait => [M1Progress::equip_outcome({}, 'equipped')],
    equip_done => [M1Progress::equip_outcome({ack => {ok => 1, location => 2}}, 'equipped')],
    equip_refused => [M1Progress::equip_outcome({ack => {ok => 0, location => 2}}, 'equipped')],
    equip_nowhere => [M1Progress::equip_outcome({ack => {ok => 1, location => 0}}, 'equipped')],
    equip_silent => [M1Progress::equip_outcome({expired => 1}, 'equipped')],
    unequip_done => [M1Progress::equip_outcome({ack => {ok => 1, location => 2}}, 'unequipped')],
);
print JSON::PP->new->canonical->encode({validate => \%v, ack => \%ack, outcome => \%o,
    jobs => [map { M1Progress::job_name($_) } 0, 1, 3, 6, 7]});
'''


class ProgressContractTests(unittest.TestCase):
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
            'stat_ok': None, 'stat_extra': 'invalid_stat_up', 'stat_bad_name': 'invalid_stat_up',
            'stat_timeout': 'invalid_timeout', 'stat_legacy': 'executor_not_native', 'stat_dead': 'dead',
            'stat_recovering': 'recovering', 'stat_unobserved': 'stats_not_observed', 'stat_max': 'stat_at_max',
            'stat_poor': 'insufficient_stat_points',
            'skill_ok': None, 'skill_bad_handle': 'invalid_skill_up', 'skill_unlisted': 'skill_not_available',
            'skill_locked': 'skill_not_upgradable', 'skill_no_points': 'insufficient_skill_points',
            'equip_ok': None, 'equip_string_id': 'invalid_equip', 'equip_not_ready': 'inventory_not_ready',
            'equip_missing': 'item_not_in_inventory', 'equip_worn': 'already_equipped',
            'equip_consumable': 'item_not_equippable', 'equip_unidentified': 'item_unidentified',
            'equip_unknown': 'equipment_requirements_unknown', 'equip_job_unknown': 'job_unknown',
            'equip_wrong_job': 'job_cannot_equip', 'equip_low_level': 'level_too_low',
            'equip_gender': 'gender_cannot_equip',
            'unequip_ok': None, 'unequip_not_worn': 'item_not_equipped'})

    def test_ack_flags_follow_packet_version(self):
        self.assertEqual(self.data['ack'], {'v5_equip_ok': 1, 'v5_equip_fail': 0, 'v5_unequip_ok': 1,
            'v5_unequip_fail': 0, 'old_equip_ok': 1, 'old_equip_fail': 0, 'other': 0})

    def test_success_needs_server_ack(self):
        self.assertEqual(self.data['outcome'], {
            'stat_wait': [], 'stat_raised': ['completed', 'stat_raised'], 'stat_refused': ['failed', 'server_refused'],
            'stat_mismatch': ['unknown', 'stat_mismatch'], 'stat_silent': ['unknown', 'result_not_confirmed'],
            'skill_wait': [], 'skill_raised': ['completed', 'skill_raised'], 'skill_same': [],
            'skill_jump': ['unknown', 'skill_mismatch'], 'skill_silent': ['unknown', 'result_not_confirmed'],
            'equip_wait': [], 'equip_done': ['completed', 'equipped'], 'equip_refused': ['failed', 'server_refused'],
            'equip_nowhere': ['unknown', 'no_location'], 'equip_silent': ['unknown', 'result_not_confirmed'],
            'unequip_done': ['completed', 'unequipped']})

    def test_job_names(self):
        self.assertEqual(self.data['jobs'], ['Novice', 'Swordman', 'Archer', 'Thief', None])

    def test_bridge_wires_every_action_and_ack(self):
        bridge = (ROOT/'bridge/openkore/m1_bridge.pl').read_text(encoding='utf-8')
        for needle in ('stat_up|skill_up|equip|unequip', "packet_pre/stats_added", 'packet/skill_update',
                       'packet/equip_item', 'packet/unequip_item', "native eq 'progress'", 'respawn|progress'):
            self.assertIn(needle, bridge)


if __name__ == '__main__':
    unittest.main()
