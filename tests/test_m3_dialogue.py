from concurrent.futures import Future
import tempfile
from pathlib import Path
import unittest
from agent.dialogue import Dialogue, PUBLIC_TOPICS, validate_reply
from agent.memory import Memory
from agent.routine import Routine
from test_m3_routine import FakeBridge


class Service:
    def submit(self, *args, **kwargs):
        self.args = args
        self.future = Future()
        return self.future

    def close(self):
        pass


class DialogueTests(unittest.TestCase):
    def test_pending_or_failed_inference_does_not_block_movement(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(Path(directory)/'memory.sqlite', 'agent')
            service = Service()
            dialogue = Dialogue(memory, {}, {}, service=service)
            bridge = FakeBridge()
            routine = Routine(memory, bridge)
            dialogue.ask('hello', bridge.session)
            routine.next_at = 0
            routine.tick()
            self.assertEqual(len(bridge.sent), 1)
            self.assertIsNone(dialogue.poll(bridge.session))
            service.future.set_result({'error': 'TimeoutError'})
            self.assertIn('error', dialogue.poll(bridge.session))
            request_id = bridge.sent[0][1]['request_id']
            routine.observe({'agent_id': 'agent', 'id': 'ack', 'session': bridge.session, 'kind': 'action_result', 'data': {'request_id': request_id, 'status': 'completed'}})
            routine.next_at = 0
            routine.tick()
            self.assertEqual(len(bridge.sent), 2)
            dialogue.close()
            memory.close()

    def test_invalid_output_is_rejected(self):
        for value in ('hello', '{}', '{"text":"@warp"}', '{"text":"ok","action":"move"}', '{"text":"line\\nnext"}'):
            with self.assertRaises(ValueError):
                validate_reply(value)

    def test_identity_context_stale_fallback_and_single_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(Path(directory)/'memory.sqlite', 'agent')
            service = Service()
            dialogue = Dialogue(memory, {}, {}, service=service)
            self.assertTrue(dialogue.ask('hello', 'boot:1'))
            self.assertFalse(dialogue.ask('second', 'boot:1'))
            service.future.set_result({'content': '{"text":"Hello!"}', 'done_reason': 'stop'})
            self.assertEqual(dialogue.poll('boot:2')['error'], 'ValueError')
            dialogue.last_admission = -100
            dialogue.ask('private question', 'boot:2')
            service.future.set_result({'error': 'timeout'})
            self.assertIn("don't know", dialogue.poll('boot:2')['text'])
            dialogue.close()
            memory.close()

    def test_public_search_worker_receives_no_private_context(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(Path(directory)/'memory.sqlite', 'agent')
            memory.record('private', 'reported_claim', {'text': 'secret private marker'})
            calls = []
            def search(query, config):
                calls.append(query)
                raise RuntimeError('search down')
            dialogue = Dialogue(memory, {}, {}, service=Service(), search=search)
            dialogue.ask('secret private marker', 'boot:1', topic='poring')
            try:
                dialogue.future.result(timeout=1)
            except RuntimeError:
                pass
            reply = dialogue.poll('boot:1')
            self.assertEqual(calls, [PUBLIC_TOPICS['poring']])
            self.assertEqual(reply['error'], 'RuntimeError')
            dialogue.close()
            memory.close()


if __name__ == '__main__':
    unittest.main()
