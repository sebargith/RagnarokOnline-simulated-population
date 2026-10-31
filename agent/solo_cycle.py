"""Persistent bounded solo policy. Decisions use one character's observations.

No bridge IO or model calls here. A checkpointed intent is never proposed twice.
Only its matching terminal result can advance confirmed progress.
"""
import copy
import json
import os
from pathlib import Path
import time

from scripts.p1_hunt import dist
from scripts.p2_supply import SHOP, buy_plan, decide

FINAL = {'completed', 'failed', 'cancelled', 'unknown', 'rejected'}
SUCCESS = {'attack': 'killed', 'take': 'picked_up', 'navigate': 'arrived',
           'travel': 'arrived', 'npc_sell': 'sold', 'npc_buy': 'bought'}


class SoloCycle:
    def __init__(self, path, goal_kills=6):
        self.path = Path(path)
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding='utf-8'))
            if self.state.get('version') != 1 or self.state.get('identity') != 'Tarin':
                raise ValueError('Unsupported cycle checkpoint')
        else:
            if not 1 <= goal_kills <= 100:
                raise ValueError('goal_kills must be 1..100')
            self.state = dict(version=1, identity='Tarin', goal_kills=goal_kills,
                kills=0, phase='hunt', status='active', inflight=None, history=[],
                failures=0, skip={}, patrol=0, loot_until=0, loot_spot=None,
                return_to={'map': 'prt_fild08', 'x': 170, 'y': 365}, observe_after=0)
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

    def reconcile_navigation(self, observations, now_ms):
        """Retire only a known-ended uncertain route, without claiming arrival."""
        s, p = self.state, self.state.get('inflight')
        if (s.get('status') != 'blocked' or s.get('reason') != 'navigate:unknown/route_ended_off_target'
                or s.get('phase') != 'hunt' or not p or p['action'].get('type') != 'navigate'):
            raise RuntimeError('Not a reconcilable navigation result')
        matches = [h for h in s['history'] if h.get('request_id') == p['request_id']
                   and h.get('session') == p['session'] and h.get('result', {}).get('status') == 'unknown'
                   and h['result'].get('reason') == 'route_ended_off_target']
        if len(matches) != 1 or len(observations) != 2:
            raise RuntimeError('Missing unique terminal evidence or observations')
        a, b = observations
        if (a['session'] != b['session'] or b['session'] == p['session'] or b['time_ms'] - a['time_ms'] < 1000 or
                now_ms - a['time_ms'] > 5000 or now_ms - b['time_ms'] < 0 or now_ms - b['time_ms'] > 2500):
            raise RuntimeError('Observations are not fresh and separated')
        for event in observations:
            snap = event['data']
            if (not snap.get('connected') or snap.get('name') != s['identity'] or
                    snap.get('executor') != 'openkore_route' or snap.get('dead') or
                    snap.get('map') != p['action']['map'] or 'native_task' not in snap or snap.get('native_task') or
                    not isinstance(snap.get('ai_queue'), list) or
                    any(x in (snap.get('ai_queue') or []) for x in ('move', 'route', 'mapRoute')) or
                    not snap.get('position') or not snap.get('destination') or
                    dist(snap['position'], snap['destination']) > 1):
                raise RuntimeError('Character is not stationary and safe to replan')
        if a['data']['position'] != b['data']['position']:
            raise RuntimeError('Position changed between observations')
        s['reconciliations'] = (s.get('reconciliations', []) + [{
            'request_id': p['request_id'], 'session': p['session'],
            'disposition': 'retired_unknown_not_arrived', 'observed_session': b['session'],
            'map': b['data']['map'], 'position': b['data']['position'],
            'observed_at_ms': b['time_ms']}])[-24:]
        s['avoid_route'] = {'map': p['action']['map'], 'x': p['action']['x'],
                            'y': p['action']['y'], 'until': now_ms / 1000 + 60}
        s.update(status='active', inflight=None, failures=s.get('failures', 0) + 1,
                 patrol=s['patrol'] + 1, observe_after=b['time_ms'])
        s.pop('reason', None)
        if s['failures'] >= 2:
            s.update(status='blocked', reason='two_consecutive_action_failures')
        self.save()

    def set_goal(self, target):
        """Set an absolute cumulative target, preserving all confirmed history."""
        s = self.state
        if not isinstance(target, int) or isinstance(target, bool) or not 1 <= target <= 100:
            raise ValueError('goal must be an integer between 1 and 100')
        if target == s['goal_kills'] and s['status'] in {'active', 'complete'} and not s['inflight']:
            return False  # An identical request is idempotent.
        if (s['status'] != 'complete' or s.get('reason') != 'confirmed_kill_goal' or
                s['phase'] != 'hunt' or s['inflight'] or s['kills'] < s['goal_kills']):
            raise RuntimeError('A new goal requires a completed goal without an unresolved intent')
        if target <= s['kills']:
            raise ValueError('New goal must exceed confirmed kills')
        s['goal_history'] = (s.get('goal_history', []) + [
            {'goal_kills': s['goal_kills'], 'confirmed_kills': s['kills']}])[-24:]
        s.update(goal_kills=target, status='active', phase='hunt', failures=0)
        s.pop('reason', None)
        self.save()
        return True

    def prepare(self, action, request_id, session, now=None):
        if self.state['inflight'] or self.state['status'] != 'active':
            raise RuntimeError('Cannot replace unresolved intent')
        now = time.time() if now is None else now
        self.state['inflight'] = dict(action=copy.deepcopy(action), request_id=request_id,
            session=session, deadline=now + action['timeout_s'] + 12)
        if getattr(self, '_exploration', None) == action:
            self.state['inflight']['exploration'] = True
            visits = self.state.get('explore_visits', [])
            self.state['explore_visits'] = (visits + [self._explore_origin,
                {'map': action['map'], 'x': action['x'], 'y': action['y']}])[-24:]
        self._exploration = None
        # Failure here prevents proposal. A crash after this write is uncertain.
        self.save()

    def result(self, result, now=None, observed_after=0):
        p = self.state['inflight']
        if not p or result.get('request_id') != p['request_id'] or result.get('status') not in FINAL:
            return False
        now = time.time() if now is None else now
        s, action = self.state, p['action']
        s['observe_after'] = observed_after
        kind, reason = action['type'], result.get('reason', '')
        s['history'] = (s['history'] + [{**p, 'result': result}])[-24:]
        if result['status'] == 'completed' and reason == SUCCESS[kind]:
            s['inflight'], s['failures'] = None, 0
            if kind == 'attack':
                s['kills'] += 1
                s.update(phase='loot', loot_until=now + 2)
            elif kind == 'npc_sell':
                s['phase'] = 'buy'
            elif kind == 'npc_buy':
                s['phase'] = 'return'
            elif kind == 'travel':
                s['phase'] = 'sell' if s['phase'] == 'to_shop' else 'hunt'
            elif kind == 'navigate':
                s['patrol'] += 1
            self.save()
            return True
        # Unknown effects, all shop/travel errors and cancellation need review.
        if result['status'] in {'unknown', 'cancelled', 'completed'} or kind in {'npc_buy', 'npc_sell', 'travel'}:
            self.block(f'{kind}:{result["status"]}/{reason}')
            return True
        s['inflight'] = None
        if reason not in {'recovering', 'hp_too_low', 'retreat_low_hp'}:
            s['failures'] += 1
        if kind == 'attack':
            s['skip'][action['target']] = now + 60
        s['phase'] = 'hunt'
        if s['failures'] >= 2:
            self.block('two_consecutive_action_failures')
        else:
            self.save()
        return True

    def interruptible(self, snap, now=None):
        """Only an explicitly marked exploration route can be interrupted."""
        now = time.time() if now is None else now
        s, p = self.state, self.state.get('inflight')
        return bool(s['status'] == 'active' and p and p.get('exploration') and
            not p.get('cancel') and now >= s.get('interrupt_after', 0) and
            snap.get('connected') and snap.get('name') == s['identity'] and
            snap.get('executor') == 'openkore_route' and not snap.get('dead') and
            snap.get('recovery') == 'none' and snap.get('hp', 0) > 0 and
            snap.get('hp_max', 0) > 0 and snap['hp'] * 100 >= snap['hp_max'] * 60 and
            snap.get('map') == p['action']['map'] and
            snap.get('native_task') == {'id': p['request_id'], 'kind': 'navigation'} and
            any(m.get('eligible') == 1 and s['skip'].get(m.get('id'), 0) <= now and
                not ((s.get('avoid_route') or {}).get('until', 0) > now and
                     (s.get('avoid_route') or {}).get('map') == snap['map'] and
                     m.get('x') == (s.get('avoid_route') or {}).get('x') and
                     m.get('y') == (s.get('avoid_route') or {}).get('y'))
                for m in snap.get('monsters', [])))

    def prepare_cancel(self, request_id):
        p = self.state['inflight']
        if not p or not p.get('exploration') or p.get('cancel'):
            raise RuntimeError('Cannot cancel this intent')
        p['cancel'] = {'request_id': request_id, 'results': {}}
        self.save()  # Never resend after a crash or uncertain send.

    def cancel_result(self, result, observed_after):
        p = self.state.get('inflight')
        c = p and p.get('cancel')
        if not c or result.get('status') not in FINAL:
            return False
        rid = result.get('request_id')
        if rid not in (p['request_id'], c['request_id']):
            return False
        c['results'][rid] = result
        s = self.state
        s['observe_after'] = max(s.get('observe_after', 0), observed_after)
        expected = (('cancelled', 'cancel_requested') if rid == p['request_id']
                    else ('completed', 'navigation_cancelled'))
        if (result['status'], result.get('reason')) != expected:
            self.block('exploration_cancel_unconfirmed'); return True
        if len(c['results']) == 2:
            s['history'] = (s['history'] + [{**p, 'result': c['results'][p['request_id']]}])[-24:]
            s.update(inflight=None, interrupt_after=time.time() + 5)
        self.save()
        return True

    @staticmethod
    def supply(snap):
        need = decide(snap)
        # Only the implemented recovery item counts as usable healing.
        apple = sum(i['amount'] for i in snap['inventory'] if i['name_id'] == 512)
        need['need_heal'] = max(0, 1 - apple)
        need['go'] = bool(need['sell']) or bool(need['need_heal'] and snap['zeny'] >= 15)
        return need

    def plan(self, snap, now=None):
        """Return one capability or None (wait/stopped). No game side effects."""
        s = self.state
        self._exploration = None
        now = time.time() if now is None else now
        if s['status'] != 'active' or s['inflight']:
            return None
        if not snap.get('connected') or not snap.get('inventory_ready'):
            return None
        if snap.get('name') != s['identity'] or snap.get('executor') != 'openkore_route':
            self.block('identity_or_executor_mismatch'); return None
        if snap.get('inventory_truncated', True):
            self.block('incomplete_inventory'); return None
        if snap.get('dead'):
            self.block('character_dead'); return None
        if snap.get('recovery') == 'exhausted':
            self.block('recovery_exhausted'); return None
        if snap.get('native_task') or snap.get('recovery') != 'none' or snap['hp'] * 100 < snap['hp_max'] * 60:
            return None
        # Bounded local phase changes; each loop either moves phase or returns.
        for _ in range(8):
            phase = s['phase']
            if phase == 'loot':
                spot = s['loot_spot'] or snap['position']
                drops = [i for i in snap['ground_items'] if dist(i, spot) <= 4]
                if drops:
                    return {'type': 'take', 'target': drops[0]['id'], 'timeout_s': 15}
                if now < s['loot_until']:
                    return None
                s['phase'] = 'hunt'
            elif phase == 'hunt':
                need = self.supply(snap)
                if need['go']:
                    if snap['map'] == 'prt_fild08':
                        s['return_to'] = {'map': snap['map'], **snap['position']}
                    s['phase'] = 'to_shop'
                elif s['kills'] >= s['goal_kills']:
                    s.update(status='complete', reason='confirmed_kill_goal'); self.save(); return None
                elif snap['map'] != 'prt_fild08':
                    s['phase'] = 'return'
                else:
                    s['skip'] = {k: v for k, v in s['skip'].items() if v > now}
                    avoid = s.get('avoid_route') or {}
                    monsters = sorted((m for m in snap['monsters'] if m.get('eligible', 1) == 1 and m['id'] not in s['skip'] and not
                        (avoid.get('until', 0) > now and avoid.get('map') == snap['map'] and
                         m['x'] == avoid.get('x') and m['y'] == avoid.get('y'))),
                                      key=lambda m: dist(m, snap['position']))
                    if monsters:
                        m = monsters[0]
                        if dist(m, snap['position']) > 14:
                            return {'type': 'navigate', 'map': snap['map'], 'x': m['x'], 'y': m['y'], 'timeout_s': 25}
                        s['loot_spot'] = {'x': m['x'], 'y': m['y']}
                        return {'type': 'attack', 'target': m['id'], 'timeout_s': 45}
                    candidates = snap.get('explore_candidates')
                    if not isinstance(candidates, list):
                        self.block('exploration_candidates_unavailable'); return None
                    avoid = s.get('avoid_route') or {}
                    candidates = [p for p in candidates if isinstance(p, dict) and
                        type(p.get('x')) is int and type(p.get('y')) is int and
                        dist(p, snap['position']) > 1 and not
                        (avoid.get('until', 0) > now and avoid.get('map') == snap['map'] and
                         p['x'] == avoid.get('x') and p['y'] == avoid.get('y'))]
                    if not candidates:
                        self.block('exploration_no_reachable_candidate'); return None
                    visits = [p for p in s.get('explore_visits', []) if p.get('map') == snap['map']]
                    # Prefer the least recently covered area; deterministic ties
                    # favor longer rays, then rotate according to completed routes.
                    def score(p):
                        nearest = min((dist(p, v) for v in visits), default=1000)
                        return (nearest, dist(p, snap['position']))
                    best = max(score(p) for p in candidates)
                    choices = [p for p in candidates if score(p) == best]
                    target = choices[s['patrol'] % len(choices)]
                    action = {'type': 'navigate', 'map': snap['map'], **target, 'timeout_s': 25}
                    self._exploration, self._explore_origin = action.copy(), {'map': snap['map'], **snap['position']}
                    return action
            elif phase == 'to_shop':
                stand = {'x': SHOP['stand'][0], 'y': SHOP['stand'][1]}
                if snap['map'] == SHOP['map'] and dist(snap['position'], stand) <= 1:
                    s['phase'] = 'sell'
                else:
                    return {'type': 'travel', 'map': SHOP['map'], **stand, 'timeout_s': 150}
            elif phase == 'sell':
                sell = self.supply(snap)['sell']
                if sell:
                    return {'type': 'npc_sell', 'x': SHOP['npc'][0], 'y': SHOP['npc'][1],
                            'items': sell, 'timeout_s': 20}
                s['phase'] = 'buy'
            elif phase == 'buy':
                items, cost = buy_plan(snap, self.supply(snap)['need_heal'])
                if items:
                    return {'type': 'npc_buy', 'x': SHOP['npc'][0], 'y': SHOP['npc'][1],
                            'items': items, 'max_zeny': cost, 'timeout_s': 20}
                s['phase'] = 'return'
            elif phase == 'return':
                home = s['return_to']
                if snap['map'] == home['map'] and dist(snap['position'], home) <= 1:
                    s['phase'] = 'hunt'
                else:
                    return {'type': 'travel', **home, 'timeout_s': 150}
            else:
                self.block('invalid_phase'); return None
        self.block('phase_transition_limit')
        return None
