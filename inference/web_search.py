"""Bounded public web search. Results are external claims, never game observations."""
from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import re
from urllib.parse import urlsplit


class SearchUnavailable(RuntimeError):
    """The search provider failed or returned no usable results."""


def validate_query(query: str, *, private_terms=()) -> str:
    if not isinstance(query, str):
        raise ValueError("search query must be text")
    if any(ord(char) < 32 and char != " " for char in query):
        raise ValueError("search query contains control characters")
    clean = " ".join(query.split())
    if not 3 <= len(clean) <= 160:
        raise ValueError("search query must be 3-160 characters")
    if re.search(r"https?://|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", clean, re.I):
        raise ValueError("search query contains a URL or email address")
    folded = clean.casefold()
    if any(term and term.casefold() in folded for term in private_terms):
        raise ValueError("search query contains private context")
    return clean


def _public_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 500:
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        return None
    host = parsed.hostname.casefold()
    if host == "localhost" or host.endswith(".local"):
        return None
    try:
        if not ipaddress.ip_address(host).is_global:
            return None
    except ValueError:
        pass
    return value


def _short(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def search_public_web(query: str, config: dict, *, private_terms=(), client_factory=None) -> dict:
    """Return at most a few snippets from a fixed public search backend.

    The caller owns consent and identity scoping. No page is fetched by URL.
    """
    clean = validate_query(query, private_terms=private_terms)
    if client_factory is None:
        from ddgs import DDGS
        client_factory = DDGS
    try:
        raw = client_factory(timeout=config["timeout_s"]).text(
            clean,
            region="us-en",
            safesearch="moderate",
            max_results=config["max_results"],
            backend="duckduckgo",
        )
    except Exception as exc:
        raise SearchUnavailable("public search unavailable") from exc
    results = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        url = _public_url(item.get("href"))
        if not url or url in seen:
            continue
        seen.add(url)
        results.append({
            "title": _short(item.get("title"), config["max_title_chars"]),
            "url": url,
            "snippet": _short(item.get("body"), config["max_snippet_chars"]),
        })
        if len(results) == config["max_results"]:
            break
    if not results:
        raise SearchUnavailable("public search returned no usable results")
    return {
        "kind": "external_web_search",
        "query": clean,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
