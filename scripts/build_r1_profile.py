"""R1 trial: translate the declarative policy (config/r1-policy.json) into an
OpenKore profile for --ai=auto: config.txt, mon_control.txt, items_control.txt
and routeweights.txt.

Deterministic: same policy and pinned data give the same files. Each rule maps
to native OpenKore keys only; a rule with no native equivalent becomes a gap in
the report, never custom code. Credentials are not handled here (run_r1.py adds
them when it writes the live profile).
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent import build_policy, hunting

RATHENA = ROOT.parent/'vendor/rathena'
OPENKORE = ROOT.parent/'vendor/openkore'
SUPPLY_MAPS = {'prontera', 'prt_in'}
JOB_SKILL_PREFIX = {'Novice': 'NV_'}
TRANSPORT_WEIGHTS = {'NPC', 'COMMAND', 'AIRSHIP'}
# Unconditional profile settings (not decisions): the observer only reads, so
# OpenKore must not trade, gather others' loot or sit idle like a bot, nor
# record portals into the pinned tables (portalRecord rewrites portals.txt).
BASE = {'dealAuto': '1', 'itemsGatherAuto': '0', 'sitAuto_idle': '0', 'storageAuto': '0',
        'teleportAuto_dropTargetEngaged': '0', 'attackChangeTarget': '1', 'portalRecord': '0'}
# Tables OpenKore writes back to while playing; the profile keeps its own copy.
WRITTEN_TABLES = ('portals.txt', 'npc_shops.txt')


def load_summoners(path=None):
    """Monsters with NPC_SUMMONSLAVE in the pinned pre-Renewal mob_skill_db: master id -> minion ids."""
    out = {}
    for line in Path(path or RATHENA/'db/pre-re/mob_skill_db.txt').read_text(encoding='utf-8', errors='replace').splitlines():
        cols = line.split(',')
        if line.startswith('//') or len(cols) < 17 or '@NPC_SUMMONSLAVE' not in cols[1]:
            continue
        out.setdefault(int(cols[0]), set()).update(int(v) for v in cols[12:17] if v.strip().isdigit())
    return out


def load_shops(paths=None):
    """NPC shop name -> 'map x y' from the pinned rAthena shop scripts."""
    out = {}
    for path in paths or (RATHENA/'npc/merchants/shops.txt', RATHENA/'npc/pre-re/merchants/shops.txt'):
        for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
            m = re.match(r'^(\w+),(\d+),(\d+),\d+\tshop\t([^\t]+)\t', line)
            if m:
                out[m.group(4)] = f'{m.group(1)} {m.group(2)} {m.group(3)}'
    return out


def me_of(character, equipment):
    """The same strength estimate as hunting.profile, from the policy's recorded facts."""
    snap = {'progress': {'stats': {k: {'value': v} for k, v in character['stats'].items()}},
            'inventory': [{'equipped': True, 'name_id': i} for i in character['equipped']],
            'level': character['level'], 'hp_max': character['hp_max']}
    return hunting.profile(snap, equipment)


def classify(monsters, summoners, me, exp_min=0):
    """Per monster id: 'threat' (boss or summoner), 'viable', 'aggressive' (not viable) or 'spare'.
    exp_min drops targets worth no EXP (plants take 1 damage per hit and give none)."""
    out = {}
    for key, mob in monsters.items():
        if mob['boss'] or int(key) in summoners:
            out[key] = 'threat'
        elif hunting.assess(mob, me)['viable'] and mob['base_exp'] >= exp_min:
            out[key] = 'viable'
        else:
            out[key] = 'aggressive' if mob['aggressive'] else 'spare'
    return out


def hostile(field, monsters, kinds):
    """Why a field is dangerous to cross: boss spawns, summoners or rare aggressive threats."""
    why = set()
    for spawn in field['monsters']:
        kind = kinds.get(str(spawn['id']))
        if spawn.get('boss_spawn') or monsters.get(str(spawn['id']), {}).get('boss'):
            why.add('boss')
        if kind == 'threat' and not monsters[str(spawn['id'])]['boss']:
            why.add('summoner')
        if spawn['rare'] and kind == 'aggressive':
            why.add('rare_threat')
    return why


def translate(policy, tables):
    """Rules -> {config, blocks, mon, items, weights, gaps, mapping}. tables: monsters, fields,
    builds, equipment, summoners, shops."""
    monsters, fields = tables['monsters'], tables['fields']['fields']
    me = me_of(policy['character'], tables['equipment'])
    exp_min = max([r.get('requires', {}).get('base_exp_at_least', 0) for r in policy['rules']])
    kinds = classify(monsters, tables['summoners'], me, exp_min)
    config, blocks, mon, items, weights, gaps, mapping = dict(BASE), [], {}, {}, {}, [], {}
    columns = {'viable': [1, 0], 'spare': [0, 0], 'aggressive': [0, 0], 'threat': [0, 0]}
    lock = None

    def emit(rule, **keys):
        config.update(keys)
        mapping.setdefault(rule['id'], []).extend(keys)

    for rule in policy['rules']:
        do, req, rid = rule['do'], rule.get('requires', {}), rule['id']
        if 'hunt' in do:
            lock = do['hunt']['field']
            if lock not in fields:
                raise ValueError(f'{rid}: unknown field {lock}')
            emit(rule, lockMap=lock, attackAuto='2', route_randomWalk='1', route_randomWalk_inTown='0',
                 attackAuto_notInTown='1', itemsTakeAuto='2')
        elif 'attack' in do:
            # mon_control <attack>: 1 always attack, 0 only when it attacks first.
            kind = 'viable' if req.get('assess') == 'viable' else None
            for k in ([kind] if kind else ['spare', 'aggressive', 'threat']):
                columns[k][0] = 1 if do['attack'] == 'always' else 0
            mapping.setdefault(rid, []).append('mon_control.attack')
        elif do.get('teleport') and rule['on'] == 'attacked_by':
            columns['aggressive'][1] = 2  # teleport when it attacks; needs a Fly Wing
            mapping.setdefault(rid, []).append('mon_control.teleport=2')
        elif do.get('teleport') and rule['on'] == 'monster_near':
            columns['threat'][1] = -int(rule['value'])  # teleport at this distance
            mapping.setdefault(rid, []).append(f'mon_control.teleport=-{rule["value"]}')
        elif 'avoid_map' in do:
            wanted = set(req.get('field_has', []))
            for name in sorted(fields):
                if name in SUPPLY_MAPS or name == lock:
                    continue
                if hostile(fields[name], monsters, kinds) & wanted:
                    weights[name] = int(do['avoid_map'])
            mapping.setdefault(rid, []).append(f'routeweights x{len([w for w in weights if w not in TRANSPORT_WEIGHTS])}')
        elif 'warp_fee_max' in do:
            emit(rule, route_maxWarpFee=str(do['warp_fee_max']))
            for kind in do.get('avoid_transport', []):
                weights[kind] = 10000
            mapping[rid].extend(do.get('avoid_transport', []))
        elif 'sit_until_hp' in do:
            emit(rule, sitAuto_hp_lower=str(rule['value']), sitAuto_hp_upper=str(do['sit_until_hp']))
        elif 'use_item' in do:
            # Item ids: names come from the kRO tables (Korean); getByNameList also matches ids.
            blocks.append(('useSelf_item', ','.join(str(i) for i in do['use_item']),
                           {'hp': f'< {rule["value"]}%', 'timeout': '2', 'notWhileSitting': '0'}))
            mapping.setdefault(rid, []).append('useSelf_item')
        elif 'sell_at' in do:
            emit(rule, sellAuto='1', sellAuto_npc=tables['shops'][do['sell_at']],
                 itemsMaxWeight_sellOrStore=str(rule['value']))
            items['all'] = '0 0 1'
            for item in do.get('keep', []):
                items[str(item)] = '0 0 0'
        elif 'buy' in do:
            buy = do['buy']
            blocks.append(('buyAuto', str(buy['item']), {'npc': tables['shops'][buy['at']],
                           'minAmount': str(buy['min']), 'maxAmount': str(buy['max']),
                           'zeny': f'>= {req["zeny_at_least"]}'}))
            mapping.setdefault(rid, []).append(f'buyAuto {buy["name"]}')
        elif 'raise_build' in do:
            build = tables['builds'][do['raise_build']]
            prefix = JOB_SKILL_PREFIX[policy['character']['job']]
            emit(rule, statsAddAuto='1', statsAddAuto_dontUseBonus='1',
                 statsAddAuto_list=', '.join(f'{v} {s}' for s, v in build['stats']),
                 skillsAddAuto='1',
                 skillsAddAuto_list=', '.join(f'{s} {v}' for s, v in build['skills'] if s.startswith(prefix)))
        elif do.get('teleport') and rule['on'] == 'hp_below':
            emit(rule, teleportAuto_hp=str(rule['value']))
        elif do.get('teleport') and rule['on'] == 'aggressives_at_least':
            emit(rule, teleportAuto_minAggressives=str(rule['value']))
        elif do.get('respawn'):
            # Native: processDead sends the restart; lockMap routes back to the field.
            emit(rule, dcOnDeath='0')
        else:
            gaps.append({'rule': rid, 'on': rule['on'], 'do': do,
                         'why': GAP_REASONS.get(next(iter(do)), 'no native OpenKore equivalent')})

    if lock and hostile(fields[lock], monsters, kinds):
        raise ValueError(f'hunt field {lock} is hostile: {sorted(hostile(fields[lock], monsters, kinds))}')
    for key in sorted(monsters, key=int):
        attack, teleport = columns[kinds[key]]
        mon[key] = (f'{attack} {teleport} 0 0 0 0 0 0 0', monsters[key]['name'], kinds[key])
    return {'config': config, 'blocks': blocks, 'mon': mon, 'items': items, 'weights': weights,
            'gaps': gaps, 'mapping': mapping, 'kinds': kinds, 'me': me}


GAP_REASONS = {
    'move_away': 'melee without Fly Wing: OpenKore has no flee for melee (runFromTarget only keeps range '
                 'while attacking); routeWeights is fixed at load time, so a map cannot be avoided after the fact',
    'regenerate_profile': 'OpenKore applies config on load/reload only; raising stats is native '
                          '(raiseStat) but re-deciding viability per level needs the planner to rewrite and reload',
}


def render(result, template):
    """Profile files as text. template: the agent config.txt text the live profiles start from."""
    text = template
    for name in ('useSelf_item', 'buyAuto'):  # drop the empty template blocks
        text = re.sub(rf'(?m)^{name} {{\n(?:.*\n)*?}}\n', '', text, count=1)
    for key, value in result['config'].items():
        line = f'{key} {value}'
        text, n = re.subn(rf'(?m)^{re.escape(key)}(?:[ \t].*)?$', lambda _: line, text, count=1)
        if not n:
            text += line + '\n'
    for name, value, keys in result['blocks']:
        text += f'\n{name} {value} {{\n' + ''.join(f'\t{k} {v}\n' for k, v in keys.items()) + '}\n'
    mon = ['# Generated by scripts/build_r1_profile.py from config/r1-policy.json; do not edit.',
           '# <id>\t<attack> <teleport> <search> <skillcancel> <lv> <joblv> <hp> <sp> <weight>  # name (class)',
           'all\t0 0 0 0 0 0 0 0 0']
    mon += [f'{key}\t{cols}  # {name} ({kind})' for key, (cols, name, kind) in result['mon'].items()]
    items = ['# Generated by scripts/build_r1_profile.py; <item> <keep> <store> <sell>']
    items += [f'{key} {value}' for key, value in result['items'].items()]
    weights = ['# Generated by scripts/build_r1_profile.py; <map or transport> <weight>',
               'PORTAL 20', 'WARPTOSAVEMAP 200', 'ZENY 0.1', 'TICKET 100']
    weights += [f'{key} {value}' for key, value in sorted(result['weights'].items())]
    return {'config.txt': text, 'mon_control.txt': '\n'.join(mon) + '\n',
            'items_control.txt': '\n'.join(items) + '\n', 'routeweights.txt': '\n'.join(weights) + '\n'}


def load_tables():
    return {'monsters': hunting.load_monsters(), 'fields': hunting.load_fields(),
            'builds': build_policy.load_builds(),
            'equipment': build_policy.load_equipment(), 'summoners': load_summoners(), 'shops': load_shops()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', type=Path, default=ROOT/'config/r1-policy.json')
    parser.add_argument('--template', type=Path, required=True, help='agent config.txt to start from')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = translate(json.loads(args.policy.read_text(encoding='utf-8')), load_tables())
    args.out.mkdir(parents=True, exist_ok=True)
    for name, text in render(result, args.template.read_text(encoding='utf-8')).items():
        (args.out/name).write_text(text, encoding='utf-8', newline='\n')
    report = {'mapping': result['mapping'], 'gaps': result['gaps'],
              'avoided_maps': sorted(k for k in result['weights'] if k not in TRANSPORT_WEIGHTS),
              'classes': {k: sum(1 for v in result['kinds'].values() if v == k) for k in ('viable', 'spare', 'aggressive', 'threat')}}
    (args.out/'r1-report.json').write_text(json.dumps(report, indent=1, default=str) + '\n', encoding='utf-8')
    print(json.dumps({'gaps': [g['rule'] for g in result['gaps']], **{k: report[k] for k in ('classes',)},
                      'avoided_maps': len(report['avoided_maps'])}))


if __name__ == '__main__':
    main()
