"""Separate P1 native-navigation profile. Never initializes or resets a database.

Creates one NEW normal pre-Renewal novice (level 1, default start point and
items, no Zeny) and an OpenKore profile that runs with --ai=manual, so route
tasks are the only movement owner. Processes live in runtime/p1/processes.json;
M1/M4 registries, characters and clients are untouched.
"""
import argparse
import json
from pathlib import Path
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import m1
from scripts.prepare_m4 import bind_runtime

ACCOUNT, NAME, PORT = 2000030, 'Tarin', 8770


def prepare(runtime):
    bind_runtime(runtime)
    secret_path = runtime/'p1/secrets.json'
    if not secret_path.exists():
        m1.write(secret_path, json.dumps({'password': secrets.token_hex(10), 'token': secrets.token_hex(20)}))
    credentials = json.loads(secret_path.read_text())
    # Values follow rAthena's pre-Renewal new character: start_point_pre and
    # start_items_pre (Knife, Cotton Shirt equipped). INSERT only; never updated.
    m1.sql(f"""USE ragnarok;
INSERT IGNORE INTO login(account_id,userid,user_pass,sex,email)
VALUES({ACCOUNT},'p1solo','{credentials['password']}','M','p1@localhost');
INSERT INTO `char`(account_id,char_num,name,class,base_level,job_level,str,agi,vit,`int`,dex,luk,max_hp,hp,max_sp,sp,zeny,last_map,last_x,last_y,save_map,save_x,save_y,sex)
SELECT {ACCOUNT},0,'{NAME}',0,1,1,5,5,5,5,5,5,42,42,11,11,0,'new_1-1',53,111,'new_1-1',53,111,'M'
WHERE NOT EXISTS(SELECT 1 FROM `char` WHERE account_id={ACCOUNT});
INSERT INTO inventory(char_id,nameid,amount,equip,identify)
SELECT c.char_id,i.nameid,1,i.equip,1 FROM `char` c JOIN (SELECT 1201 nameid,2 equip UNION SELECT 2301,16) i
WHERE c.account_id={ACCOUNT} AND NOT EXISTS(SELECT 1 FROM inventory v WHERE v.char_id=c.char_id);
""")
    profile = runtime/'p1/openkore/solo'
    for filename in ('config.txt', 'servers.txt', 'sys.txt', 'timeouts.txt'):
        text = (runtime/'openkore/agent'/filename).read_text()
        if filename == 'config.txt':
            for key, value in {'username': 'p1solo', 'password': credentials['password'],
                    'dealAuto': '0', 'sitAuto_idle': '0'}.items():
                text = re.sub(rf'(?m)^{key}(?:[ \t].*)?$', key+' '+value, text)
        m1.write(profile/filename, text)
    (profile/'logs').mkdir(exist_ok=True)
    m1.write(profile/'bridge.json', json.dumps({'agent_id': 'solo', 'port': PORT,
        'token': credentials['token'], 'native_navigation': True}))
    print(f'P1 profile ready: {profile}')


def processes(runtime):
    # m1's lifecycle helpers use RUN for their registry and logs.
    m1.RUN = runtime.resolve()/'p1'
    (m1.RUN/'logs').mkdir(parents=True, exist_ok=True)


def start(runtime):
    profile = runtime.resolve()/'p1/openkore/solo'
    processes(runtime)
    registry = m1.RUN/'processes.json'
    if registry.exists():
        raise RuntimeError('P1 registry exists; stop it first')
    if not m1.available(PORT):
        raise RuntimeError(f'Port {PORT} is occupied')
    args = [m1.PERL/'perl/bin/perl.exe', f'-I{ROOT/"bridge/lib"}', 'openkore.pl',
        f'--control={profile};{m1.OK/"control"}', f'--tables={profile};{m1.OK/"tables"}',
        f'--logs={profile/"logs"}', f'--plugins={ROOT/"bridge/openkore"}', '--interface=M1Headless', '--ai=manual']
    env = m1.env_perl()
    env['M1_BRIDGE_CONFIG'] = str(profile/'bridge.json')
    process = m1.launch(args, 'p1-solo', m1.OK, env)
    m1.write(registry, json.dumps({'p1-solo': {'pid': process.pid,
        'exe': str((m1.PERL/'perl/bin/perl.exe').resolve())}}, indent=2))
    m1.wait_port(PORT, 60)
    print(f'P1 client listening on 127.0.0.1:{PORT}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'start', 'stop'))
    parser.add_argument('--runtime', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.runtime)
    else:
        bind_runtime(args.runtime)
        if args.command == 'start':
            start(args.runtime)
        else:
            processes(args.runtime)
            m1.stop('p1-solo')


if __name__ == '__main__':
    main()
