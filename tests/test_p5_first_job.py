"""Restricted first-job bridge contract; no live server or character changes."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.install_first_job import install
from agent.solo_cycle import SoloCycle
from test_p5_build import snapshot

ROOT = Path(__file__).resolve().parents[1]
PERL = ROOT.parent / 'vendor/strawberry-perl/perl/bin/perl.exe'


class FirstJobContract(unittest.TestCase):
    def test_bridge_validation_and_confirmation(self):
        code = r'''use M1Travel; use JSON::PP;
my $c = {manual_ai=>1,hp=>40,recovering=>0,talking=>0,npc=>{x=>153,y=>193},
 pos=>{x=>153,y=>192},npc_name=>'First Job Changer',map=>'prontera',job_id=>0,job_level=>10,points_skill=>0};
my $a = {type=>'first_job',job=>'Swordman',timeout_s=>40};
my @jobs = qw(Swordman Mage Archer Acolyte Merchant Thief);
print JSON::PP->new->encode({
 valid=>[map { M1Travel::validate_first_job({%$a,job=>$_},$c) } @jobs],
 invalid=>M1Travel::validate_first_job({%$a,job=>'Knight'},$c),
 low=>M1Travel::validate_first_job($a,{%$c,job_level=>9}),
 points=>M1Travel::validate_first_job($a,{%$c,points_skill=>1}),
 wrong_class=>M1Travel::validate_first_job($a,{%$c,job_id=>1}),
 wrong_npc=>M1Travel::validate_first_job($a,{%$c,npc_name=>'Other'}),
 yes=>[M1Travel::first_job_outcome(1,1,1,'close')],
 close=>[M1Travel::first_job_outcome(1,1,undef,'close')],
 wrong=>[M1Travel::first_job_outcome(1,1,2,'close')],
 no_confirm=>[M1Travel::first_job_outcome(0,1,undef,'timeout')],
 early_packet=>[M1Travel::first_job_outcome(0,1,1,'close')]});'''
        result = subprocess.run([str(PERL), '-I' + str(ROOT / 'bridge/lib'), '-e', code],
                                capture_output=True, text=True, timeout=10, check=True)
        data = json.loads(result.stdout)
        self.assertEqual(data['valid'], [None] * 6)
        self.assertEqual(data['invalid'], 'invalid_first_job')
        for key in ('low', 'points', 'wrong_class'):
            self.assertEqual(data[key], 'not_eligible')
        self.assertEqual(data['wrong_npc'], 'wrong_map_or_npc')
        self.assertEqual(data['yes'], ['completed', 'job_changed'])
        for key in ('close', 'wrong', 'early_packet'):
            self.assertEqual(data[key], ['unknown', 'job_change_unconfirmed'])
        self.assertEqual(data['no_confirm'], ['failed', 'timeout'])

    def test_name_resolution_requires_same_actor_and_fresh_response(self):
        code = r'''use M1Travel; use JSON::PP; print JSON::PP->new->encode([
          M1Travel::first_job_name_step(1,undef,1,6),
          M1Travel::first_job_name_step(1,'First Job Changer',2,6),
          M1Travel::first_job_name_step(1,'Other',2,6),
          M1Travel::first_job_name_step(1,undef,6,6),
          M1Travel::first_job_name_step(0,'First Job Changer',2,6)]);'''
        result = subprocess.run([str(PERL), '-I' + str(ROOT / 'bridge/lib'), '-e', code],
                                capture_output=True, text=True, timeout=10, check=True)
        self.assertEqual(json.loads(result.stdout), ['waiting', 'resolved', 'wrong_map_or_npc',
                                                     'npc_name_timeout', 'npc_actor_changed'])

    def test_training_resumes_without_replacing_prior_goal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            c = SoloCycle(path)
            c.state.update(status='complete', reason='confirmed_kill_goal', kills=6, goal_kills=6)
            c.save()
            self.assertTrue(c.train_first_job())
            resumed = SoloCycle(path)
            self.assertFalse(resumed.train_first_job())
            self.assertEqual(resumed.state['previous_goal']['kills'], 6)
            self.assertEqual(resumed.state['goal_kills'], 6)
            self.assertEqual(resumed.state['status'], 'active')
            resumed.block('unknown_effect')
            with self.assertRaises(RuntimeError): resumed.train_first_job()

    def test_first_job_waits_for_level_and_spent_points(self):
        for level, points in ((9, 0), (10, 1)):
            with self.subTest(level=level, points=points), tempfile.TemporaryDirectory() as directory:
                c = SoloCycle(Path(directory) / 'state.json', p5={'build': {'target_class': 'Swordman'},
                    'tables': {'monsters': {}, 'fields': {}}, 'equipment': {}})
                c.progress_action = lambda snap: None
                c.supply = lambda snap: {'go': False}
                c.state['macro_goal'] = 'train_first_job'
                c.state['field']['id'] = 'prt_fild08'
                snap = snapshot(points_skill=points)
                snap.update(executor='openkore_route', recovery='none', hp=40, hp_max=40,
                            map='prt_fild08', position={'x': 100, 'y': 100}, monsters=[],
                            explore_candidates=[{'x': 110, 'y': 100}])
                snap['level']['job'] = level
                with patch('agent.solo_cycle.hunting.viable_targets', return_value=set()):
                    self.assertEqual(c.plan(snap)['type'], 'navigate')
                self.assertEqual(c.state['phase'], 'hunt')

    def test_npc_is_restricted(self):
        text = (ROOT / 'config/npc/first-job-changer.txt').read_text()
        self.assertEqual(text.count('Class != Job_Novice || JobLevel < 10 || SkillPoint != 0'), 2)
        self.assertIn('Swordman:Mage:Archer:Acolyte:Merchant:Thief:Cancel', text)
        self.assertEqual(text.count('jobchange '), 1)
        for forbidden in ('getitem', 'zeny', 'reset'):
            self.assertNotIn(forbidden, text.lower())

    def test_install_idempotent_and_preserves_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'npc/custom').mkdir(parents=True)
            conf = root / 'npc/scripts_custom.conf'
            conf.write_bytes(b'// user config\r\nnpc: npc/custom/m4-pve.txt\r\n')
            source = ROOT / 'config/npc/first-job-changer.txt'
            install(root, source)
            first = conf.read_bytes()
            install(root, source)
            self.assertEqual(conf.read_bytes(), first)
            target = root / 'npc/custom/first-job-changer.txt'
            target.write_bytes(b'user data')
            with self.assertRaises(RuntimeError):
                install(root, source)
            self.assertEqual(target.read_bytes(), b'user data')
            self.assertEqual(conf.read_bytes(), first)

    def test_cycle_routes_then_blocks_uncertain_without_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            cycle = SoloCycle(Path(directory) / 'state.json', p5={'build': {'target_class': 'Swordman'}})
            cycle.progress_action = lambda snap: None
            snap = snapshot()
            snap.update(executor='openkore_route', recovery='none', hp=40, hp_max=40,
                        map='prt_fild08', position={'x': 100, 'y': 100})
            snap['level']['job'] = 10
            travel = cycle.plan(snap)
            self.assertEqual(travel['type'], 'travel')
            self.assertEqual(travel['map'], 'prontera')
            cycle.prepare(travel, 'c1', 's')
            cycle.result({'request_id': 'c1', 'status': 'completed', 'reason': 'arrived'})
            snap.update(map='prontera', position={'x': 153, 'y': 192})
            action = cycle.plan(snap)
            self.assertEqual(action, {'type': 'first_job', 'job': 'Swordman', 'timeout_s': 40})
            cycle.prepare(action, 'c2', 's')
            cycle.result({'request_id': 'c2', 'status': 'unknown', 'reason': 'job_change_unconfirmed'})
            self.assertEqual(cycle.state['status'], 'blocked')
            self.assertEqual(cycle.state['inflight']['request_id'], 'c2')
            self.assertIsNone(cycle.plan(snap))


if __name__ == '__main__':
    unittest.main()
