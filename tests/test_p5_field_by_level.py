"""P5.5: during train_first_job the planner re-decides the hunting field when one is
due (level up, unsafe field, periodic review). One request at a time, hunting goes
on while it is pending, and a failed or late answer keeps the field."""
from concurrent.futures import Future
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent.goal_planner import FieldPlanner
from agent.solo_cycle import SoloCycle
from scripts import run_p2_cycle
from scripts.run_p2_cycle import P5Planning, Runner
from test_p3_runner import ControlledBridge
from test_p5_build import Service
from test_p5_hunting import BUILDS, EQUIPMENT, TABLES, tarin


class Pending:
    """A planner service whose answer never arrives (or arrives when set)."""
    def __init__(self):
        self.future, self.calls = Future(), []

    def submit(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.future


class FieldByLevelTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        (self.directory/'build.json').write_text(json.dumps({'build_id': 'novice-swordman'}), encoding='utf-8')
        p5 = {'tables': TABLES, 'equipment': EQUIPMENT, 'build': BUILDS['novice-swordman']}
        self.cycle = SoloCycle(self.directory/'state.json', 20, p5, 'Tarin')
        self.cycle.state['macro_goal'] = 'train_first_job'
        # Field chosen earlier at base 5, like Nilo's decision before training.
        self.cycle.set_field('prt_fild08', None, {'decision': 'change', 'field_id': 'prt_fild08'}, 5)

    def runner(self, service, snap, planner_deadline=None):
        planning = P5Planning(self.cycle, service, self.directory)
        if planner_deadline:
            planning.field_planner.deadline_s = planner_deadline
        bridge = ControlledBridge(snap)
        bridge.events.insert(0, {'kind': 'ready', 'data': {'next_serial': bridge.next_serial}})
        runner = Runner(self.cycle, bridge, self.directory, p5=planning)
        runner.inventory_session, runner.inventory_ready_after = bridge.session, 0
        self.addCleanup(runner.log.close)
        return runner, bridge

    def drive(self, runner, seconds=.05, actions=1):
        with patch.object(runner, 'resource_guard'):
            return runner.run(seconds, max_actions=actions)

    def test_same_level_asks_nothing(self):
        service = Service({'field_id': 'prt_fild06', 'reason': 'x'})
        runner, bridge = self.runner(service, tarin())
        out = self.drive(runner)
        self.assertEqual((out['inference_calls'], service.calls), (0, []))
        self.assertEqual(bridge.proposals[0][0]['type'], 'navigate')  # Hunting goes on.

    def test_level_up_keep_records_trigger_facts_and_server(self):
        service = Service({'field_id': 'prt_fild08', 'reason': 'Still the best EXP per hit.'})
        runner, _ = self.runner(service, tarin(level={'base': 6, 'job': 4}))
        out = self.drive(runner)
        decision = self.cycle.state['field_decisions'][-1]
        self.assertEqual((decision['trigger'], decision['decision'], decision['field_id'], decision['previous']),
                         ('level_up', 'keep', 'prt_fild08', 'prt_fild08'))
        self.assertEqual((decision['served_by'], decision['reason']), ('groq-gpt-oss', 'Still the best EXP per hit.'))
        self.assertEqual(decision['facts']['level'], {'base': 6, 'job': 4})
        self.assertEqual((decision['facts']['map'], decision['facts']['build']), ('prt_fild08', 'novice-swordman'))
        self.assertIn('hp_max', decision['facts'])
        self.assertIn('field_history', decision['facts'])
        self.assertTrue(decision['options'])
        self.assertEqual((self.cycle.state['field']['decided_level'], out['inference_calls']), (6, 1))
        self.assertIsNone(self.cycle.field_due(tarin(level={'base': 6, 'job': 4})))

    def test_level_up_change_travels_to_new_field(self):
        service = Service({'field_id': 'prt_fild06', 'reason': 'More Lunatics, low danger.'})
        runner, bridge = self.runner(service, tarin(level={'base': 6, 'job': 4}))
        self.drive(runner)
        decision = self.cycle.state['field_decisions'][-1]
        self.assertEqual((decision['trigger'], decision['decision'], decision['field_id']), ('level_up', 'change', 'prt_fild06'))
        self.assertEqual(bridge.proposals[0][0], {'type': 'travel', 'map': 'prt_fild06', 'x': 33, 'y': 185, 'timeout_s': 174})

    def test_pending_request_never_repeats_and_hunting_continues(self):
        service = Pending()
        runner, bridge = self.runner(service, tarin(level={'base': 6, 'job': 4}))
        out = self.drive(runner, seconds=.3, actions=1)
        self.assertEqual(len(service.calls), 1)
        self.assertEqual(out['inference_calls'], 1)
        self.assertEqual(len(bridge.proposals), 1)  # A game action went out while the planner was pending.
        self.assertEqual(self.cycle.state['field']['decided_level'], 5)  # Nothing applied yet.

    def test_late_answer_keeps_field_without_blocking_or_asking_again(self):
        service = Pending()
        runner, _ = self.runner(service, tarin(level={'base': 6, 'job': 4}), planner_deadline=.05)
        runner.p5_tick()
        time.sleep(.06)
        for _ in range(3):
            runner.p5_tick()
        decision = self.cycle.state['field_decisions'][-1]
        self.assertEqual((decision['decision'], decision['field_id'], decision['reason'], decision['trigger']),
                         ('kept_on_failure', 'prt_fild08', 'planning_deadline', 'level_up'))
        self.assertEqual(self.cycle.state['status'], 'active')
        self.assertEqual(self.cycle.state['field']['decided_level'], 6)
        self.assertEqual(len(service.calls), 1)

    def test_failed_inference_keeps_field(self):
        service = Service(error='RoleUnavailable')
        runner, bridge = self.runner(service, tarin(level={'base': 6, 'job': 4}))
        self.drive(runner)
        decision = self.cycle.state['field_decisions'][-1]
        self.assertEqual((decision['decision'], decision['reason']), ('kept_on_failure', 'invalid_or_failed_inference'))
        self.assertEqual(bridge.proposals[0][0]['type'], 'navigate')

    def test_request_error_backs_off(self):
        runner, _ = self.runner(Service({'field_id': 'prt_fild08', 'reason': 'ok'}), tarin(level={'base': 6, 'job': 4}))
        with patch.object(FieldPlanner, 'request', side_effect=RuntimeError('quota')) as request:
            for _ in range(5):
                runner.p5_tick()
        self.assertEqual(request.call_count, 1)
        self.assertEqual(self.cycle.state['status'], 'active')

    def test_not_applied_with_action_in_flight(self):
        service = Pending()
        runner, _ = self.runner(service, tarin(level={'base': 6, 'job': 4}))
        runner.p5_tick()  # Request sent; the cycle then starts an attack.
        self.cycle.state['inflight'] = {'action': {'type': 'attack'}, 'request_id': 'c_9', 'session': 'boot:1'}
        service.future.set_result({'content': json.dumps({'field_id': 'prt_fild06', 'reason': 'x'}),
                                   'served_by': 'gemma4-12b', 'degraded': True})
        runner.p5_tick()
        self.assertIsNotNone(runner.p5.ready)
        self.assertEqual(self.cycle.state['field']['id'], 'prt_fild08')
        self.cycle.state['inflight'] = None
        runner.p5_tick()
        decision = self.cycle.state['field_decisions'][-1]
        self.assertEqual((self.cycle.state['field']['id'], len(service.calls)), ('prt_fild06', 1))
        self.assertEqual((decision['served_by'], decision['degraded']), ('gemma4-12b', True))


class TrainingModeTests(unittest.TestCase):
    def test_train_first_job_without_no_inference_builds_field_planner(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)/'p5'
            (base/'cycle').mkdir(parents=True)
            (base/'identity.json').write_text(json.dumps({'name': 'Nilo'}))
            (base/'cycle/build.json').write_text(json.dumps({'identity': 'Nilo', 'build_id': 'novice-swordman'}))
            lesson = SimpleNamespace(state={'status': 'complete', 'destination': {'job': 'Swordsman'}})
            cycle = SimpleNamespace(state={'status': 'active', 'field': {'id': 'prt_fild08'},
                                           'return_to': {'map': 'prt_fild08'}})
            trained = []
            cycle.train_first_job = lambda: trained.append(True)
            service = SimpleNamespace(close=lambda: None)
            planning, seen = object(), []
            def runner(*args, **kwargs):
                seen.append(args)
                return SimpleNamespace(run=lambda *a: {'inference_calls': 0})
            args = ['run_p2_cycle.py', 'run', '--runtime', directory, '--agent', 'p5', '--p5',
                    '--train-first-job', '--seconds', '10', '--max-actions', '1']
            with patch.object(sys, 'argv', args), patch.object(run_p2_cycle, 'Tutorial', return_value=lesson), \
                 patch.object(run_p2_cycle, 'SoloCycle', return_value=cycle), \
                 patch.object(run_p2_cycle, 'Bridge', return_value=object()), \
                 patch.object(run_p2_cycle, 'Runner', side_effect=runner), \
                 patch.object(run_p2_cycle, 'P5Planning', return_value=planning) as p5_planning, \
                 patch('inference.roles.build_role', return_value=service) as role:
                run_p2_cycle.main()
            role.assert_called_once_with('planner')
            self.assertEqual(p5_planning.call_args[0][3], 'Swordman')
            self.assertIs(seen[0][5], planning)
            self.assertEqual(trained, [True])

    def test_training_requires_saved_field(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)/'p5'
            (base/'cycle').mkdir(parents=True)
            (base/'identity.json').write_text(json.dumps({'name': 'Nilo'}))
            (base/'cycle/build.json').write_text(json.dumps({'identity': 'Nilo', 'build_id': 'novice-swordman'}))
            lesson = SimpleNamespace(state={'status': 'complete', 'destination': {'job': 'Swordsman'}})
            cycle = SimpleNamespace(state={'status': 'active', 'field': {'id': None}, 'return_to': None})
            args = ['run_p2_cycle.py', 'run', '--runtime', directory, '--agent', 'p5', '--p5',
                    '--train-first-job', '--seconds', '10']
            with patch.object(sys, 'argv', args), patch.object(run_p2_cycle, 'Tutorial', return_value=lesson), \
                 patch.object(run_p2_cycle, 'SoloCycle', return_value=cycle), \
                 patch('inference.roles.build_role', side_effect=AssertionError('service built')), \
                 self.assertRaises(RuntimeError):
                run_p2_cycle.main()

    def test_train_first_job_rejects_intent(self):
        args = ['run_p2_cycle.py', 'run', '--runtime', '.', '--agent', 'p5', '--p5', '--train-first-job', '--intent', 'hi']
        with patch.object(sys, 'argv', args), self.assertRaises(SystemExit):
            run_p2_cycle.main()


if __name__ == '__main__':
    unittest.main()
