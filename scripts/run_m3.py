"""Run one persistent M3 agent with optional bounded dialogue/public search."""
import argparse
import json
import msvcrt
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agent.memory import Memory
from agent.routine import Routine
from bridge.client import Bridge
from agent.dialogue import Dialogue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--dialogue', action='store_true')
    parser.add_argument('--state', type=Path)
    parser.add_argument('--fault', choices=('inference', 'search'))
    args = parser.parse_args()
    if not 0 < args.seconds <= 1800:
        parser.error('seconds must be in (0,1800]')
    config = args.runtime/'openkore/agent/bridge.json'
    # OS releases the lock after a crash; two orchestrators cannot own this DB.
    lease = (args.runtime/'m3.lock').open('a+b')
    lease.seek(0)
    if lease.read(1) == b'':
        lease.write(b'0')
        lease.flush()
    lease.seek(0)
    msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
    identity = json.loads(config.read_text())['agent_id']
    memory = Memory(args.state or args.runtime/'m3.sqlite', identity)
    bridge = Bridge(config)
    routine = Routine(memory, bridge)
    operating = json.loads((ROOT/'config/m2-operating.json').read_text())
    web = json.loads((ROOT/'config/web-search.json').read_text())
    if args.fault == 'inference':
        operating['endpoint'] = 'http://127.0.0.1:9'
    if args.fault == 'search':
        web['endpoint'] = 'http://127.0.0.1:9'
    dialogue = Dialogue(memory, operating, web) if args.dialogue else None
    last_observation = 0
    reconnects = 0
    started = time.monotonic()
    events = 0
    last_snapshot = None
    max_gap = 0
    disconnected = 0
    outbox = None
    try:
        while time.monotonic()-started < args.seconds:
            try:
                incoming = bridge.poll(.1)
            except (OSError, BufferError):
                bridge.close()
                if reconnects >= 3:
                    raise RuntimeError('Bridge reconnect budget exhausted')
                reconnects += 1
                time.sleep(5 * reconnects)
                bridge = Bridge(config)
                routine.bridge = bridge
                continue
            for event in incoming:
                pending = routine.state['pending']
                if event['kind'] == 'action_result' and pending and pending.get('commitment') and event['data'].get('request_id') == pending['id'] and event['data'].get('status') == 'completed':
                    memory.record('meeting-spoken', 'commitment', {'text': 'Meet on this map after restart', 'map': bridge.latest['data'].get('map'), 'status': 'spoken', 'source': event['id']})
                routine.observe(event)
                events += 1
                if event['kind'] == 'action_result':
                    print(json.dumps({'time_ms': event['time_ms'], **event['data']}), flush=True)
                if event['kind'] == 'snapshot':
                    max_gap = max(max_gap, (event['time_ms']-last_snapshot)/1000 if last_snapshot else 0)
                    last_snapshot = event['time_ms']
                    disconnected += not event['data']['connected']
                if event['kind'] == 'snapshot' and event['data']['connected'] and time.monotonic()-last_observation > 30:
                    data = event['data']
                    memory.record(event['id'], 'observation', {'map': data['map'], 'name': data['name'], 'source': 'openkore_snapshot', 'time_ms': event['time_ms']})
                    last_observation = time.monotonic()
                if dialogue and event['kind'] == 'chat' and not event['data'].get('self'):
                    text = event['data'].get('text', '')
                    if text.startswith('M3:'):
                        memory.record(event['id'], 'reported_claim', {'speaker': event['data'].get('speaker'), 'text': text[:240]})
                        question = text[3:].strip()
                        if question == 'promise to meet here after restart':
                            memory.record('meeting-commitment', 'commitment', {'text': 'Meet at the current map after orchestrator restart', 'map': bridge.latest['data'].get('map'), 'status': 'intended', 'source': event['id']})
                            try:
                                routine.chat("I'll meet you on this map after restart.")
                                routine.state['pending']['commitment'] = True
                                routine.save()
                            except (RuntimeError, ValueError, OSError):
                                print(json.dumps({'commitment': 'intended_delivery_unconfirmed'}), flush=True)
                            continue
                        topic = 'poring' if question == 'web poring' else None
                        try:
                            dialogue.ask(question, bridge.session, topic)
                        except (ValueError, RuntimeError, BufferError):
                            print(json.dumps({'dialogue': 'admission_rejected'}), flush=True)
            bridge.drain()
            routine.tick()
            if dialogue:
                reply = dialogue.poll(bridge.session)
                if reply:
                    memory.record(str(time.time_ns()), 'dialogue', reply)
                    print(json.dumps({'dialogue': reply}), flush=True)
                    if outbox is None:
                        outbox = reply
                    else:
                        print(json.dumps({'dialogue': 'outbox_full'}), flush=True)
                if outbox:
                    if bridge.session != outbox['session'] or time.monotonic()-outbox['started'] > (100 if outbox.get('cold') else 45):
                        print(json.dumps({'dialogue': 'outbox_expired'}), flush=True)
                        outbox = None
                    elif not routine.state['pending'] and time.time()-routine.state.get('last_send', 0) >= 1.1:
                        try:
                            routine.chat(outbox['text'])
                        except (RuntimeError, ValueError, OSError):
                            print(json.dumps({'dialogue': 'delivery_unconfirmed'}), flush=True)
                        outbox = None
    finally:
        print(json.dumps({'seconds': time.monotonic()-started, 'events': events, 'max_snapshot_gap_s': max_gap, 'disconnected_snapshots': disconnected, 'reason': routine.reason, 'state': routine.state}), flush=True)
        bridge.close()
        if dialogue:
            dialogue.close()
        memory.close()
        lease.close()


if __name__ == '__main__':
    main()
