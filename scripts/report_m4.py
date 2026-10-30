"""Export a compact, hash-linked M4 review set from bounded local evidence."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess


def load(run):
    summary = json.loads((run/'summary.json').read_text())
    events = [json.loads(line) for line in (run/'events.jsonl').read_text().splitlines()]
    if len(events) > 12000:
        raise ValueError('Evidence exceeds runner bound')
    resources = summary['resources']
    gaps = []
    last = {}
    for event in events:
        if event['kind'] == 'snapshot':
            key = event['agent_id'], event['session']
            if key in last:
                gaps.append((event['time_ms']-last[key])/1000)
            last[key] = event['time_ms']
    summary.pop('resources')
    return {'run': run.name, 'summary': summary,
        'resource_samples': len(resources),
        'min_available_ram_gib': min(r['ram_available'] for r in resources)/1024**3,
        'peak_gpu_used_mib': max(r['gpu_used_mib'] for r in resources),
        'max_resource_sample_gap_s': max((b['elapsed_s']-a['elapsed_s'] for a, b in zip(resources, resources[1:])), default=0),
        'max_snapshot_gap_within_epoch_s': max(gaps, default=0),
        'events_by_kind': dict(Counter(e['kind'] for e in events)),
        'completed_trade_results_consumed': sum(e['kind'] == 'action_result' and e['data'].get('reason') == 'server_trade_complete' for e in events),
        'hashes': {name: hashlib.sha256((run/name).read_bytes()).hexdigest() for name in ('summary.json', 'events.jsonl', 'manifest.json')},
        'source_manifest': json.loads((run/'manifest.json').read_text())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--combined', required=True)
    parser.add_argument('--combined-commit', required=True)
    parser.add_argument('--interrupted', required=True)
    parser.add_argument('--recovery', required=True)
    parser.add_argument('--web', required=True)
    parser.add_argument('--repeat')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    runs = {key: load(args.runtime/'evidence'/getattr(args, key)) for key in ('combined', 'interrupted', 'recovery', 'web')}
    if args.repeat:
        runs['repeat_conversation'] = load(args.runtime/'evidence'/args.repeat)
    if not runs['combined']['summary']['functional_complete']:
        raise ValueError('Combined proof incomplete')
    if runs['interrupted']['completed_trade_results_consumed']:
        raise ValueError('Interrupted run consumed a trade completion')
    recovery = runs['recovery']['summary']['trade']
    if recovery['new_transfer_attempted'] or recovery['recovered_only'][0]['reconciliation'] != 'completed':
        raise ValueError('Recovery did not reconcile without a new transfer')
    output = {'combined_tested_commit': args.combined_commit,
        'export_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'acceptance': 'functional prototype demonstrated; social quality and one-hour trial deferred',
        'limitations': ['Controlled stationary Poring fixture and fixed trade only.',
            'Read-only SQL verification is privileged test instrumentation, absent from player minds.',
            'RAM/GPU sampling pauses during client lifecycle subprocesses; samples are not continuous peaks.',
            'No one-hour trial, general routing, open-ended social acceptance or M5.'],
        **runs}
    args.output.write_text(json.dumps(output, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: {k: value[k] for k in ('run', 'min_available_ram_gib', 'peak_gpu_used_mib', 'max_snapshot_gap_within_epoch_s', 'completed_trade_results_consumed')} for key, value in runs.items()}, indent=2))


if __name__ == '__main__':
    main()
