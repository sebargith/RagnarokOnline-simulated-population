"""Bounded OpenAI-compatible chat transport (Gemini, Groq, OpenRouter).

Same signature and budgets as inference.m2.stream_chat, so BoundedInference can
own queueing and the circuit. The API key is read only from the environment
variable named by the config; it is never returned, logged or put in an error.
No retries; a refused, slow, oversized or truncated reply raises.
"""
from __future__ import annotations

import http.client
import json
import os
import socket
import threading
import time
from urllib.parse import urlsplit


class KeyUnavailable(RuntimeError):
    """The configured API key variable is missing or empty."""


class QuotaExceeded(RuntimeError):
    """Provider answered 429 (rate limit or exhausted free quota)."""


class AuthRejected(RuntimeError):
    """Provider rejected the key (401/403)."""


def api_key(config, environ=None):
    name = config.get('api_key_env')
    if not isinstance(name, str) or not name:
        raise ValueError('api_key_env must name an environment variable')
    value = (os.environ if environ is None else environ).get(name, '')
    if not value.strip():
        raise KeyUnavailable(name + ' is not set')
    return value.strip()


def https_send(url, headers, body, timeout, max_bytes):
    """POST once with an absolute wall deadline; return (status, raw<=max_bytes+1)."""
    parts = urlsplit(url)
    loopback = parts.hostname in ('127.0.0.1', 'localhost')
    if parts.scheme == 'https':
        connection = http.client.HTTPSConnection(parts.hostname, parts.port, timeout=timeout)
    elif parts.scheme == 'http' and loopback:
        connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=timeout)
    else:
        raise ValueError('remote inference requires HTTPS')
    connection.connect()
    sock = connection.sock

    def abort():
        # Same reason as stream_chat: per-recv timeouts do not bound wall time.
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    watchdog = threading.Timer(max(.001, timeout), abort)
    watchdog.daemon = True
    watchdog.start()
    try:
        connection.request('POST', parts.path, body=body, headers=headers)
        response = connection.getresponse()
        return response.status, response.read(max_bytes + 1)
    finally:
        watchdog.cancel()
        connection.close()


def _response_format(config, schema):
    mode = config.get('json_mode', 'json_schema')
    if schema is None or mode == 'none':
        return None
    if mode == 'json_object':
        return {'type': 'json_object'}
    if mode == 'json_schema':
        return {'type': 'json_schema', 'json_schema': {'name': 'reply', 'schema': schema, 'strict': True}}
    raise ValueError('unsupported json_mode')


def openai_chat(config, model, messages, seed, cold=False, response_format=None, *,
                send=https_send, environ=None):
    if sum(len(m['content']) for m in messages) > config['max_prompt_chars']:
        raise ValueError('prompt character budget exceeded')
    key = api_key(config, environ)
    limit = config['cold_service_timeout_s' if cold else 'service_timeout_s']
    body = dict(config.get('options', {}), model=model, stream=False,
                messages=[{'role': m['role'], 'content': m['content']} for m in messages])
    if config.get('send_seed'):
        body['seed'] = seed
    fmt = _response_format(config, response_format)
    if fmt is not None:
        body['response_format'] = fmt
    started = time.monotonic()
    try:
        status, raw = send(config['endpoint'].rstrip('/') + '/chat/completions',
                           {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key},
                           json.dumps(body).encode(), limit, config['max_response_bytes'])
    except Exception as error:
        # Never let a lower layer echo request headers back to the caller.
        kind = TimeoutError if isinstance(error, TimeoutError) else ConnectionError
        raise kind(type(error).__name__ + ': ' + str(error).replace(key, '[redacted]')) from None
    service_s = time.monotonic() - started
    # Provider bodies are not copied into errors: they may echo request data.
    if status == 429:
        raise QuotaExceeded('HTTP 429 rate limit or quota exhausted')
    if status in (401, 403):
        raise AuthRejected(f'HTTP {status} key rejected')
    if status != 200:
        raise RuntimeError(f'HTTP {status}')
    if len(raw) > config['max_response_bytes']:
        raise ValueError('response byte budget exceeded')
    if service_s > limit:
        raise TimeoutError('inference exceeded service deadline')
    payload = json.loads(raw)
    choices = payload.get('choices') if isinstance(payload, dict) else None
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ValueError('expected exactly one choice')
    choice = choices[0]
    message = choice.get('message') or {}
    content = message.get('content')
    if choice.get('finish_reason') == 'length':
        raise ValueError('truncated response')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('empty visible answer')
    if len(content) > config['max_content_chars']:
        raise ValueError('content character budget exceeded')
    usage = payload.get('usage') or {}
    reasoning = message.get('reasoning') or message.get('reasoning_content') or ''
    return {'content': content, 'ttft_s': service_s, 'service_s': service_s,
            'thinking_chars': len(reasoning) if isinstance(reasoning, str) else 0,
            'done_reason': choice.get('finish_reason'),
            'prompt_eval_count': usage.get('prompt_tokens'), 'eval_count': usage.get('completion_tokens'),
            'reasoning_tokens': (usage.get('completion_tokens_details') or {}).get('reasoning_tokens'),
            'served_model': payload.get('model')}
