"""Export sanitized metrics and fixture conversation from a retained M3 run."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--web-run', type=Path)
    args = parser.parse_args()
    summary = json.loads((args.run/'summary.json').read_text())
    rows = [json.loads(line) for name in ('before', 'after') for line in (args.run/(name+'.jsonl')).read_text().splitlines()]
    turns = [r['dialogue'] for r in rows if isinstance(r.get('dialogue'), dict)]
    resources = json.loads((args.run/'resources.json').read_text())
    manifest = json.loads((args.run/'manifest.json').read_text())
    def matches_frozen(name, digest):
        blob = subprocess.check_output(['git', 'show', 'beb18a7:'+name.replace('\\', '/')], cwd=ROOT)
        return digest in {hashlib.sha256(blob).hexdigest(), hashlib.sha256(blob.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')).hexdigest()}
    def profile(values):
        return {'n': len(values), **{key: max(r['metrics'][key] for r in values) for key in ('ttft_s', 'service_s', 'queue_s', 'response_s')}}
    warm = [r for r in turns if not r['topic'] and not r['cold']]
    report = {'run': args.run.name, 'implementation_commit': 'beb18a7', 'scenario': summary,
              'action_status_counts': dict(Counter(r['status'] for r in rows if 'status' in r)),
              'result_reason_counts': dict(Counter(r['reason'] for r in rows if 'request_id' in r)),
              'segments': [r for r in rows if 'events' in r],
              'no_search_cold_maxima': profile([r for r in turns if not r['topic'] and r['cold']]),
              'no_search_warm_maxima': profile(warm),
              'no_search_warm_p95': {key: sorted(r['metrics'][key] for r in warm)[math.ceil(.95*len(warm))-1] for key in ('ttft_s', 'service_s', 'queue_s', 'response_s')},
              'web_turns': [r for r in turns if r['topic']],
              'resources': {'samples': len(resources), 'min_available_ram_gib': min(r['ram_available'] for r in resources)/1024**3, 'sampled_peak_gpu_mib': max(r['gpu_used_mib'] for r in resources)},
              'source_hashes': manifest, 'raw_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.run.iterdir() if p.suffix in ('.json', '.jsonl')},
              'source_mismatches': [name for name, digest in manifest.items() if not matches_frozen(name, digest)],
              'source_comparison': 'frozen beb18a7 Git content, allowing Windows checkout line endings; raw source hashes retained separately',
              'human_review': 'pending', 'web_utility': 'unhelpful response; selected snippet describes Ragnarok M, not the requested classic PC game'}
    if args.web_run:
        repair_rows = [json.loads(line) for line in (args.web_run/'agent.jsonl').read_text().splitlines()]
        repair_summary = json.loads((args.web_run/'summary.json').read_text())
        report['web_repair'] = {'run': args.web_run.name, 'summary': repair_summary, 'turns': [r['dialogue'] for r in repair_rows if isinstance(r.get('dialogue'), dict)], 'raw_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.web_run.iterdir() if p.suffix in ('.json', '.jsonl')}}
    output = ROOT/'docs/evidence'
    (output/'M3-results.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    text = ['# M3 conversation review', '', 'Run: `'+args.run.name+'`, frozen implementation `beb18a7`.', '', 'All seven peer-received replies are retained below. Human review is pending.', '']
    for request, reply in zip(summary['sent'], summary['replies']):
        text += [f"- Peer ({request['elapsed']:.1f}s): {request['text']}", f"- Agent ({reply['elapsed']:.1f}s): {reply['text']}", '']
    text += ['The web reply is an unhelpful refusal. Its single selected source was', '`https://poring.gg/classic/monsters`, whose snippet identifies Ragnarok M:', 'Eternal Love and Classic. Selecting the last search result was insufficient', 'for PC/pre-Renewal relevance. No snippet was stored as game observation.', '', 'Earlier development failures (unrelated commitment context in map/web replies', 'and dropped replies during action reconciliation) are recorded in', '[M3 evidence](M3-persistence.md). The duration run used narrowed retrieval,', 'one unsent-reply slot and source-isolated web context.', '']
    if args.web_run:
        text += ['## Targeted search repair', '', 'The original duration transcript above is unchanged. A subsequent 35-second', 'check selected a PC/pre-Renewal source and retained its complete generated', 'claim separately from the 80-character public-chat excerpt.', '']
        for reply in repair_summary['replies']:
            text += ['- Peer: web poring', '- Agent: '+reply['text'], '']
        text += ['Source: https://ratemyserver.net/index.php?page=mob_db&mob_id=1002', '', 'The displayed ellipsis is an explicit chat-length excerpt; the full generated', 'sentence and exact snippet are retained in M3-results.json. Human review of', 'naturalness remains pending.', '']
    (output/'M3-conversations.md').write_text('\n'.join(text), encoding='utf-8')
    print('Exported M3-results.json and M3-conversations.md')


if __name__ == '__main__':
    main()
