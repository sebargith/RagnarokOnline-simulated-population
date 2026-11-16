"""Build config/p5-equipment.json from the pinned rAthena pre-Renewal item data.

The table holds what a player reads in an item's in-game description (classes,
required level, slot, ATK/DEF, weight, slots, refine) and in an NPC shop (price,
which shop) for the starting gear and every equipment item sold by an NPC shop. The bridge admits an equip only for items listed here;
anything else (rare loot) is rejected as equipment_requirements_unknown.
Only the fixed indentation layout of item_db_equip.yml is parsed (no PyYAML).
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RATHENA = ROOT.parent/'vendor/rathena'
# First classes reachable from Novice; anything else is out of P5's scope.
JOBS = ('Novice', 'Swordman', 'Mage', 'Archer', 'Acolyte', 'Merchant', 'Thief')
START = (1201, 2301)  # conf/char_athena.conf start_items_pre
SHOPS = ('npc/merchants/shops.txt', 'npc/pre-re/merchants/shops.txt')
SIZE_FIX = ('db/size_fix.yml', 'db/pre-re/size_fix.yml')  # base, then the pre-Renewal import


def size_fix():
    """Weapon type -> % damage against Small/Medium/Large (rAthena SizeFixDatabase: a
    missing size is 100; an import entry changes only the sizes it lists)."""
    table, weapon = {}, None
    for name in SIZE_FIX:
        for line in (RATHENA/name).read_text(encoding='utf-8').splitlines():
            if line.startswith('  - Weapon: '):
                weapon = table.setdefault(line.split(': ', 1)[1].strip(), {'Small': 100, 'Medium': 100, 'Large': 100})
            elif weapon is not None and line.startswith('    ') and ':' in line:
                key, _, value = line.strip().partition(': ')
                if key in weapon:
                    weapon[key] = int(value)
            elif not line.startswith(' '):
                weapon = None
    return dict(sorted(table.items()))


def entries(text):
    item, section = None, None
    for line in text.splitlines():
        if line.startswith('  - Id: '):
            if item:
                yield item
            item, section = {'Id': int(line[8:]), 'Jobs': None, 'Locations': {}}, None
        elif item is None or not line.strip() or line.lstrip().startswith('#'):
            continue
        elif line.startswith('      ') and section:
            key, _, value = line.strip().partition(': ')
            if section in ('Jobs', 'Locations'):
                if item[section] is None:
                    item[section] = {}
                item[section][key] = value == 'true'
        elif line.startswith('    ') and not line.startswith('     '):
            key, _, value = line.strip().partition(':')
            value = value.strip()
            section = key if not value else None
            if value:
                item[key] = value
    if item:
        yield item


def jobs(item):
    flags = item['Jobs'] if item['Jobs'] is not None else {'All': True}
    return [j for j in JOBS if flags.get(j, flags.get('All', False))]


def shop_items():
    """Item id -> sorted NPC shop names (the names scripts/build_r1_profile.py resolves)."""
    sold = {}
    for name in SHOPS:
        for line in (RATHENA/name).read_text(encoding='utf-8', errors='replace').splitlines():
            parts = line.split('\t')
            if len(parts) == 4 and parts[1] == 'shop' and not line.lstrip().startswith('//'):
                for i, price in re.findall(r',(\d+):(-?\d+)', parts[-1]):
                    # Every pinned shop sells at the item_db price (-1); anything else is not modelled.
                    if price != '-1':
                        raise ValueError(f'{parts[2]}: explicit price for {i}')
                    sold.setdefault(int(i), set()).add(parts[2])
    return {i: sorted(names) for i, names in sold.items()}


def prices(item):
    """NPC buy and sell prices as rAthena derives them (itemdb.cpp loadingFinished)."""
    buy, sell = item.get('Buy'), item.get('Sell')
    buy = int(buy) if buy is not None else (int(sell) * 2 if sell is not None else 0)
    sell = int(sell) if sell is not None else buy // 2
    if buy / 124 < sell / 75:  # discount/overcharge exploit guard
        sell = 1
    return buy, sell


def build():
    sold = shop_items()
    wanted = set(sold) | set(START)
    table = {}
    for item in entries((RATHENA/'db/pre-re/item_db_equip.yml').read_text(encoding='utf-8')):
        if item['Id'] not in wanted or item.get('Type') not in ('Weapon', 'Armor'):
            continue
        allowed = jobs(item)
        if not allowed or item.get('Classes', 'All') != 'All':
            continue
        table[str(item['Id'])] = {
            'name': item.get('Name', item['AegisName']), 'type': item['Type'],
            'subtype': item.get('SubType'), 'locations': sorted(k for k, v in item['Locations'].items() if v),
            'jobs': allowed, 'gender': item.get('Gender', 'Both'),
            'min_level': int(item.get('EquipLevelMin', 0)),
            'attack': int(item.get('Attack', 0)), 'defense': int(item.get('Defense', 0)),
            'buy': prices(item)[0], 'sell': prices(item)[1], 'weight': int(item.get('Weight', 0)) / 10,
            'slots': int(item.get('Slots', 0)), 'refineable': item.get('Refineable') == 'true',
            'weapon_level': int(item.get('WeaponLevel', 1)) if item['Type'] == 'Weapon' else None,
            'shops': sold.get(item['Id'], [])}
    commit = subprocess.run(['git', '-C', str(RATHENA), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, check=True).stdout.strip()
    return {'version': 2, 'source': {'rathena_commit': commit, 'item_db': 'db/pre-re/item_db_equip.yml',
            'shops': list(SHOPS), 'start_items': list(START), 'size_fix': list(SIZE_FIX)},
            'note': 'Generated by scripts/build_p5_equipment.py; do not edit by hand.',
            'size_fix': size_fix(),
            'items': dict(sorted(table.items(), key=lambda kv: int(kv[0])))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default=str(ROOT/'config/p5-equipment.json'))
    args = parser.parse_args()
    doc = build()
    Path(args.out).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"{len(doc['items'])} items -> {args.out}")


if __name__ == '__main__':
    main()
