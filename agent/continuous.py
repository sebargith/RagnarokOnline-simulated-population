"""Continuous M4 fixture controller; no LLM gameplay authority or action retries."""
from collections import deque
import json
import os
import subprocess
import time

from agent.live_io import RingLog, atomic_json, exclusive
from agent.prototype import Prototype
from agent.trade import TradeLedger, balances
from bridge.client import Bridge
from scripts.bench_m2 import ram_sample


class StopRequested(Exception):
    pass


class Continuous(Prototype):
    def __init__(self, root, runtime, run_id, duration=None):
        # Startup connects after owning m4.lock; caller starts existing profiles
        # from this source first. A full login makes prior nontrade intent stale.
        self.live = runtime/'m4/live'
        self.live.mkdir(parents=True, exist_ok=True)
        super().__init__(root, runtime, self.live)
        self.run_id, self.duration = run_id, duration
        self.results = {}
        self.replies, self.resources = deque(maxlen=32), deque(maxlen=120)
        self.pending_replies = {}
        self.reply_requests = set()
        self.connection_retry = {who: [0, 1] for who in self.bridges}
        self.offline = set()
        self.cycle = 0
        self.phase = 'starting'
        self.last_status = self.last_patrol = self.last_commands = 0
        self.inference_retry = 0
        self.suspended = True
        self.manual = deque(maxlen=8)
        self.counters = {'completed': 0, 'unknown': 0, 'rejected': 0, 'delivered_replies': 0, 'reconnections': 0, 'trade_completed': 0}
        for memory in self.community.memories.values():
            memory.db.execute('CREATE TABLE IF NOT EXISTS live_intents(session TEXT,id TEXT,action TEXT,status TEXT,created REAL,retired INTEGER DEFAULT 0,PRIMARY KEY(session,id))')
            memory.db.commit()

    def open_log(self, path):
        return RingLog(path)

    def client_options(self):
        return ['--continuous']

    def await_result(self, who, request, action):
        self.wait(lambda: self.results.get((who, request), {}).get('status') in ('completed', 'rejected', 'unknown'), 7)
        result = self.results[(who, request)]
        if result['status'] != 'completed':
            raise RuntimeError('Action did not complete: '+json.dumps(result))
        return result

    def note(self, kind, **data):
        self.raw.write(json.dumps({'controller': kind, 'time': time.time(), 'run_id': self.run_id, **data})+'\n')

    def journal(self, who):
        return self.community.memories[who].db

    def available(self, who):
        bridge = self.bridges[who]
        if who in self.offline or not bridge.latest or time.monotonic()-self.last_send[who] < 1.15:
            return False
        data = bridge.latest['data']
        return (0 <= time.time()*1000-bridge.latest['time_ms'] <= 2500 and bridge.latest['session'] == bridge.session and data.get('connected')
                and data.get('hp', 0) > 0 and bridge.next_serial is not None
                and not self.journal(who).execute("SELECT 1 FROM live_intents WHERE retired=0 AND status IN ('unknown','accepted')").fetchone())

    def send_now(self, who, action):
        if not self.available(who):
            raise RuntimeError('Agent busy, uncertain or disconnected')
        bridge, db = self.bridges[who], self.journal(who)
        request = bridge.serial_id()
        db.execute('INSERT INTO live_intents(session,id,action,status,created) VALUES (?,?,?,?,?)',
                   (bridge.session, request, json.dumps(action), 'unknown', time.time()))
        db.execute("DELETE FROM live_intents WHERE (retired=1 OR status IN ('completed','rejected')) AND rowid NOT IN (SELECT rowid FROM live_intents ORDER BY rowid DESC LIMIT 512)")
        db.commit()
        self.last_send[who] = time.monotonic()
        bridge.proposal(action, request_id=request)  # write once; failed send stays unknown
        return request

    def submit(self, who, action):
        self.wait(lambda: self.available(who), 8)
        return self.send_now(who, action)

    def snapshot_status(self):
        agents = {}
        for who, bridge in self.bridges.items():
            snap = bridge.latest
            agents[who] = {'session': bridge.session, 'snapshot': snap,
                           'pending_inference': self.community.dialogues[who].future is not None,
                           'journal_rows': self.journal(who).execute('SELECT COUNT(*) FROM live_intents').fetchone()[0]}
        ledger = TradeLedger(self.runtime/'m4/trades.sqlite')
        try:
            blocked = [key for key, _ in ledger.unresolved()]
        finally:
            ledger.close()
        return {'run_id': self.run_id, 'pid': os.getpid(), 'updated': time.time(), 'running': True,
                'elapsed_s': time.monotonic()-self.started, 'cycle': self.cycle, 'phase': self.phase,
                'counters': self.counters, 'agents': agents, 'unresolved_trades': blocked,
                'resources': list(self.resources), 'recent_replies': list(self.replies), 'event_count': self.event_count}

    def controls(self):
        stop = self.live/'stop.json'
        if stop.exists():
            if json.loads(stop.read_text())['run_id'] == self.run_id:
                raise StopRequested()
        if self.duration and time.monotonic()-self.started >= self.duration:
            raise StopRequested()
        if time.monotonic()-self.last_commands < .5:
            return
        self.last_commands = time.monotonic()
        try:
            with exclusive(self.live/'control.lock'):
                path = self.live/'commands.json'
                commands = json.loads(path.read_text()) if path.exists() else []
                atomic_json(path, [])
        except OSError:
            return
        for command in commands[:8]:
            if command.get('run_id') == self.run_id and time.time()-command.get('created', 0) < 30:
                if len(self.manual) < self.manual.maxlen:
                    self.manual.append(command)

    def background(self):
        if self.suspended:
            return
        now = time.monotonic()
        for who, (session, reply) in list(self.pending_replies.items()):
            if session != self.bridges[who].session or now-reply['ready_at'] > 20:
                self.note('reply_discarded', who=who, reason='stale_session_or_delivery_deadline')
                del self.pending_replies[who]
            elif self.available(who) and not self.data(who)['deal']['name']:
                request = self.send_now(who, {'type': 'chat', 'text': reply['text']})
                self.reply_requests.add((who, request))
                self.note('reply_submitted', who=who, request=request)
                del self.pending_replies[who]
        if self.manual:
            command = self.manual[0]
            who, target, text = command.get('sender'), command.get('target'), command.get('text')
            if (time.time()-command.get('created', 0) >= 30 or who not in self.bridges or target not in self.bridges
                    or who == target or not isinstance(text, str) or not 1 <= len(text) <= 65
                    or any(not 32 <= ord(c) <= 126 for c in text)):
                self.manual.popleft()
            elif self.available(who) and self.available(target) and not self.data(who)['deal']['name']:
                self.send_now(who, {'type': 'chat', 'text': 'M4:'+target+':'+text})
                self.manual.popleft()
                self.note('manual_public_chat', sender=who, target=target, text=text)
        if now-self.last_patrol >= 5 and self.available('third'):
            data = self.data('third')
            if data['map'] == 'prontera' and data['destination']['x'] == 152 and data['destination']['y'] in (180, 181):
                self.send_now('third', {'type': 'move', 'map': 'prontera', 'x': 152, 'y': 181 if data['destination']['y'] == 180 else 180})
            self.last_patrol = now

    def pump(self, seconds=.1):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            self.controls()
            now = time.monotonic()
            for who in self.bridges:
                if who in self.offline:
                    due, delay = self.connection_retry[who]
                    if now < due:
                        continue
                    try:
                        self.bridges[who] = Bridge(self.runtime/'m4/openkore'/who/'bridge.json')
                        self.community.bridges = self.bridges
                        self.offline.remove(who)
                        self.connection_retry[who] = [0, 1]
                        self.counters['reconnections'] += 1
                    except OSError:
                        self.connection_retry[who] = [now+delay, min(30, delay*2)]
                        continue
                bridge = self.bridges[who]
                try:
                    incoming = bridge.poll(.01)
                except (OSError, BufferError, ValueError) as error:
                    bridge.close()
                    bridge.latest = None
                    self.offline.add(who)
                    self.note('bridge_offline', who=who, error=str(error))
                    continue
                for event in incoming:
                    self.event_count += 1
                    self.raw.write(json.dumps(event)+'\n')
                    self.events.append(event)
                    self.community.observe(who, event)
                    db = self.journal(who)
                    if event['kind'] == 'snapshot' and event['data']['connected']:
                        # Preserve unknown outcomes, retire their authority only
                        # after a new full game epoch. Never mark them completed.
                        db.execute('UPDATE live_intents SET retired=1 WHERE session!=?', (event['session'],))
                        db.commit()
                    if event['kind'] == 'action_result':
                        result = event['data']
                        request = result['request_id']
                        db.execute('UPDATE live_intents SET status=? WHERE session=? AND id=?', (result['status'], event['session'], request))
                        db.commit()
                        self.results[(who, request)] = result
                        while len(self.results) > 256:
                            del self.results[next(iter(self.results))]
                        if result['status'] in self.counters:
                            self.counters[result['status']] += 1
                        if result['status'] in ('completed', 'rejected', 'unknown') and (who, request) in self.reply_requests:
                            self.reply_requests.remove((who, request))
                            if result['status'] == 'completed':
                                self.counters['delivered_replies'] += 1
                                self.note('reply_delivered', who=who, result=result)
                bridge.drain()
                reply = self.community.poll(who)
                if reply:
                    self.replies.append({'who': who, **reply})
                    self.pending_replies[who] = (reply['session'], {**reply, 'ready_at': now})
                    self.note('reply_ready', who=who, reply=reply)
            service = self.community.service
            if service.circuit.is_set():
                if not self.inference_retry:
                    self.inference_retry = now+30
                if now >= self.inference_retry and service.recover_idle_circuit():
                    self.inference_retry = 0
                    self.note('inference_circuit_reopened')
            self.background()
            if now-self.last_resource >= 5:
                sample = {'elapsed_s': now-self.started, **ram_sample(set())}
                gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
                sample['gpu_used_mib'] = int(gpu.strip())
                self.resources.append(sample)
                self.last_resource = now
                if sample['ram_available'] < 2*1024**3 or sample['gpu_used_mib'] > 14336:
                    raise RuntimeError('Unchanged M2 resource budget exceeded')
            if now-self.last_status >= 1:
                atomic_json(self.live/'status.json', self.snapshot_status())
                self.last_status = now
            time.sleep(.01)

    def reconnect_clients(self):
        self.suspended = True
        try:
            self.offline.clear()
            self.results.clear()
            self.reply_requests.clear()
            super().reconnect_clients()
            self.counters['reconnections'] += 3
        finally:
            self.suspended = False

    def trade(self, fault=None):
        ledger = TradeLedger(self.runtime/'m4/trades.sqlite')
        try:
            unresolved = bool(ledger.unresolved())
        finally:
            ledger.close()
        if not unresolved:
            before = {who: balances(self.data(who)) for who in ('agent', 'peer')}
            if before['agent']['jellopy'] < 1 or before['peer']['zeny'] < 10:
                self.note('trade_skipped', reason='seller_lacks_goods_or_buyer_cannot_afford', perceived=before)
                return {'skipped': True}
        result = super().trade(fault)
        if result.get('reconciliation') == 'completed':
            self.counters['trade_completed'] += 1
        self.note('trade_result', result=result)
        return result

    def run(self):
        self.ready()
        self.suspended = False
        self.phase = 'recover_transfers'
        ledger = TradeLedger(self.runtime/'m4/trades.sqlite')
        try:
            unresolved = bool(ledger.unresolved())
        finally:
            ledger.close()
        if unresolved:
            self.trade()  # recover only, no new transfer
        backoff = 5
        while True:
            try:
                self.phase = 'cooperative_hunt' if self.cycle % 2 else 'solo_hunt'
                result = self.encounter(bool(self.cycle % 2))
                self.cycle += 1
                self.note('cycle_completed', cycle=self.cycle, result=result)
                if self.cycle % 3 == 0:
                    self.phase = 'fixed_trade'
                    self.trade()
                self.phase = 'rest'
                self.pump(5)
                backoff = 5
            except (TimeoutError, OSError, ValueError, RuntimeError) as error:
                # Unknown protocol work is never reissued; full login resync
                # precedes a fresh routine goal. Ledger still blocks transfers.
                if 'resource budget' in str(error):
                    raise
                self.phase = 'recovery_backoff'
                self.note('routine_paused', error=str(error), backoff_s=backoff)
                self.pump(backoff)
                try:
                    self.reconnect_clients()
                    ledger = TradeLedger(self.runtime/'m4/trades.sqlite')
                    try:
                        unresolved = bool(ledger.unresolved())
                    finally:
                        ledger.close()
                    if unresolved:
                        self.trade()
                except (TimeoutError, OSError, ValueError, RuntimeError) as recovery_error:
                    self.note('recovery_failed', error=str(recovery_error))
                backoff = min(60, backoff*2)

    def close(self):
        self.note('stopping', cycle=self.cycle)
        status = self.snapshot_status()
        status.update(phase='stopping')
        atomic_json(self.live/'status.json', status)
        super().close()
        status.update(running=False, phase='stopped', updated=time.time())
        atomic_json(self.live/'status.json', status)
