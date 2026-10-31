import json
from pathlib import Path
import unittest

from scripts.eval_p5_planner import score, summarize

ROOT = Path(__file__).resolve().parents[1]
BENCH = json.loads((ROOT/'fixtures/p5-planner-bench.json').read_text(encoding='utf-8'))
CASES = {c['id']: c for c in BENCH['cases']}


class BenchTests(unittest.TestCase):
    def test_fixture_holds_only_game_facts(self):
        text = json.dumps(BENCH).casefold()
        for word in ('password', 'api_key', 'secret', 'token', 'userid', 'account'):
            self.assertNotIn(word, text)
        for case in BENCH['cases']:
            self.assertLessEqual(sum(len(m['content']) for m in case['messages']), 5000)
            self.assertEqual([m['role'] for m in case['messages']], ['system', 'user'])

    def test_goal_scoring_checks_schema_capability_and_expectation(self):
        case = CASES['goal-inflight']
        self.assertEqual(score(case, '{"type":"ask_help","additional_kills":0}'),
                         {'json': True, 'capability': True, 'fact': True})
        self.assertEqual(score(case, '{"type":"continue_current","additional_kills":0}'),
                         {'json': True, 'capability': False, 'fact': False})
        self.assertFalse(score(CASES['goal-injection'], '{"type":"hunt","additional_kills":50}')['json'])
        self.assertFalse(score(case, '```json\n{"type":"ask_help","additional_kills":0}\n```')['json'])

    def test_report_scoring_flags_invented_numbers_and_missing_facts(self):
        case = CASES['report-final']
        good = score(case, json.dumps({'summary': 'Tarin is level 4 on prt_fild08 with 57/57 HP and 13 zeny.'}))
        self.assertEqual((good['json'], good['capability'], good['fact']), (True, True, True))
        bad = score(case, json.dumps({'summary': 'Tarin is level 5 on prt_fild08 with 57 HP.'}))
        self.assertFalse(bad['capability'])
        self.assertEqual(bad['invented_numbers'], [5.0])
        self.assertIn(13, bad['missing_facts'])

    def test_mechanics_scoring_and_summary(self):
        case = CASES['mech-weight']
        rows = [{'response_s': 1.0, 'score': score(case, '{"topic":"weight"}')},
                {'response_s': 3.0, 'score': score(case, '{"topic":"stats"}')},
                {'response_s': 9.0, 'error': 'TimeoutError: x', 'score': score(case, None)}]
        self.assertEqual(rows[1]['score'], {'json': True, 'capability': True, 'fact': False})
        summary = summarize(rows)
        self.assertEqual((summary['json_pct'], summary['fact_pct'], summary['errors'], summary['max_s']),
                         (67, 33, 1, 3.0))


if __name__ == '__main__':
    unittest.main()
