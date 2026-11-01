"""Build config/p5-monsters.json and config/p5-fields.json from pinned public data.

Monsters come from rAthena pre-Renewal mob_db.yml (what a player reads on a
monster wiki page: level, HP, ATK, DEF, aggressiveness, speed, EXP). Fields come
from the field spawn scripts the pre-Renewal server loads, and their walkable
exits from OpenKore's portals table, with the same filter as
M1Travel::walk_graph: free, talk-less, permanent map-to-map portals only.
Each field also gets, per neighbour, a walkable hunting entry spot read from
OpenKore's field files (the same walk map the client-side route uses).
Custom server scripts (the M4 fixture) are not read. No live server state.
"""
import argparse
import gzip
import json
from pathlib import Path
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RATHENA = ROOT.parent/'vendor/rathena'
OPENKORE = ROOT.parent/'vendor/openkore'
SPAWNS_CONF = 'npc/pre-re/scripts_monsters.conf'
FIELD_DIR = 'npc/pre-re/mobs/fields/'
MOB_DB = 'db/pre-re/mob_db.yml'
PORTALS = 'tables/portals.txt'
# src/map/mob.hpp e_aegis_monstertype; bits from status.hpp e_mode.
AI_MODES = {'01': 0x81, '02': 0x83, '03': 0x1089, '04': 0x3885, '05': 0x2085, '06': 0, '07': 0x108B,
            '08': 0x7085, '09': 0x3095, '10': 0x84, '11': 0x84, '12': 0x2085, '13': 0x308D, '17': 0x91,
            '19': 0x3095, '20': 0x3295, '21': 0x3695, '24': 0xA1, '25': 0x1, '26': 0xB695, '27': 0x8084}
MD_CANMOVE, MD_AGGRESSIVE, MD_CANATTACK = 0x1, 0x4, 0x80
MODE_BITS = {'CanMove': MD_CANMOVE, 'Aggressive': MD_AGGRESSIVE, 'CanAttack': MD_CANATTACK}
DEFAULT_WALK_SPEED = 150
SPAWN = re.compile(r'^([a-z0-9_]+),\d+,\d+(?:,\d+,\d+)?\t(monster|boss_monster)\t[^\t]+\t(\d+),(\d+)(?:,(\d+))?')
RARE_DELAY_MS = 600000  # A respawn delay of ten minutes or more is a rare, placed spawn.
ENTRY_STEPS = 10


def mobs(text):
    mob, section = None, None
    for line in text.splitlines():
        if line.startswith('  - Id: '):
            if mob:
                yield mob
            mob, section = {'Id': int(line[8:]), 'Modes': {}}, None
        elif mob is None or not line.strip() or line.lstrip().startswith('#'):
            continue
        elif line.startswith('      ') and section == 'Modes':
            key, _, value = line.strip().partition(': ')
            mob['Modes'][key] = value == 'true'
        elif line.startswith('    ') and not line.startswith('     '):
            key, _, value = line.strip().partition(':')
            value = value.strip()
            section = key if not value else None
            if value:
                mob[key] = value
    if mob:
        yield mob


def monster(m):
    mode = AI_MODES[m.get('Ai', '06')]
    for name, bit in MODE_BITS.items():
        if name in m['Modes']:
            mode = mode | bit if m['Modes'][name] else mode & ~bit
    return {'name': m['Name'], 'level': int(m.get('Level', 1)), 'hp': int(m.get('Hp', 1)),
            'attack': [int(m.get('Attack', 0)), int(m.get('Attack2', 0))], 'defense': int(m.get('Defense', 0)),
            'aggressive': bool(mode & MD_AGGRESSIVE), 'can_attack': bool(mode & MD_CANATTACK),
            'can_move': bool(mode & MD_CANMOVE), 'boss': m.get('Class', 'Normal') != 'Normal',
            'walk_speed': int(m.get('WalkSpeed', DEFAULT_WALK_SPEED)),
            'attack_delay': int(m.get('AttackDelay', 0)),
            'base_exp': int(m.get('BaseExp', 0)), 'job_exp': int(m.get('JobExp', 0))}


def field_scripts():
    for line in (RATHENA/SPAWNS_CONF).read_text(encoding='utf-8').splitlines():
        if line.startswith('npc: ' + FIELD_DIR):
            yield line[5:].strip()


def spawns():
    fields = {}
    for name in field_scripts():
        for line in (RATHENA/name).read_text(encoding='utf-8', errors='replace').splitlines():
            match = SPAWN.match(line)
            if not match:
                continue
            area, kind, mob, amount, delay = match.groups()
            entry = fields.setdefault(area, {})
            spot = entry.setdefault(int(mob), {'count': 0, 'rare': True, 'boss_spawn': False})
            spot['count'] += int(amount)
            spot['rare'] = spot['rare'] and int(delay or 0) >= RARE_DELAY_MS
            spot['boss_spawn'] = spot['boss_spawn'] or kind == 'boss_monster'
    return fields


def portals():
    graph = {}
    for line in (OPENKORE/PORTALS).read_text(encoding='utf-8', errors='replace').splitlines():
        parts = line.split()
        # Only the bare six-field form: anything after it is a cost, ticket or talk sequence.
        if line.startswith('#') or len(parts) != 6 or not all(p.isdigit() for p in parts[1:3] + parts[4:6]):
            continue
        src, x, y, dst, tx, ty = parts
        if src != dst:
            graph.setdefault(src, []).append([int(x), int(y), dst, int(tx), int(ty)])
    return {m: sorted(e) for m, e in sorted(graph.items())}


def walk_map(name):
    """OpenKore .fld2: uint16 width, height, then one byte per cell; bit 1 = walkable."""
    path = OPENKORE/'fields'/f'{name}.fld2.gz'
    if not path.exists():
        return None
    data = gzip.decompress(path.read_bytes())
    width, height = struct.unpack('<HH', data[:4])
    return width, height, data[4:]


def entry_spot(grid, landing):
    """A walkable cell ENTRY_STEPS walking steps from where a portal lands, toward the map
    centre: away from the warp back, and reachable from the landing by construction."""
    width, height, cells = grid
    walk = lambda x, y: 0 <= x < width and 0 <= y < height and cells[y*width + x] & 1
    start = min(((x, y) for x in range(landing[0]-3, landing[0]+4) for y in range(landing[1]-3, landing[1]+4)
                 if walk(x, y)), key=lambda c: (abs(c[0]-landing[0]) + abs(c[1]-landing[1]), c), default=None)
    if not start:
        return None
    seen, ring = {start}, [start]
    for _ in range(ENTRY_STEPS):
        nxt = []
        for x, y in ring:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    c = (x+dx, y+dy)
                    if c not in seen and walk(*c):
                        seen.add(c); nxt.append(c)
        if not nxt:
            break
        ring = nxt
    centre = (width // 2, height // 2)
    best = min(ring, key=lambda c: ((c[0]-centre[0])**2 + (c[1]-centre[1])**2, c))
    return list(best)


def entries(name, graph):
    """For each neighbour map with a walkable portal into this field: where to hunt from."""
    grid = walk_map(name)
    spots = {}
    for src, edges in graph.items():
        for x, y, dst, tx, ty in edges:
            if dst == name and src not in spots and grid:
                spot = entry_spot(grid, (tx, ty))
                if spot:
                    spots[src] = spot
    return dict(sorted(spots.items()))


def commit(path):
    return subprocess.run(['git', '-C', str(path), 'rev-parse', 'HEAD'],
                          capture_output=True, text=True, check=True).stdout.strip()


def build():
    db = {m['Id']: m for m in mobs((RATHENA/MOB_DB).read_text(encoding='utf-8'))}
    fields, graph = spawns(), portals()
    used = sorted({mob for f in fields.values() for mob in f})
    monsters = {str(i): monster(db[i]) for i in used if i in db}
    table = {}
    for name, spots in sorted(fields.items()):
        table[name] = {'monsters': [{'id': mob, **spot} for mob, spot in sorted(spots.items()) if str(mob) in monsters],
                       'exits': graph.get(name, []), 'entries': entries(name, graph)}
    source = {'rathena_commit': commit(RATHENA), 'openkore_commit': commit(OPENKORE)}
    note = 'Generated by scripts/build_p5_hunting.py; do not edit by hand.'
    return ({'version': 1, 'source': {**source, 'mob_db': MOB_DB}, 'note': note, 'monsters': monsters},
            {'version': 1, 'source': {**source, 'spawns': SPAWNS_CONF, 'portals': PORTALS}, 'note': note,
             'fields': table, 'portals': graph})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default=str(ROOT/'config'))
    args = parser.parse_args()
    monsters, fields = build()
    for name, doc in (('p5-monsters.json', monsters), ('p5-fields.json', fields)):
        path = Path(args.out)/name
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"{len(monsters['monsters'])} monsters, {len(fields['fields'])} fields, "
          f"{len(fields['portals'])} maps with walkable portals -> {args.out}")


if __name__ == '__main__':
    main()
