"""Freeze the old P5 cycle when Nilo moves to the R1 executor (one-time, idempotent).

Under the cycle lock: the checkpoint's in-flight action is reconciled only with its
final result already recorded in events.jsonl (never resent, never guessed); the
status becomes frozen/migrated_to_r1 and events.jsonl is kept untouched. A stale
client registry (its process gone) is archived and removed, and FROZEN.json makes
run_p5_background.py refuse to launch. Refuses while the registered client runs.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.live_io import atomic_json, exclusive
from scripts.run_r1 import alive


def final_result(events, request_id):
    """The last non-accepted action_result for request_id, or None."""
    found = None
    for line in events.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get('kind') == 'action_result' and e['data'].get('request_id') == request_id and e['data'].get('status') != 'accepted':
            found = e
    return found


def freeze(base, now=None):
    now = time.time() if now is None else now
    cycle, registry, marker = base/'cycle', base/'processes.json', base/'FROZEN.json'
    if marker.exists():
        return json.loads(marker.read_text())
    if registry.exists():
        for name, info in json.loads(registry.read_text()).items():
            if alive(info['pid']):
                raise RuntimeError(f'{name} (PID {info["pid"]}) is running; stop it first')
    archive = base/'evidence/frozen'
    archive.mkdir(parents=True, exist_ok=True)
    with exclusive(cycle/'cycle.lock'):
        for name in ('state.json', 'status.json'):  # the checkpoint as it was
            shutil.copyfile(cycle/name, archive/f'{name[:-5]}-before.json')
        state = json.loads((cycle/'state.json').read_text())
        record = {'frozen_at': now, 'reason': 'migrated_to_r1', 'previous_status': state['status'],
                  'previous_reason': state.get('reason'), 'kills': state['kills'], 'inflight': None}
        inflight = state.get('inflight')
        if inflight:
            result = final_result(cycle/'events.jsonl', inflight['request_id'])
            if not result:
                raise RuntimeError(f'{inflight["request_id"]} has no recorded final result; reconcile it on the bridge')
            entry = {'request_id': inflight['request_id'], 'session': inflight['session'], 'action': inflight['action'],
                     'disposition': 'final_result_recorded', 'status': result['data']['status'],
                     'reason': result['data'].get('reason'), 'observed_at_ms': int(result['time']*1000), 'resent': False}
            state['reconciliations'].append(entry)
            state['inflight'] = None
            record['inflight'] = entry
        state.update(status='frozen', reason='migrated_to_r1')
        atomic_json(cycle/'state.json', state)
        status = json.loads((cycle/'status.json').read_text())
        status.update(status='frozen', reason='migrated_to_r1', inflight=None, running=False)
        atomic_json(cycle/'status.json', status)
    if registry.exists():
        shutil.copyfile(registry, archive/'processes-stale.json')
        registry.unlink()
        record['stale_registry'] = 'evidence/frozen/processes-stale.json'
    atomic_json(marker, record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--runtime', required=True, type=Path)
    print(json.dumps(freeze(parser.parse_args().runtime.resolve()/'p5'), indent=1))


if __name__ == '__main__':
    main()
