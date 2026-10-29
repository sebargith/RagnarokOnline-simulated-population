"""Read only: show one agent's normalized observations for a bounded interval."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.client import Bridge

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("agent", choices=("agent", "peer"), default="agent", nargs="?")
p.add_argument("--seconds", type=float, default=5)
a = p.parse_args()
if not 0 < a.seconds <= 60:
    p.error("seconds must be in (0,60]")
b = Bridge(ROOT / "runtime/openkore" / a.agent / "bridge.json")
try:
    end = time.monotonic() + a.seconds
    while time.monotonic() < end:
        for e in b.poll(.25):
            print(json.dumps(e), flush=True)
        b.drain()
finally:
    b.close()
