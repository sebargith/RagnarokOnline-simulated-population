from concurrent.futures import Future
import functools
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent.goal_planner import GoalPlanner
from agent.solo_cycle import SoloCycle
from inference.m2 import BoundedInference
from inference.openai_compat import api_key, AuthRejected, KeyUnavailable, QuotaExceeded, https_send, openai_chat
from inference.roles import RoleService, build_role, candidate, load_roles
from scripts.run_p2_cycle import Runner

ROOT = Path(__file__).resolve().parents[1]
KEY = 'sk-test-SECRET-0123456789'
ENV = {'GEMINI_API_KEY': KEY}
GOAL = '{"type":"continue_current","additional_kills":0}'


def reply(content=GOAL, finish='stop', status=200, extra=b''):
    body = {'model': 'm', 'choices': [{'message': {'role': 'assistant', 'content': content},
                                       'finish_reason': finish}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}
    return status, json.dumps(body).encode() + extra


def isolated():
    """Roles config that ignores the user's real key file."""
    doc = load_roles()
    doc['key_file'] = None
    return doc


class Sender:
    def __init__(self, *results, delay=0):
        self.results, self.delay, self.calls = list(results), delay, []

    def __call__(self, url, headers, body, timeout, max_bytes):
        self.calls.append({'url': url, 'headers': headers, 'body': json.loads(body), 'timeout': timeout})
        time.sleep(self.delay)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class OpenAICompatTests(unittest.TestCase):
    def setUp(self):
        self.doc = isolated()
        self.config, self.model, _ = candidate(self.doc, 'gemini-flash', ENV)
        self.messages = [{'role': 'system', 'content': 'Return only JSON.'},
                         {'role': 'user', 'content': '{"kills":9}'}]

    def call(self, sender, config=None, schema=None, environ=ENV):
        return openai_chat(config or self.config, self.model, self.messages, 31, True, schema,
                           send=sender, environ=environ)

    def test_request_shape_schema_and_result(self):
        sender = Sender(reply())
        schema = {'type': 'object'}
        result = self.call(sender, schema=schema)
        sent = sender.calls[0]
        self.assertTrue(sent['url'].startswith('https://') and sent['url'].endswith('/chat/completions'))
        self.assertEqual(sent['body']['model'], self.model)
        self.assertEqual(sent['body']['response_format']['json_schema']['schema'], schema)
        self.assertFalse(sent['body']['stream'])
        self.assertEqual(sent['timeout'], self.config['cold_service_timeout_s'])
        self.assertEqual(result['content'], GOAL)
        self.assertEqual(result['eval_count'], 5)

    def test_missing_key_fails_before_network(self):
        sender = Sender()
        for environ in ({}, {'GEMINI_API_KEY': '  '}):
            with self.assertRaises(KeyUnavailable):
                self.call(sender, environ=environ)
        self.assertEqual(sender.calls, [])
        with self.assertRaises(KeyUnavailable):
            candidate(self.doc, 'groq-gpt-oss', {})

    def test_budgets_and_failures_raise_without_retry(self):
        cases = [(reply(status=429), QuotaExceeded), (reply(status=401), AuthRejected),
                 (reply(status=500), RuntimeError), (reply(finish='length'), ValueError),
                 (reply(content=''), ValueError), (reply(content='x'*5000), ValueError),
                 (reply(extra=b' '*300000), ValueError),
                 ((200, b'{"choices":[]}'), ValueError), ((200, b'not json'), ValueError)]
        for result, error in cases:
            sender = Sender(result)
            with self.subTest(error=error), self.assertRaises(error):
                self.call(sender)
            self.assertEqual(len(sender.calls), 1)
        with self.assertRaises(ValueError):
            openai_chat(self.config, self.model, [{'role': 'user', 'content': 'x'*6000}], 1,
                        send=Sender(), environ=ENV)

    def test_slow_reply_exceeds_service_deadline(self):
        config = dict(self.config, cold_service_timeout_s=.05)
        with self.assertRaises(TimeoutError):
            self.call(Sender(reply(), delay=.1), config=config)

    def test_key_never_appears_in_results_errors_or_logs(self):
        echo = Sender(ConnectionError('failed with Authorization: Bearer ' + KEY))
        service = BoundedInference(self.config, self.model,
                                   functools.partial(openai_chat, send=echo, environ=ENV))
        self.addCleanup(service.close)
        failed = service.submit('a', self.messages, 1).result(2)
        self.assertIn('error', failed)
        ok = openai_chat(self.config, self.model, self.messages, 1, send=Sender(reply()), environ=ENV)
        role = RoleService('planner', ('gemini-flash', service))
        dumped = json.dumps([failed, ok, role.status(), repr(self.config)])
        self.assertNotIn(KEY, dumped)
        self.assertNotIn('SECRET', dumped)
        self.assertNotIn(KEY, json.dumps(load_roles()))

    def test_plain_http_is_only_for_loopback(self):
        with self.assertRaises(ValueError):
            https_send('http://example.com/v1/chat/completions', {}, b'{}', 1, 10)

    def test_bounded_queue_and_open_circuit_are_explicit(self):
        gate = threading.Event()

        def slow(url, headers, body, timeout, max_bytes):
            gate.wait(2)
            return reply()
        service = BoundedInference(self.config, self.model,
                                   functools.partial(openai_chat, send=slow, environ=ENV))
        self.addCleanup(service.close)
        futures = [service.submit(str(i), self.messages, 1) for i in range(5)]
        with self.assertRaises(BufferError):
            service.submit('6', self.messages, 1)
        gate.set()
        self.assertTrue(all('content' in f.result(2) for f in futures))


class KeyFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'model-keys.env'
        self.config = {'api_key_env': 'GEMINI_API_KEY', 'key_file': str(self.path)}

    def test_file_is_read_when_env_missing_and_env_wins(self):
        self.path.write_text('# comment\n\nGROQ_API_KEY=\nGEMINI_API_KEY = ' + KEY + '\n', encoding='utf-8')
        self.assertEqual(api_key(self.config, {}), KEY)
        self.assertEqual(api_key(self.config, {'GEMINI_API_KEY': ' '}), KEY)
        self.assertEqual(api_key(self.config, {'GEMINI_API_KEY': 'from-env'}), 'from-env')
        with self.assertRaises(KeyUnavailable):
            api_key(dict(self.config, api_key_env='GROQ_API_KEY'), {})

    def test_empty_or_missing_file_means_unavailable(self):
        for content in (None, 'GEMINI_API_KEY=\n', '# GEMINI_API_KEY=' + KEY + '\n'):
            if content is None:
                self.path.unlink(missing_ok=True)
            else:
                self.path.write_text(content, encoding='utf-8')
            with self.subTest(content=content), self.assertRaises(KeyUnavailable) as caught:
                api_key(self.config, {})
            self.assertNotIn(KEY, str(caught.exception))

    def test_roles_resolve_key_file_under_runtime_and_never_expose_value(self):
        doc = load_roles()
        doc['key_file'] = self.path
        self.path.write_text('GEMINI_API_KEY=' + KEY + '\n', encoding='utf-8')
        config, model, transport = candidate(doc, 'gemini-flash', {})
        self.assertEqual(config['key_file'], str(self.path))  # absolute path wins the join
        self.assertEqual(Path(candidate(load_roles(), 'gemini-flash', ENV)[0]['key_file']),
                         ROOT.parent/'runtime/secrets/model-keys.env')
        sender = Sender(reply(status=429))
        service = BoundedInference(config, model, functools.partial(openai_chat, send=sender, environ={}))
        self.addCleanup(service.close)
        failed = service.submit('a', [{'role': 'user', 'content': 'x'}], 1).result(2)
        self.assertEqual(sender.calls[0]['headers']['Authorization'], 'Bearer ' + KEY)
        self.assertIn('QuotaExceeded', failed['error'])
        self.assertNotIn(KEY, json.dumps([failed, config, repr(transport)]))


class RoleTests(unittest.TestCase):
    def test_default_roles_stay_on_current_local_9b(self):
        doc = load_roles()
        operating = json.loads((ROOT/'config/m2-operating.json').read_text())
        for role in ('planner', 'chat'):
            config, model, _ = candidate(doc, doc['roles'][role]['primary'])
            self.assertEqual(model, operating['model'])
            self.assertEqual(config, operating)
        tuned, _, _ = candidate(doc, 'qwen9b-tuned')
        self.assertTrue(tuned['think'])
        self.assertEqual(tuned['options']['num_ctx'], 8192)
        self.assertEqual(tuned['options']['top_k'], operating['options']['top_k'])

    def test_chat_role_rejects_cloud_models(self):
        doc = load_roles()
        doc['roles']['chat']['primary'] = 'gemini-flash'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'roles.json'
            path.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):
                load_roles(path)

    def test_missing_key_marks_candidate_unavailable_and_uses_fallback(self):
        doc = isolated()
        doc['roles']['planner'].update(primary='gemini-flash', fallback='qwen9b-current')
        with patch('inference.roles.BoundedInference') as bounded:
            role = build_role('planner', doc, environ={})
        self.assertIsNone(role.primary)
        self.assertIn('GEMINI_API_KEY is not set', role.unavailable)
        self.assertEqual(role.fallback_name, 'qwen9b-current')
        self.assertEqual(bounded.call_count, 1)


class FallbackTests(unittest.TestCase):
    """Cloud quota exhaustion never blocks play and is reported."""
    def setUp(self):
        doc = load_roles()
        config, model, _ = candidate(doc, 'gemini-flash', ENV)
        self.cloud_sender = Sender(reply(status=429), reply())
        self.cloud = BoundedInference(config, model, functools.partial(
            openai_chat, send=self.cloud_sender, environ=ENV))
        self.local_calls = []

        def local(config, model, messages, seed, cold, response_format):
            self.local_calls.append(messages)
            return {'content': GOAL, 'service_s': .01}
        self.local = BoundedInference(dict(config, cold_service_timeout_s=5), 'local-9b', local)
        self.now = [100.0]
        self.role = RoleService('planner', ('gemini-flash', self.cloud), ('qwen9b-current', self.local),
                                cooldown_s=300, clock=lambda: self.now[0])
        self.addCleanup(self.role.close)
        root = ROOT.parent/'runtime'
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'state.json'
        self.cycle = SoloCycle(self.path, 1)

    def plan(self):
        planner = GoalPlanner(self.role, self.path)
        planner.request('Continue the current goal')
        while (result := planner.poll()) is None:
            time.sleep(.01)
        return result

    def test_quota_failure_reports_and_later_requests_degrade_to_local(self):
        before = self.path.read_bytes()
        self.assertEqual(self.plan(), {'status': 'unavailable', 'reason': 'invalid_or_failed_inference'})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(self.cloud_sender.calls), 1)  # no hidden retry
        self.assertEqual(self.local_calls, [])             # failed request not re-sent
        raw = self.role.submit('x', [{'role': 'user', 'content': 'hi'}], 1).result(2)
        self.assertEqual((raw['served_by'], raw['degraded']), ('qwen9b-current', True))
        self.assertIn('cooling down', raw['degraded_reason'])
        self.assertEqual(self.plan()['status'], 'proposed')
        kinds = [e['kind'] for e in self.role.status()['events']]
        self.assertIn('request_failed', kinds)
        self.assertIn('degraded_to_fallback', kinds)
        self.assertTrue(any('QuotaExceeded' in e['reason'] for e in self.role.status()['events']))
        self.now[0] += 301
        raw = self.role.submit('y', [{'role': 'user', 'content': 'hi'}], 1).result(2)
        self.assertEqual((raw['served_by'], raw['degraded']), ('gemini-flash', False))
        self.assertEqual(len(self.cloud_sender.calls), 2)

    def test_without_fallback_role_fails_fast_and_runner_keeps_playing(self):
        role = RoleService('planner', ('gemini-flash', None, 'GEMINI_API_KEY is not set'))
        result = role.submit('x', [{'role': 'user', 'content': 'hi'}], 1).result(0)
        self.assertEqual(result['fallback'], 'local_policy')
        try:
            from test_p2_cycle import FakeBridge, snapshot
        except ImportError:
            from tests.test_p2_cycle import FakeBridge, snapshot

        class GameplayBridge(FakeBridge):
            def proposal(self, action, **kwargs):
                self.proposals.append(action)
                self.events.append({'kind': 'action_result', 'data': {
                    'request_id': kwargs['request_id'], 'status': 'completed', 'reason': 'killed'}})
        bridge = GameplayBridge(snapshot())
        runner = Runner(self.cycle, bridge, Path(self.temp.name), GoalPlanner(role, self.path), 'Continue')
        self.addCleanup(runner.log.close)
        runner.inventory_session, runner.inventory_ready_after = bridge.session, 0
        with patch.object(runner, 'resource_guard'):
            outcome = runner.run(.2, max_actions=1)
        self.assertEqual(outcome['actions_sent'], 1)
        self.assertEqual(self.cycle.state['kills'], 1)
        self.assertEqual(outcome['planning_result']['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
