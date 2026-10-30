"""Run the deterministic M3 movement slice, without inference or search."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.memory import Memory
from agent.routine import Routine
from bridge.client import Bridge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=60)
    args = parser.parse_args()
    if not 0 < args.seconds <= 1800:
        parser.error('seconds must be in (0,1800]')
    config = args.runtime/'openkore/agent/bridge.json'
    identity = json.loads(config.read_text())['agent_id']
    memory = Memory(args.runtime/'m3.sqlite', identity)
    bridge = Bridge(config)
    routine = Routine(memory, bridge)
    started = time.monotonic()
    events = 0
    try:
        while time.monotonic()-started < args.seconds:
            for event in bridge.poll(.1):
                routine.observe(event)
                events += 1
                if event['kind'] == 'action_result':
                    print(json.dumps(event['data']), flush=True)
            bridge.drain()
            routine.tick()
    finally:
        print(json.dumps({'seconds': time.monotonic()-started, 'events': events, 'reason': routine.reason, 'state': routine.state}), flush=True)
        bridge.close()
        memory.close()


if __name__ == '__main__':
    main()
