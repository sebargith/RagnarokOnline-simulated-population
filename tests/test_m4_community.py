import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import Future
from types import SimpleNamespace

from agent.community import Community

ROOT = Path(__file__).resolve().parents[1]


class Service:
    def __init__(self):
        self.calls = []

    def submit(self, who, messages, *args, **kwargs):
        self.calls.append((who, messages))
        return Future()

    def close(self):
        pass


class CommunityTests(unittest.TestCase):
    def test_private_fact_restart_and_directed_turns(self):
        with tempfile.TemporaryDirectory() as folder:
            service = Service()
            bridges = {who: SimpleNamespace(session='epoch') for who in ('agent', 'peer', 'third')}
            community = Community(ROOT, folder, bridges, service=service)
            community.memories['agent'].record('private', 'observation', {'test_fact': 'blue pebble'})
            event = {'agent_id': 'peer', 'id': 'e1', 'session': 'epoch', 'kind': 'chat', 'data': {'speaker': 'M4 Alden', 'text': 'Hello', 'self': 0}}
            community.observe('peer', event)
            self.assertEqual(service.calls, [])
            event['data']['text'] = 'M4:peer:What is my secret?'
            community.observe('peer', event)
            self.assertEqual(len(service.calls), 1)
            self.assertNotIn('blue pebble', json.dumps(service.calls[0]))
            community.observe('peer', event)
            self.assertEqual(len(service.calls), 1)  # outstanding admission bounded
            with self.assertRaises(ValueError):
                community.observe('third', event)
            community.close()
            community = Community(ROOT, folder, bridges, service=Service())
            self.assertIn('blue pebble', json.dumps(community.memories['agent'].retrieve()))
            self.assertNotIn('blue pebble', json.dumps(community.memories['third'].retrieve()))
            self.assertNotEqual(community.dialogues['agent'].persona, community.dialogues['third'].persona)
            community.close()
