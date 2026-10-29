import unittest

from inference.web_search import SearchUnavailable, search_public_web, validate_query


CONFIG = {
    "timeout_s": 8,
    "max_results": 2,
    "max_title_chars": 12,
    "max_snippet_chars": 20,
}


class FakeSearch:
    def __call__(self, config, query):
        assert query == "Prontera guide"
        return {"results": [
            {"title": "First useful result", "url": "https://example.org/a", "content": "A long public excerpt of search results"},
            {"title": "Private address", "url": "http://127.0.0.1/secret", "content": "ignore"},
            {"title": "Second result", "url": "https://example.org/b", "content": "another"},
        ]}


class WebSearchTests(unittest.TestCase):
    def test_rejects_private_or_malformed_query(self):
        for query in ("x", "a" * 161, "hello\nworld", "https://example.org", "user@example.org"):
            with self.subTest(query=query), self.assertRaises(ValueError):
                validate_query(query)
        with self.assertRaises(ValueError):
            validate_query("Where is the copper wren?", private_terms=("copper wren",))

    def test_bounded_result_and_public_links(self):
        result = search_public_web(" Prontera   guide ", CONFIG, transport=FakeSearch())
        self.assertEqual(result["kind"], "external_web_search")
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["results"][0]["title"], "First useful")
        self.assertEqual(len(result["results"][0]["snippet"]), 20)
        self.assertEqual(result["results"][1]["url"], "https://example.org/b")

    def test_provider_failure_is_explicit(self):
        def broken(config, query):
            raise RuntimeError("provider failed")

        with self.assertRaises(SearchUnavailable):
            search_public_web("Prontera guide", CONFIG, transport=broken)

    def test_rejects_nonlocal_endpoint(self):
        from inference.web_search import _fetch_searx

        with self.assertRaises(ValueError):
            _fetch_searx(dict(CONFIG, endpoint="https://example.org"), "Prontera")


if __name__ == "__main__":
    unittest.main()
