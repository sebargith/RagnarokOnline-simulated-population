"""docs/PROGRESSION_ECONOMY.md E3: progression metrics from recorded observer events."""
import json
from pathlib import Path
import re
import unittest

from agent import build_policy, progress

ROOT = Path(__file__).resolve().parents[1]
EQUIPMENT = build_policy.load_equipment()
LOOT = json.loads((ROOT/'config/p5-loot.json').read_text(encoding='utf-8'))['items']
KNIFE_SET, BLADE_SET = [1201, 2305], [1107, 2101, 2305, 2401]


def sample(t, equipped, map='prt_fild00', zeny=100, inventory=None, exp=0, ai=('attack',), sitting=0):
    return {'t': t, 'type': 'sample', 'connected': 1, 'map': map, 'dead': 0, 'sitting': sitting, 'ai': list(ai),
            'equipped': equipped, 'zeny': zeny, 'inventory': inventory or {'909': 10},
            'level': {'base': 13, 'exp': exp, 'exp_max': 585, 'job': 4, 'job_exp': 0, 'job_exp_max': 76}}


def kill(t, duration, hits, misses=0, taken=0, dodged=0, dealt=None, name_id=1063, name='Lunatic'):
    return {'t': t, 'type': 'kill', 'name_id': name_id, 'name': name, 'duration_s': duration, 'hits': hits,
            'misses': misses, 'dmg_dealt': dealt if dealt is not None else 50 * (hits - misses),
            'dmg_taken': taken, 'dodged': dodged}


class Progress(unittest.TestCase):
    def setUp(self):
        self.events = [sample(0, KNIFE_SET, zeny=5495), kill(4, 6.0, 5, misses=1, taken=12),
                       sample(5, KNIFE_SET, exp=6), kill(9, 4.0, 4, taken=8, dodged=1), sample(10, KNIFE_SET, exp=12),
                       sample(15, BLADE_SET, zeny=1695, exp=12), kill(18, 2.0, 2), sample(20, BLADE_SET, zeny=1695, exp=18),
                       {'t': 21, 'type': 'kill', 'name_id': 1063, 'name': 'Lunatic'},  # older observer: no combat facts
                       sample(25, BLADE_SET, zeny=1695, exp=24, ai=('buyAuto', 'route')),
                       sample(35, BLADE_SET, zeny=1695, exp=30)]
        self.r = progress.report(self.events, EQUIPMENT, LOOT, {'prt_fild00'})

    def test_power_from_worn_gear(self):
        self.assertEqual(progress.gear_power(KNIFE_SET, EQUIPMENT), (17, 3))
        self.assertEqual(progress.gear_power(BLADE_SET, EQUIPMENT), (53, 7))
        p = self.r['power']
        self.assertEqual(((p['start']['atk'], p['end']['atk']), len(p['changes'])), ((17, 53), 1))

    def test_wealth_at_npc_sell_price(self):
        w = self.r['wealth']
        self.assertEqual(w['start'], {'zeny': 5495, 'goods': 30, 'total': 5525, 'unpriced_items': 0})  # Jellopy 3 z
        unknown = progress.wealth({'zeny': 1, 'inventory': {'999999': 2}}, EQUIPMENT, LOOT)
        self.assertEqual((unknown['total'], unknown['unpriced_items']), (1, 2))

    def test_combat_split_by_gear_set(self):
        rows = {tuple(r['equipped']): r for r in self.r['by_monster']}
        knife, blade = rows[tuple(KNIFE_SET)], rows[tuple(BLADE_SET)]
        self.assertEqual((knife['kills'], knife['ttk_s_median'], knife['hits_per_kill']), (2, 5.0, 4.5))
        self.assertEqual((knife['miss_rate'], knife['dmg_taken_per_kill'], knife['kills_hit_by_monster']), (0.111, 10.0, 2))
        self.assertEqual((blade['kills'], blade['measured'], blade['ttk_s_median']), (2, 1, 2.0))
        self.assertEqual(blade['atk_def'], [53, 7])

    def test_field_rates_count_only_hunting_time(self):
        f = self.r['by_field']['prt_fild00']
        self.assertEqual((f['hunt_s'], f['kills'], f['base_exp']), (25, 4, 24))  # the buyAuto span (25-35) is supply
        self.assertEqual(progress.report(self.events, EQUIPMENT, LOOT, {'prt_fild06'})['by_field'], {})

    def test_observer_records_combat_facts_without_acting(self):
        text = (ROOT/'bridge/r1/r1_observer.pl').read_text()
        for key in ('duration_s', 'dmgFromYou', 'numAtkFromYou', 'missedFromYou', 'dmgToYou', 'missedYou', "'attack_start'"):
            self.assertIn(key, text)
        self.assertIsNone(re.search(r'\bsend\w*\(|AI::queue|Commands::', text))


if __name__ == '__main__':
    unittest.main()
