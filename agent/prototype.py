"""Bounded deterministic M4 scenario driver. Inference can only propose dialogue."""
from collections import deque
import json
from pathlib import Path
import subprocess
import time
import uuid

from agent.community import Community
from agent.trade import TradeLedger, balances, server_balances
from bridge.client import Bridge
from scripts.bench_m2 import ram_sample


class Prototype:
    def __init__(self, root, runtime, evidence):
        self.root, self.runtime, self.evidence = Path(root), Path(runtime), Path(evidence)
        self.bridges = {who: Bridge(self.runtime/'m4/openkore'/who/'bridge.json') for who in ('agent', 'peer', 'third')}
        self.community = Community(root, self.runtime/'m4/state', self.bridges)
        self.events = deque(maxlen=2048)
        self.results, self.resources = {}, []
        self.last_send = {who: 0 for who in self.bridges}
        self.last_resource = -10
        self.started = time.monotonic()
        self.raw = (self.evidence/'events.jsonl').open('w', encoding='utf-8')
        self.event_count = 0
        self.replies = []
        for memory in self.community.memories.values():
            memory.db.execute('CREATE TABLE IF NOT EXISTS intents(id TEXT PRIMARY KEY, session TEXT, action TEXT, status TEXT)')
            memory.db.commit()

    def pump(self, seconds=.1):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            for who, bridge in self.bridges.items():
                for event in bridge.poll(.01):
                    self.event_count += 1
                    if self.event_count > 12000:
                        raise RuntimeError('Evidence/event budget exhausted')
                    self.raw.write(json.dumps(event)+'\n')
                    self.events.append(event)
                    self.community.observe(who, event)
                    if event['kind'] == 'action_result':
                        result = event['data']
                        self.results[result['request_id']] = result
                        db = self.community.memories[who].db
                        db.execute('UPDATE intents SET status=? WHERE id=?', (result['status'], result['request_id']))
                        db.commit()
                bridge.drain()
                reply = self.community.poll(who)
                if reply:
                    self.replies.append({'who': who, **reply})
            now = time.monotonic()
            if now-self.last_resource >= 5:
                sample = {'elapsed_s': now-self.started, **ram_sample(set())}
                gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
                sample['gpu_used_mib'] = int(gpu.strip())
                self.resources.append(sample)
                self.last_resource = now
                if sample['ram_available'] < 2*1024**3 or sample['gpu_used_mib'] > 14336:
                    raise RuntimeError('Unchanged M2 resource budget exceeded')

    def wait(self, predicate, timeout=10):
        end = time.monotonic()+timeout
        while time.monotonic() < end:
            self.pump()
            if predicate():
                return
        raise TimeoutError('Scenario condition timed out; no automatic action retry')

    def ready(self):
        self.wait(lambda: all(b.latest and b.latest['data']['connected'] and b.latest['data'].get('inventory_ready') for b in self.bridges.values()), 45)
        self.pump(2.5)  # legacy isReady() is constant; initial lists arrive later

    def data(self, who):
        bridge = self.bridges[who]
        if not bridge.latest or not 0 <= time.time()*1000-bridge.latest['time_ms'] <= 2500 or not bridge.latest['data']['connected']:
            raise RuntimeError('Fresh connected perception required')
        return bridge.latest['data']

    def action(self, who, action):
        request = self.submit(who, action)
        return self.await_result(who, request, action)

    def submit(self, who, action):
        self.wait(lambda: time.monotonic()-self.last_send[who] >= 1.15, 3)
        bridge = self.bridges[who]
        self.data(who)
        db = self.community.memories[who].db
        unresolved = db.execute("SELECT id FROM intents WHERE status IN ('unknown','accepted') AND session=?", (bridge.session,)).fetchone()
        if unresolved:
            raise RuntimeError('Unresolved intent blocks further actions in this session')
        request = uuid.uuid4().hex
        db.execute('INSERT INTO intents VALUES (?,?,?,?)', (request, bridge.session, json.dumps(action), 'unknown'))
        db.execute("DELETE FROM intents WHERE status IN ('completed','rejected') AND rowid NOT IN (SELECT rowid FROM intents ORDER BY rowid DESC LIMIT 512)")
        db.commit()  # durable before network, never replay on restart
        bridge.proposal(action, request_id=request)
        self.last_send[who] = time.monotonic()
        return request

    def await_result(self, who, request, action):
        self.wait(lambda: self.results.get(request, {}).get('status') in ('completed', 'rejected', 'unknown'), 7)
        result = self.results[request]
        print(json.dumps({'who': who, 'action': action, 'result': result}), flush=True)
        if result['status'] != 'completed':
            raise RuntimeError('Action did not complete: '+json.dumps(result))
        return result

    def walk_to(self, who, x, y, within=0):
        for _ in range(20):
            data = self.data(who)
            pos = data['destination']
            dx, dy = x-pos['x'], y-pos['y']
            if max(abs(dx), abs(dy)) <= within:
                return
            occupied = {(p['x'], p['y']) for p in data['players']}
            candidates = [(pos['x']+a, pos['y']+b) for a in (-1, 0, 1) for b in (-1, 0, 1)
                          if (a or b) and (pos['x']+a, pos['y']+b) not in occupied]
            nx, ny = min(candidates, key=lambda p: (max(abs(x-p[0]), abs(y-p[1])), abs(x-p[0])+abs(y-p[1])))
            action = {'type': 'move', 'map': data['map'], 'x': nx, 'y': ny}
            self.action(who, action)
            # A later server packet can correct an occupied-cell destination.
            # Replan from a NEW snapshot instead of replaying the old path goal.
            sent_ms = int(time.time()*1000)
            self.wait(lambda: self.bridges[who].latest['time_ms'] >= sent_ms+400, 3)
            self.pump(.4)
        raise RuntimeError('Local navigation budget exhausted')

    def chat(self, who, text):
        return self.action(who, {'type': 'chat', 'text': text})

    def conversation(self):
        start = len(self.replies)
        for sender, target in [('third', 'agent'), ('agent', 'peer'), ('peer', 'third')]:
            self.chat(sender, 'M4:'+target+':Name and one preference only, very briefly?')
        pending_during_movement = any(d.future is not None for d in self.community.dialogues.values())
        self.walk_to('third', 152, 181)
        self.wait(lambda: len(self.replies)-start >= 3, 105)
        replies = self.replies[start:]
        for reply in replies:
            self.chat(reply['who'], reply['text'])
        return {'replies': replies, 'inference_pending_before_independent_movement': pending_during_movement}

    def isolation(self):
        note = 'blue-pebble-'+uuid.uuid4().hex[:8]
        memory = self.community.memories['agent']
        memory.record(note, 'reported_claim', {'speaker': 'private_test_note', 'text': note})
        for who in ('peer', 'third'):
            if note in json.dumps(self.community.memories[who].retrieve(16)):
                raise RuntimeError('Private note leaked before communication')
        text = 'My private test note says '+note+'.'
        self.chat('agent', text)
        self.wait(lambda: all(any(e['agent_id'] == who and e['kind'] == 'chat' and e['data']['text'] == text and not e['data']['self'] for e in self.events) for who in ('peer', 'third')), 3)
        # Reopen all minds from disk. No prompt/history is copied between them.
        self.community.close()
        self.community = Community(self.root, self.runtime/'m4/state', self.bridges)
        for who in self.bridges:
            if note not in json.dumps(self.community.memories[who].retrieve(16)):
                raise RuntimeError('Information path failed to persist')
        return {'private_note': note, 'initial_owner': 'agent', 'learned_via': 'perceived public chat', 'database_reopen_recall': list(self.bridges)}

    def boundaries(self):
        checked = []
        cases = [('agent', {'type': 'attack', 'target': 'ffffffff'}, 'target_not_visible_nearby_or_allowed'),
                 ('agent', {'type': 'take', 'target': 'ffffffff'}, 'target_not_visible_nearby_or_allowed'),
                 ('third', {'type': 'trade_request'}, 'invalid_trade'),
                 ('agent', {'type': 'trade_offer', 'amount': 999}, 'invalid_trade'),
                 ('agent', {'type': 'chat', 'text': '@item 909'}, 'invalid_chat')]
        for who, action, reason in cases:
            request = self.submit(who, action)
            self.wait(lambda: self.results.get(request, {}).get('status') == 'rejected', 3)
            if self.results[request]['reason'] != reason:
                raise RuntimeError('Unexpected rejection reason')
            checked.append({'who': who, 'action': action, **self.results[request]})
        bridge = self.bridges['agent']
        request = uuid.uuid4().hex
        bridge.proposal({'type': 'chat', 'text': 'stale must not be sent'}, request_id=request, session='old-epoch')
        self.wait(lambda: request in self.results, 3)
        if self.results[request]['reason'] != 'stale_session':
            raise RuntimeError('Stale request not rejected')
        checked.append(self.results[request])
        bridge.proposal({'type': 'chat', 'text': 'duplicate must not be sent'}, request_id=request)
        self.wait(lambda: self.results.get(request, {}).get('replay') == 1, 3)
        checked.append(self.results[request])
        return checked

    def reconnect_clients(self):
        for bridge in self.bridges.values():
            bridge.close()
        command = [str(__import__('sys').executable), str(self.root/'scripts/prepare_m4.py'), '--runtime', str(self.runtime), '--clients-only', '--start']
        # Lifecycle signals only the verified project clients. Server/DB stay up.
        subprocess.run(command, check=True, timeout=100)
        self.bridges = {who: Bridge(self.runtime/'m4/openkore'/who/'bridge.json') for who in ('agent', 'peer', 'third')}
        self.community.bridges = self.bridges
        self.ready()

    def trade(self, fault=None):
        ledger = TradeLedger(self.runtime/'m4/trades.sqlite')
        try:
            if ledger.unresolved():
                self.reconnect_clients()
                recovered = []
                authoritative = server_balances(self.runtime)
                self.wait(lambda: {who: balances(self.data(who)) for who in ('agent', 'peer')} == authoritative, 10)
                for key, _ in ledger.unresolved():
                    recovered.append(ledger.finish(key, {who: self.bridges[who].latest for who in ('agent', 'peer')}, authoritative))
                return {'recovered_only': recovered, 'new_transfer_attempted': False}
            self.walk_to('peer', 153, 180)
            self.walk_to('agent', 154, 179)
            self.chat('agent', 'Offer: one Jellopy to Bram for ten Zeny.')
            self.chat('peer', 'Agreed: ten Zeny to Alden for one Jellopy.')
            before = {who: balances(self.data(who)) for who in ('agent', 'peer')}
            if before['agent']['jellopy'] < 1 or before['peer']['zeny'] < 10:
                raise RuntimeError('Fixed trade requires earned Jellopy and ten Zeny')
            key = ledger.begin(before, {who: self.bridges[who].session for who in ('agent', 'peer')})
            try:
                request = self.submit('agent', {'type': 'trade_request'})
                self.wait(lambda: self.data('peer')['deal']['incoming'] == 'M4 Alden', 3)
                self.action('peer', {'type': 'trade_accept'})
                self.await_result('agent', request, {'type': 'trade_request'})
                self.action('agent', {'type': 'trade_offer'})
                self.wait(lambda: self.data('peer')['deal']['other_item'] == 1, 3)
                self.action('peer', {'type': 'trade_offer'})
                self.wait(lambda: all(self.data(who)['deal']['other_zeny' if who == 'agent' else 'other_item'] == (10 if who == 'agent' else 1) for who in ('agent', 'peer')), 3)
                self.action('agent', {'type': 'trade_lock'})
                self.wait(lambda: all(self.data(who)['deal']['other_locked'] for who in ('agent', 'peer')), 3)
                commits = {who: self.submit(who, {'type': 'trade_commit'}) for who in ('agent', 'peer')}
                if fault != 'after_commit':
                    for who, request in commits.items():
                        self.await_result(who, request, {'type': 'trade_commit'})
                else:
                    # Simulate losing both completion observations. Never resend.
                    pass  # reconnect closes sockets before consuming completion
                protocol = {'commits': commits, 'completion_observations_discarded': fault == 'after_commit'}
            except (RuntimeError, TimeoutError, OSError) as error:
                protocol = {'uncertain_protocol': str(error)}
            # Even success packets are insufficient: reconnect fetches actual
            # server inventories and balances, undoing speculative local edits.
            self.reconnect_clients()
            authoritative = server_balances(self.runtime)
            self.wait(lambda: {who: balances(self.data(who)) for who in ('agent', 'peer')} == authoritative, 10)
            body = ledger.finish(key, {who: self.bridges[who].latest for who in ('agent', 'peer')}, authoritative)
            if body['reconciliation'] != 'completed':
                raise RuntimeError('Trade not confirmed: '+json.dumps({**body, **protocol}))
            return {'id': key, **body, **protocol}
        finally:
            ledger.close()

    def encounter(self, cooperative=False):
        leader = 'agent'
        self.wait(lambda: any(m['name_id'] == 1002 for m in self.data(leader)['monsters']), 25)
        monster = next(m for m in self.data(leader)['monsters'] if m['name_id'] == 1002)
        target = monster['id']
        old_items = {i['id'] for i in self.data(leader)['ground_items']}
        actors = ('agent', 'peer') if cooperative else ('agent',)
        evidence_start = self.event_count
        if cooperative:
            goal = 'Goal: hunt Poring '+target+'. I lead; Bram flank and strike it.'
            self.chat('agent', goal)
            self.wait(lambda: any(e['agent_id'] == 'peer' and e['kind'] == 'chat' and e['data']['text'] == goal and not e['data']['self'] for e in self.events), 3)
            self.chat('peer', 'Agreed. I flank and strike that Poring; Alden gathers the loot.')
        damage = {who: 0 for who in actors}
        for turn in range(50):
            who = actors[turn % len(actors)]
            monsters = self.data(who)['monsters']
            visible = next((m for m in monsters if m['id'] == target), None)
            deaths = [e for e in self.events if e['agent_id'] == leader and e['kind'] == 'monster_departure' and e['data']['target'] == target and e['data']['dead']]
            if deaths:
                break
            if not visible:
                self.pump(1.1)
                continue
            self.walk_to(who, visible['x'], visible['y'], within=1)
            result = self.action(who, {'type': 'attack', 'target': target})
            damage[who] += result['evidence']['damage']
            self.pump(1.1)
        else:
            raise RuntimeError('Encounter turn budget exhausted')
        if any(value <= 0 for value in damage.values()):
            raise RuntimeError('Each assigned attacker must cause confirmed damage')
        before = self.item_count(self.data(leader), 909)
        self.wait(lambda: any(i['name_id'] == 909 and i['id'] not in old_items for i in self.data(leader)['ground_items']), 5)
        item = next(i for i in self.data(leader)['ground_items'] if i['name_id'] == 909 and i['id'] not in old_items)
        self.walk_to(leader, item['x'], item['y'], within=1)
        loot = self.action(leader, {'type': 'take', 'target': item['id']})
        self.wait(lambda: self.item_count(self.data(leader), 909) > before, 4)
        return {'target': target, 'cooperative': cooperative, 'goal_chosen_by': leader, 'roles': {who: ('lead_and_gather' if who == leader else 'flank_and_strike') for who in actors}, 'damage': damage, 'death': deaths[0], 'loot': loot, 'inventory_before': before, 'inventory_after': self.item_count(self.data(leader), 909), 'event_start': evidence_start}

    @staticmethod
    def item_count(data, item):
        return sum(i['amount'] for i in data['inventory'] if i['name_id'] == item)

    def close(self):
        self.raw.close()
        for bridge in self.bridges.values():
            bridge.close()
        self.community.close()
