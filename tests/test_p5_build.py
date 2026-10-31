from concurrent.futures import Future
import copy
import json
from pathlib import Path
import tempfile
import unittest

from agent import build_policy as policy
from agent.goal_planner import BuildPlanner, apply_build, read_build, validate_build

ROOT = Path(__file__).resolve().parents[1]
BUILDS = policy.load_builds()
EQUIPMENT = policy.load_equipment()


def stats(**values):
    out = {s: {'value': 1, 'cost': 2} for s in policy.STATS}
    for k, v in values.items():
        out[k] = {'value': v, 'cost': 2 + v // 10}
    return out


def snapshot(**progress):
    p = {'job_id': 0, 'job': 'Novice', 'sex': 1, 'stats_ready': 1, 'points_free': 0, 'points_skill': 0,
         'stats': stats(str=5, agi=5, vit=5, dex=5), 'skills': [{'handle': 'NV_BASIC', 'lv': 0, 'up': 1}]}
    p.update(progress)
    return {'connected': 1, 'name': 'Tarin', 'dead': 0, 'native_task': None, 'inventory_ready': 1,
            'inventory_truncated': 0, 'level': {'base': 4, 'job': 3}, 'progress': p,
            'inventory': [{'name': 'Knife', 'name_id': 1201, 'amount': 1, 'type': 5, 'equipped': 2, 'identified': 1},
                          {'name': 'Cotton Shirt', 'name_id': 2301, 'amount': 1, 'type': 4, 'equipped': 16, 'identified': 1}]}


class Service:
    def __init__(self, content=None, error=None):
        self.future, self.calls = Future(), []
        self.future.set_result({'error': error} if error else {'content': json.dumps(content), 'served_by': 'groq-gpt-oss'})

    def submit(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.future


class PolicyTests(unittest.TestCase):
    def test_config_is_valid(self):
        self.assertEqual({b['target_class'] for b in BUILDS.values()}, {'Swordman', 'Archer', 'Thief'})
        self.assertTrue(all(b['skills'][0] == ['NV_BASIC', 9] for b in BUILDS.values()))
        knife = EQUIPMENT['1201']
        self.assertEqual((knife['attack'], knife['locations'], knife['min_level']), (17, ['Right_Hand'], 1))

    def test_stats_follow_priority_and_save_points(self):
        build = BUILDS['novice-swordman']
        snap = snapshot(points_free=3)
        self.assertEqual(policy.next_action(snap, build, EQUIPMENT)[0], {'type': 'stat_up', 'stat': 'str', 'timeout_s': 10})
        snap['progress']['stats']['str'] = {'value': 20, 'cost': 4}
        self.assertEqual(policy.next_action(snap, build, EQUIPMENT)[0]['stat'], 'vit')
        # Not enough for VIT: points are kept instead of skipping to DEX.
        snap['progress']['points_free'] = 1
        self.assertEqual(policy.stat_action(snap['progress'], build), (None, 'saving_points_for_vit'))

    def test_skills_skip_unlisted_and_locked(self):
        build = BUILDS['novice-swordman']
        snap = snapshot(points_skill=1)
        self.assertEqual(policy.next_action(snap, build, EQUIPMENT)[0], {'type': 'skill_up', 'skill': 'NV_BASIC', 'timeout_s': 10})
        snap['progress']['skills'] = [{'handle': 'NV_BASIC', 'lv': 9, 'up': 0}, {'handle': 'SM_BASH', 'lv': 0, 'up': 0},
                                      {'handle': 'SM_SWORD', 'lv': 0, 'up': 1}]
        self.assertEqual(policy.next_action(snap, build, EQUIPMENT)[0]['skill'], 'SM_SWORD')

    def test_equips_only_strictly_better_wearable_gear(self):
        build = BUILDS['novice-swordman']
        snap = snapshot()
        self.assertEqual(policy.next_action(snap, build, EQUIPMENT),
                         (None, 'saving_points_for_str,no_skill_points,nothing_better_to_equip'))
        inv = snap['inventory']
        inv.append({'name': 'Sword', 'name_id': 1101, 'amount': 1, 'type': 5, 'equipped': 0, 'identified': 1})
        inv.append({'name': 'Bow', 'name_id': 1701, 'amount': 1, 'type': 5, 'equipped': 0, 'identified': 1})  # Novice cannot
        inv.append({'name': 'Sandals', 'name_id': 2401, 'amount': 1, 'type': 4, 'equipped': 0, 'identified': 1})
        inv.append({'name': 'Cotton Shirt', 'name_id': 2301, 'amount': 1, 'type': 4, 'equipped': 0, 'identified': 1})
        action, why = policy.next_action(snap, build, EQUIPMENT)
        self.assertEqual((action['name_id'], why), (1101, 'better_weapon'))  # +8 ATK beats +1 DEF
        snap['level']['base'] = 1  # Sword needs base level 2
        self.assertEqual(policy.next_action(snap, build, EQUIPMENT)[0]['name_id'], 2401)

    def test_unknown_worn_item_is_left_alone(self):
        snap = snapshot()
        snap['inventory'][0]['name_id'] = 13000  # not in the table
        snap['inventory'].append({'name': 'Sword', 'name_id': 1101, 'amount': 1, 'type': 5, 'equipped': 0, 'identified': 1})
        self.assertIsNone(policy.equip_action(snap, EQUIPMENT)[0])

    def test_not_ready_states(self):
        for change in ({'dead': 1}, {'native_task': {'id': 'x'}}, {'inventory_truncated': 1}):
            snap = {**snapshot(points_free=9), **change}
            self.assertIsNone(policy.next_action(snap, BUILDS['novice-archer'], EQUIPMENT)[0])
        snap = snapshot(points_free=9, stats_ready=0)
        self.assertEqual(policy.stat_action(snap['progress'], BUILDS['novice-archer']), (None, 'stats_not_observed'))


class BuildPlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT.parent/'runtime')
        self.addCleanup(self.temp.cleanup)
        self.path, self.lock = Path(self.temp.name)/'build.json', Path(self.temp.name)/'build.lock'
        self.observation = {'time_ms': 1000, 'data': snapshot(points_free=3)}

    def ask(self, content=None, current=None, error=None):
        service = Service(content, error)
        planner = BuildPlanner(service, BUILDS)
        planner.request(self.observation['data'], current)
        return service, planner.poll()

    def test_prompt_has_only_facts_and_restricted_schema(self):
        service, _ = self.ask({'type': 'choose_build', 'build_id': 'novice-archer', 'reason': 'DEX scales'})
        (identity, messages, seed), kwargs = service.calls[0]
        schema = kwargs['response_format']
        self.assertEqual(schema['properties']['build_id']['enum'], list(BUILDS))
        self.assertEqual(schema['properties']['type']['enum'], ['choose_build'])
        user = json.loads(messages[1]['content'])
        self.assertEqual(set(user), {'current_build', 'observed', 'options'})
        self.assertEqual(user['observed']['equipped'], ['Cotton Shirt', 'Knife'])
        self.assertNotIn('Tarin', messages[1]['content'])

    def test_choice_is_stored_with_reason_and_facts(self):
        _, envelope = self.ask({'type': 'choose_build', 'build_id': 'novice-archer', 'reason': 'DEX scales'})
        record = apply_build(self.path, self.lock, envelope, self.observation, 'Tarin', now_ms=1500)
        self.assertEqual((record['build_id'], record['reason'], record['served_by']), ('novice-archer', 'DEX scales', 'groq-gpt-oss'))
        self.assertEqual(read_build(self.path)['facts']['points_free'], 3)

    def test_failure_or_invalid_answer_keeps_build(self):
        for content, error in ((None, 'HTTP 429'), ({'type': 'choose_build', 'build_id': 'novice-mage', 'reason': 'x'}, None),
                               ({'type': 'keep_build', 'build_id': 'novice-thief', 'reason': 'x'}, None)):
            _, result = self.ask(content, current='novice-archer', error=error)
            self.assertEqual((result['status'], result['build_id']), ('kept', 'novice-archer'))

    def test_validation_rules(self):
        with self.assertRaises(ValueError):
            validate_build({'type': 'choose_build', 'build_id': 'novice-archer', 'reason': ''}, BUILDS, None)
        with self.assertRaises(ValueError):
            validate_build({'type': 'choose_build', 'build_id': 'novice-archer', 'reason': 'r'}, BUILDS, 'novice-archer')
        self.assertEqual(validate_build({'type': 'keep_build', 'build_id': 'novice-archer', 'reason': 'r'}, BUILDS,
                                        'novice-archer')['type'], 'keep_build')

    def test_application_needs_fresh_perception_and_unchanged_build(self):
        _, envelope = self.ask({'type': 'choose_build', 'build_id': 'novice-archer', 'reason': 'r'})
        with self.assertRaises(ValueError):
            apply_build(self.path, self.lock, envelope, self.observation, 'Tarin', now_ms=9000)
        stale = copy.deepcopy(envelope)
        stale['current'] = 'novice-thief'
        with self.assertRaises(RuntimeError):
            apply_build(self.path, self.lock, stale, self.observation, 'Tarin', now_ms=1500)

    def test_build_fixed_after_job_change(self):
        self.observation['data']['progress']['job'] = 'Archer'
        with self.assertRaises(RuntimeError):
            self.ask({'type': 'keep_build', 'build_id': 'novice-archer', 'reason': 'r'}, current='novice-archer')


if __name__ == '__main__':
    unittest.main()
