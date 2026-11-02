"""P5 hunting knowledge: monster danger, viable targets and validated field options.

Deterministic, no model and no bridge IO. Inputs are the character's own
snapshot, the public tables (config/p5-monsters.json, config/p5-fields.json)
and the character's own outcome history from the cycle checkpoint.

The danger figures are a simple, explainable pre-Renewal estimate, not the exact
damage formula: hit/flee, ASPD variance, skills and elements are ignored.
"""
import hashlib
import json
from math import ceil
from pathlib import Path

from agent import walk

ROOT = Path(__file__).resolve().parents[1]
SHOP_MAP = 'prontera'  # scripts.p2_supply.SHOP; supply trips must fit the travel hop limit.
SHOP_STAND = (104, 51)  # scripts.p2_supply.SHOP['stand']
MAX_HOPS = walk.MAX_HOPS
PLAYER_DELAY_MS = 1500  # Conservative novice attack interval; ASPD is not observed.
LEVEL_MARGIN = 5
MAX_LOSS = .50          # Estimated HP lost per kill, as a share of max HP.
MAX_AGGRESSIVE_LOSS = .25
MAX_HITS = 12           # Longer fights are not worth it at this level.
RECENT_DEATH_S = 3600
MAX_OPTIONS = 6
NEAR_BEST = .90         # Options within 10% of the best score are equivalent.
TEMPERAMENTS = {
    'prudent': 'Prefers safer fields even if experience is slower.',
    'ambitious': 'Prefers the fastest experience among safe fields.',
    'explorer': 'Prefers fields it has not hunted yet when they are comparable.'}


def load_monsters(path=None):
    return json.loads(Path(path or ROOT/'config/p5-monsters.json').read_text(encoding='utf-8'))['monsters']


def load_fields(path=None):
    return json.loads(Path(path or ROOT/'config/p5-fields.json').read_text(encoding='utf-8'))


def temperament(identity):
    """Stable per character: the same name always gets the same temperament."""
    names = sorted(TEMPERAMENTS)
    return names[hashlib.sha256(identity.encode()).digest()[0] % len(names)]


def profile(snap, equipment):
    """Own observed strength: status ATK + weapon ATK, worn DEF, VIT soft DEF, HP and level."""
    stats = {k: v['value'] for k, v in snap['progress']['stats'].items()}
    atk, defense = stats['str'] + (stats['str'] // 10) ** 2 + stats['dex'] // 5 + stats['luk'] // 5, 0
    for item in snap['inventory']:
        entry = item['equipped'] and equipment.get(str(item['name_id']))
        if entry:
            atk += entry['attack'] if entry['type'] == 'Weapon' else 0
            defense += entry['defense']
    return {'level': snap['level']['base'], 'hp_max': snap['hp_max'], 'atk': atk,
            'def': min(defense, 99), 'soft_def': stats['vit'] // 2}


def assess(mob, me):
    """Estimated hits to kill and HP lost doing it; viable or the first reason it is not."""
    hit = max(1, int(me['atk'] * (100 - min(mob['defense'], 99)) / 100))
    hits = ceil(mob['hp'] / hit)
    taken = 0
    if mob['can_attack']:
        per_hit = max(1, sum(mob['attack']) / 2 * (100 - me['def']) / 100 - me['soft_def'])
        taken = hits * PLAYER_DELAY_MS / max(mob['attack_delay'], 500) * per_hit
    loss = round(taken / me['hp_max'], 2)
    why = ('boss' if mob['boss'] else
           'level_too_high' if mob['level'] > me['level'] + LEVEL_MARGIN else
           'fight_too_long' if hits > MAX_HITS else
           'too_much_damage' if loss > MAX_LOSS else
           'aggressive_and_risky' if mob['aggressive'] and loss > MAX_AGGRESSIVE_LOSS else None)
    return {'hits': hits, 'loss': loss, 'viable': why is None, 'why': why}


def learned_too_strong(record):
    """Own history: two bad outcomes that are more than a third of the encounters."""
    bad = record.get('retreats', 0) + record.get('deaths', 0)
    return bad >= 2 and bad * 3 > bad + record.get('kills', 0)


def viable(mob_id, monsters, me, outcomes):
    mob = monsters.get(str(mob_id))
    if not mob:
        return False
    return assess(mob, me)['viable'] and not learned_too_strong(outcomes.get(str(mob_id), {}))


def walk_table(tables):
    """Zone graph (agent/walk.py); the real config/walk-zones.json unless tables carry one."""
    if 'walk' not in tables:
        tables['walk'] = walk.load()
    return tables['walk']


def hops(walk_graph, start, goal, start_zone=None, goal_zone=None):
    """Fewest walkable-portal map hops between walk zones (same graph and limits as
    M1Travel::route) and the last other map before the goal; None when unreachable."""
    if start == goal and (start_zone is None or goal_zone is None or start_zone == goal_zone):
        return 0, None
    r = walk.route(walk_graph, start, goal, start_zone, goal_zone)
    return (r['hops'], r['via']) if r else None


def entry_zone(entry):
    return entry[2] if len(entry) > 2 else None


def field_facts(name, field, monsters, me, outcomes):
    total = sum(s['count'] for s in field['monsters'] if not s['rare']) or 1
    common, threats, rare = [], [], []
    for spawn in field['monsters']:
        mob = monsters[str(spawn['id'])]
        a = assess(mob, me)
        ok = a['viable'] and not learned_too_strong(outcomes.get(str(spawn['id']), {}))
        if spawn['rare']:
            if not ok and (mob['aggressive'] or mob['boss']):
                rare.append(mob['name'])
            continue
        row = {'id': spawn['id'], 'name': mob['name'], 'level': mob['level'], 'share': round(spawn['count'] / total, 2),
               'aggressive': mob['aggressive'], 'hits': a['hits'], 'hp_loss': a['loss'], 'viable': ok,
               'base_exp': mob['base_exp'], 'why': a['why'] or ('learned_too_strong' if not ok else None)}
        common.append(row)
        if not ok and mob['aggressive']:
            threats.append(mob['name'])
    good = [m for m in common if m['viable']]
    value = sum(m['share'] * m['base_exp'] / m['hits'] for m in good)
    danger = sum(m['share'] * m['hp_loss'] for m in good) / (sum(m['share'] for m in good) or 1)
    return {'monsters': common, 'aggressive_threats': threats, 'rare_threats': rare,
            'viable_share': round(sum(m['share'] for m in good), 2),
            'exp_per_hit': round(value, 2), 'danger': round(danger, 2)}


def history_view(record, now):
    minutes = record.get('hunt_s', 0) / 60
    return {'kills': record.get('kills', 0), 'minutes': round(minutes, 1),
            'kills_per_min': round(record['kills'] / minutes, 2) if minutes >= 1 and record.get('kills') else None,
            'deaths': record.get('deaths', 0), 'retreats': record.get('retreats', 0),
            'recent_death': now - record.get('last_death', -RECENT_DEATH_S) < RECENT_DEATH_S}


def options(snap, current, tables, equipment, history, identity, now):
    """Validated field options, ordered by the character's temperament. The current
    field is always included (to keep it); others must have an entry spot reachable on
    foot from where the character stands (walk zones, portals within the hop limits),
    allow supply trips from that entry to the shop and back, offer viable common
    monsters and no aggressive threat, and have no recent own death."""
    monsters, fields, graph = tables['monsters'], tables['fields']['fields'], walk_table(tables)
    here_zone = walk.zone_at(graph, snap['map'], (snap['position']['x'], snap['position']['y']))
    shop_zone = walk.zone_at(graph, SHOP_MAP, SHOP_STAND)
    me = profile(snap, equipment)
    outcomes, field_history = history.get('monsters', {}), history.get('fields', {})
    mood = temperament(identity)
    out = []
    for name, field in fields.items():
        here = name == current
        if not here and name == snap['map']:
            continue
        # The entry spot reached with the fewest hops (then inner portals, then via name).
        best = None
        for via, spot in sorted(field['entries'].items()):
            r = walk.route(graph, snap['map'], name, here_zone, entry_zone(spot))
            if r and r['hops'] and (best is None or (r['hops'], r['inner']) < (best[0]['hops'], best[0]['inner'])):
                best = (r, via, spot)
        if not here and best is None:
            continue
        route, entry = ((best[0]['hops'], best[1]), best[2]) if best else (None, None)
        zone = entry_zone(entry) if entry else None
        trip = hops(graph, name, SHOP_MAP, zone, shop_zone), hops(graph, SHOP_MAP, name, shop_zone, zone)
        facts = field_facts(name, field, monsters, me, outcomes)
        past = history_view(field_history.get(name, {}), now)
        unsafe = ([] if trip[0] and trip[1] else ['no_supply_route']) + \
                 (['aggressive_threats'] if facts['aggressive_threats'] else []) + \
                 (['no_viable_monster'] if not facts['exp_per_hit'] else []) + \
                 (['recent_death'] if past['recent_death'] else [])
        if not here and (unsafe or not entry):
            continue
        score = facts['exp_per_hit'] * (1 - facts['danger'] if mood == 'prudent' else 1) * \
                (1.5 if mood == 'explorer' and not past['minutes'] else 1)
        out.append({'field_id': name, 'current': here, 'hops': route[0] if route else None,
                    'entry': {'via': route[1], 'x': entry[0], 'y': entry[1]} if entry else None,
                    'unsafe': unsafe, 'score': round(score, 3), **facts, 'history': past})
    best = max((o['score'] for o in out), default=0)
    # Comparable options are ordered by a per-character seed, the rest by score.
    tie = lambda o: hashlib.sha256(f'{identity}:{o["field_id"]}'.encode()).hexdigest()
    out.sort(key=lambda o: (o['score'] < best * NEAR_BEST, tie(o) if o['score'] >= best * NEAR_BEST else -o['score'],
                            o['field_id']))
    chosen = [o for o in out if not o['current']][:MAX_OPTIONS - 1]
    return [o for o in out if o['current'] or o in chosen], mood


def viable_targets(snap, tables, equipment, history):
    """Monster ids (name_id) this character may attack now."""
    me = profile(snap, equipment)
    outcomes = history.get('monsters', {})
    return {m['name_id'] for m in snap['monsters'] if viable(m.get('name_id'), tables['monsters'], me, outcomes)}
