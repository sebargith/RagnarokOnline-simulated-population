"""R1 runner metrics from recorded observer events, and the observer's read-only contract."""
import json
from pathlib import Path
import re
import tempfile
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
        self.assertEqual(run_r1.PLUGINS, 'r1_observer,r1_reload,r1_flee,raiseStat,raiseSkill')  # m1_bridge never loads

    def test_flee_plugin_only_routes_without_attacking(self):
        text = (ROOT/'bridge/r1/r1_flee.pl').read_text()
        for pattern in (r'messageSender', r'Commands::', r'\bsend\w*\(', r'configModify', r'talk', r'useTeleport'):
            self.assertIsNone(re.search(pattern, text), pattern)
        self.assertIn('attackOnRoute => 0', text)
        self.assertIn('getByNameID(FLY_WING)', text)  # only without a Fly Wing

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
        self.assertEqual(run_r1.facts_of(dict(s, job_id=1))['job'], 'Swordman')
        self.assertIsNone(run_r1.facts_of(dict(s, job_id=2)))  # Mage: no build here

    def test_job10_stop_matches_the_job_changer_rule(self):
        ready = dict(sample(0, job=10), job_id=0, points_skill=0)
        self.assertTrue(run_r1.ready_for_first_job(ready))
        self.assertFalse(run_r1.ready_for_first_job(dict(ready, points_skill=1)))  # raiseSkill not done
        self.assertFalse(run_r1.ready_for_first_job(dict(ready, level=dict(ready['level'], job=9))))
        self.assertFalse(run_r1.ready_for_first_job(dict(ready, job_id=1)))  # already Swordman

    def test_refits_are_reported(self):
        events = [sample(0), {'t': 1, 'type': 'reloaded', 'id': 'refit-6-1', 'ok': 1, 'lockMap': LOCK, 'error': ''}]
        self.assertEqual(run_r1.summarize(events, LOCK, 0)['refits'][0]['id'], 'refit-6-1')


class Characters(unittest.TestCase):
    def tearDown(self):
        run_r1.use('tarin')

    def test_each_character_has_its_own_profile_port_and_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            run_r1.use('nilo')
            p = run_r1.paths(runtime)
            self.assertEqual((run_r1.NAME, run_r1.PORT, run_r1.CLIENT), ('Nilo', 8773, 'r1-nilo'))
            self.assertEqual(p['base'], runtime.resolve()/'r1-nilo')
            self.assertEqual(json.loads(run_r1.default_policy().read_text(encoding='utf-8'))['identity'], 'Nilo')
            (runtime/'p5').mkdir()
            (runtime/'p5/processes.json').write_text('{}')
            self.assertEqual(run_r1.same_account(runtime), ['p5/processes.json'])  # P5 client: refuse
            run_r1.use('tarin')
            self.assertEqual((run_r1.paths(runtime)['base'], run_r1.PORT), (runtime.resolve()/'r1', 8772))
            self.assertEqual(run_r1.same_account(runtime), [])  # another account's registry does not block


class FakeFuture:
    def __init__(self, value):
        self.value = value

    def done(self):
        return True

    def result(self):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class FakeService:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def submit(self, identity, messages, seed, cold=False, response_format=None):
        self.calls.append(response_format['properties']['field_id']['enum'])
        return FakeFuture(self.answer)


class FieldDecision(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = Path(self.tmp.name)
        run_r1.use('nilo')
        self.policy = json.loads(run_r1.default_policy().read_text(encoding='utf-8'))

    def tearDown(self):
        run_r1.use('tarin')
        self.tmp.cleanup()

    def test_planner_picks_a_validated_option_and_it_is_recorded(self):
        service = FakeService({'content': json.dumps({'field_id': 'prt_fild08', 'reason': 'more Drops'}),
                               'served_by': 'groq-gpt-oss', 'degraded': False})
        d = run_r1.FieldChoice(self.runtime, service).decide(self.policy, 'level_up', {'prt_fild06': {'kills': 3, 'hunt_s': 60}})
        self.assertEqual((d['field_id'], d['decision'], d['served_by'], d['trigger']),
                         ('prt_fild08', 'planner', 'groq-gpt-oss', 'level_up'))
        self.assertIn('prt_fild08', service.calls[0])
        p = run_r1.paths(self.runtime)
        self.assertEqual(json.loads(p['field'].read_text())['field_id'], 'prt_fild08')
        self.assertEqual(len(p['decisions'].read_text().splitlines()), 1)
        self.assertEqual(d['history']['prt_fild06'], {'kills': 3, 'hunt_s': 60})
        self.assertEqual(run_r1.lock_map(run_r1.with_field(self.policy, d['field_id'])), 'prt_fild08')

    def test_invalid_or_failed_answer_keeps_the_current_field(self):
        for answer in ({'content': json.dumps({'field_id': 'prt_fild04', 'reason': 'x'})}, RuntimeError('down')):
            d = run_r1.FieldChoice(self.runtime, FakeService(answer)).decide(self.policy, 'level_up')
            self.assertEqual((d['field_id'], d['decision']), ('prt_fild06', 'local_fallback'))

    def test_without_planner_a_dangerous_current_field_is_left(self):
        p = run_r1.paths(self.runtime)
        p['base'].mkdir(parents=True)
        p['danger'].write_text(json.dumps({'prt_fild06': {'deaths': 1, 'level': 9, 't': 0}}))
        d = run_r1.FieldChoice(self.runtime).decide(self.policy, 'death')
        self.assertNotEqual(d['field_id'], 'prt_fild06')
        self.assertEqual(d['field_id'], d['options'][0][0])  # best score

    def test_field_history_and_reloaded_fields_count_as_hunting(self):
        events = [sample(0), {'t': 1, 'type': 'kill'}, sample(5), sample(10, map='prt_fild08'),
                  {'t': 11, 'type': 'reloaded', 'id': 'r', 'ok': 1, 'lockMap': 'prt_fild08', 'error': ''},
                  {'t': 12, 'type': 'kill'}, sample(15, map='prt_fild08')]
        self.assertEqual(run_r1.field_history(events),
                         {LOCK: {'kills': 1, 'hunt_s': 10}, 'prt_fild08': {'kills': 1, 'hunt_s': 5}})
        self.assertEqual(run_r1.summarize(events, LOCK, 0)['time_share_s']['hunt'], 15)


if __name__ == '__main__':
    unittest.main()
