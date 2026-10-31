"""Run/resume one bounded solo goal; status reads files without bridge access.

Requires the separate P1 client already running. Does not restart any service.
The checkpoint survives this process; uncertain intents are queried, never sent
again. Result loss blocks the goal, rather than guessing a purchase or kill.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.live_io import RingLog, atomic_json, exclusive
from agent.solo_cycle import SoloCycle, FINAL
from bridge.client import Bridge
from scripts.bench_m2 import ram_sample
from agent.goal_planner import GoalPlanner, apply_proposal_locked


class Runner:
    def __init__(self, cycle, bridge, directory, planner=None, intent=None):
        self.cycle, self.b, self.directory = cycle, bridge, directory
        self.ready = None
        self.last_send, self.last_query, self.last_status = 0, 0, 0
        self.last_resource = 0
        self.resources = None
        self.actions = 0
        self.inventory_session, self.inventory_ready_after = None, None
        self.log = RingLog(directory/'events.jsonl')
        self.planner, self.intent = planner, intent
        self.planning_requested, self.planning_done = False, planner is None
        self.inference_calls, self.planning_result = 0, None

    def planning_tick(self):
        if self.planning_done:
            return
        latest = self.b.latest
        if not latest or not latest['data'].get('connected') or not 0 <= time.time()*1000-latest['time_ms'] <= 2500:
            return
        self.resource_guard()
        if not self.planning_requested:
            self.planning_requested = True
            try:
                self.planner.request(self.intent)
                self.inference_calls += 1
            except Exception as error:
                self.planning_done = True
                self.planning_result = {'status':'unavailable','reason':type(error).__name__}
                self.note('planning_result', self.planning_result)
                return
        result = self.planner.poll()
        if result is None:
            return
        self.planning_done = True
        self.note('planning_proposal', result)
        if result['status'] == 'proposed':
            try:
                result = apply_proposal_locked(self.cycle, result, latest)
            except (ValueError, RuntimeError, OSError) as error:
                result = {'status':'rejected','reason':str(error)}
        self.planning_result = result
        self.note('planning_result', result)

    def note(self, kind, data):
        self.log.write(json.dumps({'time': time.time(), 'kind': kind, 'data': data})+'\n')

    def pump(self):
        self.b.poll(.1)
        for e in self.b.drain():
            kind, data = e['kind'], e['data']
            if kind == 'ready':
                self.ready = data
            if kind == 'action_result' and data.get('status') in FINAL:
                p = self.cycle.state['inflight']
                if p and e['session'] == p['session'] and (self.cycle.cancel_result(data, e['time_ms']) if p.get('cancel') else self.cycle.result(data, observed_after=e['time_ms'])):
                    self.note(kind, data)
            elif kind == 'request_status':
                p = self.cycle.state['inflight']
                if p and e['session'] == p['session'] and data['request_id'] in (p['request_id'], (p.get('cancel') or {}).get('request_id')) and data['session'] == p['session']:
                    if not data['available']:
                        self.cycle.block('result_unavailable_no_replay')
                    elif data['result']['status'] in FINAL:
                        (self.cycle.cancel_result(data['result'], e['time_ms']) if p.get('cancel') else self.cycle.result(data['result'], observed_after=e['time_ms']))
                    self.note(kind, data)
            elif kind in {'healing', 'recovery', 'death', 'connection'}:
                self.note(kind, data)

    def status(self, running, reason=None):
        s = self.cycle.state
        latest = self.b.latest
        atomic_json(self.directory/'status.json', {
            'running': running, 'pid': os.getpid(), 'updated': time.time(), 'reason': reason,
            'status': s['status'], 'phase': s['phase'], 'kills': s['kills'],
            'goal_kills': s['goal_kills'], 'inflight': s['inflight'],
            'block_reason': s.get('reason'), 'resources': self.resources,
            'planning_result': self.planning_result, 'inference_calls': self.inference_calls,
            'observed': {k: latest['data'].get(k) for k in
                ('map', 'position', 'hp', 'hp_max', 'level', 'recovery', 'zeny')} if latest else None})

    def resource_guard(self):
        # No inference here, but preserve the project's total machine limits.
        if time.monotonic() - self.last_resource < 15:
            return
        sample = ram_sample(set())
        if sample['ram_available'] < 2*1024**3:
            raise RuntimeError('Available RAM below 2 GiB')
        raw = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used',
            '--format=csv,noheader,nounits'], text=True, timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW)
        gpu = int(raw.strip())
        if gpu > 14336:
            raise RuntimeError('GPU above 14336 MiB')
        self.resources = {'ram_available': sample['ram_available'], 'gpu_used_mib': gpu}
        self.last_resource = time.monotonic()

    def run(self, seconds, max_actions=0, pause_after_send=False):
        end, connect_end = time.monotonic()+seconds, time.monotonic()+15
        reason = 'time_budget'
        try:
            while time.monotonic() < end:
                self.pump()
                self.planning_tick()
                if self.cycle.state['status'] != 'active' and self.planning_done:
                    reason = self.cycle.state['status']; break
                if self.cycle.state['status'] != 'active':
                    if time.monotonic() - self.last_status >= 1:
                        self.status(True)
                        self.last_status = time.monotonic()
                    continue
                latest = self.b.latest
                if not self.ready or not latest or not latest['data'].get('connected') or self.b.next_serial is None:
                    if time.monotonic() >= connect_end:
                        raise RuntimeError('No connected bridge within 15 seconds')
                    continue
                if self.inventory_session != self.b.session:
                    self.inventory_session, self.inventory_ready_after = self.b.session, None
                if not latest['data'].get('inventory_ready'):
                    self.inventory_ready_after = None
                elif self.inventory_ready_after is None:
                    self.inventory_ready_after = latest['time_ms'] + 1500
                p = self.cycle.state['inflight']
                if p:
                    if self.b.session != p['session']:
                        self.cycle.block('session_changed_no_replay'); continue
                    if time.time() >= p['deadline']:
                        self.cycle.block('intent_deadline_no_replay'); continue
                    if (p.get('exploration') and not p.get('cancel') and (not max_actions or self.actions < max_actions) and self.b.session == latest['session'] and
                            0 <= time.time()*1000 - latest['time_ms'] <= 2500 and
                            self.cycle.interruptible(latest['data'])):
                        rid = self.b.serial_id()
                        self.cycle.prepare_cancel(rid)
                        self.note('cancel_intent', {'request_id': rid, 'target': p['request_id'], 'snapshot_ms': latest['time_ms']})
                        self.b.proposal({'type': 'cancel', 'target': p['request_id']}, request_id=rid)
                        self.actions += 1
                    if time.monotonic() - self.last_query >= 1:
                        ids = [p['request_id']]
                        if p.get('cancel'):
                            ids.append(p['cancel']['request_id'])
                        for rid in ids:
                            if rid not in (p.get('cancel') or {}).get('results', {}):
                                self.b.send({'type': 'query_result', 'request_id': rid, 'session': p['session']})
                        self.last_query = time.monotonic()
                elif max_actions and self.actions >= max_actions:
                    if self.planning_done:
                        reason = 'action_budget'; break
                    # Gameplay budget is exhausted; finish observing this one
                    # admitted inference without sending further game actions.
                    if time.monotonic() - self.last_status >= 1:
                        self.status(True)
                        self.last_status = time.monotonic()
                    continue
                elif time.monotonic() - self.last_send >= 1.2:
                    if self.inventory_ready_after is None or latest['time_ms'] <= max(
                            self.inventory_ready_after, self.cycle.state.get('observe_after', 0)):
                        continue
                    # Only current complete observations may select new work.
                    if time.time()*1000 - latest['time_ms'] > 2500:
                        raise RuntimeError('Stale snapshot')
                    self.resource_guard()
                    if time.time()*1000 - latest['time_ms'] > 2500:
                        continue  # Telemetry may have taken long enough to age the observation.
                    action = self.cycle.plan(latest['data'])
                    if action:
                        rid = self.b.serial_id()
                        self.cycle.prepare(action, rid, self.b.session)
                        self.note('intent', self.cycle.state['inflight'])
                        self.b.proposal(action, request_id=rid)
                        self.last_send = time.monotonic()
                        self.actions += 1
                        if pause_after_send:
                            reason = 'paused_after_send'; break
                if time.monotonic() - self.last_status >= 1:
                    self.status(True)
                    self.last_status = time.monotonic()
        except BaseException as error:
            reason = type(error).__name__+': '+str(error)
            self.note('runner_error', {'reason': reason})
            raise
        finally:
            if not self.planning_done:
                self.planning_result = {'status':'unfinished','reason':reason}
                self.note('planning_result', self.planning_result)
            self.status(False, reason)
            self.log.close()
            self.b.close()
        return {'reason': reason, 'status': self.cycle.state['status'],
                'kills': self.cycle.state['kills'], 'actions_sent': self.actions,
                'inflight': self.cycle.state['inflight'], 'inference_calls': self.inference_calls,
                'planning_result': self.planning_result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'status', 'set-goal', 'reconcile-navigation'))
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--seconds', type=int, default=180)
    parser.add_argument('--goal-kills', type=int, default=6, help='Only used when creating a new checkpoint')
    parser.add_argument('--target-kills', type=int, help='New absolute cumulative goal for set-goal')
    parser.add_argument('--intent', help='One bounded player intention for the local 9B (max 400 characters)')
    parser.add_argument('--max-actions', type=int, default=0)
    parser.add_argument('--pause-after-send', action='store_true', help='Disconnect after one proposal to verify restart recovery')
    args = parser.parse_args()
    if args.intent is not None and (args.command != 'run' or not 1 <= len(args.intent) <= 400):
        parser.error('--intent requires run and 1..400 characters')
    directory = args.runtime/'p1/cycle'
    if args.command == 'status':
        path = directory/'status.json'
        state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'running': False, 'reason': 'not_started'}
        state['status_age_s'] = round(time.time()-state['updated'], 1) if 'updated' in state else None
        print(json.dumps(state))
        return
    if not 1 <= args.seconds <= 3600 or not 0 <= args.max_actions <= 100:
        parser.error('seconds must be 1..3600 and max-actions 0..100')
    directory.mkdir(parents=True, exist_ok=True)
    with exclusive(args.runtime/'p1/cycle.lock'):
        if args.command == 'set-goal' and (args.target_kills is None or not (directory/'state.json').exists()):
            parser.error('set-goal requires --target-kills and an existing checkpoint')
        cycle = SoloCycle(directory/'state.json', args.goal_kills)
        if args.command == 'reconcile-navigation':
            bridge = Bridge(args.runtime/'p1/openkore/solo/bridge.json')
            observations, ready = [], None
            try:
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline and len(observations) < 2:
                    bridge.poll(.1)
                    for event in bridge.drain():
                        if event['kind'] == 'ready':
                            ready = event['data']
                        if event['kind'] == 'snapshot' and event['data'].get('connected') and ready:
                            if 'pending_request_id' not in ready or ready['pending_request_id'] is not None:
                                raise RuntimeError('Bridge has a pending action')
                            if not observations or event['time_ms'] - observations[0]['time_ms'] >= 1000:
                                observations.append(event)
                cycle.reconcile_navigation(observations, int(time.time()*1000))
                print(json.dumps({'status': cycle.state['status'], 'reconciliation': cycle.state['reconciliations'][-1]}))
            finally:
                bridge.close()
            return
        if args.command == 'set-goal':
            changed = cycle.set_goal(args.target_kills)
            print(json.dumps({'changed': changed, 'goal_kills': cycle.state['goal_kills'],
                              'kills': cycle.state['kills'], 'status': cycle.state['status']}))
            return
        if cycle.state['status'] != 'active' and args.intent is None:
            print(json.dumps(cycle.state)); return
        bridge = Bridge(args.runtime/'p1/openkore/solo/bridge.json')
        service = None
        try:
            planner = None
            if args.intent is not None:
                from inference.roles import build_role
                service = build_role('planner')  # cloud primary, local fallback, explicit errors
                planner = GoalPlanner(service, directory/'state.json')
            print(json.dumps(Runner(cycle, bridge, directory, planner, args.intent).run(
                args.seconds, args.max_actions, args.pause_after_send)))
        finally:
            bridge.close()
            if service:
                service.close()


if __name__ == '__main__':
    main()
