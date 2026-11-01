"""Separate P5 profile: one NEW pre-Renewal novice created like the server does.

Never initializes or resets a database, and never updates a row: INSERT only,
idempotent. The character gets what rAthena's char server gives a new one with
this client (PACKETVER 20211103): stats 1, start_status_points 48, HP 40/SP 11,
0 Zeny, start_items_pre (Knife and Cotton Shirt equipped) and one of the
start_point_pre maps picked at random, as the server picks it. After creation
only the game changes it. Processes live in runtime/p5/processes.json; Tarin
(P1), Visitor and every other account are untouched.
`check-save` only reads the stored save point (SELECT), for evidence.
"""
import argparse
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import m1
from scripts.prepare_m4 import bind_runtime

ACCOUNT, USERID, NAME, PORT = 2000031, 'p5novice', 'Nilo', 8771
# conf/char_athena.conf: start_point_pre, start_items_pre, start_zeny; char.cpp defaults.
START_POINTS = [('new_1-1', 53, 111), ('new_2-1', 53, 111), ('new_3-1', 53, 111), ('new_4-1', 53, 111), ('new_5-1', 53, 111)]
START_ITEMS = [(1201, 1, 2), (2301, 1, 16)]
STATUS_POINTS, HP, SP = 48, 40, 11  # 40*(100+VIT)/100 and 11*(100+INT)/100 with VIT=INT=1.


def query(sql):
    """Read-only query; returns tab-separated rows."""
    out = subprocess.run([str(m1.DB/'mariadb.exe'), f'--defaults-file={m1.RUN/"mariadb/root.ini"}', '-N', '-B', '-e', sql],
                         capture_output=True, text=True, creationflags=m1.FLAGS)
    if out.returncode:
        raise RuntimeError(f'mariadb exited {out.returncode}: {out.stderr.strip()[:200]}')
    return [line.split('\t') for line in out.stdout.splitlines() if line]


def prepare(runtime):
    bind_runtime(runtime)
    base = runtime/'p5'
    secret_path = base/'secrets.json'
    if not secret_path.exists():
        m1.write(secret_path, json.dumps({'password': secrets.token_hex(10), 'token': secrets.token_hex(20)}))
    credentials = json.loads(secret_path.read_text())
    if query(f"SELECT 1 FROM ragnarok.`char` WHERE name='{NAME}' AND account_id<>{ACCOUNT}"):
        raise RuntimeError(f'Name {NAME} belongs to another account')
    start = secrets.choice(START_POINTS)  # rnd() % start_point_count in char_make_new_char
    items = ' UNION '.join(f'SELECT {i} nameid,{a} amount,{e} equip' for i, a, e in START_ITEMS)
    m1.sql(f"""USE ragnarok;
INSERT IGNORE INTO login(account_id,userid,user_pass,sex,email)
VALUES({ACCOUNT},'{USERID}','{credentials['password']}','M','p5@localhost');
INSERT INTO `char`(account_id,char_num,name,class,base_level,job_level,zeny,status_point,str,agi,vit,`int`,dex,luk,max_hp,hp,max_sp,sp,last_map,last_x,last_y,save_map,save_x,save_y,sex)
SELECT {ACCOUNT},0,'{NAME}',0,1,1,0,{STATUS_POINTS},1,1,1,1,1,1,{HP},{HP},{SP},{SP},'{start[0]}',{start[1]},{start[2]},'{start[0]}',{start[1]},{start[2]},'M'
WHERE NOT EXISTS(SELECT 1 FROM `char` WHERE account_id={ACCOUNT});
INSERT INTO inventory(char_id,nameid,amount,equip,identify)
SELECT c.char_id,i.nameid,i.amount,i.equip,1 FROM `char` c JOIN ({items}) i
WHERE c.account_id={ACCOUNT} AND NOT EXISTS(SELECT 1 FROM inventory v WHERE v.char_id=c.char_id);
""")
    row = query(f"SELECT char_id,name,last_map,base_level,zeny,status_point FROM ragnarok.`char` WHERE account_id={ACCOUNT}")
    if not row or row[0][1] != NAME:
        raise RuntimeError('Character was not created')
    if not (base/'identity.json').exists():
        m1.write(base/'identity.json', json.dumps({'account_id': ACCOUNT, 'char_id': int(row[0][0]), 'name': NAME,
                                                   'created_at_map': row[0][2]}))
    profile = base/'openkore/solo'
    for filename in ('config.txt', 'servers.txt', 'sys.txt', 'timeouts.txt'):
        text = (runtime/'openkore/agent'/filename).read_text()
        if filename == 'config.txt':
            for key, value in {'username': USERID, 'password': credentials['password'], 'char': '0',
                    'dealAuto': '0', 'sitAuto_idle': '0',
                    'attackChangeTarget': '0', 'teleportAuto_dropTargetEngaged': '0'}.items():
                text = re.sub(rf'(?m)^{key}(?:[ \t].*)?$', key+' '+value, text)
        m1.write(profile/filename, text)
    (profile/'logs').mkdir(exist_ok=True)
    m1.write(profile/'bridge.json', json.dumps({'agent_id': 'p5', 'port': PORT,
        'token': credentials['token'], 'native_navigation': True}))
    print(json.dumps({'profile': str(profile), 'character': row[0]}))


def processes(runtime):
    m1.RUN = runtime.resolve()/'p5'
    (m1.RUN/'logs').mkdir(parents=True, exist_ok=True)


def start(runtime):
    profile = runtime.resolve()/'p5/openkore/solo'
    processes(runtime)
    registry = m1.RUN/'processes.json'
    if registry.exists():
        raise RuntimeError('P5 registry exists; stop it first')
    if not m1.available(PORT):
        raise RuntimeError(f'Port {PORT} is occupied')
    args = [m1.PERL/'perl/bin/perl.exe', f'-I{ROOT/"bridge/lib"}', 'openkore.pl',
        f'--control={profile};{m1.OK/"control"}', f'--tables={profile};{m1.OK/"tables"}',
        f'--logs={profile/"logs"}', f'--plugins={ROOT/"bridge/openkore"}', '--interface=M1Headless', '--ai=manual']
    env = m1.env_perl()
    env['M1_BRIDGE_CONFIG'] = str(profile/'bridge.json')
    process = m1.launch(args, 'p5-novice', m1.OK, env)
    m1.write(registry, json.dumps({'p5-novice': {'pid': process.pid,
        'exe': str((m1.PERL/'perl/bin/perl.exe').resolve())}}, indent=2))
    m1.wait_port(PORT, 60)
    print(f'P5 client listening on 127.0.0.1:{PORT}')


def check_save(runtime):
    row = query(f"SELECT name,last_map,last_x,last_y,save_map,save_x,save_y,base_level,job_level,zeny "
                f"FROM ragnarok.`char` WHERE account_id={ACCOUNT}")
    keys = ('name', 'last_map', 'last_x', 'last_y', 'save_map', 'save_x', 'save_y', 'base_level', 'job_level', 'zeny')
    print(json.dumps(dict(zip(keys, row[0])) if row else None))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'start', 'stop', 'check-save'))
    parser.add_argument('--runtime', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.runtime)
        return
    bind_runtime(args.runtime)
    if args.command == 'start':
        start(args.runtime)
    elif args.command == 'check-save':
        check_save(args.runtime)
    else:
        processes(args.runtime)
        m1.stop('p5-novice')


if __name__ == '__main__':
    main()
