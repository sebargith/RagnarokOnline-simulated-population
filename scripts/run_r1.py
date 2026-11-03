"""R1 runner: one character on OpenKore --ai=auto with the profile generated from
its policy (config/r1-policy*.json), plus a read-only observer.

--character tarin (account 2000030, runtime/r1/, port 8772) or nilo (account
2000031, runtime/r1-nilo/, port 8773). Profile, logs, observer events and process
registry live in the character's own directory. The existing password is read
from the P1/P5 secrets and never printed; P1/P5 files and checkpoints are not
modified. Nothing here sends a game action: OpenKore's own AI acts, the observer
only writes events.

  preflight  services, ports, registries, RAM and GPU (read-only)
  prepare    write the profile
  start      launch the client (refuses if a P1 or R1 client is registered)
  watch      run up to --seconds with stop guards, then stop and summarize
  stop       stop the R1 client
  report     summarize the character's observer events
  campaign   one unattended run of --seconds: auto until Job 10, the first-job step,
             the policy for the new class and auto again until the budget ends

Field choice: at prepare and on each base level-up or death, the planner role
(Groq, Gemma fallback) picks one field among code-validated options
(build_r1_profile.field_options); a failed or late answer keeps the current field
or takes the best-scored one. The decision is applied at the single sync point
(regenerate the profile, r1_reload). Each death is recorded in danger.json and the
map is avoided for a few levels.
  first-job  irreversible class change on the reconciled bridge: the R1 profile
             in --ai=manual with m1_bridge (own port), travel to the Job Changer,
             one first_job request; success only from the server's job packet
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import m1, build_r1_profile
from scripts.bench_m2 import ram_sample
from scripts.prepare_m4 import bind_runtime

# Per character: login, bridge port, client name, runtime dir, secrets, policy and
# the registries of other profiles on the same account (never run two at once).
CHARACTERS = {
    'tarin': {'name': 'Tarin', 'userid': 'p1solo', 'port': 8772, 'client': 'r1-tarin', 'dir': 'r1',
              'secrets': 'p1/secrets.json', 'policy': 'config/r1-policy.json', 'same_account': ['p1/processes.json']},
    'nilo': {'name': 'Nilo', 'userid': 'p5novice', 'port': 8773, 'client': 'r1-nilo', 'dir': 'r1-nilo',
             'secrets': 'p5/secrets.json', 'policy': 'config/r1-policy-nilo.json', 'same_account': ['p5/processes.json']},
}
WHO = 'tarin'
NAME, USERID, PORT, CLIENT = 'Tarin', 'p1solo', 8772, 'r1-tarin'
PLUGINS = 'r1_observer,r1_reload,r1_flee,raiseStat,raiseSkill'
JOBS = {0: 'Novice', 1: 'Swordman'}  # OpenKore jobID -> classes the generator knows skill prefixes for
RELOAD_CONFIRM_S = 60
SUPPLY_AI = {'sellAuto', 'buyAuto', 'storageAuto'}
CONSUMED = {512, 507, 601}  # useSelf_item Apple/Red Herb, teleport Fly Wing
RAM_MIN, GPU_MAX = 2 * 1024**3, 14336
DEATHS_MAX, DEATH_WINDOW_S = 3, 900
FLY_WING = '601'


def use(who):
    """Select the character every command acts on."""
    global WHO, NAME, USERID, PORT, CLIENT
    c = CHARACTERS[who]
    WHO, NAME, USERID, PORT, CLIENT = who, c['name'], c['userid'], c['port'], c['client']


def default_policy():
    return ROOT/CHARACTERS[WHO]['policy']


def same_account(runtime):
    """Registered clients of other profiles on this account."""
    return [n for n in CHARACTERS[WHO]['same_account'] if (runtime.resolve()/n).exists()]


def paths(runtime):
    base = runtime.resolve()/CHARACTERS[WHO]['dir']
    return {'base': base, 'profile': base/'openkore'/WHO, 'observer': base/'observer',
            'events': base/'observer/events.jsonl', 'summary': base/'summary.json',
            'field': base/'field.json', 'decisions': base/'field-decisions.jsonl', 'danger': base/'danger.json',
            'effective': base/'policy-effective.json'}


def load(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def effective_policy(runtime, policy_path=None):
    """The policy as last applied (observed facts and chosen field), else the configured one."""
    p = paths(runtime)
    if p['effective'].exists() and policy_path is None:
        return load(p['effective'], None)
    return json.loads(Path(policy_path or default_policy()).read_text(encoding='utf-8'))


def with_field(policy, field):
    policy = json.loads(json.dumps(policy))
    policy['rules'][0]['do']['hunt']['field'] = field
    return policy


def bind(runtime):
    bind_runtime(runtime)
    m1.RUN = paths(runtime)['base']
    (m1.RUN/'logs').mkdir(parents=True, exist_ok=True)


def prepare(runtime, policy_path=None, character=None):
    """Write the profile. With character (observed facts), only the generated
    files are rewritten, for r1_reload to apply in place."""
    p, template = paths(runtime), runtime.resolve()/'openkore/agent'
    password = json.loads((runtime.resolve()/CHARACTERS[WHO]['secrets']).read_text())['password']
    policy = effective_policy(runtime, policy_path)
    if policy['identity'] != NAME:
        raise ValueError(f'policy is for {policy["identity"]}, not {NAME}')
    if character:
        policy['character'] = character
    if p['field'].exists():
        policy = with_field(policy, load(p['field'], None)['field_id'])
    result = build_r1_profile.translate(policy, build_r1_profile.load_tables(), load(p['danger'], {}))
    p['base'].mkdir(parents=True, exist_ok=True)
    m1.write(p['effective'], json.dumps(policy, indent=1, ensure_ascii=False))
    files = build_r1_profile.render(result, (template/'config.txt').read_text(encoding='utf-8'))
    for key, value in {'username': USERID, 'password': password}.items():
        files['config.txt'] = re.sub(rf'(?m)^{key}(?:[ \t].*)?$', lambda _: f'{key} {value}', files['config.txt'], count=1)
    p['profile'].mkdir(parents=True, exist_ok=True)
    (p['profile']/'logs').mkdir(exist_ok=True)
    p['observer'].mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        m1.write(p['profile']/name, text)
    if character:
        return result
    for name in ('servers.txt', 'timeouts.txt'):
        shutil.copyfile(template/name, p['profile']/name)
    # The profile is first in --tables, so OpenKore's shop/portal recording
    # writes these copies instead of the pinned vendor tables.
    for name in build_r1_profile.WRITTEN_TABLES:
        shutil.copyfile(m1.OK/'tables'/name, p['profile']/name)
    sys_txt = (template/'sys.txt').read_text()
    sys_txt = re.sub(r'(?m)^loadPlugins_list.*$', f'loadPlugins_list {PLUGINS}', sys_txt)
    m1.write(p['profile']/'sys.txt', sys_txt)
    report = {'mapping': result['mapping'], 'gaps': result['gaps'],
              'avoided_maps': sorted(k for k in result['weights'] if k not in build_r1_profile.TRANSPORT_WEIGHTS)}
    m1.write(p['base']/'profile-report.json', json.dumps(report, indent=1, default=str))
    print(f'R1 profile ready: {p["profile"]} (gaps: {[g["rule"] for g in result["gaps"]]})')
    return result


class FieldChoice:
    """One field decision at a time: validated options, one planner request, and a
    deterministic answer when the planner fails, is late or is off."""
    def __init__(self, runtime, service=None):
        from agent.goal_planner import FieldPlanner
        self.runtime, self.service = runtime, service
        self.planner = FieldPlanner(service) if service else None
        self.pending = None

    def start(self, policy, why, history=None):
        if self.pending:
            raise RuntimeError('one field decision at a time')
        p = paths(self.runtime)
        current = load(p['field'], {}).get('field_id') or policy['rules'][0]['do']['hunt']['field']
        stored = load(p['field'], {}).get('history', {})
        for name, h in (history or {}).items():
            row = stored.setdefault(name, {'kills': 0, 'hunt_s': 0})
            row['kills'] += h['kills']; row['hunt_s'] += h['hunt_s']
        options = build_r1_profile.field_options(policy, build_r1_profile.load_tables(), load(p['danger'], {}),
                                                 current, stored)
        if not options:
            raise ValueError('no validated field option')
        keep = current if any(o['current'] for o in options) else None
        c = policy['character']
        facts = {'level': c['level'], 'job': c['job'], 'stats': c['stats'], 'hp_max': c['hp_max']}
        self.pending = {'why': why, 'options': options, 'current': keep, 'previous': current, 'history': stored,
                        'facts': facts, 't': time.time()}
        if self.planner:
            from agent.hunting import temperament
            self.planner.request(facts, options, keep, temperament(NAME), why)
        return self.pending

    def poll(self):
        """None while waiting; else the decision, recorded in field.json and field-decisions.jsonl."""
        q = self.pending
        if not q:
            return None
        result = self.planner.poll() if self.planner else {'status': 'kept', 'reason': 'no_planner'}
        if result is None:
            return None
        self.pending = None
        ids = [o['field_id'] for o in q['options']]
        if result['status'] == 'proposed' and result['proposal']['field_id'] in ids:
            field, decision, reason = result['proposal']['field_id'], 'planner', result['proposal']['reason']
        else:
            field = q['current'] or ids[0]
            decision, reason = 'local_fallback', f"planner {result['status']}: {result.get('reason')}"
        record = {'t': time.time(), 'trigger': q['why'], 'field_id': field, 'previous': q['previous'],
                  'decision': decision, 'reason': reason, 'served_by': result.get('served_by'),
                  'degraded': result.get('degraded'), 'facts': q['facts'],
                  'options': [[o['field_id'], o['score']] for o in q['options']], 'history': q['history']}
        p = paths(self.runtime)
        m1.write(p['field'], json.dumps(record, indent=1))
        with p['decisions'].open('a', encoding='utf-8') as f:
            f.write(json.dumps(record) + '\n')
        return record

    def decide(self, policy, why, history=None, timeout=110):
        """Synchronous decision (before a client runs)."""
        self.start(policy, why, history)
        end = time.time() + timeout
        while True:
            out = self.poll()
            if out:
                return out
            if time.time() > end:
                raise TimeoutError('field decision')
            time.sleep(.5)


def planner_service():
    from inference.roles import build_role
    return build_role('planner')  # cloud primary, local fallback, explicit errors


def field_history(events):
    """Own kills and hunting seconds per map in these events (the last sample's map)."""
    out, here, last = {}, None, None
    for e in events:
        if e['type'] == 'sample' and e.get('connected'):
            if here and last is not None and not e['dead'] and not e['sitting']:
                out.setdefault(here, {'kills': 0, 'hunt_s': 0})['hunt_s'] += min(e['t'] - last, 15)
            here, last = e['map'], e['t']
        elif e['type'] == 'kill' and here:
            out.setdefault(here, {'kills': 0, 'hunt_s': 0})['kills'] += 1
    return {k: {'kills': v['kills'], 'hunt_s': round(v['hunt_s'])} for k, v in out.items()}


def ready_for_first_job(sample):
    """Novice at Job 10 with no unspent skill points: the custom Job Changer's own rule
    (config/npc/first-job-changer.txt). The class change itself goes through the bridge."""
    return sample.get('job_id', 0) == 0 and sample['level']['job'] >= 10 and sample.get('points_skill', 0) == 0


def facts_of(sample):
    """Policy character facts from one observer sample; None for a class the generator does not know."""
    job = JOBS.get(sample.get('job_id', 0))
    if not job or not sample.get('equipped'):
        return None
    return {'source': f'observer sample t={sample["t"]}', 'job': job,
            'level': {'base': sample['level']['base'], 'job': sample['level']['job']},
            'stats': sample['stats'], 'hp_max': sample['hp_max'], 'equipped': sample['equipped']}


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
           'character': NAME, 'same_account_registries': same_account(runtime),
           'r1_registry': (paths(runtime)['base']/'processes.json').exists(),
           'ports_free': {port: m1.available(port) for port in (8770, 8771, 8772, 8773)}, **resources()}
    out['ok'] = (all(out['services'][n] for n in ('mariadb', 'login-server', 'char-server', 'map-server'))
                 and not out['same_account_registries'] and not out['r1_registry'] and out['ports_free'][PORT]
                 and out['ram_available'] >= RAM_MIN and out['gpu_used_mib'] < GPU_MAX)
    print(json.dumps(out, indent=1))
    return out


def start(runtime):
    p = paths(runtime)
    bind(runtime)
    if same_account(runtime):
        raise RuntimeError(f'another client registered for the same account: {same_account(runtime)}; refusing')
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


def first_job(runtime, job):
    """One reconciled class change. Never resends an action: an uncertain result
    is recorded for reconciliation and the client is stopped."""
    from bridge.client import Bridge
    p = paths(runtime)
    bind(runtime)
    if same_account(runtime) or (m1.RUN/'processes.json').exists():
        raise RuntimeError('A client for this account is registered; stop it first')
    bridge_dir = p['base']/'bridge'
    bridge_dir.mkdir(parents=True, exist_ok=True)
    config = bridge_dir/'bridge.json'
    m1.write(config, json.dumps({'agent_id': WHO, 'port': PORT, 'token': secrets.token_hex(20),
                                 'native_navigation': True}))
    sys_txt = p['profile']/'sys.txt'
    auto_plugins = sys_txt.read_text()
    m1.write(sys_txt, re.sub(r'(?m)^loadPlugins_list.*$', 'loadPlugins_list m1_bridge,r1_observer', auto_plugins))
    args = [m1.PERL/'perl/bin/perl.exe', f'-I{ROOT/"bridge/lib"}', 'openkore.pl',
            f'--control={p["profile"]};{m1.OK/"control"}', f'--tables={p["profile"]};{m1.OK/"tables"}',
            f'--logs={p["profile"]/"logs"}', f'--plugins={ROOT/"bridge/openkore"};{ROOT/"bridge/r1"}',
            '--interface=M1Headless', '--ai=manual']
    env = m1.env_perl()
    env.update(M1_BRIDGE_CONFIG=str(config), R1_OBSERVER_DIR=str(p['observer']))
    process = m1.launch(args, CLIENT, m1.OK, env)
    m1.write(m1.RUN/'processes.json', json.dumps({CLIENT: {'pid': process.pid,
        'exe': str((m1.PERL/'perl/bin/perl.exe').resolve()), 'started': time.time()}}, indent=2))
    log = {'job': job, 'started': time.time(), 'pid': process.pid, 'requests': []}
    try:
        m1.wait_port(PORT, 60)
        b = Bridge(config)

        def snapshot(timeout=900):
            end = time.time() + timeout
            while time.time() < end:
                b.poll(.5)
                b.drain()  # only the latest snapshot matters here
                s = b.latest and b.latest['data']
                if s and s.get('connected') and s.get('inventory_ready') and time.time() * 1000 - b.latest['time_ms'] < 2000:
                    return s
            raise TimeoutError('no fresh in-game snapshot')

        def act(action, timeout):
            snapshot()
            request = b.proposal(action, request_id=b.serial_id())
            entry = {'request': request['id'], 'action': action, 'results': []}
            log['requests'].append(entry)
            end = time.time() + timeout + 30
            while time.time() < end:
                received = b.poll(.5)
                b.drain()
                for e in received:
                    if e['kind'] == 'action_result' and e['data']['request_id'] == request['id']:
                        entry['results'].append(e['data'])
                        if e['data']['status'] != 'accepted':
                            return e['data']
            return {'status': 'unknown', 'reason': 'no_final_result_observed'}

        start = snapshot()
        log['before'] = {k: start.get(k) for k in ('map', 'position', 'level', 'zeny')}
        if start['map'] != 'prontera':
            moved = act({'type': 'travel', 'map': 'prontera', 'x': 153, 'y': 190, 'timeout_s': 300}, 300)
            if moved['status'] != 'completed':
                log['outcome'] = 'travel_' + moved['status']; return log
        else:
            moved = act({'type': 'navigate', 'map': 'prontera', 'x': 153, 'y': 190, 'timeout_s': 60}, 60)
        log['outcome'] = act({'type': 'first_job', 'job': job, 'timeout_s': 30}, 30)
        after = snapshot(30)
        log['after'] = {k: after.get(k) for k in ('map', 'position', 'level', 'zeny', 'progress')}
        return log
    finally:
        log['ended'] = time.time()
        m1.write(p['base']/'first-job.json', json.dumps(log, indent=1, default=str))
        if alive(process.pid):
            stop(runtime)
        m1.write(sys_txt, auto_plugins)


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
    """Trial metrics from observer events. Pure: tests feed recorded events. The hunt
    field is lock_map plus every lockMap a confirmed reload applied."""
    samples = [e for e in events if e['type'] == 'sample' and e.get('connected')]
    locks = {lock_map} | {e['lockMap'] for e in events if e['type'] == 'reloaded' and e.get('ok') and e.get('lockMap')}
    if started is None:
        started = events[0]['t'] if events else 0
    span = (samples[-1]['t'] - samples[0]['t']) if len(samples) > 1 else 0
    share = {'hunt': 0.0, 'rest': 0.0, 'travel': 0.0, 'supply': 0.0, 'dead': 0.0}
    for a, b in zip(samples, samples[1:]):
        dt = min(b['t'] - a['t'], 15)
        state = ('dead' if a['dead'] else 'supply' if SUPPLY_AI & set(a['ai']) else
                 ('rest' if a['sitting'] else 'hunt') if a['map'] in locks else 'travel')
        share[state] += dt
    deaths = []
    for d in (e for e in events if e['type'] == 'died'):
        back = next((s for s in samples if s['t'] > d['t'] and not s['dead'] and s['map'] in locks), None)
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
    refits = [{'t': e['t'], 'id': e['id'], 'ok': e['ok'], 'lockMap': e['lockMap'], 'error': e['error']}
              for e in events if e['type'] == 'reloaded']
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
            'flees': [{k: e.get(k) for k in ('t', 'map', 'why', 'aggressives')} for e in events if e['type'] == 'flee'],
            'fly_wings': {'start': first.get('inventory', {}).get(FLY_WING, 0), 'end': last.get('inventory', {}).get(FLY_WING, 0)},
            'npc_dialogs': [{'name': e['name'], 'map': e['map'], 'supply': bool(SUPPLY_AI & set(e.get('ai', [])))}
                            for e in events if e['type'] == 'npc_talk'],
            'refits': refits, 'unexpected': unexpected, 'disconnects': sum(1 for e in events if e['type'] == 'disconnected')}


def lock_map(policy):
    if not isinstance(policy, dict):
        policy = json.loads(Path(policy).read_text(encoding='utf-8'))
    return policy['rules'][0]['do']['hunt']['field']


def watch(runtime, seconds, policy_path=None, summary=None, ram_min=RAM_MIN, service=None):
    """Supervise one bounded run: only guards, measurement and the single refit
    point (field decision, regenerated profile, r1_reload), never game input."""
    p = paths(runtime)
    policy = effective_policy(runtime, policy_path)
    lock = lock_map(policy)
    bind(runtime)
    pid = json.loads((m1.RUN/'processes.json').read_text())[CLIENT]['pid']
    started, reason, res = time.time(), 'time_budget', []
    # Refit from the level the profile was generated for, so a character that has
    # outgrown it is refit as soon as it is observed.
    refit_level = policy['character']['level']['base']
    pending, refit_log, choice, deaths_seen, since_decision = None, [], FieldChoice(runtime, service), 0, started
    died_since_choice, choice_facts = False, None
    try:
        while time.time() - started < seconds:
            time.sleep(10)
            if not alive(pid):
                reason = 'client_exited'; break
            sample = resources(pid); sample['t'] = time.time(); res.append(sample)
            if sample['ram_available'] < ram_min:
                reason = 'ram_guard'; break
            if sample['gpu_used_mib'] >= GPU_MAX:
                reason = 'gpu_guard'; break
            events = read_events(p['events'], started)
            deaths = [e for e in events if e['type'] == 'died' and e['t'] > time.time() - DEATH_WINDOW_S]
            if len(deaths) >= DEATHS_MAX:
                reason = 'death_loop'; break
            samples = [e for e in events if e['type'] == 'sample' and e.get('connected')]
            died = [e for e in events if e['type'] == 'died']
            for d in died[deaths_seen:]:
                # A death marks its map as dangerous and asks for a new field decision.
                level = (d.get('level') or {}).get('base') or refit_level
                m1.write(p['danger'], json.dumps(build_r1_profile.record_death(load(p['danger'], {}), d.get('map'),
                                                                               level, d['t']), indent=1))
            died_since_choice = died_since_choice or len(died) > deaths_seen
            deaths_seen = len(died)
            why = 'death' if died_since_choice else None
            if samples:
                if ready_for_first_job(samples[-1]):
                    reason = 'job10_ready'; break
                base = samples[-1]['level']['base']
                if base > refit_level:
                    why = why or 'level_up'
                facts = facts_of(samples[-1])
                if why and facts and not pending and not choice.pending:
                    refit_level = max(refit_level, base)
                    policy = effective_policy(runtime)
                    policy['character'] = facts
                    died_since_choice, choice_facts = False, facts
                    try:
                        choice.start(policy, why, field_history(read_events(p['events'], since_decision)))
                        since_decision = time.time()
                    except ValueError as e:  # no validated option: keep the loaded profile
                        refit_log.append({'t': time.time(), 'facts': facts, 'error': str(e)})
                decided = choice.poll()
                if decided:
                    # Single sync point: regenerate from observed facts and the chosen field, then ask r1_reload.
                    try:
                        result = prepare(runtime, None, choice_facts)
                    except ValueError as e:
                        refit_log.append({'t': time.time(), 'field': decided['field_id'], 'error': str(e)})
                        result = None
                    if result:
                        pending = (f'refit-{base}-{int(time.time())}', time.time())
                        m1.write(p['observer']/'reload.request', pending[0])
                        refit_log.append({'t': time.time(), 'id': pending[0], 'trigger': decided['trigger'],
                                          'field': decided['field_id'], 'decision': decided['decision'],
                                          'served_by': decided['served_by'],
                                          'classes': {k: sum(1 for v in result['kinds'].values() if v == k)
                                                      for k in ('viable', 'spare', 'aggressive', 'threat')}})
            if pending:
                done = [e for e in events if e['type'] == 'reloaded' and e['id'] == pending[0]]
                if done and not done[-1]['ok']:
                    reason = 'reload_failed'; break
                if done:
                    pending = None
                elif time.time() - pending[1] > RELOAD_CONFIRM_S:
                    reason = 'reload_unconfirmed'; break
            bad = [u for u in summarize(events, lock, started)['unexpected'] if u['kind'] != 'inventory_loss']
            if bad:
                reason = f'unexpected:{bad[0]["kind"]}'; break
    except KeyboardInterrupt:
        reason = 'interrupted'
    finally:
        if alive(pid):
            stop(runtime)
    out = summarize(read_events(p['events'], started), lock, started)
    out['field_decisions'] = [d for d in (json.loads(l) for l in p['decisions'].read_text(encoding='utf-8').splitlines())
                              if d['t'] >= started] if p['decisions'].exists() else []
    cpu = [r for r in res if r['cpu_s'] is not None]
    out['refit_requests'] = refit_log
    out.update({'ram_min_gib': round(ram_min / 2**30, 2), 'stop_reason': reason, 'started': started, 'ended': time.time(), 'pid': pid,
                'resources': {'samples': len(res),
                              'cpu_pct_one_core': round(100 * (cpu[-1]['cpu_s'] - cpu[0]['cpu_s']) / (cpu[-1]['t'] - cpu[0]['t']), 2) if len(cpu) > 1 else None,
                              'client_ws_max_mib': round(max(r['client_ws'] for r in res) / 2**20) if res else None,
                              'ram_available_min_gib': round(min(r['ram_available'] for r in res) / 2**30, 2) if res else None,
                              'gpu_used_mib': [min(r['gpu_used_mib'] for r in res), max(r['gpu_used_mib'] for r in res)] if res else None}})
    m1.write(summary or p['summary'], json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ('stop_reason', 'span_s', 'kills', 'kills_per_h', 'base_exp_per_h', 'deaths', 'time_share_s')}))
    return out


def campaign(runtime, seconds, job, summary_dir, ram_min=RAM_MIN, service=None):
    """One unattended run: auto until Job 10, the reconciled first-job step, the
    policy for the new class and auto again until the budget ends. Any other stop
    ends it; nothing is retried or resent."""
    p = paths(runtime)
    summary_dir.mkdir(parents=True, exist_ok=True)
    started, legs, n = time.time(), [], 0
    while time.time() - started < seconds - 60:
        n += 1
        start(runtime)
        out = watch(runtime, seconds - (time.time() - started), None, summary_dir/f'leg-{n}.json', ram_min, service)
        legs.append({'leg': n, 'stop_reason': out['stop_reason'], 'span_s': out['span_s']})
        if out['stop_reason'] != 'job10_ready':
            break
        log = first_job(runtime, job)
        legs.append({'first_job': log.get('outcome'), 'before': log.get('before'), 'after': log.get('after')})
        m1.write(summary_dir/'first-job.json', json.dumps(log, indent=1, default=str))
        outcome = log.get('outcome') or {}
        if not isinstance(outcome, dict) or outcome.get('status') != 'completed':
            break
        samples = [e for e in read_events(p['events'], log['started']) if e['type'] == 'sample' and e.get('connected')]
        facts = facts_of(samples[-1]) if samples else None
        if not facts or facts['job'] != job:
            legs.append({'stop': 'new_class_not_observed'}); break
        policy = effective_policy(runtime)
        policy['character'] = facts
        FieldChoice(runtime, service).decide(policy, 'class_change')
        prepare(runtime, None, facts)
    record = {'started': started, 'ended': time.time(), 'seconds': seconds, 'legs': legs,
              'interventions': 0, 'note': 'interventions counts manual actions during the campaign; it starts at 0 and '
                                          'any manual stop, restart or command ends the campaign'}
    m1.write(summary_dir/'campaign.json', json.dumps(record, indent=1, default=str))
    print(json.dumps(record, default=str))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('preflight', 'prepare', 'start', 'watch', 'stop', 'report', 'first-job',
                                            'campaign'))
    parser.add_argument('--job', default='Swordman', choices=('Swordman', 'Mage', 'Archer', 'Acolyte', 'Merchant', 'Thief'))
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--seconds', type=int, default=3600)
    parser.add_argument('--since', type=float, default=0)
    parser.add_argument('--character', default='tarin', choices=sorted(CHARACTERS))
    parser.add_argument('--policy', type=Path, help="default: the character's config/r1-policy*.json")
    parser.add_argument('--summary', type=Path, help='summary path (default <character dir>/summary.json)')
    parser.add_argument('--ram-min-gib', type=float, default=RAM_MIN / 2**30,
                        help='stop below this free RAM (default 2; the user may lower it)')
    parser.add_argument('--no-inference', action='store_true', help='field decisions without the planner')
    parser.add_argument('--out', type=Path, help='campaign: summaries directory')
    args = parser.parse_args()
    use(args.character)
    service = None if args.no_inference or args.command not in ('prepare', 'watch', 'campaign') else planner_service()
    try:
        run(args, service)
    finally:
        if service:
            service.close()


def run(args, service):
    if args.command == 'preflight':
        preflight(args.runtime)
    elif args.command == 'prepare':
        bind(args.runtime)
        policy = effective_policy(args.runtime, args.policy)
        print(json.dumps({k: v for k, v in FieldChoice(args.runtime, service).decide(policy, 'start').items()
                          if k in ('field_id', 'decision', 'served_by', 'reason', 'options')}))
        prepare(args.runtime, args.policy)
    elif args.command == 'start':
        start(args.runtime)
    elif args.command == 'watch':
        watch(args.runtime, args.seconds, args.policy, args.summary, int(args.ram_min_gib * 2**30), service)
    elif args.command == 'campaign':
        campaign(args.runtime, args.seconds, args.job, args.out or paths(args.runtime)['base']/'campaign',
                 int(args.ram_min_gib * 2**30), service)
    elif args.command == 'stop':
        stop(args.runtime)
    elif args.command == 'first-job':
        log = first_job(args.runtime, args.job)
        print(json.dumps({k: log.get(k) for k in ('outcome', 'before', 'after')}, default=str))
    else:
        print(json.dumps(summarize(read_events(paths(args.runtime)['events'], args.since),
                                   lock_map(effective_policy(args.runtime, args.policy)), args.since or None), indent=1))


if __name__ == '__main__':
    main()
