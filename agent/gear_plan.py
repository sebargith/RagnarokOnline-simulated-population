"""Deterministic NPC-shop gear upgrades (docs/PROGRESSION_ECONOMY.md, E2).

From the policy's recorded facts (class, level, equipped, inventory, Zeny) and
the generated equipment table, decide:
- equip: per OpenKore slot, the best wearable item the character already owns;
- buys: in slot priority order, the best affordable strict upgrade per slot, each
  paid from what the previous ones leave, all within a Zeny reserve for consumables,
  so one trip to town buys them all; buy is the first of them (or None).
No model is involved; the decision carries its facts so it can be audited.
"""
from agent.build_policy import _score, _slot, can_wear

# Slots in buying order: damage first, then the body, then the rest.
PRIORITY = ('weapon', 'armor', 'shield', 'shoes', 'garment', 'head_top', 'head_mid', 'head_low')
OPENKORE_SLOT = {'weapon': 'rightHand', 'shield': 'leftHand', 'armor': 'armor', 'garment': 'robe',
                 'shoes': 'shoes', 'head_top': 'topHead', 'head_mid': 'midHead', 'head_low': 'lowHead'}


def wearable(entry, character, gear):
    """Class, level and gender (only 'Both' while the sex is not observed), and the
    build's weapon preference: allowed weapon types, no two-handed weapon with a shield."""
    progress = {'job': character['job']}
    if entry.get('gender', 'Both') != 'Both' or not can_wear(entry, progress, character['level']['base']):
        return False
    if entry['type'] == 'Weapon':
        types = gear.get('weapon_types')
        if types and entry['subtype'] not in types:
            return False
        if gear.get('shield') and 'Both_Hand' in entry['locations']:
            return False
    return _slot(entry) in OPENKORE_SLOT


def owned(character):
    """Item ids the character has, equipped or not (inventory counts equipped items too)."""
    ids = {int(i) for i in character.get('equipped', [])}
    ids |= {int(i) for i, n in (character.get('inventory') or {}).items() if n > 0}
    return ids


def best_owned(character, equipment, gear):
    """slot -> (score, id): the best item the character owns per slot; ties keep what is worn."""
    worn = {int(i) for i in character.get('equipped', [])}
    best = {}
    for iid in sorted(owned(character)):
        entry = equipment.get(str(iid))
        # What is worn counts as is (the server accepted it); a spare must pass the rule.
        if not entry or _slot(entry) not in OPENKORE_SLOT or (iid not in worn and not wearable(entry, character, gear)):
            continue
        key = (_score(entry), iid in worn)
        slot = _slot(entry)
        if slot not in best or key > best[slot][0]:
            best[slot] = (key, iid)
    return {slot: (key[0], iid) for slot, (key, iid) in best.items()}


def plan(character, equipment, gear, shops, reserve):
    """-> {'equip': {okslot: id}, 'buys': [...], 'buy': buys[0] | None, 'reason': str, 'facts': {...}}.
    shops: allowed NPC shop names in preference order. reserve: Zeny kept for consumables."""
    have = best_owned(character, equipment, gear)
    zeny = int(character.get('zeny') or 0)
    budget = zeny - reserve
    facts = {'job': character['job'], 'base_level': character['level']['base'], 'zeny': zeny,
             'reserve': reserve, 'current': {s: have[s][1] for s in sorted(have)}}
    equip = {OPENKORE_SLOT[s]: iid for s, (_, iid) in sorted(have.items())}
    buys, reason = [], 'no_affordable_upgrade' if budget > 0 else 'below_reserve'
    for slot in PRIORITY if budget > 0 else ():
        if slot == 'shield' and gear.get('shield') is False:
            continue
        current = have.get(slot, (0, None))[0]
        options = []
        for iid, entry in equipment.items():
            sold = [s for s in shops if s in entry.get('shops', [])]
            if (sold and _slot(entry) == slot and wearable(entry, character, gear)
                    and _score(entry) > current and 0 < entry['buy'] <= budget):
                options.append((-_score(entry), entry['buy'], int(iid), sold[0]))
        if options:
            _, price, iid, shop = min(options)
            entry = equipment[str(iid)]
            buys.append({'id': iid, 'name': entry['name'], 'slot': slot, 'okslot': OPENKORE_SLOT[slot],
                         'price': price, 'shop': shop, 'score': _score(entry), 'gain': _score(entry) - current})
            equip[OPENKORE_SLOT[slot]] = iid
            budget -= price
            if not reason.startswith('upgrade_'):
                reason = f'upgrade_{slot}'
    return {'equip': equip, 'buys': buys, 'buy': buys[0] if buys else None, 'reason': reason, 'facts': facts}
