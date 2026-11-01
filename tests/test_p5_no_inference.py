import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import run_p2_cycle
from scripts import run_p5_background


class NoInferenceTests(unittest.TestCase):
    def test_cleanup_requires_same_session_idle_and_no_pending_request(self):
        snap = {'name': 'Nilo', 'connected': True, 'recovery': 'none', 'native_task': None,
                'ai_queue': [], 'position': {'x': 10, 'y': 10}}
        def run(ready_data, second=None):
            events = [{'kind': 'ready', 'data': ready_data, 'session': 's'},
                      {'kind': 'snapshot', 'data': snap, 'session': 's', 'time_ms': 1000},
                      {'kind': 'snapshot', 'data': second or snap, 'session': 's', 'time_ms': 2000}]
            class FakeBridge:
                def __init__(self, config): self.events = events
                def poll(self, delay): pass
                def drain(self): result, self.events = self.events, []; return result
                def close(self): pass
            with patch.object(run_p5_background, 'Bridge', FakeBridge):
                return run_p5_background.idle(Path('unused'))
        self.assertTrue(run({'pending_request_id': None}))
        self.assertFalse(run({'pending_request_id': 'c_1'}))
        self.assertFalse(run({}))
        self.assertFalse(run({'pending_request_id': None}, {**snap, 'native_task': {'id': 'c_1'}}))

    def test_run_constructs_no_planner_or_inference_service(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / 'p5'
            (base / 'cycle').mkdir(parents=True)
            (base / 'identity.json').write_text(json.dumps({'name': 'Nilo'}))
            (base / 'cycle/build.json').write_text(json.dumps({'identity': 'Nilo', 'build_id': 'novice-swordman'}))
            lesson = SimpleNamespace(state={'status': 'complete', 'destination': {'job': 'Swordsman'}})
            cycle = SimpleNamespace(state={'status': 'active', 'field': {'id': 'prt_fild08'},
                                           'return_to': {'map': 'prt_fild08'}})
            cycle.train_first_job = lambda: None
            seen = []
            def runner(*args, **kwargs):
                seen.append((args, kwargs))
                return SimpleNamespace(run=lambda *a: {'inference_calls': 0})
            args = ['run_p2_cycle.py', 'run', '--runtime', directory, '--agent', 'p5', '--p5',
                    '--no-inference', '--train-first-job', '--seconds', '10', '--max-actions', '1']
            with patch.object(sys, 'argv', args), patch.object(run_p2_cycle, 'Tutorial', return_value=lesson), \
                 patch.object(run_p2_cycle, 'SoloCycle', return_value=cycle), \
                 patch.object(run_p2_cycle, 'Bridge', return_value=object()), \
                 patch.object(run_p2_cycle, 'Runner', side_effect=runner), \
                 patch.object(run_p2_cycle, 'P5Planning', side_effect=AssertionError('planner constructed')), \
                 patch.object(run_p2_cycle, 'GoalPlanner', side_effect=AssertionError('goal planner constructed')), \
                 patch.object(run_p2_cycle, 'TutorialPlanning', side_effect=AssertionError('tutorial planner constructed')), \
                 patch('inference.roles.build_role', side_effect=AssertionError('inference service constructed')):
                run_p2_cycle.main()
            self.assertEqual(len(seen), 1)
            self.assertIsNone(seen[0][0][3])  # Goal planner
            self.assertIsNone(seen[0][0][5])  # P5 planner

    def test_no_inference_disallows_intent(self):
        args = ['run_p2_cycle.py', 'run', '--runtime', '.', '--agent', 'p5', '--p5',
                '--no-inference', '--intent', 'hello']
        with patch.object(sys, 'argv', args), self.assertRaises(SystemExit):
            run_p2_cycle.main()


if __name__ == '__main__':
    unittest.main()
