"""R1 trial runner: Tarin (account 2000030) on OpenKore --ai=auto with the profile
generated from config/r1-policy.json, plus a read-only observer.

Separate from P1/P5: profile, logs, observer events and process registry live in
runtime/r1/. Tarin's existing password is read from runtime/p1/secrets.json and
never printed; P1's files and checkpoint are not modified. Nothing here sends a
game action: OpenKore's own AI acts, the observer only writes events.

  preflight  services, ports, registries, RAM and GPU (read-only)
  prepare    write the profile
  start      launch the client (refuses if a P1 or R1 client is registered)
  watch      run up to --seconds with stop guards, then stop and summarize
  stop       stop the R1 client
  report     summarize runtime/r1/observer/events.jsonl
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import m1, build_r1_profile
from scripts.bench_m2 import ram_sample
from scripts.prepare_m4 import bind_runtime

NAME, USERID, PORT, CLIENT = 'Tarin', 'p1solo', 8772, 'r1-tarin'
PLUGINS = 'r1_observer,raiseStat,raiseSkill'
SUPPLY_AI = {'sellAuto', 'buyAuto', 'storageAuto'}
CONSUMED = {512, 507, 601}  # useSelf_item Apple/Red Herb, teleport Fly Wing
RAM_MIN, GPU_MAX = 2 * 1024**3, 14336
DEATHS_MAX, DEATH_WINDOW_S = 3, 900


def paths(runtime):
    base = runtime.resolve()/'r1'
    return {'base': base, 'profile': base/'openkore/tarin', 'observer': base/'observer',
            'events': base/'observer/events.jsonl', 'summary': base/'summary.json'}


def bind(runtime):
    bind_runtime(runtime)
    m1.RUN = paths(runtime)['base']
    (m1.RUN/'logs').mkdir(parents=True, exist_ok=True)


def prepare(runtime):
    p, template = paths(runtime), runtime.resolve()/'openkore/agent'
    password = json.loads((runtime.resolve()/'p1/secrets.json').read_text())['password']
    policy = json.loads((ROOT/'config/r1-policy.json').read_text(encoding='utf-8'))
    result = build_r1_profile.translate(policy, build_r1_profile.load_tables())
    files = build_r1_profile.render(result, (template/'config.txt').read_text(encoding='utf-8'))
    for key, value in {'username': USERID, 'password': password}.items():
        files['config.txt'] = re.sub(rf'(?m)^{key}(?:[ \t].*)?$', lambda _: f'{key} {value}', files['config.txt'], count=1)
    p['profile'].mkdir(parents=True, exist_ok=True)
    (p['profile']/'logs').mkdir(exist_ok=True)
    p['observer'].mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        m1.write(p['profile']/name, text)
    for name in ('servers.txt', 'timeouts.txt'):
        shutil.copyfile(template/name, p['profile']/name)
    sys_txt = (template/'sys.txt').read_text()
    sys_txt = re.sub(r'(?m)^loadPlugins_list.*$', f'loadPlugins_list {PLUGINS}', sys_txt)
    m1.write(p['profile']/'sys.txt', sys_txt)
    report = {'mapping': result['mapping'], 'gaps': result['gaps'],
              'avoided_maps': sorted(k for k in result['weights'] if k not in build_r1_profile.TRANSPORT_WEIGHTS)}
    m1.write(p['base']/'profile-report.json', json.dumps(report, indent=1, default=str))
    print(f'R1 profile ready: {p["profile"]} (gaps: {[g["rule"] for g in result["gaps"]]})')


def resources(pid=None):
    sample = ram_sample({pid} if pid else set())
    raw = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                                  text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    return {'ram_available': sample['ram_available'], 'gpu_used_mib': int(raw.strip().splitlines()[0]),
            'client_ws': sample['m1']['ws'] if pid else None, 'cpu_s': cpu_seconds(pid) if pid else None}


def cpu_seconds(pid):
    kernel = ctypes.windll.kernel32
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        times = [wt.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
            return None
        return sum((t.dwHighDateTime << 32 | t.dwLowDateTime) for t in times[2:]) / 1e7
    finally:
        kernel.CloseHandle(handle)


def alive(pid):
    handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        code = wt.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        return code.value == 259  # STILL_ACTIVE
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def preflight(runtime):
    root = runtime.resolve()
    services = json.loads((root/'processes.json').read_text())
    out = {'services': {n: alive(v['pid']) for n, v in services.items()},
           'p1_registry': (root/'p1/processes.json').exists(), 'p5_registry': (root/'p5/processes.json').exists(),
           'r1_registry': (paths(runtime)['base']/'processes.json').exists(),
           'ports_free': {port: m1.available(port) for port in (8770, 8771, PORT)}, **resources()}
    out['ok'] = (all(out['services'][n] for n in ('mariadb', 'login-server', 'char-server', 'map-server'))
                 and not out['p1_registry'] and not out['r1_registry']
                 and out['ram_available'] >= RAM_MIN and out['gpu_used_mib'] < GPU_MAX)
    print(json.dumps(out, indent=1))
    return out


def start(runtime):
    p = paths(runtime)
    bind(runtime)
    if (runtime.resolve()/'p1/processes.json').exists():
        raise RuntimeError('P1 client registered for the same account; refusing')
    registry = m1.RUN/'processes.json'
    if registry.exists():
        raise RuntimeError('R1 registry exists; stop it first')
    args = [m1.PERL/'perl/bin/perl.exe', f'-I{ROOT/"bridge/lib"}', 'openkore.pl',
            f'--control={p["profile"]};{m1.OK/"control"}', f'--tables={p["profile"]};{m1.OK/"tables"}',
            f'--logs={p["profile"]/"logs"}', f'--plugins={ROOT/"bridge/r1"};{m1.OK/"plugins"}',
            '--interface=M1Headless', '--ai=auto']
    env = m1.env_perl()
    env['R1_OBSERVER_DIR'] = str(p['observer'])
    process = m1.launch(args, CLIENT, m1.OK, env)
    m1.write(registry, json.dumps({CLIENT: {'pid': process.pid, 'exe': str((m1.PERL/'perl/bin/perl.exe').resolve()),
                                            'started': time.time()}}, indent=2))
    print(f'R1 client started: PID {process.pid}')
    return process.pid


def stop(runtime):
    bind(runtime)
    m1.stop(CLIENT)


def read_events(path, since=0):
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get('t', 0) >= since:
            out.append(e)
    return out


def exp_gained(levels):
    """Base and job EXP summed across level samples, carrying over level-ups."""
    total = {'base': 0, 'job': 0}
    for a, b in zip(levels, levels[1:]):
        for kind, lv, exp, top in (('base', 'base', 'exp', 'exp_max'), ('job', 'job', 'job_exp', 'job_exp_max')):
            if b.get(lv) == a.get(lv):
                total[kind] += max(0, b[exp] - a[exp])
            elif b.get(lv, 0) > a.get(lv, 0):
                total[kind] += max(0, a[top] - a[exp]) + b[exp]
    return total


def summarize(events, lock_map, started=None):
    """Trial metrics from observer events. Pure: tests feed recorded events."""
    samples = [e for e in events if e['type'] == 'sample' and e.get('connected')]
    if started is None:
        started = events[0]['t'] if events else 0
    span = (samples[-1]['t'] - samples[0]['t']) if len(samples) > 1 else 0
    share = {'hunt': 0.0, 'rest': 0.0, 'travel': 0.0, 'supply': 0.0, 'dead': 0.0}
    for a, b in zip(samples, samples[1:]):
        dt = min(b['t'] - a['t'], 15)
        state = ('dead' if a['dead'] else 'supply' if SUPPLY_AI & set(a['ai']) else
                 ('rest' if a['sitting'] else 'hunt') if a['map'] == lock_map else 'travel')
        share[state] += dt
    deaths = []
    for d in (e for e in events if e['type'] == 'died'):
        back = next((s for s in samples if s['t'] > d['t'] and not s['dead'] and s['map'] == lock_map), None)
        respawn = next((s for s in samples if s['t'] > d['t'] and not s['dead']), None)
        deaths.append({'t': d['t'], 'map': d.get('map'), 'respawned_s': round(respawn['t'] - d['t'], 1) if respawn else None,
                       'back_in_field_s': round(back['t'] - d['t'], 1) if back else None})
    levels = [e['level'] for e in samples if e.get('level')]
    exp = exp_gained(levels)
    unexpected = []
    for e in events:
        supply = SUPPLY_AI & set(e.get('ai', []))
        if e['type'] == 'npc_talk' and not supply:
            unexpected.append({'t': e['t'], 'kind': 'npc_dialog_outside_supply', 'name': e['name'], 'map': e['map']})
        # The first stat packet after login reports the whole balance as a change.
        if e['type'] == 'zeny' and not supply and e['change'] != e['zeny']:
            unexpected.append({'t': e['t'], 'kind': 'zeny_change_outside_supply', 'change': e['change'], 'map': e['map']})
    teleports = [e['t'] for e in events if e['type'] == 'teleport']
    for a, b in zip(samples, samples[1:]):
        if SUPPLY_AI & set(a['ai'] + b['ai']):
            continue
        for item, amount in a['inventory'].items():
            lost = amount - b['inventory'].get(item, 0)
            if lost > 0 and not (int(item) in CONSUMED and (int(item) != 601 or any(a['t'] <= t <= b['t'] + 5 for t in teleports))):
                unexpected.append({'t': b['t'], 'kind': 'inventory_loss', 'item': int(item), 'amount': lost, 'map': b['map']})
    hours = span / 3600 if span else 0
    kills = sum(1 for e in events if e['type'] == 'kill')
    first, last = (samples[0], samples[-1]) if samples else ({}, {})
    return {'span_s': round(span), 'kills': kills, 'kills_per_h': round(kills / hours, 1) if hours else None,
            'base_exp': exp['base'], 'job_exp': exp['job'],
            'base_exp_per_h': round(exp['base'] / hours) if hours else None,
            'job_exp_per_h': round(exp['job'] / hours) if hours else None,
            'level': {'start': first.get('level'), 'end': last.get('level')},
            'stats': {'start': first.get('stats'), 'end': last.get('stats')},
            'zeny': {'start': first.get('zeny'), 'end': last.get('zeny')},
            'inventory': {'start': first.get('inventory'), 'end': last.get('inventory')},
            'time_share_s': {k: round(v) for k, v in share.items()},
            'maps_visited': sorted({s['map'] for s in samples}),
            'deaths': deaths, 'teleports': len(teleports),
            'npc_dialogs': [{'name': e['name'], 'map': e['map'], 'supply': bool(SUPPLY_AI & set(e.get('ai', [])))}
                            for e in events if e['type'] == 'npc_talk'],
            'unexpected': unexpected, 'disconnects': sum(1 for e in events if e['type'] == 'disconnected')}


def watch(runtime, seconds):
    """Supervise one bounded run: only guards and measurement, never game input."""
    p = paths(runtime)
    lock = json.loads((ROOT/'config/r1-policy.json').read_text(encoding='utf-8'))['rules'][0]['do']['hunt']['field']
    bind(runtime)
    pid = json.loads((m1.RUN/'processes.json').read_text())[CLIENT]['pid']
    started, reason, res = time.time(), 'time_budget', []
    try:
        while time.time() - started < seconds:
            time.sleep(10)
            if not alive(pid):
                reason = 'client_exited'; break
            sample = resources(pid); sample['t'] = time.time(); res.append(sample)
            if sample['ram_available'] < RAM_MIN:
                reason = 'ram_guard'; break
            if sample['gpu_used_mib'] >= GPU_MAX:
                reason = 'gpu_guard'; break
            events = read_events(p['events'], started)
            deaths = [e for e in events if e['type'] == 'died' and e['t'] > time.time() - DEATH_WINDOW_S]
            if len(deaths) >= DEATHS_MAX:
                reason = 'death_loop'; break
            bad = [u for u in summarize(events, lock, started)['unexpected'] if u['kind'] != 'inventory_loss']
            if bad:
                reason = f'unexpected:{bad[0]["kind"]}'; break
    except KeyboardInterrupt:
        reason = 'interrupted'
    finally:
        if alive(pid):
            stop(runtime)
    out = summarize(read_events(p['events'], started), lock, started)
    cpu = [r for r in res if r['cpu_s'] is not None]
    out.update({'stop_reason': reason, 'started': started, 'ended': time.time(), 'pid': pid,
                'resources': {'samples': len(res),
                              'cpu_pct_one_core': round(100 * (cpu[-1]['cpu_s'] - cpu[0]['cpu_s']) / (cpu[-1]['t'] - cpu[0]['t']), 2) if len(cpu) > 1 else None,
                              'client_ws_max_mib': round(max(r['client_ws'] for r in res) / 2**20) if res else None,
                              'ram_available_min_gib': round(min(r['ram_available'] for r in res) / 2**30, 2) if res else None,
                              'gpu_used_mib': [min(r['gpu_used_mib'] for r in res), max(r['gpu_used_mib'] for r in res)] if res else None}})
    m1.write(p['summary'], json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ('stop_reason', 'span_s', 'kills', 'kills_per_h', 'base_exp_per_h', 'deaths', 'time_share_s')}))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('preflight', 'prepare', 'start', 'watch', 'stop', 'report'))
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--seconds', type=int, default=3600)
    parser.add_argument('--since', type=float, default=0)
    args = parser.parse_args()
    if args.command == 'preflight':
        preflight(args.runtime)
    elif args.command == 'prepare':
        bind(args.runtime); prepare(args.runtime)
    elif args.command == 'start':
        start(args.runtime)
    elif args.command == 'watch':
        watch(args.runtime, args.seconds)
    elif args.command == 'stop':
        stop(args.runtime)
    else:
        lock = json.loads((ROOT/'config/r1-policy.json').read_text(encoding='utf-8'))['rules'][0]['do']['hunt']['field']
        print(json.dumps(summarize(read_events(paths(args.runtime)['events'], args.since), lock, args.since or None), indent=1))


if __name__ == '__main__':
    main()
