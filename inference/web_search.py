"""Bounded public web search. Results are external claims, never game observations."""
from __future__ import annotations

from datetime import datetime, timezone
import http.client
import ipaddress
import json
import re
import socket
import threading
from urllib.parse import urlencode, urlsplit


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
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
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


def _fetch_searx(config: dict, query: str) -> dict:
    endpoint = urlsplit(config["endpoint"])
    if (endpoint.scheme != "http" or endpoint.hostname not in ("127.0.0.1", "localhost")
            or endpoint.path not in ("", "/") or endpoint.query or endpoint.fragment):
        raise ValueError("web search requires a local SearXNG endpoint")
    timeout = config["timeout_s"]
    connection = http.client.HTTPConnection(endpoint.hostname, endpoint.port, timeout=timeout)
    connection.connect()
    sock = connection.sock

    def abort():
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    watchdog = threading.Timer(timeout, abort)
    watchdog.daemon = True
    watchdog.start()
    try:
        params = urlencode({"q": query, "format": "json", "categories": "general",
                            "language": "en", "safesearch": "1"})
        connection.request("GET", "/search?" + params,
                           headers={"Accept": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise SearchUnavailable(f"SearXNG returned HTTP {response.status}")
        raw = response.read(config["max_response_bytes"] + 1)
        if len(raw) > config["max_response_bytes"]:
            raise SearchUnavailable("SearXNG response exceeded byte budget")
        return json.loads(raw)
    finally:
        watchdog.cancel()
        connection.close()


def search_public_web(query: str, config: dict, *, private_terms=(), transport=None) -> dict:
    """Return bounded snippets from the local SearXNG instance.

    The caller owns consent and identity scoping. No page is fetched by URL.
    """
    clean = validate_query(query, private_terms=private_terms)
    transport = transport or _fetch_searx
    try:
        payload = transport(config, clean)
    except Exception as exc:
        raise SearchUnavailable("public search unavailable") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise SearchUnavailable("SearXNG returned invalid results")
    results = []
    seen = set()
    for item in payload["results"]:
        if not isinstance(item, dict):
            continue
        url = _public_url(item.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        results.append({
            "title": _short(item.get("title"), config["max_title_chars"]),
            "url": url,
            "snippet": _short(item.get("content"), config["max_snippet_chars"]),
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
