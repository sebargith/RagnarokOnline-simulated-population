"""M2 benchmark-only boundary. No bridge commands, persistence or autonomous agent."""
from __future__ import annotations

from collections import deque
from concurrent.futures import Future
import http.client
import json
import socket
import threading
import time
from urllib.request import Request, urlopen
from urllib.parse import urlsplit


def api(endpoint, route, body=None, timeout=30):
    request = Request(endpoint + route, data=None if body is None else json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def stream_chat(config, model, messages, seed, cold=False):
    """Absolute service deadline, bounded NDJSON/content, no network retries."""
    if sum(len(m["content"]) for m in messages) > config["max_prompt_chars"]:
        raise ValueError("prompt character budget exceeded")
    body = {"model": model, "messages": messages, "stream": True, "think": config["think"],
            "keep_alive": config["keep_alive"], "options": dict(config["options"], seed=seed)}
    started = time.monotonic()
    limit = config["cold_service_timeout_s" if cold else "service_timeout_s"]
    deadline = started + limit
    result = {"content": "", "ttft_s": None, "thinking_chars": 0}
    size = 0
    endpoint = urlsplit(config["endpoint"])
    if endpoint.scheme != "http" or endpoint.hostname not in ("127.0.0.1", "localhost"):
        raise ValueError("M2 requires local HTTP inference")
    connection = http.client.HTTPConnection(endpoint.hostname, endpoint.port, timeout=limit)
    connection.connect()
    sock = connection.sock
    def abort():
        # Shutdown interrupts even an indefinitely trickling line/header. Socket
        # read timeouts alone restart on each recv and do not enforce wall time.
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    watchdog = threading.Timer(max(.001, deadline-time.monotonic()), abort)
    watchdog.daemon = True
    watchdog.start()
    try:
        connection.request("POST", "/api/chat", body=json.dumps(body).encode(),
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("absolute inference deadline exceeded")
            line = response.readline(config["max_response_bytes"] + 1)
            size += len(line)
            if size > config["max_response_bytes"]:
                raise ValueError("response byte budget exceeded")
            if not line:
                raise ConnectionError("stream ended without done")
            chunk = json.loads(line)
            if "error" in chunk:
                raise RuntimeError(chunk["error"])
            message = chunk.get("message", {})
            content = message.get("content", "")
            if content and result["ttft_s"] is None:
                result["ttft_s"] = time.monotonic() - started
            result["content"] += content
            result["thinking_chars"] += len(message.get("thinking", ""))
            if len(result["content"]) > config["max_content_chars"]:
                raise ValueError("content character budget exceeded")
            if chunk.get("done"):
                result.update({k: chunk.get(k) for k in (
                    "done_reason", "prompt_eval_count", "eval_count", "total_duration",
                    "load_duration", "prompt_eval_duration", "eval_duration")})
                result["service_s"] = time.monotonic() - started
                if result["service_s"] > limit:
                    raise TimeoutError("inference exceeded service deadline")
                if not result["content"] or result["ttft_s"] is None:
                    raise ValueError("empty visible answer")
                return result
    finally:
        watchdog.cancel()
        connection.close()


class BoundedInference:
    """One active/reserved slot plus four FIFO waiting slots, one call per identity.

    Any transport/budget failure opens a circuit: no following request is dispatched
    against a possibly still-busy Ollama runner. There is no retry or game action.
    """
    def __init__(self, config, model, transport=stream_chat):
        if config["concurrency"] != 1 or config["retries"] != 0:
            raise ValueError("M2 supports one worker and zero retries")
        self.config, self.model, self.transport = config, model, transport
        self.condition = threading.Condition()
        self.queue = deque()
        self.identities = set()
        self.closed = False
        self.circuit = threading.Event()
        self.thread = threading.Thread(target=self._work, daemon=True)
        self.thread.start()

    def submit(self, identity, messages, seed, cold=False):
        future = Future()
        with self.condition:
            if self.closed or self.circuit.is_set():
                raise RuntimeError("inference closed/circuit open")
            if identity in self.identities:
                raise ValueError("identity already has an outstanding request")
            # Reserve the active slot immediately, including before worker wakeup.
            if len(self.identities) >= self.config["concurrency"] + self.config["max_waiting"]:
                raise BufferError("inference queue full")
            if sum(len(m["content"]) for m in messages) > self.config["max_prompt_chars"]:
                raise ValueError("prompt character budget exceeded")
            self.identities.add(identity)
            self.queue.append((identity, messages, seed, cold, time.monotonic(), future))
            self.condition.notify()
        return future

    def _work(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.queue or self.closed)
                if not self.queue:
                    return
                identity, messages, seed, cold, admitted, future = self.queue.popleft()
            queue_s = time.monotonic() - admitted
            try:
                ttl = self.config["cold_request_deadline_s" if cold else "request_deadline_s"]
                if self.circuit.is_set():
                    raise RuntimeError("circuit open; request not dispatched")
                if queue_s >= ttl:
                    raise TimeoutError("request expired in queue")
                remaining_config = dict(self.config)
                key = "cold_service_timeout_s" if cold else "service_timeout_s"
                remaining_config[key] = min(self.config[key], ttl - queue_s)
                result = self.transport(remaining_config, self.model, messages, seed, cold)
                result.update(queue_s=queue_s, response_s=time.monotonic() - admitted)
                if result["response_s"] > ttl:
                    raise TimeoutError("request deadline exceeded")
                # Release ownership before waking the session for its next turn.
                with self.condition:
                    self.identities.remove(identity)
                future.set_result(result)
            except Exception as error:
                self.circuit.set()
                with self.condition:
                    self.identities.remove(identity)
                future.set_result({"error": type(error).__name__ + ": " + str(error),
                                   "queue_s": queue_s, "response_s": time.monotonic() - admitted})

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()
        self.thread.join(self.config["cold_service_timeout_s"] + 2)
        if self.thread.is_alive():
            raise TimeoutError("worker failed to stop")


def validate_action(content, state, epoch):
    """Fixture validator only; simulated current state is rechecked, never executed."""
    action = json.loads(content)
    if action == {"type": "none"}:
        return action
    if not isinstance(action, dict) or set(action) != {"type", "x", "y"} or action["type"] != "move":
        raise ValueError("action schema not permitted")
    if type(action["x"]) is not int or type(action["y"]) is not int:
        raise ValueError("coordinates must be integers")
    if not state["connected"] or state["age_ms"] > 2500 or state["epoch"] != epoch:
        raise ValueError("fresh connected epoch required")
    cell = [action["x"], action["y"]]
    if cell not in state["allowed"] or abs(cell[0]-state["x"]) + abs(cell[1]-state["y"]) != 1:
        raise ValueError("cell not permitted/adjacent")
    return action


def score(case, identity, content):
    if case["kind"] == "action":
        try:
            action = validate_action(content, case["state"], case["state"]["epoch"])
            return {"pass": action == case["expected"], "validated_proposal": action,
                    "executed": False}
        except (ValueError, TypeError, KeyError) as error:
            return {"pass": False, "rejection": str(error), "executed": False}
    if case["kind"] == "recall":
        try:
            value = json.loads(content)
            expected = {"friend": identity["friend"], "meeting": "west gate after resting",
                        "potion_source": identity["friend"], "east_field": "unverified",
                        "walk_result": "unknown", "friend_inventory": "unknown"}
            checks = {key: isinstance(value, dict) and value.get(key) == val for key, val in expected.items()}
            checks["keys"] = isinstance(value, dict) and set(value) == set(expected)
            return {"pass": all(checks.values()), "checks": checks}
        except ValueError:
            return {"pass": False, "rejection": "invalid JSON"}
    return {"pass": None, "human_review": "pending"}
