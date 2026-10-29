"""Live regression for buffered frames and the 128-ID cache. Use a fresh test peer.

This deliberately exhausts the peer's action-ID budget. Restart that client after.
"""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.client import Bridge


def main():
    b = Bridge(ROOT / "runtime/openkore/peer/bridge.json")
    results = {}

    def collect(until, timeout=5):
        end = time.monotonic() + timeout
        while not until():
            if time.monotonic() > end:
                raise TimeoutError(f"Only {len(results)} buffered results received")
            b.poll(.05)
            for e in b.drain():
                if e["kind"] == "action_result":
                    results[e["data"]["request_id"]] = e["data"]

    def request(i, action=None):
        return {"v": 1, "id": f"batch_{i}", "session": b.session,
            "deadline_ms": int(time.time()*1000)+4000,
            "action": action or {"type": "console", "text": "must not run"}}

    try:
        collect(lambda: b.latest is not None and b.latest["data"]["connected"])
        # One OS send, five complete frames, and no more bytes while waiting:
        # this catches a parser that only drains buffered frames on new input.
        frame = b"".join(json.dumps(request(i)).encode()+b"\n" for i in range(5))
        b.socket.settimeout(2)
        b.socket.sendall(frame)
        b.socket.setblocking(False)
        collect(lambda: len(results) == 5)
        assert all(r["reason"] == "action_not_allowed" for r in results.values()), results
        print("PASS five coalesced frames drained without additional writes", flush=True)
        for start in range(5, 128, 5):
            stop = min(start + 5, 128)
            frame = b"".join(json.dumps(request(i)).encode()+b"\n" for i in range(start, stop))
            b.socket.settimeout(2)
            b.socket.sendall(frame)
            b.socket.setblocking(False)
            collect(lambda: len(results) == stop)
        assert all(r["reason"] == "action_not_allowed" for r in results.values())
        b.send(request(128, {"type": "chat", "text": "CACHE LIMIT MUST NOT SEND"}))
        collect(lambda: "batch_128" in results)
        assert results["batch_128"]["reason"] == "session_action_limit"
        b.send(request(0, {"type": "chat", "text": "DUPLICATE ID MUST NOT SEND"}))
        collect(lambda: results["batch_0"].get("replay"))
        assert results["batch_0"]["reason"] == "action_not_allowed"
        print("PASS 128 IDs retained; overflow refused; oldest ID replays without execution", flush=True)
        path = ROOT / "runtime/evidence/framing-cache-regression.json"
        path.write_text(json.dumps({"passed": True, "coalesced_frames": 5,
            "retained_ids": 128, "overflow": results["batch_128"], "oldest_replay": results["batch_0"]}, indent=2))
    finally:
        b.close()


if __name__ == "__main__":
    main()
