"""P5 step 3: danger, viable targets, field options, field planner and cycle/runner integration.
Synthetic tables keep option tests independent of the generated data; no game services are used."""
from concurrent.futures import Future
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from agent import build_policy, hunting, walk
from agent.goal_planner import FieldPlanner, validate_field
from agent.solo_cycle import SoloCycle
from scripts.run_p2_cycle import P5Planning, Runner
from test_p2_cycle import snapshot as p2_snapshot
from test_p3_runner import ControlledBridge
from test_p5_build import Service, snapshot as p5_snapshot

ROOT = Path(__file__).resolve().parents[1]
EQUIPMENT = build_policy.load_equipment()
BUILDS = build_policy.load_builds()
TABLES = {'monsters': hunting.load_monsters(), 'fields': hunting.load_fields()}


def mob(name, level, hp, attack, aggressive=False, can_attack=True, boss=False, base_exp=10):
    return {'name': name, 'level': level, 'hp': hp, 'attack': attack, 'defense': 0, 'aggressive': aggressive,
            'can_attack': can_attack, 'can_move': True, 'boss': boss, 'walk_speed': 200, 'attack_delay': 1500,
            'base_exp': base_exp, 'job_exp': 5}


def field(spawns, entries=None, exits=()):
    return {'monsters': [{'id': i, 'count': c, 'rare': r, 'boss_spawn': False} for i, c, r in spawns],
            'exits': list(exits), 'entries': entries or {}}


def synthetic():
    monsters = {'1': mob('Weak', 1, 50, [7, 10]), '2': mob('Brute', 20, 900, [80, 90], aggressive=True),
                '3': mob('Ghoul', 30, 3000, [200, 250], aggressive=True, boss=True), '4': mob('Rich', 2, 50, [7, 10], base_exp=40)}
    edge = lambda dst: [1, 1, dst, 5, 5]
    portals = {'home': [edge('town'), edge('safe'), edge('risky'), edge('far1')], 'town': [edge('home'), edge('safe'), edge('rich')],
               'safe': [edge('home'), edge('town')], 'risky': [edge('home')], 'far1': [edge('far2')], 'far2': [edge('far3')],
               'far3': [edge('far4')], 'far4': [edge('far3')], 'rich': [edge('town')]}
    fields = {'home': field([(1, 50, False)]),
              'safe': field([(1, 60, False), (3, 1, True)], {'home': [10, 10], 'town': [11, 11]}),
              'risky': field([(1, 40, False), (2, 10, False)], {'home': [12, 12]}),
              'rich': field([(4, 40, False)], {'town': [13, 13]}),
              'far4': field([(1, 50, False)], {'far3': [14, 14]})}
    return {'monsters': monsters, 'fields': {'fields': fields, 'portals': portals}, 'walk': walk.from_graph(portals)}


def tarin(**changes):
    snap = p5_snapshot()
    snap['progress']['stats']['str'] = {'value': 11, 'cost': 3}
    snap['level']['base'] = 5
    snap.update(hp=57, hp_max=57, map='prt_fild08', executor='openkore_route', recovery='none',
                position={'x': 170, 'y': 250}, zeny=10, weight=10, weight_max=2000, ground_items=[],
                monsters=[], explore_candidates=[{'x': 220, 'y': 250}])
    snap['inventory'].append({'name': 'Apple', 'name_id': 512, 'amount': 3, 'type': 0, 'equipped': 0, 'identified': 1})
    snap.update(changes)
    return snap


class DangerTests(unittest.TestCase):
    def setUp(self):
        self.me = hunting.profile(tarin(), EQUIPMENT)

    def test_profile_uses_stats_and_worn_gear(self):
        # STR 11 + (11//10)^2 + DEX 5//5 + LUK 1//5 + Knife 17; Cotton Shirt DEF 1; VIT 5//2.
        self.assertEqual(self.me, {'level': 5, 'hp_max': 57, 'atk': 30, 'def': 1, 'soft_def': 2})

    def test_real_prontera_monsters(self):
        m = TABLES['monsters']
        self.assertTrue(hunting.assess(m['1002'], self.me)['viable'])        # Poring
        self.assertTrue(hunting.assess(m['1063'], self.me)['viable'])        # Lunatic
        self.assertEqual(hunting.assess(m['1004'], self.me)['why'], 'too_much_damage')  # Hornet
        self.assertEqual(hunting.assess(m['1008'], self.me)['why'], 'fight_too_long')    # Pupa, DEF 64

    def test_rules_order_and_aggression(self):
        self.assertEqual(hunting.assess(mob('X', 30, 10, [1, 1]), self.me)['why'], 'level_too_high')
        self.assertEqual(hunting.assess(mob('X', 1, 10, [1, 1], boss=True), self.me)['why'], 'boss')
        calm = mob('X', 3, 60, [12, 14])
        a = hunting.assess(calm, self.me)
        self.assertTrue(MAX_AGG < a['loss'] <= hunting.MAX_LOSS and a['viable'])
        self.assertEqual(hunting.assess({**calm, 'aggressive': True}, self.me)['why'], 'aggressive_and_risky')
        self.assertEqual(hunting.assess(mob('Egg', 3, 60, [0, 0], can_attack=False), self.me)['loss'], 0)

    def test_learned_too_strong(self):
        self.assertFalse(hunting.learned_too_strong({'kills': 1, 'retreats': 1}))
        self.assertTrue(hunting.learned_too_strong({'kills': 3, 'retreats': 1, 'deaths': 1}))
        self.assertFalse(hunting.learned_too_strong({'kills': 9, 'retreats': 2}))
        snap = tarin(monsters=[{'id': 'a', 'name_id': 1002, 'x': 171, 'y': 250}, {'id': 'b', 'name_id': 1063, 'x': 172, 'y': 250},
                               {'id': 'c', 'name_id': 1004, 'x': 173, 'y': 250}, {'id': 'd', 'name_id': 99999, 'x': 1, 'y': 1}])
        self.assertEqual(hunting.viable_targets(snap, TABLES, EQUIPMENT, {}), {1002, 1063})
        history = {'monsters': {'1063': {'retreats': 2, 'kills': 1}}}
        self.assertEqual(hunting.viable_targets(snap, TABLES, EQUIPMENT, history), {1002})


MAX_AGG = hunting.MAX_AGGRESSIVE_LOSS


class OptionTests(unittest.TestCase):
    def setUp(self):
        self.tables = synthetic()
        self.snap = tarin(map='home')

    def ids(self, history=None, identity='Tarin', current='home', snap=None):
        # Synthetic maps have no real cells: supply trip length is tested on real tables.
        with patch.object(hunting, 'SHOP_MAP', 'town'), patch.object(hunting, 'HUNT_STINT_S', 10**9):
            opts, mood = hunting.options(snap or self.snap, current, self.tables, EQUIPMENT, history or {}, identity, 10000)
        return [o['field_id'] for o in opts], opts, mood

    def test_reachable_safe_fields_only(self):
        ids, opts, _ = self.ids()
        # risky has an aggressive threat; far4 is 4 hops away; rich is 2 hops via town.
        self.assertEqual(sorted(ids), ['home', 'rich', 'safe'])
        safe = next(o for o in opts if o['field_id'] == 'safe')
        self.assertEqual((safe['hops'], safe['entry']), (1, {'via': 'home', 'x': 10, 'y': 10}))
        self.assertEqual(safe['rare_threats'], ['Ghoul'])
        risky = hunting.field_facts('risky', self.tables['fields']['fields']['risky'], self.tables['monsters'],
                                    hunting.profile(self.snap, EQUIPMENT), {})
        self.assertEqual(risky['aggressive_threats'], ['Brute'])

    def test_current_field_is_kept_even_if_unsafe_and_recent_death_excludes(self):
        history = {'fields': {'safe': {'deaths': 1, 'last_death': 9000}, 'home': {'deaths': 1, 'last_death': 9500}}}
        ids, opts, _ = self.ids(history)
        self.assertNotIn('safe', ids)
        home = next(o for o in opts if o['field_id'] == 'home')
        self.assertEqual((home['current'], home['unsafe']), (True, ['recent_death']))

    def test_temperament_and_seeded_ties_vary_by_character(self):
        self.assertEqual(hunting.temperament('Tarin'), hunting.temperament('Tarin'))
        moods = {hunting.temperament(n) for n in ('Tarin', 'Bob', 'Cara', 'Dax', 'Eli', 'Fen')}
        self.assertEqual(moods, set(hunting.TEMPERAMENTS))
        self.tables['monsters']['4'] = dict(self.tables['monsters']['1'])  # rich == safe == home now
        orders = {tuple(self.ids(identity=n)[0]) for n in ('Tarin', 'Bob', 'Cara', 'Dax', 'Eli', 'Fen')}
        self.assertGreater(len(orders), 1)
        self.assertEqual(self.ids(identity='Bob')[0], self.ids(identity='Bob')[0])

    def test_prudent_prefers_lower_danger_ambitious_prefers_exp(self):
        with patch.object(hunting, 'temperament', return_value='ambitious'):
            self.assertEqual(self.ids()[0][0], 'rich')
        with patch.object(hunting, 'temperament', return_value='prudent'):
            self.assertEqual(self.ids()[0][0], 'rich')  # Same danger, more EXP.
        # Riskier but richer: only the ambitious character still puts it first.
        self.tables['monsters']['4'].update(attack=[14, 18], base_exp=12)
        with patch.object(hunting, 'temperament', return_value='ambitious'):
            self.assertEqual(self.ids()[0][0], 'rich')
        with patch.object(hunting, 'temperament', return_value='prudent'):
            self.assertEqual(self.ids()[0][-1], 'rich')

    def test_real_tables_for_tarin(self):
        opts, _ = hunting.options(tarin(), 'prt_fild08', TABLES, EQUIPMENT, {}, 'Tarin', 0)
        ids = [o['field_id'] for o in opts]
        self.assertIn('prt_fild08', ids)
        self.assertTrue({'prt_fild05', 'prt_fild06'} <= set(ids))
        self.assertTrue(all(o['entry'] for o in opts if not o['current']))

    def test_long_supply_trips_lower_the_score(self):
        # Live 2026-11-02: prt_fild00 cost about 7.5 min per supply round trip.
        snap = tarin(map='prt_fild05', position={'x': 130, 'y': 298})
        opts = {o['field_id']: o for o in hunting.options(snap, 'prt_fild05', TABLES, EQUIPMENT, {}, 'Nilo', 0)[0]}
        far, near = opts['prt_fild00'], opts['prt_fild06']
        self.assertGreater(far['supply_round_trip_s'], 3 * near['supply_round_trip_s'])
        self.assertLess(far['hunt_share'], near['hunt_share'])
        self.assertGreater(near['score'], far['score'])
        self.assertIsNotNone(opts['prt_fild05']['supply_round_trip_s'])  # Current field: from where it stands.


class TableTests(unittest.TestCase):
    def test_prt_fild08(self):
        f = TABLES['fields']['fields']['prt_fild08']
        names = {TABLES['monsters'][str(s['id'])]['name'] for s in f['monsters']}
        self.assertEqual(names, {'Poring', 'Pupa', 'Lunatic', 'Drops'})
        self.assertIn([170, 378, 'prontera', 156, 22], f['exits'])
        self.assertEqual(set(f['entries']), {'izlude', 'moc_fild01', 'prontera', 'prt_fild07'})
        self.assertNotIn('prt_sewb1', [e[2] for e in TABLES['fields']['portals']['prt_fild05']])  # paid/talk portal

    @unittest.skipUnless((ROOT.parent/'vendor/rathena/db/pre-re/mob_db.yml').exists(), 'pinned vendor data absent')
    def test_regeneration_is_identical(self):
        from scripts import build_p5_hunting
        monsters, fields = build_p5_hunting.build()
        self.assertEqual(json.loads(json.dumps(monsters)), json.loads((ROOT/'config/p5-monsters.json').read_text(encoding='utf-8')))
        self.assertEqual(json.loads(json.dumps(fields)), TABLES['fields'])


class FieldPlannerTests(unittest.TestCase):
    def setUp(self):
        self.opts, self.mood = hunting.options(tarin(), 'prt_fild08', TABLES, EQUIPMENT, {}, 'Tarin', 0)
        self.facts = {'level': {'base': 5, 'job': 3}}

    def ask(self, service):
        planner = FieldPlanner(service)
        planner.request(self.facts, self.opts, 'prt_fild08', self.mood, 'no_decision')
        return planner, planner.poll()

    def test_valid_choice_prompt_and_schema(self):
        service = Service({'field_id': 'prt_fild06', 'reason': 'More Lunatics, low danger.'})
        _, result = self.ask(service)
        self.assertEqual((result['status'], result['proposal']['field_id']), ('proposed', 'prt_fild06'))
        (identity, messages, seed), kwargs = service.calls[0]
        self.assertEqual(kwargs['response_format']['properties']['field_id']['enum'], [o['field_id'] for o in self.opts])
        prompt = messages[1]['content']
        self.assertNotIn('Tarin', prompt)
        self.assertIn(hunting.TEMPERAMENTS[self.mood], messages[0]['content'])
        self.assertNotIn('entry', json.loads(prompt)['options'][0])
        self.assertLess(sum(len(m['content']) for m in messages), 5000)  # cloud_limits.max_prompt_chars

    def test_request_error_backs_off_instead_of_retrying_every_tick(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory/'build.json').write_text(json.dumps({'build_id': 'novice-swordman'}), encoding='utf-8')
            cycle = SoloCycle(directory/'state.json', 20, {'tables': TABLES, 'equipment': EQUIPMENT, 'build': None})
            service = Service({'field_id': 'prt_fild08', 'reason': 'ok'})
            bridge = ControlledBridge(tarin())
            runner = Runner(cycle, bridge, directory, p5=P5Planning(cycle, service, directory))
            with patch.object(FieldPlanner, 'request', side_effect=ValueError('prompt character budget exceeded')) as req:
                runner.p5_tick(); runner.p5_tick()
            self.assertEqual(req.call_count, 1)
            runner.log.close()

    def test_invalid_failed_or_late_answers_keep_current(self):
        for service in (Service({'field_id': 'gef_fild10', 'reason': 'x'}), Service({'field_id': 'prt_fild06', 'reason': ''}),
                        Service(error='RoleUnavailable')):
            _, result = self.ask(service)
            self.assertEqual((result['status'], result['field_id'], result['reason']),
                             ('kept', 'prt_fild08', 'invalid_or_failed_inference'))
        planner = FieldPlanner(type('Slow', (), {'submit': lambda *a, **k: Future()})(), deadline_s=.01)
        planner.request(self.facts, self.opts, 'prt_fild08', self.mood, 'level_up')
        time.sleep(.02)
        self.assertEqual(planner.poll()['reason'], 'planning_deadline')
        with self.assertRaises(ValueError):
            validate_field({'field_id': 'prt_fild08', 'reason': 'ok', 'extra': 1}, self.opts)


class CycleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.p5 = {'tables': TABLES, 'equipment': EQUIPMENT, 'build': BUILDS['novice-swordman']}
        self.c = SoloCycle(self.directory/'state.json', 20, self.p5)
        self.n = 0

    def run_action(self, snap, status='completed', reason=None, now=100):
        action = self.c.plan(snap, now=now)
        self.n += 1
        self.c.prepare(action, f'c_{self.n}', 'boot:1', now=now)
        reason = reason or {'attack': 'killed', 'travel': 'arrived', 'stat_up': 'stat_raised', 'navigate': 'arrived',
                            'take': 'picked_up', 'skill_up': 'skill_raised', 'equip': 'equipped'}[action['type']]
        self.c.result({'request_id': f'c_{self.n}', 'status': status, 'reason': reason}, now=now + 5)
        return action

    def test_attacks_nearest_viable_and_learns(self):
        snap = tarin(monsters=[{'id': 'h', 'name_id': 1004, 'x': 171, 'y': 250, 'eligible': 1},
                               {'id': 'l', 'name_id': 1063, 'x': 175, 'y': 250, 'eligible': 1}])
        self.assertEqual(self.run_action(snap)['target'], 'l')
        self.assertEqual(self.c.state['outcomes']['monsters']['1063']['kills'], 1)
        self.c.state['phase'] = 'hunt'
        self.run_action(snap, 'failed', 'retreat_low_hp', now=200)
        o = self.c.state['outcomes']
        self.assertEqual((o['monsters']['1063']['retreats'], o['fields']['prt_fild08']['retreats']), (1, 1))
        self.assertEqual(o['fields']['prt_fild08']['hunt_s'], 10)

    def test_build_points_first_and_refusal_pauses_until_level(self):
        snap = tarin()
        snap['progress']['points_free'] = 3
        self.assertEqual(self.run_action(snap), {'type': 'stat_up', 'stat': 'str', 'timeout_s': 10})
        self.assertEqual(self.c.state['failures'], 0)
        self.run_action(snap, 'failed', 'server_refused')
        self.assertEqual(self.c.state['build_pause'], [5, 3])
        self.assertEqual((self.c.state['status'], self.c.plan(snap, now=100)['type']), ('active', 'navigate'))
        snap['level']['base'] = 6
        self.assertEqual(self.c.plan(snap, now=100)['type'], 'stat_up')

    def test_unknown_progress_result_blocks_without_replay(self):
        snap = tarin()
        snap['progress']['points_skill'] = 1
        self.run_action(snap, 'unknown', 'result_not_confirmed')
        self.assertEqual(self.c.state['reason'], 'skill_up:unknown/result_not_confirmed')

    def test_new_field_travel_hunt_and_supply_return(self):
        self.assertEqual(self.c.field_due(tarin(), now=100), 'no_decision')
        self.c.set_field('prt_fild06', {'via': 'prontera', 'x': 33, 'y': 185}, {'decision': 'change'}, 5, now=100)
        self.assertIsNone(self.c.field_due(tarin(), now=200))
        self.assertEqual(self.c.field_due(tarin(level={'base': 6, 'job': 3}), now=200), 'level_up')
        self.assertEqual(self.c.field_due(tarin(), now=100 + 1800), 'periodic_review')
        action = self.run_action(tarin())
        self.assertEqual(action, {'type': 'travel', 'map': 'prt_fild06', 'x': 33, 'y': 185, 'timeout_s': 174})
        there = tarin(map='prt_fild06', position={'x': 33, 'y': 185},
                      monsters=[{'id': 'p', 'name_id': 1002, 'x': 34, 'y': 185, 'eligible': 1}])
        self.assertEqual(self.c.plan(there, now=120)['type'], 'attack')
        # Out of apples: shop trip, then back to the chosen field (not prt_fild08).
        broke = copy.deepcopy(there)
        broke['inventory'] = [i for i in broke['inventory'] if i['name_id'] != 512]
        broke['zeny'] = 100
        self.assertEqual(self.c.plan(broke, now=120)['map'], 'prontera')
        self.assertEqual(self.c.state['return_to'], {'map': 'prt_fild06', 'x': 33, 'y': 185})
        with self.assertRaises(RuntimeError):
            self.c.set_field('prt_fild05', {'x': 1, 'y': 1}, {}, 5)

    def test_death_is_recorded_for_field_and_target(self):
        snap = tarin(monsters=[{'id': 'l', 'name_id': 1063, 'x': 175, 'y': 250, 'eligible': 1}])
        self.run_action(snap, 'failed', 'target_lost')
        self.c.plan(tarin(dead=True), now=300)
        o = self.c.state['outcomes']
        self.assertEqual((self.c.state['reason'], o['fields']['prt_fild08']['deaths'], o['monsters']['1063']['deaths']),
                         ('character_dead', 1, 1))

    def test_legacy_checkpoint_keeps_prt_fild08(self):
        legacy = SoloCycle(self.directory/'old.json', 3)
        self.assertEqual(legacy.state['field']['id'], 'prt_fild08')
        snap = p2_snapshot(monsters=[{'id': 'x', 'x': 171, 'y': 250}])
        self.assertEqual(legacy.plan(snap)['type'], 'attack')  # No P5 context: no viability filter.


class RunnerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.p5 = {'tables': TABLES, 'equipment': EQUIPMENT, 'build': None}

    def run_runner(self, service, snap):
        cycle = SoloCycle(self.directory/'state.json', 20, self.p5)
        planning = P5Planning(cycle, service, self.directory)
        bridge = ControlledBridge(snap)
        bridge.events.insert(0, {'kind': 'ready', 'data': {'next_serial': bridge.next_serial}})
        runner = Runner(cycle, bridge, self.directory, p5=planning)
        runner.inventory_session, runner.inventory_ready_after = bridge.session, 0
        with patch.object(runner, 'resource_guard'):
            out = runner.run(.05, max_actions=1)
        return cycle, bridge, out

    def write_build(self):
        (self.directory/'build.json').write_text(json.dumps({'build_id': 'novice-swordman'}), encoding='utf-8')

    def test_planner_field_choice_is_validated_and_travelled(self):
        self.write_build()
        service = Service({'field_id': 'prt_fild06', 'reason': 'Two hops, more Lunatics, low danger.'})
        cycle, bridge, out = self.run_runner(service, tarin())
        decision = cycle.state['field_decisions'][-1]
        self.assertEqual((decision['decision'], decision['field_id'], decision['previous'], decision['trigger']),
                         ('change', 'prt_fild06', 'prt_fild08', 'no_decision'))
        self.assertEqual(decision['reason'], 'Two hops, more Lunatics, low danger.')
        self.assertEqual(bridge.proposals[0][0], {'type': 'travel', 'map': 'prt_fild06', 'x': 33, 'y': 185, 'timeout_s': 174})
        self.assertEqual(out['inference_calls'], 1)
        events = [json.loads(l)['kind'] for l in (self.directory/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertIn('field_result', events)

    def test_failed_planner_keeps_field_and_missing_build_is_chosen_once(self):
        service = Service(error='RoleUnavailable')
        cycle, bridge, out = self.run_runner(service, tarin())
        decision = cycle.state['field_decisions'][-1]
        self.assertEqual((decision['decision'], decision['field_id']), ('kept_on_failure', 'prt_fild08'))
        self.assertFalse((self.directory/'build.json').exists())  # Failed build choice: no build, no points spent.
        self.assertEqual(out['inference_calls'], 2)
        self.assertEqual(bridge.proposals[0][0]['type'], 'navigate')


if __name__ == '__main__':
    unittest.main()
