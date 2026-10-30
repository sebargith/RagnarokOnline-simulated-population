"""Idempotent local M4 profiles/fixture. Never initializes or resets a database.

Creates three NEW test accounts, then optionally restarts only the map server
and project clients. M1 characters, profiles, M3 memory and WIP are preserved.
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


def bind_runtime(runtime):
    base = runtime.resolve().parent
    m1.ROOT, m1.RUN, m1.VENDOR = base, runtime.resolve(), base/'vendor'
    m1.RA, m1.OK = m1.VENDOR/'rathena', m1.VENDOR/'openkore'
    m1.DB, m1.PERL = m1.VENDOR/'mariadb/bin', m1.VENDOR/'strawberry-perl'


def client(who):
    profile = m1.RUN/'m4/openkore'/who
    args = [m1.PERL/'perl/bin/perl.exe', f'-I{ROOT / "bridge/lib"}', 'openkore.pl',
            f'--control={profile};{m1.OK / "control"}', f'--tables={profile};{m1.OK / "tables"}',
            f'--logs={profile / "logs"}', f'--plugins={ROOT / "bridge/openkore"}', '--interface=M1Headless', '--ai=off']
    registry = m1.RUN/'processes.json'
    processes = json.loads(registry.read_text())
    name = 'm4-'+who
    if name in processes:
        raise RuntimeError(f'{name} already registered')
    env = m1.env_perl()
    env['M1_BRIDGE_CONFIG'] = str(profile/'bridge.json')
    process = m1.launch(args, name, m1.OK, env)
    processes[name] = {'pid': process.pid, 'exe': str((m1.PERL/'perl/bin/perl.exe').resolve())}
    m1.write(registry, json.dumps(processes, indent=2))


def stop_client(who):
    try:
        m1.stop(who)
    except RuntimeError as error:
        if 'no longer belongs' not in str(error):
            raise
        # The lifecycle helper verified a different executable at a reused PID.
        # Remove only the stale registry entry; never signal that process.
        registry = m1.RUN/'processes.json'
        processes = json.loads(registry.read_text())
        processes.pop(who, None)
        m1.write(registry, json.dumps(processes, indent=2))
        print(f'Removed stale {who} registry entry; process untouched.')


def prepare(runtime):
    bind_runtime(runtime)
    identities = json.loads((ROOT/'config/m4-identities.json').read_text())
    secret_path = runtime/'m4/secrets.json'
    if not secret_path.exists():
        m1.write(secret_path, json.dumps({who: {'password': secrets.token_hex(10), 'token': secrets.token_hex(20)} for who in identities}))
    credentials = json.loads(secret_path.read_text())
    for index, (who, identity) in enumerate(identities.items()):
        account = 2000010+index
        # INSERT IGNORE only; existing records are never updated or replenished.
        m1.sql(f"""USE ragnarok;
INSERT IGNORE INTO login(account_id,userid,user_pass,sex,email)
VALUES({account},'m4{who}','{credentials[who]['password']}','M','m4@localhost');
INSERT INTO `char`(account_id,char_num,name,class,base_level,job_level,str,agi,vit,`int`,dex,luk,max_hp,hp,max_sp,sp,zeny,last_map,last_x,last_y,save_map,save_x,save_y,sex)
SELECT {account},0,'{identity['name']}',0,10,10,10,10,10,10,20,10,500,500,50,50,100,'prontera',{150+index},180,'prontera',{150+index},180,'M'
WHERE NOT EXISTS(SELECT 1 FROM `char` WHERE account_id={account});
INSERT IGNORE INTO skill(char_id,id,lv,flag) SELECT char_id,1,1,0 FROM `char` WHERE account_id={account};
""")
        profile = runtime/'m4/openkore'/who
        for filename in ('config.txt', 'servers.txt', 'sys.txt', 'timeouts.txt'):
            text = (runtime/'openkore/agent'/filename).read_text()
            if filename == 'config.txt':
                for key, value in {'username': 'm4'+who, 'password': credentials[who]['password'], 'dealAuto': '0'}.items():
                    text = re.sub(rf'(?m)^{key}(?:[ \t].*)?$', key+' '+value, text)
            m1.write(profile/filename, text)
        (profile/'logs').mkdir(exist_ok=True)
        m1.write(profile/'bridge.json', json.dumps({'agent_id': who, 'port': 8765+index, 'token': credentials[who]['token'], 'm4_fixture': True,
            'trade_role': {'agent': 'seller', 'peer': 'buyer'}.get(who),
            'trade_peer': identities['peer' if who == 'agent' else 'agent']['name']}))
    m1.write(m1.RA/'npc/custom/m4-pve.txt', (ROOT/'fixtures/m4-pve.txt').read_text())
    include = m1.RA/'npc/scripts_custom.conf'
    text = include.read_text()
    if '\nnpc: npc/custom/m4-pve.txt\n' not in text:
        m1.write(include, text+'\nnpc: npc/custom/m4-pve.txt\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--start', action='store_true')
    parser.add_argument('--clients-only', action='store_true')
    args = parser.parse_args()
    bind_runtime(args.runtime)
    if args.start:
        for who in ('agent', 'peer', 'm4-agent', 'm4-peer', 'm4-third'):
            stop_client(who)
    if not args.clients_only:
        prepare(args.runtime)
    if args.start:
        if not args.clients_only:
            m1.restart_map()
        for who in ('agent', 'peer', 'third'):
            client(who)
    print('M4 profiles ready; existing characters and database preserved.')


if __name__ == '__main__':
    main()
