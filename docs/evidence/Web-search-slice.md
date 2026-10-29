# Local 9B web-search slice

Date: 2026-10-29 (America/Santiago). This is a standalone inference/tool check, not a persistent game-agent trial.

- User chose `hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q6_K` and stopped further model comparison. The previously recorded grounding failures remain open for M3 dialogue review.
- The existing Docker container `local-web-search-searxng-1` (observed image ID `sha256:268a4b460136dcefc8f2e896b6098ba3f770c8218dbbddcb86811b06b06816f1`) served JSON at `http://127.0.0.1:8080/search`; `/config` returned HTTP 200 and a public query returned JSON results. Its configuration mount is `D:\Local_AI\Services\WebSearch\searxng`, outside this repository. No new SearXNG instance was installed or changed.
- `python -m unittest tests.test_web_search tests.test_web_turn -v`: seven tests passed after the SearXNG switch. `python -m unittest discover -s tests -v`: 26 tests passed on the final source. Python compile checks passed.
- `python scripts/ask_9b.py 'Search the web for the iRO Wiki Prontera page and tell me its URL.'` completed a live Ollama tool-call turn through SearXNG. It returned `https://irowiki.org/wiki/Prontera` and printed three external result URLs. Total command wall time was 18.956 seconds; this is one cold/warm mixed example, not a latency benchmark.

The Python boundary accepts one `web_search` call per turn, limits query length, rejects URL/email and caller-supplied private terms, uses only a loopback SearXNG endpoint, caps response bytes and result snippets, and does not fetch result pages. Web results are labeled external and never sent to the game bridge. A generated query can still reveal sensitive paraphrases that simple term checks miss; M3 must keep private memories and game observations out of the search-planning context and test query privacy. SearXNG is local software, but its configured engines require internet access for web search.
