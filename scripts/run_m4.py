"""Run/observe the controlled M4 prototype. Raw evidence remains under runtime."""
import argparse
import hashlib
import json
import msvcrt
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.prototype import Prototype


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--mode', choices=('observe', 'isolation', 'boundaries', 'conversation', 'web', 'solo', 'cooperate', 'trade', 'all'), default='all')
    parser.add_argument('--trade-fault', choices=('after_commit', 'after_commit_exit'))
    parser.add_argument('--seconds', type=int, default=15)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 60:
        parser.error('seconds must be 1..60')
    lock = (args.runtime/'m4.lock').open('a+b')
    lock.seek(0)
    if not lock.read(1):
        lock.write(b'0'); lock.flush()
    lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    evidence = args.runtime/'evidence'/('m4-'+time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    evidence.mkdir(parents=True)
    sources = [*ROOT.glob('agent/*.py'), *ROOT.glob('inference/*.py'), *ROOT.glob('bridge/**/*.pl'), *ROOT.glob('bridge/**/*.pm'), ROOT/'bridge/client.py',
               ROOT/'scripts/run_m4.py', ROOT/'scripts/prepare_m4.py', ROOT/'scripts/m1.py', ROOT/'scripts/bench_m2.py',
               ROOT/'fixtures/m4-pve.txt', ROOT/'config/m4-identities.json', ROOT/'config/m2-operating.json', ROOT/'config/web-search.json']
    (evidence/'manifest.json').write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, indent=2))
    print(evidence, flush=True)
    prototype = None
    summary = {'mode': args.mode, 'trade_fault': args.trade_fault, 'functional_complete': False}
    try:
        prototype = Prototype(ROOT, args.runtime, evidence)
        prototype.ready()
        if args.mode in ('boundaries', 'all'):
            summary['boundaries'] = prototype.boundaries()
        if args.mode in ('isolation', 'all'):
            summary['isolation'] = prototype.isolation()
        if args.mode == 'observe':
            prototype.pump(args.seconds)
            summary['snapshots'] = {who: b.latest for who, b in prototype.bridges.items()}
        if args.mode in ('conversation', 'all'):
            summary['conversation'] = prototype.conversation()
        if args.mode == 'web':
            summary['web'] = prototype.web()
        if args.mode in ('solo', 'all'):
            summary['solo'] = prototype.encounter()
        if args.mode in ('cooperate', 'all'):
            summary['cooperation'] = prototype.encounter(True)
        if args.mode in ('trade', 'all'):
            summary['trade'] = prototype.trade(args.trade_fault)
        if args.mode == 'all':
            summary['functional_complete'] = (summary['trade'].get('reconciliation') == 'completed' and
                len([r for r in summary['conversation']['replies'] if 'error' not in r]) == 3)
    except BaseException as error:
        summary['error'] = str(error)
        raise
    finally:
        if prototype:
            summary['elapsed_s'] = time.monotonic()-prototype.started
            summary['resources'] = prototype.resources
            summary['event_count'] = prototype.event_count
            prototype.close()
        (evidence/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        lock.close()
        print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
