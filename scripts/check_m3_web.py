"""Bounded live check of one attributed search reply beside routine movement."""
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    args = parser.parse_args()
    evidence = args.runtime/'evidence'/('m3-web-'+time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    evidence.mkdir(parents=True)
    peer = Bridge(args.runtime/'openkore/peer/bridge.json')
    replies = []
    started = time.monotonic()
    sent = False
    with (evidence/'agent.jsonl').open('w', encoding='utf-8') as log:
        child = subprocess.Popen([sys.executable, str(ROOT/'scripts/run_m3.py'), '--runtime', str(args.runtime), '--state', str(evidence/'agent.sqlite'), '--seconds', '35', '--dialogue'], stdout=log, stderr=subprocess.STDOUT)
        try:
            while child.poll() is None:
                if time.monotonic()-started > 100:
                    child.terminate()
                    raise TimeoutError('Web check deadline')
                for event in peer.poll(.1):
                    if event['kind'] == 'chat' and not event['data'].get('self'):
                        replies.append(event['data'])
                peer.drain()
                if not sent and time.monotonic()-started > 5 and peer.latest and peer.latest['data']['connected']:
                    peer.proposal({'type': 'chat', 'text': 'M3: web poring'})
                    sent = True
        finally:
            peer.close()
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=10)
    summary = {'seconds': time.monotonic()-started, 'exit_code': child.returncode, 'replies': replies, 'source_hashes': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('agent/dialogue.py', 'scripts/run_m3.py', 'scripts/check_m3_web.py')}}
    (evidence/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(evidence)
    if child.returncode != 0 or len(replies) != 1:
        raise RuntimeError('Expected one peer-received reply')


if __name__ == '__main__':
    main()
