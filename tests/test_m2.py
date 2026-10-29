import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
import unittest

from inference.m2 import BoundedInference, stream_chat, validate_action

ROOT = Path(__file__).resolve().parents[1]


class M2BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config/m2-candidates.json").read_text())
        self.state = {"connected": True, "epoch": 7, "age_ms": 100,
                      "x": 150, "y": 180, "allowed": [[151, 180]]}

    def test_proposals_recheck_state_and_deny_extra_fields(self):
        move = json.dumps({"type": "move", "x": 151, "y": 180})
        self.assertEqual(validate_action(move, self.state, 7)["x"], 151)
        for state, epoch in ((dict(self.state, connected=False), 7),
                             (dict(self.state, age_ms=2501), 7), (self.state, 8),
                             (dict(self.state, allowed=[]), 7)):
            with self.assertRaises(ValueError):
                validate_action(move, state, epoch)
        for action in ({"type": "teleport", "x": 151, "y": 180},
                       {"type": "move", "x": 151, "y": 180, "command": "admin"},
                       {"type": "move", "x": True, "y": 180}, {"type": "say", "text": "done"}):
            with self.assertRaises(ValueError):
                validate_action(json.dumps(action), self.state, 7)

    def test_fifo_capacity_identity_isolation_and_ownership_release(self):
        release, started = threading.Event(), threading.Event()
        seen = []
        def transport(config, model, messages, seed, cold):
            seen.append(messages[0]["content"])
            started.set()
            release.wait(2)
            return {"content": "ok", "service_s": .01}
        scheduler = BoundedInference(self.config, "fake", transport)
        try:
            futures = [scheduler.submit("0", [{"content": "private-0"}], 42)]
            self.assertTrue(started.wait(1))
            for i in range(1, 5):
                futures.append(scheduler.submit(str(i), [{"content": f"private-{i}"}], 42))
            with self.assertRaises(BufferError):
                scheduler.submit("overflow", [], 42)
            with self.assertRaises(ValueError):
                scheduler.submit("0", [], 42)
            release.set()
            for future in futures:
                self.assertNotIn("error", future.result(2))
            self.assertEqual(seen, [f"private-{i}" for i in range(5)])
            self.assertNotIn("error", scheduler.submit("0", [{"content": "private-0-again"}], 42).result(1))
        finally:
            release.set()
            scheduler.close()

    def test_failure_opens_circuit_without_retries(self):
        calls = []
        def fail(*args):
            calls.append(1)
            raise TimeoutError("injected timeout")
        scheduler = BoundedInference(self.config, "fake", fail)
        try:
            result = scheduler.submit("0", [], 42).result(1)
            self.assertIn("TimeoutError", result["error"])
            with self.assertRaises(RuntimeError):
                scheduler.submit("1", [], 42)
            self.assertEqual(len(calls), 1)
        finally:
            scheduler.close()

    def test_expired_queue_request_is_not_dispatched(self):
        release, started = threading.Event(), threading.Event()
        calls = []
        def transport(*args):
            calls.append(1)
            started.set()
            release.wait(1)
            return {"content": "ok", "service_s": .01}
        config = dict(self.config, request_deadline_s=.02)
        scheduler = BoundedInference(config, "fake", transport)
        try:
            active = scheduler.submit("0", [], 42)
            self.assertTrue(started.wait(1))
            waiting = scheduler.submit("1", [], 42)
            time.sleep(.04)
            release.set()
            self.assertIn("error", active.result(1))
            self.assertIn("error", waiting.result(1))
            self.assertEqual(len(calls), 1)
        finally:
            release.set()
            scheduler.close()

    def test_prompt_bound_before_admission(self):
        scheduler = BoundedInference(self.config, "fake", lambda *args: self.fail("dispatched"))
        try:
            with self.assertRaises(ValueError):
                scheduler.submit("0", [{"content": "x"*5001}], 42)
        finally:
            scheduler.close()

    def serve_stream(self, payload, config_override=None, trickle=False):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(200)
                self.end_headers()
                try:
                    for byte in payload:
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        if trickle:
                            time.sleep(.01)
                except OSError:
                    pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        config = dict(self.config, endpoint=f"http://127.0.0.1:{server.server_port}", **(config_override or {}))
        try:
            return stream_chat(config, "fake", [{"role": "user", "content": "hello"}], 42)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(1)

    def test_stream_metrics_and_visible_first_token(self):
        payload = (json.dumps({"message": {"content": "Hi"}, "done": False}) + "\n" +
                   json.dumps({"message": {}, "done": True, "done_reason": "stop",
                               "prompt_eval_count": 12, "eval_count": 1}) + "\n").encode()
        result = self.serve_stream(payload)
        self.assertEqual(result["content"], "Hi")
        self.assertEqual(result["prompt_eval_count"], 12)
        self.assertLessEqual(result["ttft_s"], result["service_s"])

    def test_trickling_stream_cannot_extend_absolute_deadline(self):
        started = time.monotonic()
        with self.assertRaises((TimeoutError, ConnectionError, ValueError)):
            self.serve_stream(b'{"message":{"content":"never completes"}}\n'*20,
                              {"service_timeout_s": .06}, trickle=True)
        self.assertLess(time.monotonic()-started, 1)

    def test_response_overflow_and_empty_output_are_failures(self):
        with self.assertRaises(ValueError):
            self.serve_stream(b"x"*200, {"max_response_bytes": 100})
        with self.assertRaises(ValueError):
            self.serve_stream(b'{"message":{},"done":true}\n')


if __name__ == "__main__":
    unittest.main()
