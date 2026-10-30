import tempfile
import time
import unittest
from pathlib import Path
from agent.memory import Memory
from agent.routine import Routine


class FakeBridge:
    def __init__(self):
        self.session = 'boot:1'
        self.latest = {'session': self.session, 'time_ms': time.time()*1000, 'data': {'connected': True, 'hp': 10, 'map': 'prontera', 'position': {'x': 150, 'y': 180}, 'destination': {'x': 150, 'y': 180}}}
        self.sent = []

    def proposal(self, action, **kwargs):
        self.sent.append((action, kwargs))


class RoutineTests(unittest.TestCase):
    def test_send_failure_stays_unknown_and_capacity_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(Path(directory)/'state.sqlite', 'agent')
            bridge = FakeBridge()
            def broken(*args, **kwargs):
                raise ConnectionError('lost stream')
            bridge.proposal = broken
            routine = Routine(memory, bridge)
            routine.next_at = 0
            routine.tick()
            self.assertEqual(routine.reason, 'send_unknown')
            reopened = Routine(memory, bridge)
            reopened.next_at = 0
            reopened.tick()
            self.assertEqual(reopened.reason, 'pending_unknown')
            self.assertEqual(reopened.state['count'], 1)
            self.assertFalse(any(r['data'].get('status') == 'completed' for r in memory.retrieve()))
            memory.close()

    def test_restart_does_not_resend_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'state.sqlite'
            memory = Memory(path, 'agent')
            bridge = FakeBridge()
            routine = Routine(memory, bridge)
            routine.next_at = 0
            routine.tick()
            self.assertEqual(len(bridge.sent), 1)
            request_id = bridge.sent[0][1]['request_id']
            routine.observe({'agent_id': 'agent', 'id': 'accepted', 'session': bridge.session, 'kind': 'action_result', 'data': {'request_id': request_id, 'status': 'accepted'}})
            memory.close()
            memory = Memory(path, 'agent')
            routine = Routine(memory, bridge)
            routine.next_at = 0
            routine.tick()
            self.assertEqual(len(bridge.sent), 1)
            self.assertEqual(routine.reason, 'pending_accepted')
            routine.observe({'agent_id': 'agent', 'id': 'completed', 'session': bridge.session, 'kind': 'action_result', 'data': {'request_id': request_id, 'status': 'completed'}})
            routine.tick()
            self.assertEqual(len(bridge.sent), 2)
            self.assertNotEqual(bridge.sent[1][1]['request_id'], request_id)
            memory.close()

    def test_stale_and_new_epoch(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(Path(directory)/'state.sqlite', 'agent')
            bridge = FakeBridge()
            routine = Routine(memory, bridge)
            routine.next_at = 0
            bridge.latest['time_ms'] -= 3000
            routine.tick()
            self.assertEqual(bridge.sent, [])
            bridge.latest['time_ms'] = time.time()*1000
            routine.tick()
            bridge.session = bridge.latest['session'] = 'boot:2'
            routine.next_at = 0
            routine.tick()
            self.assertEqual(len(bridge.sent), 2)
            self.assertEqual(routine.state['count'], 1)
            self.assertTrue(any(r['data'].get('reason') == 'epoch_changed' and r['data']['status'] == 'unknown' for r in memory.retrieve()))
            memory.close()


if __name__ == '__main__':
    unittest.main()
