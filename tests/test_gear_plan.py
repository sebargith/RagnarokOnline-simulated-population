"""docs/PROGRESSION_ECONOMY.md E1-E2: generated shop/loot tables, the deterministic
gear plan and its translation into native OpenKore blocks. No game services."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from agent import build_policy, gear_plan
from scripts import build_r1_profile as r1
from scripts import run_r1

ROOT = Path(__file__).resolve().parents[1]
EQUIPMENT = build_policy.load_equipment()
BUILDS = build_policy.load_builds()
LOOT = json.loads((ROOT/'config/p5-loot.json').read_text(encoding='utf-8'))
SWORD = BUILDS['novice-swordman']['gear']
PRT = ['Weapon Dealer#prt', 'Armor Dealer#prt']
KNIFE, BLADE, RAPIER, KATANA, GUARD, SUIT = 1201, 1107, 1110, 1116, 2101, 2305


def char(zeny, level=13, job='Swordman', equipped=(KNIFE, SUIT), inventory=None):
    inv = inventory if inventory is not None else {str(i): 1 for i in equipped}
    return {'job': job, 'level': {'base': level, 'job': 3}, 'equipped': list(equipped), 'zeny': zeny, 'inventory': inv}


class Tables(unittest.TestCase):
    def test_equipment_has_price_shop_and_weight(self):
        blade = EQUIPMENT[str(BLADE)]
        self.assertEqual((blade['buy'], blade['sell'], blade['weight'], blade['weapon_level']), (2900, 1450, 70.0, 1))
        self.assertIn('Weapon Dealer#prt', blade['shops'])
        self.assertIn('Armor Dealer#prt', EQUIPMENT[str(GUARD)]['shops'])
        self.assertTrue(all(e['shops'] for e in EQUIPMENT.values()))  # every listed item is sold somewhere
        self.assertTrue(all(name in r1.load_shops() for e in EQUIPMENT.values() for name in e['shops']))

    def test_loot_rates_and_values(self):
        poring = LOOT['monsters']['1002']
        self.assertEqual(poring['name'], 'Poring')
        rates = {LOOT['items'][str(d['id'])]['name']: d for d in poring['drops']}
        self.assertEqual(rates['Jellopy']['rate'], 7000)
        self.assertTrue(rates['Poring Card'].get('rare'))
        self.assertEqual(LOOT['items']['909']['sell'], 3)  # Jellopy: Buy 6 -> sell 3

    def test_gear_preferences_are_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = json.loads((ROOT/'config/p5-builds.json').read_text(encoding='utf-8'))
            doc['builds']['novice-swordman']['gear']['shield'] = 'yes'
            path = Path(tmp)/'b.json'
            path.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):
                build_policy.load_builds(path)


class Plan(unittest.TestCase):
    def test_buys_best_affordable_weapon_first_within_reserve(self):
        d = gear_plan.plan(char(5495), EQUIPMENT, SWORD, PRT, 1000)
        self.assertEqual((d['buy']['id'], d['buy']['shop'], d['reason']), (BLADE, 'Weapon Dealer#prt', 'upgrade_weapon'))
        self.assertEqual(d['equip'], {'rightHand': BLADE, 'armor': SUIT})
        self.assertEqual(d['facts']['current'], {'weapon': KNIFE, 'armor': SUIT})

    def test_level_unlocks_and_reserve_limits(self):
        self.assertEqual(gear_plan.plan(char(99999, level=14), EQUIPMENT, SWORD, PRT, 1000)['buy']['id'], 1122)  # Ring Pommel Saber
        self.assertEqual(gear_plan.plan(char(3899), EQUIPMENT, SWORD, PRT, 1000)['buy']['id'], 1207)  # Main Gauche (43) beats Falchion (39); Blade is 1 z short
        low = gear_plan.plan(char(900), EQUIPMENT, SWORD, PRT, 1000)
        self.assertEqual((low['buy'], low['reason']), (None, 'below_reserve'))

    def test_build_keeps_shield_no_two_handed(self):
        d = gear_plan.plan(char(99999, equipped=(BLADE, SUIT)), EQUIPMENT, SWORD, PRT, 1000)
        self.assertNotEqual(d['buy']['id'], KATANA)
        self.assertNotIn('Both_Hand', EQUIPMENT[str(d['buy']['id'])]['locations'])

    def test_after_weapon_the_body_and_shield(self):
        d = gear_plan.plan(char(1600, level=14, equipped=(RAPIER, SUIT)), EQUIPMENT, SWORD, PRT, 1000)
        self.assertEqual((d['buy']['slot'], d['buy']['id']), ('shield', GUARD))  # no armor upgrade under 600 z

    def test_worn_gear_counts_even_above_the_rule(self):
        d = gear_plan.plan(char(1600, level=13, equipped=(RAPIER, SUIT)), EQUIPMENT, SWORD, PRT, 1000)
        self.assertNotEqual(d['buy'] and d['buy']['slot'], 'weapon')  # never a worse weapon than the Rapier
        self.assertEqual(d['equip']['rightHand'], RAPIER)

    def test_owned_better_gear_is_equipped_without_buying(self):
        d = gear_plan.plan(char(0, inventory={str(KNIFE): 1, str(SUIT): 1, str(BLADE): 1}), EQUIPMENT, SWORD, PRT, 1000)
        self.assertEqual((d['equip']['rightHand'], d['buy']), (BLADE, None))

    def test_only_listed_shops_and_class(self):
        self.assertIsNone(gear_plan.plan(char(99999), EQUIPMENT, SWORD, ['Tool Dealer#prt1'], 1000)['buy'])
        mage = gear_plan.plan(char(99999, job='Mage'), EQUIPMENT, SWORD, PRT, 1000)
        self.assertTrue(mage['buy'] is None or 'Mage' in EQUIPMENT[str(mage['buy']['id'])]['jobs'])


class Translation(unittest.TestCase):
    def policy(self, zeny):
        p = json.loads((ROOT/'config/r1-policy-nilo.json').read_text(encoding='utf-8'))
        p['rules'][0]['do']['hunt']['field'] = 'prt_fild06'
        p['character'].update(job='Swordman', zeny=zeny, inventory={str(KNIFE): 1, str(SUIT): 1})
        return p

    def test_native_blocks_and_keep(self):
        result = r1.translate(self.policy(5495), r1.load_tables())
        blocks = {name: (value, keys) for name, value, keys in result['blocks'] if name in ('equipAuto', 'buyAuto') and value != '512' and value != '601'}
        self.assertEqual(blocks['equipAuto'], ('', {'armor': str(SUIT), 'rightHand': str(BLADE)}))
        self.assertEqual(blocks['buyAuto'], (str(BLADE), {'npc': 'prt_in 172 130', 'minAmount': '0', 'maxAmount': '1',
                                                          'price': '2900', 'zeny': '>= 3900'}))
        self.assertEqual(result['items'][str(BLADE)], '1 0 0')
        text = r1.render(result, 'equipAuto {\n\ttopHead\n}\n')['config.txt']
        self.assertIn('\nequipAuto {\n\tarmor 2305\n\trightHand 1107\n}\n', text)
        self.assertNotIn('topHead', text)

    def test_no_zeny_no_purchase(self):
        result = r1.translate(self.policy(0), r1.load_tables())
        self.assertEqual([v for n, v, _ in result['blocks'] if n == 'buyAuto'], ['512', '601'])
        self.assertEqual(result['gear']['reason'], 'below_reserve')

    def test_configured_rules_reach_a_running_character(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_r1.use('nilo')
            try:
                p = run_r1.paths(Path(tmp))
                p['base'].mkdir(parents=True)
                applied = self.policy(10)
                applied['rules'] = [applied['rules'][0]]  # an old effective policy without upgrade_gear
                applied['rules'][0]['do']['hunt']['field'] = 'prt_fild00'
                p['effective'].write_text(json.dumps(applied))
                eff = run_r1.effective_policy(Path(tmp))
                self.assertIn('upgrade_gear', [r['id'] for r in eff['rules']])
                self.assertEqual((eff['character']['zeny'], eff['rules'][0]['do']['hunt']['field']), (10, 'prt_fild00'))
            finally:
                run_r1.use('tarin')

    def test_facts_carry_zeny_and_inventory(self):
        s = {'t': 1, 'job_id': 1, 'level': {'base': 13, 'job': 3}, 'stats': {}, 'hp_max': 115,
             'equipped': [KNIFE], 'zeny': 5495, 'inventory': {'601': 8}}
        f = run_r1.facts_of(s)
        self.assertEqual((f['zeny'], f['inventory']), (5495, {'601': 8}))


if __name__ == '__main__':
    unittest.main()
