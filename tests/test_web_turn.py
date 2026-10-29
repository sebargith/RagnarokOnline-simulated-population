import unittest

from inference.web_turn import run_web_turn


OPERATING = {"model": "9b"}
WEB = {"max_searches_per_turn": 1}


class WebTurnTests(unittest.TestCase):
    def test_one_validated_tool_call_then_answer(self):
        calls = []

        def chat(config, messages, *, tools=None, cold=False):
            calls.append((messages, tools, cold))
            if len(calls) == 1:
                return {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {
                    "name": "web_search", "arguments": {"query": "Prontera wiki"}}}]}
            self.assertIsNone(tools)
            self.assertEqual(messages[-1]["role"], "tool")
            self.assertIn("external_web_search", messages[-1]["content"])
            return {"role": "assistant", "content": "Prontera is a city. [Source](https://example.org)"}

        def search(query, config, *, private_terms=()):
            self.assertEqual(query, "Prontera wiki")
            return {"kind": "external_web_search", "results": [{"url": "https://example.org"}]}

        result = run_web_turn("Search for Prontera", OPERATING, WEB, chat=chat, search=search)
        self.assertEqual(len(calls), 2)
        self.assertIsNotNone(result["search"])

    def test_no_tool_call_returns_direct_answer(self):
        def chat(config, messages, *, tools=None, cold=False):
            return {"content": "Hello."}

        self.assertEqual(run_web_turn("Hello", OPERATING, WEB, chat=chat)["answer"], "Hello.")

    def test_rejects_unknown_or_multiple_tools(self):
        for tool_calls in (
            [{"function": {"name": "run_command", "arguments": {"query": "x"}}}],
            [{"function": {"name": "web_search", "arguments": {"query": "x"}}}] * 2,
        ):
            with self.subTest(tool_calls=tool_calls), self.assertRaises(ValueError):
                run_web_turn("Search", OPERATING, WEB,
                             chat=lambda *args, **kwargs: {"tool_calls": tool_calls})


if __name__ == "__main__":
    unittest.main()
