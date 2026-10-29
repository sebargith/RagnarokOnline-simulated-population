"""Live M1 acceptance against two local fixture clients. Mutates only test gameplay.

An explicit --seconds 600 is the milestone run; shorter runs are smoke checks.
The map server is deliberately restarted after the uninterrupted trial.
"""
from __future__ import annotations
import argparse
from collections import Counter, deque
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.client import Bridge
import m1


class Trial:
    def __init__(self, seconds):
        self.seconds = seconds
        self.name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.dir = ROOT / "runtime/evidence" / self.name
        self.dir.mkdir(parents=True)
        self.trace = (self.dir / "observations.ndjson").open("w", encoding="utf-8")
        self.events = deque(maxlen=256)
        self.counts = Counter()
        self.chat_counts = Counter()
        self.clients = {}
        self.checks = []
        self.guard = False
        self.last_snapshot = {}
        self.max_gap = 0
        self.raw_bytes = 0
        self.summary = {"run": self.name, "requested_trial_seconds": seconds,
            "milestone_duration": seconds >= 600, "checks": self.checks}

    def record(self, e):
        line = json.dumps(e, ensure_ascii=True) + "\n"
        self.raw_bytes += len(line)
        if self.raw_bytes > 8 * 1024**2:
            raise BufferError("8 MiB acceptance trace budget exceeded")
        self.trace.write(line)
        self.events.append(e)
        self.counts[e["agent_id"] + ":" + e["kind"]] += 1
        if e["kind"] == "chat":
            self.chat_counts[(e["agent_id"], e["data"].get("speaker"), e["data"].get("text"))] += 1
        if e["kind"] == "snapshot" and self.guard:
            assert e["data"]["connected"], "Disconnected during continuous trial"
            previous = self.last_snapshot.get(e["agent_id"], e["time_ms"])
            self.max_gap = max(self.max_gap, (e["time_ms"] - previous) / 1000)
            assert self.max_gap <= 5, "Snapshot gap exceeded fixed five-second target"
            self.last_snapshot[e["agent_id"]] = e["time_ms"]

    def connect(self, who):
        self.clients[who] = Bridge(ROOT / "runtime/openkore" / who / "bridge.json", self.record)
        self.wait(lambda: self.clients[who].latest is not None, 10)

    def pump(self, seconds=.05):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            for b in self.clients.values():
                b.poll(0)
                b.drain()
            if self.guard:
                for who, when in self.last_snapshot.items():
                    assert time.time() - when / 1000 <= 5, f"Missing heartbeat from {who}"
            time.sleep(.01)

    def wait(self, pred, timeout=10):
        end = time.monotonic() + timeout
        while not pred():
            if time.monotonic() >= end:
                raise TimeoutError("Acceptance condition timed out")
            self.pump()

    def check(self, name, details):
        self.checks.append({"check": name, "result": "pass", "details": details})
        print(f"PASS {name}: {details}", flush=True)

    def terminal(self, who, request_id, *, replay=False):
        def found():
            return next((e["data"] for e in reversed(self.events)
                if e["agent_id"] == who and e["kind"] == "action_result" and
                e["data"]["request_id"] == request_id and e["data"]["status"] != "accepted" and
                (not replay or e["data"].get("replay"))), None)
        self.wait(found)
        return found()

    def action(self, who, action, expected="completed", **kwargs):
        r = self.clients[who].proposal(action, **kwargs)
        result = self.terminal(who, r["id"])
        assert result["status"] == expected, result
        return r, result

    def chat(self, who, other, text):
        self.pump(1.1)
        r, result = self.action(who, {"type": "chat", "text": text})
        speaker = self.clients[who].latest["data"]["name"]
        self.wait(lambda: self.chat_counts[(other, speaker, text)] == 1)
        assert result["reason"] == "server_chat_echo", result
        return r, speaker

    def move(self, target):
        self.pump(1.1)
        _, result = self.action("agent", {"type": "move", "map": "prontera", **target})
        assert result["reason"] == "server_movement_ack", result
        self.wait(lambda: any(p["name"] == "M1 Agent" and p["x"] == target["x"] and
            p["y"] == target["y"] for p in self.clients["peer"].latest["data"].get("players", [])))

    def protocol_probe(self, frame):
        # Release the peer's observer connection, probe it, then explicitly resync.
        self.clients.pop("peer").close()
        self.pump(.2)
        with socket.create_connection(("127.0.0.1", 8766), timeout=3) as s:
            s.settimeout(5)
            s.sendall(frame)
            try:
                assert s.recv(1024) == b"", "Invalid auth/frame received observations"
            except ConnectionResetError:
                pass
        self.pump(.2)
        self.connect("peer")

    def run(self):
        self.connect("agent")
        self.connect("peer")
        self.wait(lambda: all(b.latest["data"]["connected"] for b in self.clients.values()), 90)
        self.wait(lambda: all(b.latest["data"].get("inventory_ready") and
            b.latest["data"].get("inventory") and b.latest["data"].get("players")
            for b in self.clients.values()), 20)
        for b in self.clients.values():
            s = b.latest["data"]
            assert s["map"] == "prontera" and s["hp"] > 0
            assert s["field"] == {"width": 312, "height": 392}
            assert any(i["name_id"] == 501 and i["amount"] == 3 for i in s["inventory"])
            assert len(s["players"]) == 1
        self.check("login_and_observation", "Both scoped clients decode position, HP, inventory and nearby player")
        origin = self.clients["agent"].latest["data"]["destination"].copy()
        target = {"x": origin["x"] + 1, "y": origin["y"]}
        self.move(target)
        self.move(origin)
        self.check("movement", {"origin": origin, "destination": target, "evidence": "0087 server ack and independent peer perception"})
        text = "M1 bridge proof " + self.name
        r, speaker = self.chat("agent", "peer", text)
        self.clients["agent"].send(r)
        replay = self.terminal("agent", r["id"], replay=True)
        assert replay["status"] == "completed"
        self.pump(1.1)
        assert self.chat_counts[("peer", speaker, text)] == 1
        self.chat("peer", "agent", "M1 reply " + self.name)
        self.check("bidirectional_chat_and_duplicate", "Server echoes, peer deliveries, cached duplicate result; one delivery")

        invalids = [({"type": "console", "text": "quit"}, {}, "action_not_allowed"),
            ({"type": "chat", "text": "@warp prontera"}, {}, "invalid_chat"),
            ({"type": "chat", "text": "line1\nline2"}, {}, "invalid_chat"),
            ({"type": "move", "map": "prontera", "x": 999, "y": 999}, {}, "invalid_move"),
            ({"type": "move", "map": "payon", **target}, {}, "invalid_move"),
            ({"type": "chat", "text": "stale"}, {"session": "stale"}, "stale_session"),
            ({"type": "chat", "text": "expired"}, {"deadline_ms": int(time.time()*1000)-10000}, "invalid_deadline")]
        for action, kwargs, reason in invalids:
            _, result = self.action("agent", action, "rejected", **kwargs)
            assert result["reason"] == reason, result
        self.check("invalid_actions", [x[2] for x in invalids])
        self.protocol_probe(b'{"type":"auth","token":"wrong"}\n')
        self.protocol_probe(b'x' * 4097)
        self.protocol_probe(b'{not-json}\n')
        self.check("protocol_limits", "Wrong token, oversized frame and malformed JSON closed; subsequent resync works")

        self.guard = True
        self.last_snapshot = {who: b.latest["time_ms"] for who, b in self.clients.items()}
        sessions = {who: b.session for who, b in self.clients.items()}
        started = time.monotonic()
        next_move, report_at = started, started
        excursions = 0
        while time.monotonic() - started < self.seconds:
            now = time.monotonic()
            if now >= next_move:
                self.move(target)
                self.move(origin)
                excursions += 1
                next_move = now + 60
            if now >= report_at:
                print(f"Trial {int(now-started)}/{self.seconds}s connected; {excursions} routine cycles", flush=True)
                report_at = now + 60
            self.pump(.1)
            assert all(b.session == sessions[who] for who, b in self.clients.items())
        elapsed = time.monotonic() - started
        self.guard = False
        self.summary.update(continuous_seconds=round(elapsed, 3), max_snapshot_gap_seconds=self.max_gap,
            routine_cycles=excursions, initial_sessions=sessions)
        self.check("continuous_connection", {"seconds": round(elapsed, 3), "routine_cycles": excursions,
            "max_snapshot_gap_seconds": self.max_gap, "target_gap_seconds": 5})

        # Real game-server outage, outside the restricted agent action interface.
        outage = subprocess.Popen([sys.executable, str(ROOT / "scripts/m1.py"), "restart-map"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=m1.FLAGS)
        down_started = time.monotonic()
        self.wait(lambda: not self.clients["agent"].latest["data"]["connected"], 20)
        raw = {"v": 1, "id": "while_disconnected_" + self.name, "session": sessions["agent"],
            "deadline_ms": int(time.time()*1000)+4000, "action": {"type": "chat", "text": "must not send"}}
        self.clients["agent"].send(raw)
        result = self.terminal("agent", raw["id"])
        assert result["status"] == "rejected" and result["reason"] == "disconnected", result
        self.wait(lambda: all(b.latest["data"]["connected"] and b.session != sessions[who]
            for who, b in self.clients.items()), 100)
        output = outage.communicate(timeout=10)[0].decode(errors="replace")
        assert outage.returncode == 0, output
        self.pump(1.1)
        _, stale = self.action("agent", {"type": "chat", "text": "old game epoch"}, "rejected", session=sessions["agent"])
        assert stale["reason"] == "stale_session"
        self.chat("agent", "peer", "M1 after reconnect " + self.name)
        self.check("forced_disconnect_reconnect", {"seconds": round(time.monotonic()-down_started, 3),
            "outcomes": [result["reason"], stale["reason"], "new session", "chat delivered once"]})
        assert not any(text == "must not send" for _, _, text in self.chat_counts)
        self.summary["counts"] = dict(self.counts)
        self.summary["passed"] = True

    def close(self):
        for b in self.clients.values():
            b.close()
        self.trace.close()
        (self.dir / "summary.json").write_text(json.dumps(self.summary, indent=2))
        print(f"Evidence: {self.dir}", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seconds", type=int, default=600)
    a = p.parse_args()
    if not 5 <= a.seconds <= 600:
        p.error("seconds must be between 5 and 600")
    trial = Trial(a.seconds)
    try:
        trial.run()
    except BaseException as exc:
        trial.summary.update(passed=False, error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        trial.close()


if __name__ == "__main__":
    main()
