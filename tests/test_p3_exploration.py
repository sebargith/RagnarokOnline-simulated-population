import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from agent.solo_cycle import SoloCycle
from test_p2_cycle import snapshot


ROOT = Path(__file__).resolve().parents[1]


class ExplorationTests(unittest.TestCase):
    def test_client_candidates_respect_bounds_walls_and_clear_path(self):
        perl = ROOT.parent/'vendor/strawberry-perl/perl/bin/perl.exe'
        script = r'''
use JSON::PP; use M1Explore;
my $p = {x=>50,y=>50};
my $c = M1Explore::candidates($p, 100, 100, sub { $_[0] != 70 },
    sub { $_[1]{y} <= 50 });
my $none = M1Explore::candidates($p, 100, 100, sub { 0 }, sub { die 'wall accepted' });
print JSON::PP->new->encode({c=>$c,none=>$none});
'''
        result = subprocess.run([str(perl), '-I'+str(ROOT/'bridge/lib'), '-e', script],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data['c'])
        self.assertEqual(data['none'], [])
        for p in data['c']:
            self.assertTrue(8 <= p['x'] < 92 and 8 <= p['y'] < 92)
            self.assertNotEqual(p['x'], 70)
            self.assertLessEqual(p['y'], 50)

    def test_coverage_persists_and_monster_takes_priority(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'state.json'
            cycle = SoloCycle(path, 8)
            points = [{'x':220,'y':250}, {'x':120,'y':250}, {'x':170,'y':300}]
            snap = snapshot(monsters=[], explore_candidates=points)
            first = cycle.plan(snap, now=100)
            cycle.prepare(first, 'c_1', 'boot:1', now=100)
            cycle.result({'request_id':'c_1','status':'completed','reason':'arrived'}, now=101)
            cycle = SoloCycle(path)
            second = cycle.plan(snap, now=102)
            self.assertNotEqual((first['x'], first['y']), (second['x'], second['y']))
            snap['monsters'] = [{'id':'01000000','x':171,'y':250}]
            self.assertEqual(cycle.plan(snap, now=103)['type'], 'attack')
            self.assertEqual(cycle.state['kills'], 0)

    def test_missing_empty_and_avoided_candidates_fail_closed(self):
        for candidates, reason in [(None, 'exploration_candidates_unavailable'),
                                   ([], 'exploration_no_reachable_candidate')]:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as folder:
                cycle = SoloCycle(Path(folder)/'state.json')
                self.assertIsNone(cycle.plan(snapshot(monsters=[], explore_candidates=candidates)))
                self.assertEqual(cycle.state['reason'], reason)
        with tempfile.TemporaryDirectory() as folder:
            cycle = SoloCycle(Path(folder)/'state.json')
            cycle.state['avoid_route'] = {'map':'prt_fild08','x':220,'y':250,'until':200}
            self.assertIsNone(cycle.plan(snapshot(monsters=[], explore_candidates=[{'x':220,'y':250}]), now=100))
            self.assertEqual(cycle.state['reason'], 'exploration_no_reachable_candidate')

    def test_uncertain_exploration_survives_reload_without_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'state.json'
            cycle = SoloCycle(path)
            action = cycle.plan(snapshot(monsters=[], explore_candidates=[{'x':220,'y':250}]), now=100)
            cycle.prepare(action, 'c_1', 'boot:1', now=100)
            restarted = SoloCycle(path)
            self.assertIsNone(restarted.plan(snapshot(monsters=[], explore_candidates=[{'x':120,'y':250}])))
            self.assertEqual(restarted.state['inflight']['action'], action)
            self.assertEqual(restarted.state['kills'], 0)

    def test_interrupt_requires_confirmations_and_fresh_replan(self):
        with tempfile.TemporaryDirectory() as folder:
            cycle = SoloCycle(Path(folder)/'state.json')
            action = cycle.plan(snapshot(monsters=[], explore_candidates=[{'x':220,'y':250}]), now=100)
            cycle.prepare(action, 'c_1', 'boot:1', now=100)
            seen = snapshot(native_task={'id':'c_1','kind':'navigation'},
                monsters=[{'id':'01000000','x':171,'y':250,'eligible':1}])
            self.assertTrue(cycle.interruptible(seen, now=101))
            cycle.prepare_cancel('c_2')
            cycle.cancel_result({'request_id':'c_1','status':'cancelled','reason':'cancel_requested'}, 2000)
            self.assertIsNotNone(cycle.state['inflight'])
            cycle.cancel_result({'request_id':'c_2','status':'completed','reason':'navigation_cancelled'}, 2100)
            self.assertIsNone(cycle.state['inflight'])
            self.assertEqual(cycle.state['observe_after'], 2100)
            self.assertEqual(cycle.state['kills'], 0)
            self.assertEqual(cycle.plan(snapshot(monsters=[], explore_candidates=[{'x':120,'y':250}]), now=102)['type'], 'navigate')

    def test_interrupt_excludes_ineligible_recovery_and_other_routes(self):
        with tempfile.TemporaryDirectory() as folder:
            cycle = SoloCycle(Path(folder)/'state.json')
            a = cycle.plan(snapshot(monsters=[], explore_candidates=[{'x':220,'y':250}]), now=100)
            cycle.prepare(a, 'c_1', 'boot:1', now=100)
            base = snapshot(native_task={'id':'c_1','kind':'navigation'}, monsters=[{'id':'01000000','x':171,'y':250,'eligible':1}])
            for changes in ({'recovery':'rest'}, {'hp':20}, {'monsters':[{'id':'01000000','x':171,'y':250,'eligible':0}]}, {'native_task':None}):
                self.assertFalse(cycle.interruptible({**base, **changes}, now=101))
            cycle.state['inflight'].pop('exploration')
            self.assertFalse(cycle.interruptible(base, now=101))

    def test_uncertain_cancel_stays_blocked_and_not_replayed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'state.json'
            cycle = SoloCycle(path)
            a = cycle.plan(snapshot(monsters=[], explore_candidates=[{'x':220,'y':250}]), now=100)
            cycle.prepare(a, 'c_1', 'boot:1', now=100)
            cycle.prepare_cancel('c_2')
            cycle = SoloCycle(path)
            self.assertFalse(cycle.interruptible(snapshot(), now=101))
            cycle.cancel_result({'request_id':'c_2','status':'unknown','reason':'lost'}, 2000)
            self.assertEqual(cycle.state['status'], 'blocked')
            self.assertIsNotNone(cycle.state['inflight'])


if __name__ == '__main__':
    unittest.main()
