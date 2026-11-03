"""R1 runner metrics from recorded observer events, and the observer's read-only contract."""
from pathlib import Path
import re
import unittest

from scripts import run_r1

ROOT = Path(__file__).resolve().parents[1]
LOCK = 'prt_fild06'


def sample(t, map=LOCK, dead=0, sitting=0, ai=(), inv=None, base=5, exp=10, job=3, job_exp=4, zeny=31):
    return {'t': t, 'type': 'sample', 'connected': 1, 'map': map, 'x': 1, 'y': 1, 'hp': 50, 'hp_max': 63,
            'dead': dead, 'sitting': sitting, 'zeny': zeny, 'weight': 10, 'weight_max': 2330, 'ai': list(ai),
            'inventory': inv if inv is not None else {'512': 2, '909': 1}, 'stats': {'str': 11},
            'level': {'base': base, 'exp': exp, 'exp_max': 100, 'job': job, 'job_exp': job_exp, 'job_exp_max': 50}}


class Summary(unittest.TestCase):
    def test_time_share_kills_exp_and_level_up(self):
        events = [sample(0), {'t': 3, 'type': 'kill', 'name_id': 1002, 'name': 'Poring'}, sample(5, exp=40),
                  sample(10, sitting=1, exp=95), sample(15, map='prontera', ai=['route', 'sellAuto'], base=6, exp=5),
                  sample(20, map='prt_fild05', ai=['mapRoute'], base=6, exp=5), sample(25, base=6, exp=5)]
        s = run_r1.summarize(events, LOCK, 0)
        self.assertEqual(s['kills'], 1)
        self.assertEqual(s['base_exp'], 30 + 55 + 5 + 5)  # 95->level up: 5 to cap + 5
        self.assertEqual(s['time_share_s'], {'hunt': 10, 'rest': 5, 'travel': 5, 'supply': 5, 'dead': 0})
        self.assertEqual(s['span_s'], 25)

    def test_death_recovery_is_measured(self):
        events = [sample(0), {'t': 1, 'type': 'died', 'map': LOCK}, sample(5, dead=1),
                  sample(20, map='prontera'), sample(80)]
        d = run_r1.summarize(events, LOCK, 0)['deaths'][0]
        self.assertEqual((d['respawned_s'], d['back_in_field_s']), (19, 79))

    def test_unexpected_zeny_npc_and_inventory(self):
        events = [{'t': 0, 'type': 'zeny', 'zeny': 31, 'change': 31, 'map': LOCK, 'ai': []},  # login balance
                  sample(1), {'t': 2, 'type': 'zeny', 'zeny': 1, 'change': -30, 'map': 'prontera', 'ai': ['route']},
                  {'t': 3, 'type': 'npc_talk', 'name': 'Kafra Employee', 'msg': 'Warp?', 'map': 'prontera', 'ai': ['mapRoute']},
                  {'t': 4, 'type': 'zeny', 'zeny': 61, 'change': 60, 'map': 'prontera', 'ai': ['sellAuto']},
                  sample(5, inv={'512': 1}), sample(10, inv={'512': 1, '601': 1}), sample(15, inv={'512': 1})]
        kinds = [u['kind'] for u in run_r1.summarize(events, LOCK, 0)['unexpected']]
        # Apple used (512) is expected; Jellopy (909) lost and a Fly Wing used without teleport are not.
        self.assertEqual(sorted(kinds), ['inventory_loss', 'inventory_loss', 'npc_dialog_outside_supply',
                                         'zeny_change_outside_supply'])

    def test_fly_wing_used_by_teleport_is_expected(self):
        events = [sample(0, inv={'601': 1}), {'t': 2, 'type': 'teleport'}, sample(5, inv={})]
        self.assertEqual(run_r1.summarize(events, LOCK, 0)['unexpected'], [])


class ObserverContract(unittest.TestCase):
    def test_observer_cannot_act(self):
        text = (ROOT/'bridge/r1/r1_observer.pl').read_text()
        for pattern in (r'messageSender', r'Commands::', r'\bsend\w*\(', r'configModify', r'AI::queue', r'ai_\w+\('):
            self.assertIsNone(re.search(pattern, text), pattern)
        self.assertEqual(run_r1.PLUGINS, 'r1_observer,r1_reload,raiseStat,raiseSkill')  # m1_bridge never loads

    def test_reload_plugin_only_reloads_profile_files(self):
        text = (ROOT/'bridge/r1/r1_reload.pl').read_text()
        for pattern in (r'messageSender', r'Commands::', r'\bsend\w*\(', r'AI::queue', r'configModify'):
            self.assertIsNone(re.search(pattern, text), pattern)
        self.assertIn('Misc::parseReload(FILES)', text)
        for name in ('config', 'mon_control', 'items_control', 'routeweights'):
            self.assertIn(name + '\\.txt$', text)


class Refit(unittest.TestCase):
    def test_facts_from_observed_sample(self):
        s = dict(sample(9, base=9), job_id=0, equipped=[1201, 2301])
        f = run_r1.facts_of(s)
        self.assertEqual((f['level'], f['job'], f['equipped'], f['hp_max']),
                         ({'base': 9, 'job': 3}, 'Novice', [1201, 2301], 63))
        self.assertIsNone(run_r1.facts_of(dict(s, job_id=1)))  # first class: not refit here

    def test_refits_are_reported(self):
        events = [sample(0), {'t': 1, 'type': 'reloaded', 'id': 'refit-6-1', 'ok': 1, 'lockMap': LOCK, 'error': ''}]
        self.assertEqual(run_r1.summarize(events, LOCK, 0)['refits'][0]['id'], 'refit-6-1')


if __name__ == '__main__':
    unittest.main()
