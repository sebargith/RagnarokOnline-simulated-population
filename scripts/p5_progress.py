"""Short live P5 step 2 run: build choice, then stats, skills and gear by local policy.

With --plan the planner role chooses or keeps one build from config/p5-builds.json
(stored in runtime/p1/cycle/build.json with its reason and facts); a failed or
late answer keeps the stored build. The deterministic policy then sends one
bridge action at a time and stops at the first result that is not 'completed'.
--cycle-equip NAME_ID takes one worn item off and puts it back, both confirmed
by the server. Requests are never resent; evidence goes to runtime/p1/evidence.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import build_policy
from agent.goal_planner import BuildPlanner, apply_build, read_build
from bridge.client import Bridge
from scripts.p1_hunt import Run


def progress_view(snap):
    p = snap['progress']
    return {'level': snap['level'], 'job': p['job'], 'points_free': p['points_free'], 'points_skill': p['points_skill'],
            'stats': {k: v['value'] for k, v in p['stats'].items()},
            'skills': {s['handle']: s['lv'] for s in p['skills']},
            'equipped': sorted((i['name_id'], i['name'], i['equipped']) for i in snap['inventory'] if i['equipped'])}


def choose(run, builds, path, lock, identity):
    from inference.roles import build_role
    service = build_role('planner')
    try:
        stored = read_build(path)
        current = stored and stored['build_id']
        planner = BuildPlanner(service, builds)
        started = time.monotonic()
        planner.request(run.fresh(), current)
        result = None
        while result is None:
            run.pump()
            result = planner.poll()
        latency = round(time.monotonic() - started, 2)
        if result['status'] != 'proposed':
            return {'outcome': result, 'latency_s': latency, 'role': service.status()}
        run.fresh()
        record = apply_build(path, lock, result, run.b.latest, identity)
        return {'outcome': record, 'proposal': result['proposal'], 'latency_s': latency}
    finally:
        service.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--plan', action='store_true', help='Ask the planner role to choose or keep the build')
    parser.add_argument('--max-actions', type=int, default=20)
    parser.add_argument('--cycle-equip', type=int, help='Worn item name_id to take off and put back')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')  # item names come from Korean client tables
    cycle = args.runtime/'p1/cycle'
    path, lock = cycle/'build.json', cycle/'build.lock'
    builds, equipment = build_policy.load_builds(), build_policy.load_equipment()
    run = Run(Bridge(args.runtime/'p1/openkore/solo/bridge.json'))
    summary, actions = {}, []
    start = time.monotonic()
    try:
        deadline = time.monotonic() + 15
        while run.snap is None or run.b.next_serial is None or 'progress' not in run.snap:
            if time.monotonic() >= deadline:
                raise RuntimeError('No ready bridge with progress state within 15 seconds')
            run.pump()
        snap = run.fresh()
        identity = snap['name']
        summary['start'] = progress_view(snap)
        if args.plan:
            summary['planner'] = choose(run, builds, path, lock, identity)
        stored = read_build(path)
        summary['build'] = stored and {k: stored[k] for k in ('build_id', 'reason', 'decision', 'served_by')}
        if args.cycle_equip:
            for kind in ('unequip', 'equip'):
                action = {'type': kind, 'name_id': args.cycle_equip, 'timeout_s': 10}
                result = run.ask(action, 15)
                actions.append({'action': action, 'why': 'cycle_check', 'result': result})
                if result['status'] != 'completed':
                    break
        if stored and all(a['result']['status'] == 'completed' for a in actions):
            build = builds[stored['build_id']]
            for _ in range(args.max_actions):
                action, why = build_policy.next_action(run.fresh(), build, equipment)
                if not action:
                    summary['policy_idle'] = why
                    break
                result = run.ask(action, action['timeout_s'] + 5)
                actions.append({'action': action, 'why': why, 'result': result})
                if result['status'] != 'completed':
                    summary['blocked'] = result['reason']
                    break
        summary['end'] = progress_view(run.fresh())
    finally:
        run.b.close()
    summary.update(actions=actions, wall_s=round(time.monotonic() - start, 1))
    out = args.runtime/'p1/evidence'/f'p5-progress-{int(time.time())}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'build': summary['build'], 'planner': summary.get('planner'),
        'actions': [(a['action'], a['result']['status'], a['result']['reason'], (a['result'].get('evidence') or {}).get('after'))
                    for a in actions], 'idle': summary.get('policy_idle'), 'blocked': summary.get('blocked'),
        'start': summary['start'], 'end': summary['end'], 'evidence': str(out)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
