"""Three private minds sharing a single bounded inference scheduler.

Only addressed, perceived chat starts a turn. Replies cannot trigger another
turn. The coordinator never supplies another identity's records to a mind.
"""
import json
import time
from pathlib import Path

from agent.dialogue import Dialogue
from agent.memory import Memory
from inference.m2 import BoundedInference


class Community:
    def __init__(self, root, state, bridges, identities=None, service=None):
        root, state = Path(root), Path(state)
        state.mkdir(parents=True, exist_ok=True)
        self.identities = identities or json.loads((root/'config/m4-identities.json').read_text())
        operating = json.loads((root/'config/m2-operating.json').read_text())
        web = json.loads((root/'config/web-search.json').read_text())
        self.service = service or BoundedInference(operating, operating['model'])
        self.bridges, self.memories, self.dialogues = bridges, {}, {}
        self.last_observation = {}
        for who, profile in self.identities.items():
            memory = Memory(state/(who+'.sqlite'), who)
            self.memories[who] = memory
            self.dialogues[who] = Dialogue(memory, operating, web, self.service, persona=profile['persona'])

    def observe(self, who, event, *, allow_dialogue=True):
        if event['agent_id'] != who:
            raise ValueError('Cross-identity observation')
        memory = self.memories[who]
        if event['kind'] == 'snapshot' and event['data']['connected'] and event['time_ms']-self.last_observation.get(who, 0) >= 30000:
            memory.record(event['id'], 'observation', {'map': event['data']['map'], 'name': event['data']['name'], 'source': event['id']})
            self.last_observation[who] = event['time_ms']
        elif event['kind'] == 'chat' and not event['data'].get('self'):
            data = event['data']
            memory.record(event['id'], 'reported_claim', {'speaker': data['speaker'], 'text': data['text'][:240], 'source': event['id']})
            prefix = 'M4:'+who+':'
            if allow_dialogue and data['text'].startswith(prefix):
                question = data['text'][len(prefix):].strip()
                self.dialogues[who].ask(question, event['session'], 'poring' if question == 'web poring' else None)
        elif event['kind'] == 'action_result':
            memory.record(event['id'], 'action', event['data'])

    def poll(self, who):
        reply = self.dialogues[who].poll(self.bridges[who].session)
        if reply:
            self.memories[who].record(str(time.time_ns()), 'dialogue', reply)
        return reply

    def close(self):
        for dialogue in self.dialogues.values():
            dialogue.close()
        self.service.close()
        for memory in self.memories.values():
            memory.close()
