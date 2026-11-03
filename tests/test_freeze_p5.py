"""Freezing P5: the in-flight action is reconciled only from its recorded final result."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts import freeze_p5

INFLIGHT = {'action': {'type': 'travel', 'map': 'prt_fild04', 'x': 27, 'y': 124}, 'request_id': 'c_177', 'session': 's:2'}


def setup(base, events):
    (base/'cycle').mkdir(parents=True)
    (base/'cycle/state.json').write_text(json.dumps({'status': 'blocked', 'reason': 'travel:failed/died', 'kills': 175,
                                                     'inflight': INFLIGHT, 'reconciliations': []}))
    (base/'cycle/status.json').write_text(json.dumps({'status': 'blocked', 'inflight': INFLIGHT, 'running': False}))
    (base/'cycle/events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    (base/'processes.json').write_text(json.dumps({'p5-novice': {'pid': 999999999, 'exe': 'perl.exe'}}))


class Freeze(unittest.TestCase):
    def test_reconciles_from_recorded_result_and_keeps_events(self):
        events = [{'time': 1.0, 'kind': 'action_result', 'data': {'request_id': 'c_177', 'status': 'accepted'}},
                  {'time': 2.0, 'kind': 'action_result', 'data': {'request_id': 'c_177', 'status': 'failed', 'reason': 'died'}}]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            setup(base, events)
            before = (base/'cycle/events.jsonl').read_text()
            record = freeze_p5.freeze(base, now=5)
            state = json.loads((base/'cycle/state.json').read_text())
            self.assertEqual((state['status'], state['reason'], state['inflight']), ('frozen', 'migrated_to_r1', None))
            r = state['reconciliations'][-1]
            self.assertEqual((r['request_id'], r['status'], r['reason'], r['resent']), ('c_177', 'failed', 'died', False))
            self.assertEqual((base/'cycle/events.jsonl').read_text(), before)
            self.assertFalse((base/'processes.json').exists())
            self.assertTrue((base/'evidence/frozen/processes-stale.json').exists())
            self.assertEqual(freeze_p5.freeze(base), record)  # idempotent

    def test_refuses_without_a_recorded_final_result(self):
        events = [{'time': 1.0, 'kind': 'action_result', 'data': {'request_id': 'c_177', 'status': 'accepted'}}]
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            setup(base, events)
            with self.assertRaises(RuntimeError):
                freeze_p5.freeze(base)
            self.assertEqual(json.loads((base/'cycle/state.json').read_text())['inflight'], INFLIGHT)
            self.assertFalse((base/'FROZEN.json').exists())


if __name__ == '__main__':
    unittest.main()
