"""Short live P1 run: one native navigation request, optional cancel, bounded evidence.

No inference is imported or called. Terminates on the bridge's final result or
on its own wall-clock bound; it never resends a request.
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--x', type=int, required=True)
    parser.add_argument('--y', type=int, required=True)
    parser.add_argument('--map', help='Defaults to the observed current map')
    parser.add_argument('--timeout', type=int, default=60)
    parser.add_argument('--cancel-after', type=float, help='Seconds after acceptance')
    args = parser.parse_args()
    b = Bridge(args.runtime/'p1/openkore/solo/bridge.json')
    progress, others, results = deque(maxlen=20), deque(maxlen=40), []
    nav_id = cancel_id = accepted_at = None
    start = time.monotonic()
    bound = 10 + args.timeout + 15
    summary = {'request': None, 'final': None}
    try:
        while time.monotonic() - start < bound:
            b.poll(.1)
            for e in b.drain():
                kind, data = e['kind'], e['data']
                if kind == 'navigation_progress':
                    progress.append(data)
                elif kind == 'action_result':
                    results.append(data)
                    if data['request_id'] == nav_id and data['status'] == 'accepted':
                        accepted_at = time.monotonic()
                    elif data['request_id'] == nav_id and data['status'] in FINAL:
                        summary['final'] = data
                elif kind != 'snapshot':
                    others.append({'kind': kind, 'data': data})
            if summary['final']:
                break
            snap = b.latest and b.latest['data']
            if nav_id is None and snap and snap['connected'] and b.next_serial is not None:
                action = {'type': 'navigate', 'map': args.map or snap['map'], 'x': args.x, 'y': args.y,
                    'timeout_s': args.timeout}
                summary['start'] = {'map': snap['map'], 'position': snap['position'], 'executor': snap.get('executor')}
                nav_id = b.serial_id()
                summary['request'] = b.proposal(action, request_id=nav_id)
            if (args.cancel_after is not None and accepted_at and cancel_id is None and
                    time.monotonic() - accepted_at >= args.cancel_after):
                cancel_id = b.serial_id()
                b.proposal({'type': 'cancel', 'target': nav_id}, request_id=cancel_id)
        else:
            summary['final'] = {'status': 'unknown', 'reason': 'runner_timeout'}
        # Bridge snapshots are 1 Hz; wait for one emitted after the final result.
        settle = time.monotonic() + 2.5
        final_ms = int(time.time() * 1000)
        while time.monotonic() < settle and not (b.latest and b.latest['time_ms'] > final_ms + 1000):
            b.poll(.1)
            for e in b.drain():
                if e['kind'] == 'action_result':
                    results.append(e['data'])
        if b.latest:
            d = b.latest['data']
            summary['end'] = {'map': d.get('map'), 'position': d.get('position'), 'navigation': d.get('navigation')}
    finally:
        b.close()
    summary.update(results=results, progress=list(progress), events=list(others),
        wall_s=round(time.monotonic() - start, 2), inference_calls=0)
    out = args.runtime/'p1/evidence'/f'nav-{int(time.time())}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({'final': summary['final'], 'start': summary.get('start'), 'end': summary.get('end'),
        'progress_events': len(progress), 'evidence': str(out)}))


if __name__ == '__main__':
    main()
