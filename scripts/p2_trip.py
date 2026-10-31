"""Short live P2a run: a fixed list of travel / npc_talk steps, bounded evidence.

Steps: travel:MAP:X:Y or talk:X:Y[:Label|Label]. No inference is imported or
called. Each step is sent once and never resent; the run stops at the first
step that ends failed/unknown/cancelled (a rejection is recorded and the next
step follows, so negative cases can be listed last).
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


def parse(step, timeout):
    kind, *rest = step.split(':')
    if kind == 'travel' and len(rest) == 3:
        return {'type': 'travel', 'map': rest[0], 'x': int(rest[1]), 'y': int(rest[2]), 'timeout_s': timeout}
    if kind == 'talk' and len(rest) in (2, 3):
        choices = rest[2].split('|') if len(rest) == 3 and rest[2] else []
        return {'type': 'npc_talk', 'x': int(rest[0]), 'y': int(rest[1]), 'choices': choices,
            'timeout_s': min(timeout, 60)}
    raise SystemExit(f'Bad step: {step}')


def view(snap):
    return {k: snap.get(k) for k in ('map', 'position', 'destination', 'zeny', 'hp', 'hp_max')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--timeout', type=int, default=120, help='Per travel step')
    parser.add_argument('steps', nargs='+')
    args = parser.parse_args()
    actions = [parse(s, args.timeout) for s in args.steps]
    b = Bridge(args.runtime/'p1/openkore/solo/bridge.json')
    events, steps = deque(maxlen=60), []
    queues_seen = set()
    current = sent_at = None
    ready_at = 0
    start = time.monotonic()
    bound = 15 + sum(a['timeout_s'] + 15 for a in actions)
    summary = {'start': None}
    try:
        while time.monotonic() - start < bound and (actions or current):
            b.poll(.1)
            for e in b.drain():
                kind, data = e['kind'], e['data']
                if kind == 'snapshot':
                    queues_seen.update(data.get('ai_queue') or [])
                elif kind == 'action_result' and current and data['request_id'] == current['id']:
                    current['results'].append(data)
                    if data['status'] in FINAL:
                        current['final'] = data
                elif kind in ('travel_progress', 'task_progress'):
                    if current:
                        current['progress'] += 1
                elif kind in ('travel_hop', 'recovery', 'death', 'connection'):
                    events.append({'kind': kind, 'data': data})
            snap = b.latest and b.latest['data']
            if current and current.get('final'):
                current['wall_s'] = round(time.monotonic() - sent_at, 2)
                current['end'] = view(snap) if snap else None
                steps.append(current)
                if current['final']['status'] != 'rejected' and current['final']['status'] != 'completed':
                    break
                current, ready_at = None, time.monotonic() + 1.5
            if current is None and actions and snap and snap['connected'] and b.next_serial is not None and \
                    time.monotonic() >= ready_at:
                summary['start'] = summary['start'] or view(snap)
                action = actions.pop(0)
                rid = b.serial_id()
                current = {'action': action, 'id': rid, 'begin': view(snap), 'results': [], 'progress': 0}
                b.proposal(action, request_id=rid)
                sent_at = time.monotonic()
        else:
            if current:
                current['final'] = {'status': 'unknown', 'reason': 'runner_timeout'}
                steps.append(current)
        settle = time.monotonic() + 2.5
        while time.monotonic() < settle:
            b.poll(.1)
            b.drain()
        summary['end'] = view(b.latest['data']) if b.latest else None
    finally:
        b.close()
    summary.update(steps=steps, events=list(events), ai_queues_seen=sorted(queues_seen),
        map_route_seen='mapRoute' in queues_seen, not_run=[a for a in actions],
        wall_s=round(time.monotonic() - start, 2), inference_calls=0)
    out = args.runtime/'p1/evidence'/f'trip-{int(time.time())}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({'steps': [{'action': s['action']['type'], 'final': s['final']['status'] + '/' + s['final']['reason'],
        'wall_s': s.get('wall_s'), 'end': s.get('end')} for s in steps], 'start': summary['start'],
        'end': summary['end'], 'map_route_seen': summary['map_route_seen'], 'evidence': str(out)}))


if __name__ == '__main__':
    main()
