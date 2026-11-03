"""R1 policy -> OpenKore profile: each rule yields its keys, and every key exists
in the pinned OpenKore. Uses the real generated tables; no game services."""
import copy
import json
from pathlib import Path
import re
import unittest

from scripts import build_r1_profile as r1

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT/'config/r1-policy.json').read_text(encoding='utf-8'))
TABLES = r1.load_tables()
CONTROL = (r1.OPENKORE/'control/config.txt').read_text(encoding='utf-8', errors='replace')
SOURCE = ''.join(p.read_text(encoding='utf-8', errors='replace') for p in (r1.OPENKORE/'src/Misc.pm', r1.OPENKORE/'src/AI.pm'))
TEMPLATE = 'lockMap\nattackAuto 0\nuseSelf_item {\n\tdcOnEmpty 0\n}\n\nbuyAuto {\n\tnpc\n\tminAmount 2\n}\n\nsellAuto 0\n'
VOCAL, ROCKER, PORING = '1088', '1052', '1002'


def scalar_known(key):
    return re.search(rf'(?m)^{re.escape(key)}(?:[ \t]|$)', CONTROL) is not None


def block_known(block, key):
    template = re.search(rf'(?ms)^{block} {{\n(.*?)^}}', CONTROL).group(1)
    return (re.search(rf'(?m)^\t{key}\b', template) is not None
            or f'$prefix . "_{key}"' in SOURCE or f'$prefix."_{key}"' in SOURCE or f'_{key}"}}' in SOURCE)


class R1Profile(unittest.TestCase):
    def setUp(self):
        self.result = r1.translate(POLICY, TABLES)

    def test_deterministic(self):
        again = r1.translate(copy.deepcopy(POLICY), r1.load_tables())
        self.assertEqual(r1.render(self.result, TEMPLATE), r1.render(again, TEMPLATE))

    def test_every_key_exists_in_pinned_openkore(self):
        for key in self.result['config']:
            self.assertTrue(scalar_known(key), key)
        for block, _, keys in self.result['blocks']:
            for key in keys:
                self.assertTrue(block_known(block, key), f'{block}.{key}')
        for key in r1.TRANSPORT_WEIGHTS:
            self.assertIn(f'\n{key} ', (r1.OPENKORE/'control/routeweights.txt').read_text())

    def test_rules_produce_expected_keys(self):
        c, m = self.result['config'], self.result['mapping']
        self.assertEqual((c['lockMap'], c['attackAuto'], c['route_randomWalk']), ('prt_fild06', '2', '1'))
        self.assertEqual(c['route_maxWarpFee'], '0')
        self.assertEqual((c['sitAuto_hp_lower'], c['sitAuto_hp_upper']), ('45', '90'))
        self.assertEqual((c['sellAuto'], c['sellAuto_npc'], c['itemsMaxWeight_sellOrStore']), ('1', 'prontera 104 49', '40'))
        self.assertTrue(c['statsAddAuto_list'].startswith('20 str, 15 vit, 10 dex'))
        self.assertEqual(c['skillsAddAuto_list'], 'NV_BASIC 9')  # Novice skills only
        self.assertEqual((c['teleportAuto_hp'], c['teleportAuto_minAggressives'], c['dcOnDeath']), ('30', '3', '0'))
        buys = {value: keys for name, value, keys in self.result['blocks'] if name == 'buyAuto'}
        self.assertEqual(buys['601']['npc'], 'prt_in 126 76')  # Tool Dealer#prt1 sells Fly Wing
        self.assertEqual(buys['512']['zeny'], '>= 150')
        for rule in POLICY['rules']:
            self.assertTrue(rule['id'] in m or rule['id'] in {g['rule'] for g in self.result['gaps']}, rule['id'])

    def test_threats_and_minions(self):
        self.assertIn(int(ROCKER), r1.load_summoners()[int(VOCAL)])
        mon = self.result['mon']
        self.assertEqual(mon[VOCAL][0].split()[:2], ['0', '-10'])
        self.assertEqual(mon[PORING][0].split()[:2], ['1', '0'])
        aggressive = [k for k, v in self.result['kinds'].items() if v == 'aggressive']
        self.assertTrue(aggressive and all(mon[k][0].split()[:2] == ['0', '2'] for k in aggressive))

    def test_route_weights_avoid_vocal_field_but_not_supply(self):
        w = self.result['weights']
        self.assertEqual(w['prt_fild04'], 10000)  # Vocal + Rocker minions killed Nilo here
        self.assertEqual((w['NPC'], w['COMMAND'], w['AIRSHIP']), (10000, 10000, 10000))
        for name in ('prt_fild06', 'prontera', 'prt_in'):
            self.assertNotIn(name, w)

    def test_hostile_hunt_field_is_refused(self):
        policy = copy.deepcopy(POLICY)
        policy['rules'][0]['do']['hunt']['field'] = 'prt_fild04'
        with self.assertRaises(ValueError):
            r1.translate(policy, TABLES)

    def test_untranslatable_rules_are_gaps(self):
        self.assertEqual({g['rule'] for g in self.result['gaps']}, {'leave_pack_no_wings', 'refit_on_level'})

    def test_render_replaces_keys_and_template_blocks(self):
        files = r1.render(self.result, TEMPLATE)
        text = files['config.txt']
        self.assertEqual(len(re.findall(r'(?m)^attackAuto ', text)), 1)
        self.assertNotIn('useSelf_item {', text)
        self.assertNotIn('buyAuto {', text)
        self.assertIn('buyAuto 601 {\n\tnpc prt_in 126 76\n', text)
        self.assertIn(f'\n{VOCAL}\t0 -10 0 0 0 0 0 0 0  # Vocal (threat)', files['mon_control.txt'])
        self.assertIn('\nall 0 0 1\n', files['items_control.txt'])
        self.assertIn('\nprt_fild04 10000\n', files['routeweights.txt'])


if __name__ == '__main__':
    unittest.main()
