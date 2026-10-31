"""Planner/chat model roles, each with its own bounded queue and explicit fallback.

A role service has the BoundedInference submit() interface, so GoalPlanner and
future callers use it unchanged. A failed request is never re-sent elsewhere:
it returns an error marked fallback=local_policy and the deterministic policy
keeps playing. Later requests go to the configured local fallback (reported as
degraded) until the cooldown lets the primary be tried again.
"""
from __future__ import annotations

from collections import deque
from concurrent.futures import Future
import functools
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

from inference.m2 import BoundedInference, stream_chat
from inference.openai_compat import KeyUnavailable, api_key, openai_chat

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT.parent/'runtime'  # shared runtime folder, outside Git


def _merge(base, override):
    out = dict(base)
    for key, value in override.items():
        out[key] = _merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def load_roles(path=None):
    doc = json.loads(Path(path or ROOT/'config/model-roles.json').read_text(encoding='utf-8'))
    for role, spec in doc['roles'].items():
        for name in (spec['primary'], spec.get('fallback')):
            if name is not None and name not in doc['candidates']:
                raise ValueError(f'{role}: unknown candidate {name}')
        if spec.get('local_only'):
            for name in (spec['primary'], spec.get('fallback')):
                if name is not None and doc['candidates'][name]['provider'] != 'ollama':
                    raise ValueError(f'{role} must stay on the local model')
    return doc


def candidate(doc, name, environ=None):
    """Return (config, model, transport) or raise KeyUnavailable. No network IO."""
    spec = doc['candidates'][name]
    if spec['provider'] == 'ollama':
        base = json.loads((ROOT/spec['base']).read_text(encoding='utf-8'))
        config = _merge(base, spec.get('override', {}))
        endpoint = urlsplit(config['endpoint'])
        if endpoint.hostname not in ('127.0.0.1', 'localhost'):
            raise ValueError('ollama candidate must be loopback')
        return config, config['model'], stream_chat
    if spec['provider'] == 'openai':
        config = _merge(doc['cloud_limits'], {k: v for k, v in spec.items() if k != 'provider'})
        if doc.get('key_file'):
            config['key_file'] = str(RUNTIME/doc['key_file'])
        api_key(config, environ)  # availability only; the value is not kept here
        return config, spec['model'], functools.partial(openai_chat, environ=environ)
    raise ValueError('unknown provider')


def _done(result):
    future = Future()
    future.set_result(result)
    return future


class RoleService:
    def __init__(self, role, primary, fallback=None, cooldown_s=300, clock=time.monotonic):
        """primary/fallback: (name, service) or (name, None, reason) when unavailable."""
        self.role, self.cooldown_s, self.clock = role, cooldown_s, clock
        self.primary_name, self.primary = primary[0], primary[1]
        self.unavailable = primary[2] if len(primary) > 2 else None
        self.fallback_name, self.fallback = (fallback or (None, None))[:2]
        self.failed_at = None
        self.lock = threading.Lock()
        self.events = deque(maxlen=32)

    def _note(self, kind, reason):
        self.events.append({'time': time.time(), 'role': self.role, 'kind': kind, 'reason': reason})

    def _primary_ready(self):
        if self.primary is None:
            return False, self.unavailable or 'primary unavailable'
        if self.primary.circuit.is_set():
            if self.failed_at is None:  # failure seen before its callback ran
                self.failed_at = self.clock()
            if self.clock() - self.failed_at < self.cooldown_s:
                return False, 'primary circuit open (cooling down)'
            if not self.primary.recover_idle_circuit():
                return False, 'primary circuit open (busy)'
            self._note('primary_retry_after_cooldown', self.primary_name)
        return True, None

    def _wrap(self, future, served_by, degraded, reason):
        out = Future()

        def finish(inner):
            result = dict(inner.result())
            result.update(role=self.role, served_by=served_by, degraded=degraded)
            if reason:
                result['degraded_reason'] = reason
            if 'error' in result:
                result['fallback'] = 'local_policy'
                if served_by == self.primary_name:
                    with self.lock:
                        self.failed_at = self.clock()
                self._note('request_failed', served_by + ': ' + result['error'])
            out.set_result(result)
        future.add_done_callback(finish)
        return out

    def submit(self, identity, messages, seed, cold=False, response_format=None):
        with self.lock:
            ready, reason = self._primary_ready()
        if ready:
            return self._wrap(self.primary.submit(identity, messages, seed, cold, response_format),
                              self.primary_name, False, None)
        if self.fallback is not None:
            self._note('degraded_to_fallback', reason)
            return self._wrap(self.fallback.submit(identity, messages, seed, cold, response_format),
                              self.fallback_name, True, reason)
        self._note('unavailable', reason)
        return _done({'error': 'RoleUnavailable: ' + reason, 'role': self.role,
                      'served_by': None, 'degraded': True, 'fallback': 'local_policy'})

    def status(self):
        with self.lock:
            ready = self.primary is not None and not self.primary.circuit.is_set()
        return {'role': self.role, 'primary': self.primary_name, 'primary_ready': ready,
                'unavailable': self.unavailable, 'fallback': self.fallback_name,
                'events': list(self.events)}

    def close(self):
        for service in {id(s): s for s in (self.primary, self.fallback) if s is not None}.values():
            service.close()


def build_role(role, doc=None, environ=None):
    doc = doc or load_roles()
    spec = doc['roles'][role]
    built = {}

    def make(name):
        if name is None:
            return None
        if name not in built:
            try:
                config, model, transport = candidate(doc, name, environ)
                built[name] = (name, BoundedInference(config, model, transport))
            except KeyUnavailable as error:
                built[name] = (name, None, str(error))
        return built[name]
    primary = make(spec['primary'])
    fallback = make(spec.get('fallback'))
    if fallback is not None and fallback[1] is None:
        fallback = None
    return RoleService(role, primary, fallback, spec.get('cloud_cooldown_s', 300))
