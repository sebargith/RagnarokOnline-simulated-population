"""Short live P2b run: a local, model-free supply decision and one shop trip.

Decides from the observed snapshot whether to sell loot and buy healing, then
travels (walk portals only) to a known shop, sells, buys and returns. Each step
is sent once and never resent; the run stops at the first step that ends
failed/unknown/cancelled. No inference is imported or called.
"""
import argparse
from collections import deque
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.client import Bridge

FINAL = {'completed', 'failed', 'cancelled', 'unknown', 'rejected'}
ETC, HEAL = 3, 0
LOOT_MIN, WEIGHT_SELL, HEAL_TARGET, MAX_LINES = 5, 40, 1, 8
# Known shop: rAthena npc/merchants/shops.txt. Prices are what the server
# listed there; the bridge always re-reads the server's list before trading.
SHOP = {'name': 'Fruit Gardener', 'map': 'prontera', 'npc': (104, 49), 'stand': (104, 51), 'sells': {512: 15}}


def decide(snap, shop=SHOP):
    """Need from observable state only: loot count, weight, healing and Zeny."""
    inv = snap.get('inventory') or []
    if not snap.get('inventory_ready') or not inv:
        # Never decide on a bag that has not been observed yet.
        return {'go': False, 'sell': [], 'need_heal': 0, 'reasons': ['inventory_not_observed'], 'observed': {}}
    loot = {}
    for item in inv:
        if item.get('type') == ETC and not item.get('equipped'):
            loot[item['name_id']] = loot.get(item['name_id'], 0) + item['amount']
    loot_count = sum(loot.values())
    weight_max = snap.get('weight_max') or 0
    weight_pct = round(100 * snap.get('weight', 0) / weight_max, 1) if weight_max else 0
    healing = sum(i['amount'] for i in inv if i.get('type') == HEAL)
    reasons = []
    if loot_count >= LOOT_MIN:
        reasons.append(f'loot {loot_count} >= {LOOT_MIN}')
    if weight_pct >= WEIGHT_SELL:
        reasons.append(f'weight {weight_pct}% >= {WEIGHT_SELL}%')
    sell = [{'name_id': k, 'amount': v} for k, v in sorted(loot.items())][:MAX_LINES] if reasons else []
    need_heal = max(0, HEAL_TARGET - healing)
    if need_heal:
        reasons.append(f'healing {healing} < {HEAL_TARGET}')
    cheapest = min(shop['sells'].values())
    go = bool(sell) or bool(need_heal and snap.get('zeny', 0) >= cheapest)
    return {'go': go, 'sell': sell, 'need_heal': need_heal, 'reasons': reasons,
        'observed': {'loot': loot_count, 'weight_pct': weight_pct, 'healing': healing, 'zeny': snap.get('zeny', 0)}}


def buy_plan(snap, need, shop=SHOP):
    """Cheapest healing the observed Zeny affords, up to the need."""
    item, price = min(shop['sells'].items(), key=lambda kv: kv[1])
    count = min(need, snap.get('zeny', 0) // price)
    return ([{'name_id': item, 'amount': count}], count * price) if count else ([], 0)


def view(snap):
    return {k: snap.get(k) for k in ('map', 'position', 'destination', 'zeny', 'weight', 'weight_max')} | {
        'inventory_detail': snap.get('inventory') or [],
        'inventory': {i['name_id']: i['amount'] for i in snap.get('inventory') or []}}


class Session:
    def __init__(self, bridge):
        self.b, self.queues, self.events, self.steps = bridge, set(), deque(maxlen=60), []
        self.current, self.ready_at = None, 0

    def pump(self):
        self.b.poll(.1)
        for e in self.b.drain():
            kind, data = e['kind'], e['data']
            if kind == 'snapshot':
                self.queues.update(data.get('ai_queue') or [])
            elif kind == 'action_result' and self.current and data['request_id'] == self.current['id']:
                self.current['results'].append(data)
                if data['status'] in FINAL:
                    self.current['final'] = data
            elif kind in ('travel_hop', 'recovery', 'death', 'connection'):
                self.events.append({'kind': kind, 'data': data})

    def snap(self, fresh_after=None, inventory=False):
        """Latest snapshot; with fresh_after (epoch ms), one emitted after it;
        with inventory, one whose inventory has been received."""
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            latest = self.b.latest
            if latest and latest['data']['connected'] and self.b.next_serial is not None and \
                    (fresh_after is None or latest['time_ms'] > fresh_after) and                     (not inventory or (latest['data'].get('inventory_ready') and latest['data'].get('inventory'))):
                return latest['data']
            self.pump()
        raise RuntimeError('No connected snapshot')

    def step(self, action):
        while time.monotonic() < self.ready_at:
            self.pump()
        begin = self.snap()
        rid = self.b.serial_id()
        self.current = {'action': action, 'id': rid, 'begin': view(begin), 'results': []}
        sent = time.monotonic()
        self.b.proposal(action, request_id=rid)
        while 'final' not in self.current and time.monotonic() - sent < action['timeout_s'] + 15:
            self.pump()
        step, self.current = self.current, None
        step.setdefault('final', {'status': 'unknown', 'reason': 'runner_timeout'})
        step['wall_s'] = round(time.monotonic() - sent, 2)
        step['end'] = view(self.snap(fresh_after=int(time.time() * 1000)))
        self.steps.append(step)
        self.ready_at = time.monotonic() + 1.2
        return step['final']


def ok(final):
    return final['status'] in ('completed', 'rejected')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--probe', action='store_true', help='Also send two must-reject requests at the shop')
    args = parser.parse_args()
    b = Bridge(args.runtime/'p1/openkore/solo/bridge.json')
    s = Session(b)
    summary = {}
    start = time.monotonic()
    try:
        s.snap(inventory=True)
        # Equipment and stackable lists arrive in separate packets: decide on a later snapshot.
        first = s.snap(fresh_after=int(time.time() * 1000) + 1500, inventory=True)
        origin = {'map': first['map'], 'x': first['destination']['x'], 'y': first['destination']['y']}
        decision = decide(first)
        summary.update(start=view(first), decision=decision)
        x, y = SHOP['npc']
        if decision['go']:
            final = {'status': 'completed'}
            if first['map'] != SHOP['map']:
                final = s.step({'type': 'travel', 'map': SHOP['map'], 'x': SHOP['stand'][0], 'y': SHOP['stand'][1],
                    'timeout_s': 150})
            if ok(final) and decision['sell']:
                final = s.step({'type': 'npc_sell', 'x': x, 'y': y, 'items': decision['sell'], 'timeout_s': 20})
            if ok(final) and args.probe:
                equipped = [i['name_id'] for i in s.snap()['inventory'] if i.get('equipped')][:1]
                if equipped:
                    s.step({'type': 'npc_sell', 'x': x, 'y': y, 'items': [{'name_id': equipped[0], 'amount': 1}],
                        'timeout_s': 20})
                s.step({'type': 'npc_buy', 'x': x, 'y': y, 'items': [{'name_id': 512, 'amount': 1}],
                    'max_zeny': s.snap()['zeny'] + 1000, 'timeout_s': 20})
            if ok(final) and decision['need_heal']:
                items, cost = buy_plan(s.snap(fresh_after=int(time.time() * 1000)), decision['need_heal'])
                summary['buy_plan'] = {'items': items, 'cost': cost}
                if items:
                    final = s.step({'type': 'npc_buy', 'x': x, 'y': y, 'items': items, 'max_zeny': cost, 'timeout_s': 20})
            if ok(final) and origin['map'] != SHOP['map']:
                s.step({'type': 'travel', **origin, 'timeout_s': 150})
        summary['end'] = view(s.snap(fresh_after=int(time.time() * 1000)))
    finally:
        b.close()
    summary.update(steps=s.steps, events=list(s.events), ai_queues_seen=sorted(s.queues),
        map_route_seen='mapRoute' in s.queues, wall_s=round(time.monotonic() - start, 2), inference_calls=0)
    out = args.runtime/'p1/evidence'/f'supply-{int(time.time())}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({'decision': {k: decision[k] for k in ('go', 'sell', 'need_heal', 'reasons')},
        'steps': [{'action': st['action']['type'], 'final': st['final']['status'] + '/' + st['final']['reason'],
            'wall_s': st['wall_s']} for st in s.steps],
        'start_zeny': summary['start']['zeny'], 'end': summary['end'], 'map_route_seen': summary['map_route_seen'],
        'evidence': str(out)}))


if __name__ == '__main__':
    main()
