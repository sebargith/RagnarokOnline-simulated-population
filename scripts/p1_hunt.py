"""Short live P1 hunt: native attack, pickup and local recovery, bounded evidence.

A deterministic loop picks the nearest visible monster from snapshots, asks the
bridge to attack it, then picks up drops that appear at the kill spot. Recovery
is the bridge's own policy; this runner only waits for it. No inference is
imported or called, requests are never resent, and the run ends by itself.
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

# Open, walkable cells of prt_fild08 visited in order when nothing is visible.
PATROL = [(150, 250), (175, 240), (160, 215), (135, 230), (140, 270), (170, 280)]
FINAL = {'completed', 'failed', 'cancelled', 'unknown', 'rejected'}


def dist(a, b):
    return max(abs(a['x'] - b['x']), abs(a['y'] - b['y']))


class Run:
    def __init__(self, bridge):
        self.b = bridge
        self.results, self.recovery, self.deaths = [], [], []
        self.progress = deque(maxlen=30)
        self.final = {}
        self.last_ask = 0

    def pump(self, seconds=.1):
        self.b.poll(seconds)
        for e in self.b.drain():
            kind, data = e['kind'], e['data']
            if kind == 'action_result':
                self.results.append(data)
                if data['status'] in FINAL:
                    self.final[data['request_id']] = data
            elif kind == 'recovery':
                self.recovery.append({**data, 'time_ms': e['time_ms']})
            elif kind == 'death':
                self.deaths.append(data)
            elif kind == 'task_progress':
                self.progress.append(data)

    @property
    def snap(self):
        return self.b.latest and self.b.latest['data']

    def fresh(self, timeout=3):
        end = time.monotonic() + timeout
        start = self.b.latest['time_ms'] if self.b.latest else 0
        while time.monotonic() < end and not (self.b.latest and self.b.latest['time_ms'] > start):
            self.pump()
        return self.snap

    def ask(self, action, bound):
        # The bridge admits one new action per second; wait instead of being refused.
        while time.monotonic() - self.last_ask < 1.05:
            self.pump()
        self.last_ask = time.monotonic()
        self.fresh()
        rid = self.b.serial_id()
        self.b.proposal(action, request_id=rid)
        end = time.monotonic() + bound
        while time.monotonic() < end and rid not in self.final:
            self.pump()
        return self.final.get(rid, {'request_id': rid, 'status': 'unknown', 'reason': 'runner_timeout'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--kills', type=int, default=3)
    parser.add_argument('--seconds', type=int, default=240)
    parser.add_argument('--probe', action='store_true', help='First attack is cancelled after 1 s; respawn is tried while alive')
    args = parser.parse_args()
    run = Run(Bridge(args.runtime/'p1/openkore/solo/bridge.json'))
    start = time.monotonic()
    tried, attacks, takes, navs, probe = set(), [], [], [], {}
    patrol = 0
    summary = {}
    try:
        while run.snap is None or run.b.next_serial is None:
            run.pump()
        summary['start'] = {k: run.snap.get(k) for k in ('map', 'position', 'hp', 'hp_max', 'level', 'inventory', 'executor')}
        kills = 0
        while kills < args.kills and time.monotonic() - start < args.seconds:
            s = run.fresh()
            if s['dead']:
                summary['respawn'] = run.ask({'type': 'respawn'}, 25)
                break
            if s['recovery'] != 'none':
                run.pump(.5)
                continue
            here = s['position']
            candidates = sorted((m for m in s['monsters'] if m['id'] not in tried), key=lambda m: dist(m, here))
            if not candidates:
                x, y = PATROL[patrol % len(PATROL)]
                patrol += 1
                navs.append(run.ask({'type': 'navigate', 'map': s['map'], 'x': x, 'y': y, 'timeout_s': 30}, 40))
                continue
            if args.probe and not probe:
                rid = run.b.serial_id()
                run.b.proposal({'type': 'attack', 'target': candidates[0]['id'], 'timeout_s': 30}, request_id=rid)
                run.last_ask = time.monotonic()
                end = time.monotonic() + 1
                while time.monotonic() < end:
                    run.pump()
                probe['cancel'] = run.ask({'type': 'cancel', 'target': rid}, 5)
                probe['attack'] = run.final.get(rid)
                probe['respawn_while_alive'] = run.ask({'type': 'respawn'}, 5)
                continue
            target = candidates[0]
            if dist(target, here) > 14:
                navs.append(run.ask({'type': 'navigate', 'map': s['map'], 'x': target['x'], 'y': target['y'],
                    'timeout_s': 30}, 40))
                continue
            tried.add(target['id'])
            result = run.ask({'type': 'attack', 'target': target['id'], 'timeout_s': 60}, 70)
            attacks.append({'target': target, 'result': result})
            if result['status'] != 'completed':
                continue
            kills += 1
            spot = {'x': target['x'], 'y': target['y']}
            settle = time.monotonic() + 2
            seen = set()
            while time.monotonic() < settle:
                s = run.fresh()
                for item in s['ground_items']:
                    if item['id'] not in seen and dist(item, spot) <= 4 and len(seen) < 3:
                        seen.add(item['id'])
                        takes.append({'item': item, 'result': run.ask(
                            {'type': 'take', 'target': item['id'], 'timeout_s': 15}, 25)})
        s = run.fresh()
        summary['end'] = {k: s.get(k) for k in ('map', 'position', 'hp', 'hp_max', 'level', 'inventory', 'recovery', 'dead')}
    finally:
        run.b.close()
    summary.update(probe=probe, kills=sum(a['result']['status'] == 'completed' for a in attacks),
        attacks=attacks, takes=takes, navigations=navs, recovery=run.recovery, deaths=run.deaths,
        progress=list(run.progress), wall_s=round(time.monotonic() - start, 1), inference_calls=0)
    out = args.runtime/'p1/evidence'/f'hunt-{int(time.time())}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({'probe': {k: (v or {}).get('reason') for k, v in probe.items()}, 'kills': summary['kills'],
        'attacks': [(a['target']['name'], a['result']['status'], a['result']['reason'],
                     (a['result'].get('evidence') or {}).get('first_hit_ms')) for a in attacks],
        'takes': [(t['item']['name_id'], t['result']['status'], t['result']['reason']) for t in takes],
        'recovery': [(r['phase'], r['hp'], r.get('hit_to_decision_ms'), r.get('hp_update_to_decision_ms')) for r in run.recovery],
        'deaths': len(run.deaths), 'end': summary['end'], 'wall_s': summary['wall_s'], 'evidence': str(out)}))


if __name__ == '__main__':
    main()
