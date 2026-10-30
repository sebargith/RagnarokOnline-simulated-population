"""Durable, deterministic adjacent-cell routine. No inference dependency."""
import json
import time
import uuid


class Routine:
    def __init__(self, memory, bridge, interval=20):
        if interval < 2:
            raise ValueError('Routine interval must be at least two seconds')
        self.memory, self.bridge, self.interval = memory, bridge, interval
        self.db = memory.db
        self.db.execute('CREATE TABLE IF NOT EXISTS routine (owner TEXT PRIMARY KEY, state TEXT)')
        row = self.db.execute('SELECT state FROM routine WHERE owner=?', (memory.identity,)).fetchone()
        self.state = json.loads(row[0]) if row else {'session': None, 'count': 0, 'direction': 1, 'pending': None}
        self.next_at = time.monotonic() + interval
        self.reason = 'awaiting_snapshot'

    def save(self):
        self.db.execute('INSERT OR REPLACE INTO routine VALUES (?,?)', (self.memory.identity, json.dumps(self.state)))
        self.db.commit()

    def observe(self, event):
        if event.get('agent_id') != self.memory.identity:
            raise ValueError('Wrong observation identity')
        pending = self.state['pending']
        if event['kind'] == 'action_result' and pending and event['session'] == self.state['session']:
            result = event['data']
            if result.get('request_id') == pending['id']:
                status = result.get('status')
                if status not in ('accepted', 'completed', 'unknown', 'rejected'):
                    raise ValueError('Unknown result status')
                self.memory.record(event['id'], 'action', result)
                pending['status'] = status
                if status in ('completed', 'rejected'):
                    self.state['pending'] = None
                self.save()

    def tick(self):
        snapshot = self.bridge.latest
        if not snapshot or not 0 <= time.time()*1000 - snapshot['time_ms'] <= 2500:
            self.reason = 'stale_snapshot'
            return
        data = snapshot['data']
        if not data['connected'] or snapshot['session'] != self.bridge.session:
            self.reason = 'disconnected_or_stale_session'
            return
        if self.state['session'] != snapshot['session']:
            if self.state['pending']:
                self.memory.record(uuid.uuid4().hex, 'action', {**self.state['pending'], 'status': 'unknown', 'reason': 'epoch_changed'})
            self.state.update(session=snapshot['session'], count=0, pending=None)
            self.save()
        pending = self.state['pending']
        if pending:
            if time.time() > pending['expires'] and pending['status'] != 'unknown':
                pending['status'] = 'unknown'
                self.save()
            # No retries across process restart. Same-epoch uncertainty fails closed.
            self.reason = 'pending_' + pending['status']
            return
        if self.state['count'] >= 110:
            self.reason = 'epoch_capacity'
            return
        if time.monotonic() < self.next_at:
            self.reason = 'waiting'
            return
        if data.get('hp', 0) <= 0:
            self.reason = 'not_alive'
            return
        # OpenKore pos can remain the old path origin; destination is the
        # acknowledged path target, not proof of arrival. The plugin rechecks it.
        action = {'type': 'move', 'map': data['map'], 'x': data['destination']['x'] + self.state['direction'], 'y': data['destination']['y']}
        request_id = uuid.uuid4().hex
        # Intent and capacity reservation reach disk before any network write.
        self.state['pending'] = {'id': request_id, 'status': 'unknown', 'action': action, 'expires': time.time()+6}
        self.state['count'] += 1
        self.state['direction'] *= -1
        self.save()
        self.next_at = time.monotonic() + self.interval
        try:
            self.bridge.proposal(action, request_id=request_id, session=snapshot['session'])
            self.reason = 'submitted_unconfirmed'
        except (OSError, RuntimeError):
            self.reason = 'send_unknown'
