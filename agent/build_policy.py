"""Deterministic P5 build policy: one stat, skill or equip action from a snapshot.

No model is involved. The build is chosen elsewhere (agent.goal_planner.BuildPlanner);
this policy only turns the observed `progress` and `inventory` facts into the
next bridge action, which the bridge admits again and confirms with the server.
"""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STATS = ('str', 'agi', 'vit', 'int', 'dex', 'luk')
JOBS = ('Novice', 'Swordman', 'Mage', 'Archer', 'Acolyte', 'Merchant', 'Thief')
SKILL = re.compile(r'^[A-Z][A-Z0-9_]{1,31}$')
TIMEOUT_S = 10
# Comparable equipment slots and the score used inside each one. Accessories
# and other slots without a simple score are left as they are.
SLOTS = {'Right_Hand': 'weapon', 'Both_Hand': 'weapon', 'Left_Hand': 'shield', 'Armor': 'armor',
         'Garment': 'garment', 'Shoes': 'shoes', 'Head_Top': 'head_top', 'Head_Mid': 'head_mid',
         'Head_Low': 'head_low'}


def load_builds(path=None):
    doc = json.loads(Path(path or ROOT/'config/p5-builds.json').read_text(encoding='utf-8'))
    for name, build in doc['builds'].items():
        if build['target_class'] not in JOBS[1:]:
            raise ValueError(f'{name}: unknown target class')
        for stat, target in build['stats']:
            if stat not in STATS or type(target) is not int or not 1 <= target <= 99:
                raise ValueError(f'{name}: invalid stat step')
        for handle, level in build['skills']:
            if not SKILL.match(handle) or type(level) is not int or not 1 <= level <= 10:
                raise ValueError(f'{name}: invalid skill step')
    return doc['builds']


def load_equipment(path=None):
    return json.loads(Path(path or ROOT/'config/p5-equipment.json').read_text(encoding='utf-8'))['items']


def can_wear(entry, progress, base_level):
    """Same rule as M1Progress::validate_equip, so the bridge will not refuse it."""
    gender = entry.get('gender', 'Both')
    sex = 'Male' if progress.get('sex') == 1 else 'Female'
    return (progress.get('job') in entry['jobs'] and base_level >= entry['min_level']
            and (gender == 'Both' or gender == sex))


def _slot(entry):
    slots = {SLOTS[loc] for loc in entry['locations'] if loc in SLOTS}
    return slots.pop() if len(slots) == 1 else None


def _score(entry):
    return entry['attack'] if entry['type'] == 'Weapon' else entry['defense']


def stat_action(progress, build):
    if not progress.get('stats_ready'):
        return None, 'stats_not_observed'
    for stat, target in build['stats']:
        s = progress['stats'][stat]
        if s['value'] >= target:
            continue
        if s['cost'] and progress['points_free'] >= s['cost']:
            return {'type': 'stat_up', 'stat': stat, 'timeout_s': TIMEOUT_S}, f'{stat}_below_{target}'
        return None, f'saving_points_for_{stat}'
    return None, 'stat_plan_done'


def skill_action(progress, build):
    if progress.get('points_skill', 0) < 1:
        return None, 'no_skill_points'
    listed = {s['handle']: s for s in progress.get('skills', [])}
    for handle, target in build['skills']:
        s = listed.get(handle)
        if s and s['lv'] < target and s['up']:
            return {'type': 'skill_up', 'skill': handle, 'timeout_s': TIMEOUT_S}, f'{handle}_below_{target}'
    return None, 'no_upgradable_skill_in_plan'


def equip_action(snap, equipment):
    progress, base = snap['progress'], snap['level']['base']
    current, unknown = {}, set()
    for item in snap['inventory']:
        if not item['equipped']:
            continue
        entry = equipment.get(str(item['name_id']))
        slot = entry and _slot(entry)
        if slot:
            current[slot] = max(current.get(slot, -1), _score(entry))
        else:
            # Something we cannot score is worn; leave every slot it might use.
            unknown.update(SLOTS.values() if not entry else {SLOTS.get(l) for l in entry['locations']})
    best = None
    for item in snap['inventory']:
        entry = equipment.get(str(item['name_id']))
        if item['equipped'] or not item.get('identified', 1) or not entry or not can_wear(entry, progress, base):
            continue
        slot = _slot(entry)
        if not slot or slot in unknown:
            continue
        # A shield cannot be added next to a two-handed weapon and vice versa.
        if slot == 'shield' and any(i['equipped'] and 'Both_Hand' in (equipment.get(str(i['name_id'])) or {}).get('locations', [])
                                    for i in snap['inventory']):
            continue
        gain = _score(entry) - current.get(slot, -1)
        if gain > 0 and (best is None or gain > best[0] or (gain == best[0] and item['name_id'] < best[1])):
            best = (gain, item['name_id'], slot)
    if best:
        return {'type': 'equip', 'name_id': best[1], 'timeout_s': TIMEOUT_S}, f'better_{best[2]}'
    return None, 'nothing_better_to_equip'


def next_action(snap, build, equipment):
    """Return (action, reason) or (None, reasons). Stats, then skills, then gear."""
    if not snap.get('connected') or snap.get('dead') or snap.get('native_task') or 'progress' not in snap:
        return None, 'not_ready'
    if not snap.get('inventory_ready') or snap.get('inventory_truncated', True):
        return None, 'incomplete_inventory'
    reasons = []
    for step in (lambda: stat_action(snap['progress'], build), lambda: skill_action(snap['progress'], build),
                 lambda: equip_action(snap, equipment)):
        action, why = step()
        if action:
            return action, why
        reasons.append(why)
    return None, ','.join(reasons)
