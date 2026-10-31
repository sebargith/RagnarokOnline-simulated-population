"""Freeze the bounded live ring and export a compact field-run review record."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    live = args.runtime/'m4/live'
    status = json.loads((live/'status.json').read_text())
    if status.get('running'):
        raise RuntimeError('Stop/finish the controller before freezing its evidence')
    run_id = status['run_id']
    dest = args.runtime/'evidence'/('m4-field-'+run_id)
    dest.mkdir(exist_ok=False, parents=True)
    for path in [live/'status.json', live/'manifest.json', *live.glob('events.jsonl*')]:
        shutil.copy2(path, dest/path.name)
    start_ms = (status['updated']-status['elapsed_s']-2)*1000
    events = []
    for path in dest.glob('events.jsonl*'):
        for line in path.read_text(encoding='utf-8').splitlines():
            e = json.loads(line)
            if e.get('controller') and e.get('run_id') == run_id:
                events.append(e)
            elif e.get('time_ms', 0) >= start_ms:
                events.append(e)
    notes = [e for e in events if e.get('controller')]
    results = [e for e in events if e.get('kind') == 'action_result']
    summary = {
        'run_id': run_id, 'elapsed_s': status['elapsed_s'], 'cycle': status['cycle'],
        'phase': status['phase'], 'error': status.get('error'), 'counters': status['counters'],
        'source_manifest': json.loads((dest/'manifest.json').read_text()),
        'portal_confirmations': [e for e in notes if e['controller'] == 'field_portal_confirmed'],
        'agreements': [e for e in notes if e['controller'] == 'field_agreement'],
        'encounters': status.get('field_results', []),
        'trips': [e for e in notes if e['controller'] == 'field_trip_completed'],
        'failures': [e for e in notes if e['controller'] in ('field_halted', 'fatal')],
        'noncompleted_results': [e for e in results if e['data']['status'] in ('unknown', 'rejected')],
        'final_agents': {who: {'session': a['session'], 'snapshot': a['snapshot']} for who, a in status['agents'].items()},
        'retained_event_count': len(events),
        'raw_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dest.iterdir())},
    }
    (dest/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(dest/'summary.json')
    print(json.dumps({k: summary[k] for k in ('run_id', 'elapsed_s', 'phase', 'cycle', 'error', 'counters')}))


if __name__ == '__main__':
    main()
