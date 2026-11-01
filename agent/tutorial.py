"""P5 step 4: a new novice leaves the pre-Renewal training grounds by talking to NPCs.

Deterministic and checkpointed, with the same interface SoloCycle offers the
runner (plan/prepare/result/block). Every step comes from config/p5-tutorial.json:
travel or a same-map portal between NPCs, then one pre-declared npc_script whose
only accepted ending is the declared warp (or a normal close). Rewards are the
observed inventory change and must equal the script's own; anything else stops
for review. The destination (a job town from Hanson's own-choice menu) comes
from code-validated options; the planner role only picks one of them.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import time

from agent import hunting
from scripts.p1_hunt import dist

ROOT = Path(__file__).resolve().parents[1]
FINAL = {'completed', 'failed', 'cancelled', 'unknown', 'rejected'}
SUCCESS = {'travel': 'arrived', 'portal': 'arrived', 'navigate': 'arrived'}
STAND_RANGE = 4  # bridge TALK_RANGE is 5; stand closer so a drift still talks.


def load(path=None):
    return json.loads(Path(path or ROOT/'config/p5-tutorial.json').read_text(encoding='utf-8'))


def inventory_delta(before, after):
    """'id:amount,...' snapshots from the bridge -> {id: change} without zeros."""
    def parse(text):
        out = {}
        for part in filter(None, (text or '').split(',')):
            key, amount = part.split(':')
            out[key] = out.get(key, 0) + int(amount)
        return out
    a, b = parse(before), parse(after)
    return {k: b.get(k, 0) - a.get(k, 0) for k in sorted(set(a) | set(b)) if b.get(k, 0) != a.get(k, 0)}


def starter_fields(start, level, tables):
    """Hunting fields a level-`level` novice may start from: within the hop limit,
    with an entry spot and a supply route, common monsters at most LEVEL_MARGIN
    above it and no aggressive common monster beyond that. Public facts only:
    its own danger is judged later by the cycle, once its build has spent the
    starting status points (at stats 1 every monster looks too strong)."""
    graph, fields, monsters = tables['fields']['portals'], tables['fields']['fields'], tables['monsters']
    out = []
    for name, field in sorted(fields.items()):
        route = hunting.hops(graph, start, name)
        if not route or not route[1] or not field['entries'].get(route[1]):
            continue
        if not (hunting.hops(graph, name, hunting.SHOP_MAP) and hunting.hops(graph, hunting.SHOP_MAP, name)):
            continue
        common = [monsters.get(str(m['id'])) for m in field['monsters'] if not m['rare']]
        common = [m for m in common if m]
        near = [m for m in common if m['level'] <= level + hunting.LEVEL_MARGIN and not m['boss']]
        if near and not any(m['aggressive'] and m['level'] > level + hunting.LEVEL_MARGIN for m in common):
            out.append((route[0], name))
    return [name for _, name in sorted(out)]


def destinations(snap, script, tables, builds):
    """Every job town of Hanson's own-choice menu, each either offered or rejected
    with the reason. Offered: the landing and the save town reach the supply shop
    and back within the travel hop limit, and the landing has a starter field."""
    graph = tables['fields']['portals']
    targets = {b['target_class'] for b in builds.values()}
    out = []
    for d in script['destinations']:
        landing, town = d['landing']['map'], d['town']
        why = []
        for place in (landing, town):
            if not (hunting.hops(graph, place, hunting.SHOP_MAP) and hunting.hops(graph, hunting.SHOP_MAP, place)):
                why.append(f'no_supply_route:{place}')
        fields = []
        if not why:
            fields = starter_fields(landing, snap['level']['base'], tables)
            if not fields:
                why.append('no_hunting_field')
        out.append({'job': d['job'], 'town': town, 'landing': d['landing'], 'save': d['save'],
                    'fields': fields[:4], 'build_for_job': (d['job'] if d['job'] != 'Swordsman' else 'Swordman') in targets,
                    'offered': not why, 'rejected': why})
    return out


def fallback_choice(options, identity):
    """Local policy when the planner fails: a per-character stable pick."""
    offered = [o for o in options if o['offered']]
    return min(offered, key=lambda o: hashlib.sha256(f'{identity}:{o["job"]}'.encode()).hexdigest()) if offered else None


class Tutorial:
    def __init__(self, path, identity, script=None):
        self.path, self.script = Path(path), script or load()
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding='utf-8'))
            if self.state.get('version') != 1 or self.state.get('identity') != identity:
                raise ValueError('Unsupported tutorial checkpoint')
        else:
            self.state = dict(version=1, identity=identity, status='active', step=0, instance=None,
                              inflight=None, history=[], failures=0, destination=None, steps_done=[],
                              observe_after=0, phase='tutorial', kills=0, goal_kills=0)
            self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        with temp.open('w', encoding='utf-8') as handle:
            json.dump(self.state, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(self.path)

    def block(self, reason):
        self.state.update(status='blocked', reason=reason)
        self.save()

    def recover_receptionist_navigation(self, observations, ready, now_ms):
        """Recover only the recorded clean rejection at Nilo's receptionist."""
        s = self.state
        if (s.get('identity') != 'Nilo' or s.get('status') != 'blocked' or
                s.get('reason') != 'two_consecutive_action_failures' or s.get('failures') != 2 or
                s.get('step') != 1 or s.get('instance') != 2 or s.get('phase') != 'tutorial' or
                s.get('inflight') is not None or s.get('destination') is not None):
            raise RuntimeError('Not the known receptionist block')
        step = self.current()
        if step.get('id') != 'receptionist' or step.get('map') != 'new_2-2':
            raise RuntimeError('Unexpected tutorial step')
        history = s.get('history', [])
        if len(history) < 3:
            raise RuntimeError('Incomplete history')
        travel, *rejected = history[-3:]
        if (travel.get('step') != 0 or travel.get('action', {}).get('type') != 'travel' or
                travel.get('result', {}).get('status') != 'completed' or
                travel.get('result', {}).get('reason') != 'arrived' or
                travel.get('result', {}).get('request_id') != travel.get('request_id')):
            raise RuntimeError('Missing completed travel')
        expected = {'type': 'navigate', 'map': step['map'], **step['stand'], 'timeout_s': 40}
        ids = []
        for h in rejected:
            result = h.get('result', {})
            if (h.get('step') != 1 or h.get('action') != expected or not h.get('session') or
                    not h.get('request_id') or result.get('request_id') != h['request_id'] or
                    result.get('status') != 'rejected' or result.get('reason') != 'already_at_destination'):
                raise RuntimeError('Navigation history is not conclusive')
            ids.append(h['request_id'])
        if len(set(ids)) != 2 or rejected[0]['session'] != rejected[1]['session']:
            raise RuntimeError('Navigation history is ambiguous')
        if len(observations) != 2 or not ready:
            raise RuntimeError('Missing observations')
        a, b = observations
        if (not a.get('session') or a['session'] != b.get('session') or
                a['session'] == rejected[0]['session'] or ready.get('session') != a['session'] or
                ready.get('data', {}).get('pending_request_id', 'missing') is not None or
                b['time_ms'] - a['time_ms'] < 1000 or now_ms - a['time_ms'] > 5000 or
                not 0 <= now_ms - b['time_ms'] <= 2500 or ready['time_ms'] > a['time_ms']):
            raise RuntimeError('Session or observation timing invalid')
        for event in observations:
            snap = event['data']
            if (not snap.get('connected') or not snap.get('inventory_ready') or snap.get('name') != 'Nilo' or
                    snap.get('executor') != 'openkore_route' or snap.get('dead') or
                    snap.get('map') != step['map'] or snap.get('recovery') != 'none' or
                    'native_task' not in snap or snap['native_task'] is not None or
                    'navigation' not in snap or snap['navigation'] is not None or
                    not isinstance(snap.get('ai_queue'), list) or
                    any(x in snap['ai_queue'] for x in ('move', 'route', 'mapRoute')) or
                    not snap.get('position') or not snap.get('destination') or
                    dist(snap['position'], snap['destination']) > 0 or
                    dist(snap['position'], step['stand']) > STAND_RANGE or
                    not any(n.get('x') == step['x'] and n.get('y') == step['y'] for n in snap.get('npcs', []))):
                raise RuntimeError('Character is not stationary beside receptionist')
        if a['data']['position'] != b['data']['position']:
            raise RuntimeError('Position changed')
        s['recoveries'] = s.get('recoveries', []) + [{'kind': 'receptionist_navigation_rejections',
            'request_ids': ids, 'prior_session': rejected[0]['session'], 'session': b['session'],
            'map': b['data']['map'], 'position': b['data']['position'],
            'observed_at_ms': [a['time_ms'], b['time_ms']]}]
        s.update(status='active', failures=0, observe_after=b['time_ms'])
        s.pop('reason', None)
        self.save()

    def reconcile_receptionist_warp(self, observations, ready, now_ms):
        """Reconcile Nilo's recorded receptionist warp, never replay the NPC."""
        s = self.state
        if (s.get('identity') != 'Nilo' or s.get('status') != 'blocked' or
                s.get('reason') != 'reward_mismatch:receptionist' or s.get('step') != 1 or
                s.get('instance') != 2 or s.get('phase') != 'tutorial' or
                s.get('inflight') is not None or s.get('destination') is not None):
            raise RuntimeError('Not the known receptionist mismatch')
        step = self.current()
        history, done = s.get('history', []), s.get('steps_done', [])
        if not history or not done:
            raise RuntimeError('Missing terminal evidence')
        h, record = history[-1], done[-1]
        r, action = h.get('result', {}), h.get('action', {})
        ev = r.get('evidence') or {}
        expected_action = {'type': 'npc_script', 'x': 100, 'y': 29, 'choices': ['Apply for training.'],
                           'name_reply': 1, 'timeout_s': 60, 'expect': {'map': 'new_1-2', 'x': 100, 'y': 70}}
        old_session = h.get('session')
        recovery = s.get('recoveries', [])
        if (step.get('id') != 'receptionist' or step.get('rewards') != {} or
                h.get('step') != 1 or h.get('request_id') != 'c_1' or not old_session or
                not recovery or recovery[-1].get('session') != old_session or action != expected_action or
                r.get('request_id') != 'c_1' or r.get('status') != 'completed' or r.get('reason') != 'warped' or
                ev.get('npc') != 'Receptionist#nv2' or ev.get('chosen') != ['Apply for training.'] or
                ev.get('name_sent') != 1 or ev.get('warped', {}).get('map') != 'new_1-2' or
                (ev.get('warped', {}).get('x'), ev.get('warped', {}).get('y')) != (100, 70) or
                (ev.get('before') or {}).get('map') != 'new_2-2' or
                (ev.get('after') or {}).get('map') != 'new_1-2' or
                (ev.get('before') or {}).get('inventory') != '1201:1,2301:1' or
                (ev.get('after') or {}).get('inventory') != '' or
                (ev.get('before') or {}).get('zeny') != 0 or (ev.get('after') or {}).get('zeny') != 0 or
                (ev.get('before') or {}).get('exp') != '1,0,1,0' or
                (ev.get('after') or {}).get('exp') != '1,0,1,0' or
                record.get('step') != 'receptionist' or record.get('items') != {'1201': -1, '2301': -1} or
                record.get('warp') != ev.get('warped')):
            raise RuntimeError('Terminal evidence does not match known warp')
        if len(observations) != 2 or not ready:
            raise RuntimeError('Missing observations')
        a, b = observations
        if (not a.get('session') or a['session'] != b.get('session') or a['session'] == old_session or
                ready.get('session') != a['session'] or ready.get('data', {}).get('pending_request_id', 'missing') is not None or
                ready.get('time_ms', now_ms + 1) > a['time_ms'] or b['time_ms'] - a['time_ms'] < 1000 or
                now_ms - a['time_ms'] > 5000 or not 0 <= now_ms - b['time_ms'] <= 2500):
            raise RuntimeError('Session or observation timing invalid')
        for e in observations:
            d = e['data']
            items = d.get('inventory')
            if (not d.get('connected') or d.get('name') != 'Nilo' or d.get('executor') != 'openkore_route' or
                    d.get('dead') or d.get('map') != 'new_1-2' or not d.get('inventory_ready') or
                    d.get('inventory_truncated') != 0 or not isinstance(items, list) or
                    d.get('zeny') != 0 or d.get('recovery') != 'none' or
                    'native_task' not in d or d['native_task'] is not None or
                    'navigation' not in d or d['navigation'] is not None or
                    not isinstance(d.get('ai_queue'), list) or d['ai_queue'] or
                    d.get('position') != {'x': 100, 'y': 70} or d.get('destination') != d.get('position') or
                    d.get('level') != {'base': 1, 'job': 1, 'exp': 0, 'job_exp': 0,
                                       'exp_max': d.get('level', {}).get('exp_max'),
                                       'job_exp_max': d.get('level', {}).get('job_exp_max')}):
                raise RuntimeError('Incomplete or unsafe current observation')
            totals = {}
            for item in items:
                key = str(item.get('name_id'))
                amount = item.get('amount')
                if type(amount) is not int or amount <= 0:
                    raise RuntimeError('Invalid inventory observation')
                totals[key] = totals.get(key, 0) + amount
            if totals != {'1201': 1, '2301': 1}:
                raise RuntimeError('Unexpected inventory effects')
        if a['data']['inventory'] != b['data']['inventory']:
            raise RuntimeError('Inventory changed between observations')
        s['reconciliations'] = s.get('reconciliations', []) + [{
            'kind': 'receptionist_warp_inventory', 'request_id': h['request_id'], 'original_session': old_session,
            'session': b['session'], 'observed_at_ms': [a['time_ms'], b['time_ms']],
            'map': b['data']['map'], 'position': b['data']['position'], 'inventory': {'1201': 1, '2301': 1},
            'zeny': 0, 'disposition': 'warp_observed_inventory_reconciled'}]
        s.update(status='active', failures=0, observe_after=b['time_ms'])
        s.pop('reason', None)
        self.advance({'step': 'receptionist_reconciliation', 'request_id': h['request_id'],
                      'original_session': old_session, 'observed_session': b['session']})

    def interruptible(self, snap, now=None):
        return False

    def current(self):
        s = self.state
        if s['step'] >= len(self.script['steps']):
            return None
        step = copy.deepcopy(self.script['steps'][s['step']])
        n = str(s['instance'] or 1)
        for key in ('map',):
            if key in step:
                step[key] = step[key].replace('{n}', n)
        if step['kind'] == 'script':
            choices = []
            for c in step['choices']:
                if c == '{answers}':
                    choices += self.script['personality_answers']
                elif c == '{job}':
                    choices.append(s['destination']['job'])
                else:
                    choices.append(c)
            step['choices'] = choices
            if step.get('expect') == '{destination}':
                step['expect'] = dict(s['destination']['landing'])
        return step

    def advance(self, record):
        s = self.state
        s['steps_done'] = (s['steps_done'] + [record])[-24:]
        s['step'] += 1
        s['failures'] = 0
        if s['step'] >= len(self.script['steps']):
            s.update(status='complete', reason='tutorial_left', phase='arrived')
        self.save()

    def needs_decision(self):
        step = self.current()
        return bool(self.state['status'] == 'active' and step and step['kind'] == 'decide' and not self.state['inflight'])

    def decide(self, choice, record):
        """Apply a validated destination (an offered option) at the decide step."""
        if not self.needs_decision() or not choice or not choice['offered']:
            raise RuntimeError('No destination decision is due or the option is not offered')
        self.state['destination'] = {k: choice[k] for k in ('job', 'town', 'landing', 'save')}
        self.advance({'step': 'destination', **record, 'job': choice['job'], 'town': choice['town']})

    def plan(self, snap, now=None):
        s = self.state
        if s['status'] != 'active' or s['inflight']:
            return None
        if not snap.get('connected') or not snap.get('inventory_ready'):
            return None
        if snap.get('name') != s['identity'] or snap.get('executor') != 'openkore_route':
            self.block('identity_or_executor_mismatch'); return None
        if snap.get('dead'):
            self.block('character_dead'); return None
        if snap.get('native_task') or snap.get('recovery') != 'none':
            return None
        if s['instance'] is None:
            if snap['map'] not in self.script['start_maps']:
                self.block('not_at_a_training_start'); return None
            s['instance'] = int(snap['map'].split('_')[1].split('-')[0])
            self.save()
        step = self.current()
        if step is None or step['kind'] == 'decide':
            return None
        here = snap['position']
        if step['kind'] == 'travel':
            if snap['map'] == step['map'] and dist(here, step) <= 1:
                self.advance({'step': step['id'], 'map': snap['map'], 'position': here}); return None
            return {'type': 'travel', 'map': step['map'], 'x': step['x'], 'y': step['y'], 'timeout_s': 120}
        if snap['map'] != step['map']:
            self.block(f'unexpected_map:{snap["map"]}'); return None
        if step['kind'] == 'portal':
            return {'type': 'portal', 'map': step['map'], 'x': step['x'], 'y': step['y'], 'timeout_s': 60}
        if dist(here, step['stand']) > STAND_RANGE:
            return {'type': 'navigate', 'map': step['map'], **step['stand'], 'timeout_s': 40}
        if not any(n.get('x') == step['x'] and n.get('y') == step['y'] for n in snap.get('npcs', [])):
            self.block(f'npc_not_seen:{step["id"]}'); return None
        action = {'type': 'npc_script', 'x': step['x'], 'y': step['y'], 'choices': step['choices'],
                  'name_reply': step['name_reply'], 'timeout_s': step['timeout_s']}
        if step.get('expect'):
            action['expect'] = step['expect']
        return action

    def prepare(self, action, request_id, session, now=None):
        if self.state['inflight'] or self.state['status'] != 'active':
            raise RuntimeError('Cannot replace unresolved intent')
        now = time.time() if now is None else now
        self.state['inflight'] = dict(action=copy.deepcopy(action), request_id=request_id, session=session,
                                      deadline=now + action['timeout_s'] + 12, prepared_at=now,
                                      step=self.state['step'])
        self.save()  # A crash after this write is uncertain and is never resent.

    def result(self, result, now=None, observed_after=0):
        s, p = self.state, self.state['inflight']
        if not p or result.get('request_id') != p['request_id'] or result.get('status') not in FINAL:
            return False
        s['observe_after'] = observed_after
        s['history'] = (s['history'] + [{**p, 'result': result}])[-24:]
        s['inflight'] = None
        kind, status, reason = p['action']['type'], result['status'], result.get('reason', '')
        step = self.current()
        if kind == 'npc_script':
            return self._script_result(step, p, result)
        if status == 'completed' and reason == SUCCESS[kind]:
            s['failures'] = 0
            if kind in ('portal', 'travel'):
                ev = result.get('evidence') or {}
                self.advance({'step': step['id'], 'map': ev.get('map'), 'position': ev.get('pos_to'),
                              'hops': ev.get('hops')})
            else:
                self.save()
            return True
        if status in {'unknown', 'cancelled', 'completed'}:
            self.block(f'{kind}:{status}/{reason}'); return True
        s['failures'] += 1
        if s['failures'] >= 2:
            self.block('two_consecutive_action_failures')
        else:
            self.save()
        return True

    def _script_result(self, step, p, result):
        s, ev = self.state, result.get('evidence') or {}
        status, reason = result['status'], result.get('reason', '')
        want = 'warped' if p['action'].get('expect') else 'conversation_closed'
        changed = ev.get('changed') or []
        if status == 'completed' and reason == want:
            got = inventory_delta((ev.get('before') or {}).get('inventory'), (ev.get('after') or {}).get('inventory'))
            expected = {k: v for k, v in step['rewards'].items()}
            record = {'step': step['id'], 'npc': step['npc'], 'chosen': ev.get('chosen'), 'pages': ev.get('pages'),
                      'warp': ev.get('warped'), 'items': got, 'zeny_before': (ev.get('before') or {}).get('zeny'),
                      'zeny_after': (ev.get('after') or {}).get('zeny'),
                      'exp_before': (ev.get('before') or {}).get('exp'), 'exp_after': (ev.get('after') or {}).get('exp')}
            if got != expected or record['zeny_before'] != record['zeny_after']:
                s['steps_done'] = (s['steps_done'] + [record])[-24:]
                self.block(f'reward_mismatch:{step["id"]}'); return True
            self.advance(record)
            return True
        # A dialog that moved us, paid us or gave items without its declared
        # ending needs review; a clean refusal or failure may be retried once.
        if status in {'unknown', 'cancelled'} or changed or status == 'completed':
            self.block(f'npc_script:{status}/{reason}'); return True
        s['failures'] += 1
        if s['failures'] >= 2:
            self.block('two_consecutive_action_failures')
        else:
            self.save()
        return True
