"""Start, stop, observe and interact with the continuous three-agent M4 fixture."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.continuous import Continuous, StopRequested
from agent.field import FieldController
from agent.live_io import atomic_json, exclusive


def read_status(live):
    path = live/'status.json'
    return json.loads(path.read_text()) if path.exists() else {'running': False}


def run(args):
    mode = getattr(args, 'mode', 'fixture')
    live = args.runtime/'m4/live'
    live.mkdir(parents=True, exist_ok=True)
    with exclusive(args.runtime/'m4.lock'):
        run_id = args.run_id or uuid.uuid4().hex
        atomic_json(live/'status.json', {'run_id': run_id, 'running': True, 'phase': 'starting_clients', 'updated': time.time()})
        sources = [*ROOT.glob('agent/*.py'), *ROOT.glob('bridge/**/*.pl'), *ROOT.glob('bridge/**/*.pm'), *ROOT.glob('inference/*.py'), ROOT/'bridge/client.py',
                   ROOT/'scripts/live_m4.py', ROOT/'scripts/prepare_m4.py', ROOT/'scripts/m1.py', ROOT/'scripts/bench_m2.py',
                   ROOT/'fixtures/m4-pve.txt', ROOT/'config/m4-identities.json', ROOT/'config/m2-operating.json', ROOT/'config/web-search.json']
        atomic_json(live/'manifest.json', {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
        controller = None
        try:
            # Load current bridge source and full inventories. Never touches
            # server lifecycle, accounts, balances, fixture or memory databases.
            subprocess.run([sys.executable, str(ROOT/'scripts/prepare_m4.py'), '--runtime', str(args.runtime),
                            '--clients-only', '--start', '--continuous', '--controller-owned', *(['--field'] if mode == 'field' else [])], check=True, timeout=100)
            controller = (FieldController if mode == 'field' else Continuous)(ROOT, args.runtime, run_id, args.seconds)
            controller.run()
        except (StopRequested, KeyboardInterrupt):
            pass
        except BaseException as error:
            if controller:
                controller.record_failure(error)
            else:
                atomic_json(live/'status.json', {'run_id': run_id, 'running': False, 'phase': 'failed', 'error': str(error), 'updated': time.time()})
            raise
        finally:
            if controller:
                controller.close()
            elif read_status(live).get('running'):
                atomic_json(live/'status.json', {'run_id': run_id, 'running': False, 'phase': 'stopped', 'updated': time.time()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('command', choices=('start', 'run', 'stop', 'status', 'observe', 'say'))
    parser.add_argument('--seconds', type=int, help='Optional run duration or observe duration (default observe: 5)')
    parser.add_argument('--mode', choices=('fixture', 'field'), default='fixture')
    parser.add_argument('--sender', choices=('agent', 'peer', 'third'), default='third')
    parser.add_argument('--target', choices=('agent', 'peer', 'third'), default='agent')
    parser.add_argument('--text')
    parser.add_argument('--run-id', help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.runtime = args.runtime.resolve()
    live = args.runtime/'m4/live'
    live.mkdir(parents=True, exist_ok=True)
    if args.seconds is not None and args.seconds < 1:
        parser.error('seconds must be positive')
    if args.command == 'run':
        run(args)
    elif args.command == 'start':
        # Check ownership before spawning; child takes the same lifetime lock.
        with exclusive(args.runtime/'m4.lock'):
            pass
        run_id = uuid.uuid4().hex
        command = [sys.executable, str(Path(__file__).resolve()), '--runtime', str(args.runtime), 'run', '--run-id', run_id, '--mode', args.mode]
        if args.seconds:
            command += ['--seconds', str(args.seconds)]
        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic()+10
        while time.monotonic() < deadline:
            status = read_status(live)
            if status.get('run_id') == run_id:
                print(json.dumps(status))
                return
            if process.poll() is not None:
                raise RuntimeError('Controller exited during startup; use run for diagnostics')
            time.sleep(.1)
        raise TimeoutError('Startup did not publish status; use status before retrying')
    elif args.command == 'status':
        status = read_status(live)
        status['status_age_s'] = time.time()-status.get('updated', 0)
        print(json.dumps(status, indent=2))
    elif args.command == 'observe':
        for _ in range(args.seconds or 5):
            status = read_status(live)
            agents = {who: {'name': (a.get('snapshot') or {}).get('data', {}).get('name'),
                            'map': (a.get('snapshot') or {}).get('data', {}).get('map'),
                            'position': (a.get('snapshot') or {}).get('data', {}).get('destination'),
                            'connected': (a.get('snapshot') or {}).get('data', {}).get('connected'),
                            'inference_pending': a.get('pending_inference')}
                      for who, a in status.get('agents', {}).items()}
            print(json.dumps({k: status.get(k) for k in ('running', 'phase', 'cycle', 'counters')} | {'age_s': round(time.time()-status.get('updated', 0), 1), 'agents': agents}), flush=True)
            time.sleep(1)
    else:
        status = read_status(live)
        if not status.get('running'):
            raise RuntimeError('No running controller')
        if args.command == 'stop':
            atomic_json(live/'stop.json', {'run_id': status['run_id']})
            print('Stop requested; status becomes stopped after durable cleanup. Clients/server remain running.')
        else:
            if args.sender == args.target or not args.text or not 1 <= len(args.text) <= 65 or any(not 32 <= ord(c) <= 126 for c in args.text):
                parser.error('say requires different sender/target and 1..65 printable ASCII characters')
            if time.time()-status['updated'] > 30:
                raise RuntimeError('Controller status is stale; inspect status before interacting')
            with exclusive(live/'control.lock'):
                path = live/'commands.json'
                commands = json.loads(path.read_text()) if path.exists() else []
                commands = [c for c in commands if c.get('run_id') == status['run_id'] and time.time()-c.get('created', 0) < 30]
                if len(commands) >= 8:
                    raise BufferError('Manual chat queue full; wait before trying another prompt')
                commands.append({'run_id': status['run_id'], 'created': time.time(), 'sender': args.sender, 'target': args.target, 'text': args.text})
                atomic_json(path, commands)
            print('Queued public chat from '+args.sender+' to '+args.target+' (expires in 30 seconds).')


if __name__ == '__main__':
    main()
