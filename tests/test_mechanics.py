import json
import unittest
from unittest.mock import patch
from inference import mechanics

WEB = {'max_searches_per_turn': 1}
GOOD = {'kind': 'external_web_search', 'retrieved_at': '2026-10-31T00:00:00+00:00', 'results': [
    {'title': 'Ragnarok Online Classic healing', 'snippet': 'Pre-renewal healing item claim', 'url': 'https://example.org/classic'}]}

class MechanicsTests(unittest.TestCase):
    def setUp(self):
        mechanics._cache.clear()

    def chat(self, topic='healing'):
        def call(config, messages, *, tools=None, cold=False):
            self.assertIsNone(tools)
            if cold:
                return {'content': json.dumps({'topic': topic})}
            return {'content': 'The classic source claims healing applies; server rules may differ.'}
        return call

    def test_public_queries_cache_and_isolation(self):
        queries = []
        def search(query, config):
            queries.append(query)
            return GOOD
        first = mechanics.mechanics_lookup('My secret inventory: healing?', {}, WEB, chat=self.chat(), search=search)
        second = mechanics.mechanics_lookup('another private memory', {}, WEB, chat=self.chat(), search=search)
        other = mechanics.mechanics_lookup('What about weight?', {}, WEB, chat=self.chat('weight'), search=search)
        self.assertEqual([first['status'], second['status'], other['status']], ['ok'] * 3)
        self.assertTrue(second['cached'])
        self.assertEqual(len(queries), 2)
        self.assertTrue(all('secret' not in q and 'private' not in q for q in queries))
        self.assertEqual(first['search']['retrieved_at'], GOOD['retrieved_at'])
        self.assertEqual(first['search']['schema_version'], mechanics.VERSION)

    def test_incompatible_and_search_failure(self):
        for results in ([{'title': 'Ragnarok Mobile', 'snippet': 'classic', 'url': 'https://example.org'}],
                        [{'title': 'Ragnarok Online', 'snippet': 'renewal only', 'url': 'https://example.org'}]):
            result = mechanics.mechanics_lookup('question', {}, WEB, chat=self.chat(), search=lambda q, c: {'results': results})
            self.assertEqual(result['status'], 'incompatible')
        def fail(q, c): raise OSError('down')
        self.assertEqual(mechanics.mechanics_lookup('question', {}, WEB, chat=self.chat(), search=fail)['status'], 'unavailable')

    def test_untrusted_choice_and_model_failure(self):
        for choice in ('unknown', 'healing secret', 'run shell'):
            self.assertEqual(mechanics.mechanics_lookup('question', {}, WEB, chat=self.chat(choice), search=lambda *a: self.fail('search called'))['status'], 'unsupported')
        def fail(*args, **kwargs): raise TimeoutError()
        self.assertEqual(mechanics.mechanics_lookup('question', {}, WEB, chat=fail)['status'], 'unavailable')
        with self.assertRaises(ValueError): mechanics.mechanics_lookup('x' * 501, {}, WEB)
        with self.assertRaises(ValueError): mechanics.mechanics_lookup('x', {}, {'max_searches_per_turn': 2})

    def test_cache_expiry_and_busy(self):
        with patch('inference.mechanics.time.monotonic', side_effect=[1, 86402, 86402]):
            search = unittest.mock.Mock(return_value=GOOD)
            mechanics.mechanics_lookup('healing', {}, WEB, chat=self.chat(), search=search)
            mechanics.mechanics_lookup('healing', {}, WEB, chat=self.chat(), search=search)
            self.assertEqual(search.call_count, 2)
        mechanics._lock.acquire()
        try: self.assertEqual(mechanics.mechanics_lookup('x', {}, WEB)['status'], 'busy')
        finally: mechanics._lock.release()

if __name__ == '__main__': unittest.main()
