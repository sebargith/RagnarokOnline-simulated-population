import unittest

from inference.web_search import SearchUnavailable, search_public_web, validate_query


CONFIG = {
    "timeout_s": 8,
    "max_results": 2,
    "max_title_chars": 12,
    "max_snippet_chars": 20,
}


class FakeSearch:
    def __init__(self, timeout):
        assert timeout == 8

    def text(self, query, **kwargs):
        assert query == "Prontera guide"
        assert kwargs["backend"] == "duckduckgo"
        assert kwargs["max_results"] == 2
        return [
            {"title": "First useful result", "href": "https://example.org/a", "body": "A long public excerpt of search results"},
            {"title": "Private address", "href": "http://127.0.0.1/secret", "body": "ignore"},
            {"title": "Second result", "href": "https://example.org/b", "body": "another"},
        ]


class WebSearchTests(unittest.TestCase):
    def test_rejects_private_or_malformed_query(self):
        for query in ("x", "a" * 161, "hello\nworld", "https://example.org", "user@example.org"):
            with self.subTest(query=query), self.assertRaises(ValueError):
                validate_query(query)
        with self.assertRaises(ValueError):
            validate_query("Where is the copper wren?", private_terms=("copper wren",))

    def test_bounded_result_and_public_links(self):
        result = search_public_web(" Prontera   guide ", CONFIG, client_factory=FakeSearch)
        self.assertEqual(result["kind"], "external_web_search")
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["results"][0]["title"], "First useful")
        self.assertEqual(len(result["results"][0]["snippet"]), 20)
        self.assertEqual(result["results"][1]["url"], "https://example.org/b")

    def test_provider_failure_is_explicit(self):
        class Broken:
            def __init__(self, timeout):
                pass

            def text(self, query, **kwargs):
                raise RuntimeError("provider failed")

        with self.assertRaises(SearchUnavailable):
            search_public_web("Prontera guide", CONFIG, client_factory=Broken)


if __name__ == "__main__":
    unittest.main()
