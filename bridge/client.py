"""Synchronous M1 bridge client. No command retries or game-truth inference."""
from __future__ import annotations
from collections import deque
import json
from pathlib import Path
import select
import socket
import time
import uuid


class Bridge:
    def __init__(self, config: Path, sink=None):
        self.config = json.loads(config.read_text())
        self.socket = socket.create_connection(("127.0.0.1", self.config["port"]), timeout=3)
        self.socket.setblocking(False)
        self.buffer = b""
        self.events = deque(maxlen=256)
        self.latest = None
        self.session = None
        self.next_serial = None
        self.sink = sink
        self.send({"type": "auth", "token": self.config["token"]})

    def close(self):
        self.socket.close()

    def send(self, value):
        frame = json.dumps(value, separators=(",", ":")).encode() + b"\n"
        if len(frame) > 4096:
            raise ValueError("Frame exceeds 4096 bytes")
        # sendall has a finite timeout; partial sends are never retried as new actions.
        self.socket.settimeout(2)
        try:
            self.socket.sendall(frame)
        finally:
            self.socket.setblocking(False)

    def poll(self, timeout=0):
        received = []
        if select.select([self.socket], [], [], timeout)[0]:
            chunk = self.socket.recv(8192)
            if not chunk:
                raise ConnectionError("Bridge closed; reconnect and resync, do not replay actions")
            self.buffer += chunk
            if len(self.buffer) > 65536:
                raise ValueError("Bridge buffer overflow")
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                event = json.loads(line)
                if event.get("agent_id") != self.config["agent_id"] or event.get("v") != 1:
                    raise ValueError("Observation identity/version mismatch")
                if len(self.events) == self.events.maxlen:
                    raise BufferError("Consumer must drain the event queue and resync")
                self.events.append(event)
                received.append(event)
                self.session = event["session"]
                if event["kind"] == "ready":
                    self.next_serial = event["data"].get("next_serial")
                if event["kind"] == "snapshot":
                    self.latest = event
                if self.sink:
                    self.sink(event)
        return received

    def drain(self):
        events = list(self.events)
        self.events.clear()
        return events

    def serial_id(self):
        if self.next_serial is None or self.next_serial >= 10**15:
            raise RuntimeError('Continuous request sequence unavailable; update/restart project clients')
        request = 'c_' + str(self.next_serial)
        self.next_serial += 1
        return request

    def proposal(self, action, *, request_id=None, session=None, deadline_ms=None):
        # Both this boundary and the plugin require a fresh observed game session.
        if self.latest is None or time.time() * 1000 - self.latest["time_ms"] > 2500:
            raise RuntimeError("Fresh snapshot required before an action")
        if not self.latest["data"]["connected"]:
            raise RuntimeError("Agent is disconnected")
        r = {"v": 1, "id": uuid.uuid4().hex if request_id is None else request_id,
            "session": self.session if session is None else session,
            "deadline_ms": int(time.time() * 1000) + 4000 if deadline_ms is None else deadline_ms,
            "action": action}
        self.send(r)
        return r
