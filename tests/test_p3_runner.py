"""Runner integration with a controlled bridge; no game services are used."""
import copy
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from agent.solo_cycle import SoloCycle
from scripts.run_p2_cycle import Runner
from test_p2_cycle import FakeBridge, snapshot


class ControlledBridge(FakeBridge):
    def __init__(self, snap, session='boot:1'):
        super().__init__(snap, session=session)
        self.latest['session'] = session
        self.freeze = True
        self.disconnect = False

    def poll(self, timeout):
        if self.disconnect:
            raise ConnectionError('simulated disconnect')
        time.sleep(.001)

    def send(self, query):
        self.queries.append(copy.deepcopy(query))

    def proposal(self, action, **kwargs):
        self.proposals.append((copy.deepcopy(action), kwargs['request_id']))

    def emit(self, kind, data, time_ms=None):
        self.events.append(dict(kind=kind, data=data, time_ms=time_ms or int(time.time()*1000)))


class RunnerInterruptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.path = self.directory/'state.json'
        self.cycle = SoloCycle(self.path)
        no_mobs = snapshot(monsters=[], explore_candidates=[{'x':220,'y':250}])
        action = self.cycle.plan(no_mobs)
        self.cycle.prepare(action, 'c_1', 'boot:1')
        self.snap = snapshot(native_task={'id':'c_1','kind':'navigation'},
            monsters=[{'id':'01000000','x':171,'y':250,'eligible':1}])
        self.bridge = ControlledBridge(self.snap)

    def run_once(self, bridge=None, cycle=None):
        bridge, cycle = bridge or self.bridge, cycle or self.cycle
        bridge.events.insert(0, {'kind':'ready','data':{'next_serial':bridge.next_serial}})
        runner = Runner(cycle, bridge, self.directory)
        runner.inventory_session, runner.inventory_ready_after = bridge.session, 0
        with patch.object(runner, 'resource_guard'):
            return runner.run(.025, max_actions=8)

    def result(self, rid, status, reason, stamp=None):
        self.bridge.emit('action_result', dict(request_id=rid, status=status, reason=reason), stamp)

    def test_cancel_once_reverse_results_then_fresh_snapshot(self):
        self.run_once()
        self.assertEqual(self.bridge.proposals, [({'type':'cancel','target':'c_1'},'c_10')])
        self.run_once()
        self.assertEqual(len(self.bridge.proposals), 1)
        stamp = int(time.time()*1000)
        self.result('c_10', 'completed', 'navigation_cancelled', stamp)
        self.run_once()
        self.assertEqual(len(self.bridge.proposals), 1)
        self.assertIsNotNone(self.cycle.state['inflight'])
        self.result('c_1', 'cancelled', 'cancel_requested', stamp+1)
        self.run_once()
        self.assertEqual(len(self.bridge.proposals), 1)  # snapshot predates both results
        self.assertIsNone(self.cycle.state['inflight'])
        self.bridge.latest['time_ms'] = stamp+2
        self.bridge.latest['data'] = snapshot(monsters=[{'id':'01000000','x':171,'y':250,'eligible':1}])
        self.run_once()
        self.assertEqual([p[0]['type'] for p in self.bridge.proposals], ['cancel','attack'])

    def test_restart_with_one_confirmation_queries_only_missing(self):
        self.run_once()
        self.result('c_10', 'completed', 'navigation_cancelled')
        self.run_once()
        restarted = SoloCycle(self.path)
        bridge = ControlledBridge(self.snap)
        self.run_once(bridge, restarted)
        self.assertEqual(bridge.proposals, [])
        self.assertEqual([q['request_id'] for q in bridge.queries], ['c_1'])
        self.assertEqual(list(restarted.state['inflight']['cancel']['results']), ['c_10'])

    def test_disconnect_new_session_and_unavailable_never_replay(self):
        self.run_once()
        self.bridge.disconnect = True
        with self.assertRaises(ConnectionError):
            self.run_once()
        saved = SoloCycle(self.path)
        self.assertIsNotNone(saved.state['inflight']['cancel'])
        self.assertEqual(len(self.bridge.proposals), 1)
        for mode in ('new_session', 'unavailable'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/'state.json'
                path.write_text(self.path.read_text(encoding='utf-8'), encoding='utf-8')
                cycle = SoloCycle(path)
                bridge = ControlledBridge(self.snap, 'new:1' if mode == 'new_session' else 'boot:1')
                if mode == 'unavailable':
                    bridge.emit('request_status', dict(request_id='c_1', session='boot:1', available=0))
                self.run_once(bridge, cycle)
                self.assertEqual(cycle.state['status'], 'blocked')
                self.assertIsNotNone(cycle.state['inflight'])
                self.assertEqual(bridge.proposals, [])

    def test_arrival_race_blocks_conservatively(self):
        self.run_once()
        self.result('c_1', 'completed', 'arrived')
        self.result('c_10', 'rejected', 'no_matching_task')
        self.run_once()
        self.assertEqual(self.cycle.state['status'], 'blocked')
        self.assertEqual(self.cycle.state['reason'], 'exploration_cancel_unconfirmed')
        self.assertIsNotNone(self.cycle.state['inflight'])
        self.assertEqual(len(self.bridge.proposals), 1)

    def test_other_routes_recovery_and_stale_snapshot_do_not_cancel(self):
        for mode in ('approach', 'travel', 'recovery', 'stale'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/'state.json'
                path.write_text(self.path.read_text(encoding='utf-8'), encoding='utf-8')
                cycle = SoloCycle(path)
                snap = copy.deepcopy(self.snap)
                if mode in ('approach', 'travel'):
                    cycle.state['inflight'].pop('exploration')
                    if mode == 'travel': cycle.state['inflight']['action']['type'] = 'travel'
                    cycle.save()
                if mode == 'recovery': snap['recovery'] = 'rest'
                bridge = ControlledBridge(snap)
                if mode == 'stale': bridge.latest['time_ms'] -= 3000
                self.run_once(bridge, cycle)
                self.assertEqual(bridge.proposals, [])
                self.assertIsNone(cycle.state['inflight'].get('cancel'))


if __name__ == '__main__':
    unittest.main()
