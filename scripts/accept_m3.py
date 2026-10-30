"""Retain one-agent dialogue/movement/restart evidence via the test peer."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.client import Bridge
from scripts.bench_m2 import ram_sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=1800)
    parser.add_argument('--fault', choices=('inference', 'search', 'outages'))
    parser.add_argument('--reconnect', action='store_true')
    args = parser.parse_args()
    if not 90 <= args.seconds <= 1800:
        parser.error('seconds must be 90..1800')
    evidence = args.runtime/'evidence'/('m3-'+time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    evidence.mkdir(parents=True)
    sources = list((ROOT/'agent').glob('*.py')) + list((ROOT/'inference').glob('*.py')) + [ROOT/'bridge/client.py', ROOT/'scripts/run_m3.py', ROOT/'scripts/accept_m3.py', ROOT/'config/m2-operating.json', ROOT/'config/web-search.json']
    (evidence/'manifest.json').write_text(json.dumps({str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}, indent=2))
    peer = Bridge(args.runtime/'openkore/peer/bridge.json')
    started = time.monotonic()
    restart_at = args.seconds/2
    plan = [(5, 'Hello! What sort of player are you?'), (18, 'I heard Aden is safe. Did you see it?'), (31, 'promise to meet here after restart'), (restart_at+8, 'What did you promise before restart?'), (restart_at+22, 'What map have you observed?'), (restart_at+36, 'web poring')]
    if args.seconds >= 180:
        plan = plan[:3] + [(restart_at+35, 'What did you promise before restart?'), (restart_at+50, 'What map have you observed?'), (restart_at+65, 'web poring'), (restart_at+80, 'What is my secret password?')]
    sent, replies, restarts = [], [], 0
    log = None
    child = None
    map_restarted = False
    last_resource = -10
    resources = []
    seen_positions = set()
    def launch(seconds, label):
        nonlocal log
        log = (evidence/(label+'.jsonl')).open('w', encoding='utf-8')
        command = [sys.executable, str(ROOT/'scripts/run_m3.py'), '--runtime', str(args.runtime), '--state', str(evidence/'agent.sqlite'), '--seconds', str(seconds), '--dialogue']
        if args.fault:
            fault = ('inference' if label == 'before' else 'search') if args.fault == 'outages' else args.fault
            command += ['--fault', fault]
        return subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    child = launch(restart_at, 'before')
    try:
        while time.monotonic()-started < args.seconds:
            elapsed = time.monotonic()-started
            if elapsed-last_resource >= 5:
                row = {'elapsed': elapsed, **ram_sample(set())}
                gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
                row['gpu_used_mib'] = int(gpu.strip())
                resources.append(row)
                last_resource = elapsed
                if row['ram_available'] < 2*1024**3 or row['gpu_used_mib'] > 14336:
                    raise RuntimeError('M2 resource budget exceeded')
            if args.reconnect and elapsed > args.seconds*.75 and not map_restarted:
                subprocess.run([sys.executable, str(args.runtime.parent/'scripts/m1.py'), 'restart-map'], check=True, timeout=90)
                map_restarted = True
            for event in peer.poll(.1):
                if event['kind'] == 'snapshot':
                    for player in event['data'].get('players', []):
                        if player['name'] == 'M1 Agent':
                            seen_positions.add((player['x'], player['y']))
                if event['kind'] == 'chat' and not event['data'].get('self'):
                    replies.append({'elapsed': elapsed, **event['data']})
            peer.drain()
            if elapsed >= restart_at and not restarts:
                child.wait(timeout=65)
                log.close()
                child = launch(args.seconds-elapsed, 'after')
                restarts = 1
            if plan and elapsed >= plan[0][0] and peer.latest and peer.latest['data']['connected']:
                _, text = plan.pop(0)
                peer.proposal({'type': 'chat', 'text': 'M3: '+text})
                sent.append({'elapsed': elapsed, 'text': text})
            if child.poll() is not None and elapsed < restart_at-1:
                raise RuntimeError('Orchestrator exited early')
    finally:
        peer.close()
        if child.poll() is None:
            if sys.exc_info()[0]:
                child.terminate()
            child.wait(timeout=65)
        if log:
            log.close()
        summary = {'seconds': time.monotonic()-started, 'restarts': restarts, 'map_restarted': map_restarted, 'fault': args.fault, 'sent': sent, 'replies': replies, 'peer_observed_agent_positions': sorted(seen_positions), 'exit_code': child.returncode, 'complete_m3': False}
        (evidence/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        (evidence/'resources.json').write_text(json.dumps(resources), encoding='utf-8')
        print(evidence)


if __name__ == '__main__':
    main()
