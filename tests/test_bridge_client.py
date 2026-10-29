import json
import socket
import time
import unittest
from collections import deque

from bridge.client import Bridge


class ClientBoundaryTests(unittest.TestCase):
    def setUp(self):
        # A real local stream exercises framing without a game server or secrets.
        self.peer, client = socket.socketpair()
        client.setblocking(False)
        self.bridge = Bridge.__new__(Bridge)
        self.bridge.socket = client
        self.bridge.config = {"agent_id": "agent"}
        self.bridge.buffer = b""
        self.bridge.events = deque(maxlen=2)
        self.bridge.session = "boot:1"
        self.bridge.latest = {"time_ms": int(time.time() * 1000), "data": {"connected": True}}
        self.bridge.sink = None

    def tearDown(self):
        self.bridge.close()
        self.peer.close()

    def test_disconnected_proposal_never_writes(self):
        self.bridge.latest["data"]["connected"] = False
        with self.assertRaisesRegex(RuntimeError, "disconnected"):
            self.bridge.proposal({"type": "chat", "text": "test"})
        self.peer.settimeout(.01)
        with self.assertRaises(TimeoutError):
            self.peer.recv(100)

    def test_stale_snapshot_never_writes(self):
        self.bridge.latest["time_ms"] -= 3000
        with self.assertRaisesRegex(RuntimeError, "Fresh snapshot"):
            self.bridge.proposal({"type": "chat", "text": "test"})

    def test_one_proposal_writes_exactly_one_frame(self):
        request = self.bridge.proposal({"type": "chat", "text": "test"})
        self.peer.settimeout(.05)
        frame = self.peer.recv(4096)
        self.assertEqual(json.loads(frame), request)
        with self.assertRaises(TimeoutError):
            self.peer.recv(4096)

    def test_explicit_invalid_overrides_are_not_silently_replaced(self):
        request = self.bridge.proposal({"type": "chat", "text": "test"},
            request_id="", session="", deadline_ms=0)
        self.assertEqual(request["id"], "")
        self.assertEqual(request["session"], "")
        self.assertEqual(request["deadline_ms"], 0)

    def event(self, **overrides):
        event = {"agent_id": "agent", "v": 1, "kind": "connection", "session": "boot:1", "data": {}}
        event.update(overrides)
        return json.dumps(event).encode() + b"\n"

    def test_fragmented_stream_and_coalesced_frames(self):
        frame = self.event()
        self.peer.sendall(frame[:10])
        self.assertEqual(self.bridge.poll(.1), [])
        self.peer.sendall(frame[10:] + frame)
        self.assertEqual(len(self.bridge.poll(.1)), 2)
        self.assertEqual(len(self.bridge.drain()), 2)

    def test_cross_agent_observation_is_rejected(self):
        self.peer.sendall(self.event(agent_id="peer"))
        with self.assertRaisesRegex(ValueError, "identity"):
            self.bridge.poll(.1)
        self.assertEqual(list(self.bridge.events), [])

    def test_queue_overflow_is_explicit(self):
        self.peer.sendall(self.event() * 3)
        with self.assertRaises(BufferError):
            self.bridge.poll(.1)
        self.assertEqual(len(self.bridge.events), 2)


if __name__ == "__main__":
    unittest.main()
