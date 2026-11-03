"""One bounded P5 training sample, with durable summary and safe cleanup.

By default the planner role re-decides the hunting field when one is due
(level up, unsafe field, periodic review); --no-inference keeps the saved
build and field without any model call."""
import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.live_io import atomic_json, exclusive
from bridge.client import Bridge
from scripts import m1, prepare_p5
from scripts.prepare_m4 import bind_runtime


def idle(config):
    b = Bridge(config)
    ready, observations = None, []
    try:
        end = time.monotonic() + 10
        while time.monotonic() < end and len(observations) < 2:
            b.poll(.2)
            for event in b.drain():
                if event['kind'] == 'ready':
                    ready = event
                if event['kind'] == 'snapshot' and event['data'].get('connected') and ready:
                    if not observations or event['time_ms'] - observations[0]['time_ms'] >= 1000:
                        observations.append(event)
        if (ready is None or len(observations) != 2 or 'pending_request_id' not in ready['data'] or
                ready['data']['pending_request_id'] is not None or
                any(e['session'] != ready['session'] for e in observations)):
            return False
        observations = [e['data'] for e in observations]
        return all(s.get('name') == 'Nilo' and s.get('recovery') == 'none' and not s.get('native_task') and
                   not any(x in ('move', 'route', 'mapRoute', 'NPC', 'attack', 'take')
                           for x in s.get('ai_queue', [])) for s in observations) and \
            observations[0].get('position') == observations[1].get('position')
    finally:
        b.close()


def runner_command(runtime, seconds, max_actions, no_inference):
    return [sys.executable, str(ROOT / 'scripts/run_p2_cycle.py'), 'run', '--runtime', str(runtime),
            '--agent', 'p5', '--p5', *(['--no-inference'] if no_inference else []),
            '--train-first-job', '--seconds', str(seconds), '--max-actions', str(max_actions)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--summary', required=True, type=Path)
    parser.add_argument('--seconds', type=int, default=600)
    parser.add_argument('--max-actions', type=int, default=150)
    parser.add_argument('--reuse-client', action='store_true')
    parser.add_argument('--no-inference', action='store_true', help='Keep the saved field; no planner calls')
    args = parser.parse_args()
    if not 30 <= args.seconds <= 3600 or not 1 <= args.max_actions <= 600:
        parser.error('seconds must be 30..3600 and max-actions 1..600')
    runtime = args.runtime.resolve()
    base = runtime / 'p5'
    if (base / 'FROZEN.json').exists():
        parser.error('P5 is frozen: Nilo runs on R1 (scripts/run_r1.py --character nilo)')
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    summary = {'phase': 'starting', 'pid': os.getpid(), 'inference_calls': 0, 'client_owned': False, 'started': time.time(),
               'max_seconds': args.seconds, 'max_actions': args.max_actions,
               'mode': 'no_inference' if args.no_inference else 'field_planner'}
    atomic_json(args.summary, summary)
    with exclusive(base / 'background.lock'):
        try:
            bind_runtime(runtime)
            # Check controller ownership before starting a client; the runner takes this lock itself.
            with exclusive(base / 'cycle.lock'):
                if args.reuse_client:
                    registry = json.loads((base / 'processes.json').read_text())
                    info = registry['p5-novice']
                    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, info['pid'])
                    if not handle:
                        raise RuntimeError('Registered client is not running')
                    try:
                        buf, size = ctypes.create_unicode_buffer(32768), ctypes.c_ulong(32768)
                        if not ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)) or os.path.normcase(buf.value) != os.path.normcase(info['exe']):
                            raise RuntimeError('Registered client identity changed')
                    finally:
                        ctypes.windll.kernel32.CloseHandle(handle)
                    if m1.available(8771):
                        raise RuntimeError('Registered client bridge unavailable')
                    summary['client_reused'] = True
                else:
                    if (base / 'processes.json').exists() or not m1.available(8771):
                        raise RuntimeError('Nilo client already present or bridge port occupied')
                    prepare_p5.start(runtime)
                    summary['client_owned'] = True
            registry = json.loads((base / 'processes.json').read_text())
            summary['client_pid'] = registry['p5-novice']['pid']
            summary['phase'] = 'running'
            atomic_json(args.summary, summary)
            remaining = min(args.seconds - 30, int(args.seconds - 10 - (time.time() - summary['started'])))
            if remaining < 10:
                raise RuntimeError('Insufficient time remaining in the sample budget')
            command = runner_command(runtime, remaining, args.max_actions, args.no_inference)
            summary['command'] = command
            atomic_json(args.summary, summary)
            result = subprocess.run(command, cwd=ROOT, timeout=remaining + 8)
            summary['runner_exit_code'] = result.returncode
        except Exception as exc:
            summary['error'] = f'{type(exc).__name__}: {exc}'
        finally:
            state_path = base / 'cycle/state.json'
            status_path = base / 'cycle/status.json'
            if state_path.exists():
                state = json.loads(state_path.read_text(encoding='utf-8'))
                summary['checkpoint'] = {k: state.get(k) for k in ('status', 'reason', 'phase', 'kills', 'inflight', 'macro_goal')}
            if status_path.exists():
                status = json.loads(status_path.read_text(encoding='utf-8'))
                if status.get('updated', 0) >= summary['started']:
                    summary['runner_status'] = status
                    summary['inference_calls'] = status.get('inference_calls')
            if summary['client_owned'] and summary.get('checkpoint', {}).get('inflight') is None:
                try:
                    if idle(base / 'openkore/solo/bridge.json'):
                        prepare_p5.processes(runtime)
                        m1.stop('p5-novice')
                        summary['client_owned'] = False
                        summary['client_stopped'] = True
                except Exception as exc:
                    summary['cleanup_error'] = f'{type(exc).__name__}: {exc}'
            summary['phase'] = 'finished'
            summary['finished'] = time.time()
            atomic_json(args.summary, summary)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if '--summary' in sys.argv:
            path = Path(sys.argv[sys.argv.index('--summary') + 1])
            if path.exists():
                summary = json.loads(path.read_text(encoding='utf-8'))
                summary.update(phase='failed', error=f'{type(exc).__name__}: {exc}', finished=time.time())
                atomic_json(path, summary)
        raise
