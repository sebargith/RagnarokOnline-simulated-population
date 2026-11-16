"""Progression metrics from R1 observer events (docs/PROGRESSION_ECONOMY.md, E3).

Pure: tests feed recorded events. Level alone does not show progress, so this
reports what the character's gear buys it in the field:
- power: ATK and DEF of the worn gear (generated equipment table), per change;
- wealth: Zeny plus the inventory at NPC sell price;
- combat per monster and per worn-gear set: time to kill, hits, misses, damage
  taken and dodges per kill (from kill events with combat facts);
- per hunt field: kills and base EXP per hour of hunting time.
The comparison is empirical (same monster, before/after a gear change), not a
damage formula.
"""
from statistics import median

HUNT_GAP_S = 15  # a longer gap between samples is not counted as hunting


def gear_power(equipped, equipment):
    """(ATK, DEF) of the worn items the table knows; unknown ids add nothing."""
    atk = dfn = 0
    for iid in equipped or []:
        entry = equipment.get(str(iid))
        if entry:
            atk += entry['attack'] if entry['type'] == 'Weapon' else 0
            dfn += entry['defense'] if entry['type'] == 'Armor' else 0
    return atk, dfn


def sell_value(item_id, equipment, loot):
    entry = equipment.get(str(item_id)) or loot.get(str(item_id))
    return entry['sell'] if entry else None


def wealth(sample, equipment, loot):
    """Zeny + inventory at NPC sell price; ids with no known price are counted apart."""
    goods, unknown = 0, 0
    for iid, amount in (sample.get('inventory') or {}).items():
        price = sell_value(iid, equipment, loot)
        if price is None:
            unknown += amount
        else:
            goods += price * amount
    zeny = int(sample.get('zeny') or 0)
    return {'zeny': zeny, 'goods': goods, 'total': zeny + goods, 'unpriced_items': unknown}


def _avg(values):
    return round(sum(values) / len(values), 2) if values else None


def combat(kills):
    """Per-kill facts -> summary; kills without combat facts (older observer) count only."""
    full = [k for k in kills if k.get('hits') is not None and k.get('duration_s') is not None]
    hits = sum(k['hits'] for k in full)
    attacks_taken = sum(k['dmg_taken'] > 0 or k['dodged'] > 0 for k in full)
    return {'kills': len(kills), 'measured': len(full),
            'ttk_s_median': round(median(k['duration_s'] for k in full), 2) if full else None,
            'hits_per_kill': _avg([k['hits'] for k in full]),
            'miss_rate': round(sum(k['misses'] for k in full) / hits, 3) if hits else None,
            'dmg_dealt_per_hit': round(sum(k['dmg_dealt'] for k in full) / (hits - sum(k['misses'] for k in full)), 1)
            if hits > sum(k['misses'] for k in full) else None,
            'dmg_taken_per_kill': _avg([k['dmg_taken'] for k in full]),
            'kills_hit_by_monster': attacks_taken}


def report(events, equipment, loot, hunt_maps=None):
    samples = [e for e in events if e['type'] == 'sample' and e.get('connected')]
    kills = [e for e in events if e['type'] == 'kill']
    out = {'samples': len(samples), 'kills': len(kills)}
    if not samples:
        return out
    # Power: every change of worn gear, with the time it was first seen.
    timeline, last = [], None
    for s in samples:
        worn = tuple(sorted(s.get('equipped') or []))
        if worn != last:
            atk, dfn = gear_power(worn, equipment)
            timeline.append({'t': s['t'], 'equipped': list(worn), 'atk': atk, 'def': dfn})
            last = worn
    out['power'] = {'start': timeline[0], 'end': timeline[-1], 'changes': timeline[1:]}
    out['wealth'] = {'start': wealth(samples[0], equipment, loot), 'end': wealth(samples[-1], equipment, loot)}
    # Combat per monster and per gear set worn at the kill (the latest sample before it).
    groups = {}
    for k in kills:
        before = [s for s in samples if s['t'] <= k['t']]
        worn = tuple(sorted((before[-1] if before else samples[0]).get('equipped') or []))
        key = (k.get('name_id', 0), worn)
        groups.setdefault(key, {'name': k.get('name', ''), 'kills': []})['kills'].append(k)
    out['by_monster'] = sorted(
        ({'name_id': mid, 'name': g['name'], 'equipped': list(worn), 'atk_def': list(gear_power(worn, equipment)),
          **combat(g['kills'])} for (mid, worn), g in groups.items()),
        key=lambda r: (-r['kills'], r['name_id'], r['atk_def']))
    # Per field: hunting time on that map, kills and base EXP there.
    fields = {}
    for a, b in zip(samples, samples[1:]):
        if hunt_maps is not None and a['map'] not in hunt_maps:
            continue
        if a['dead'] or a['sitting'] or set(a.get('ai', [])) & {'sellAuto', 'buyAuto', 'storageAuto'}:
            continue
        f = fields.setdefault(a['map'], {'hunt_s': 0.0, 'kills': 0, 'base_exp': 0})
        f['hunt_s'] += min(b['t'] - a['t'], HUNT_GAP_S)
        la, lb = a.get('level') or {}, b.get('level') or {}
        if la.get('base') == lb.get('base') and 'exp' in la and 'exp' in lb:
            f['base_exp'] += max(0, lb['exp'] - la['exp'])
        f['kills'] += sum(1 for k in kills if a['t'] < k['t'] <= b['t'])
    out['by_field'] = {m: {**f, 'hunt_s': round(f['hunt_s']),
                           'kills_per_hunt_h': round(f['kills'] * 3600 / f['hunt_s'], 1) if f['hunt_s'] else None,
                           'base_exp_per_hunt_h': round(f['base_exp'] * 3600 / f['hunt_s']) if f['hunt_s'] else None}
                       for m, f in sorted(fields.items())}
    hours = (samples[-1]['t'] - samples[0]['t']) / 3600
    out['risk_per_h'] = {kind: round(sum(1 for e in events if e['type'] == kind) / hours, 2) if hours else None
                         for kind in ('died', 'teleport', 'flee')}
    return out
