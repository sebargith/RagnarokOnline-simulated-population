from collections import deque
from concurrent.futures import Future
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest

from agent.continuous import Continuous
from agent.live_io import RingLog
from bridge.client import Bridge
from inference.m2 import BoundedInference

ROOT = Path(__file__).resolve().parents[1]


class ContinuousTests(unittest.TestCase):
    def test_real_perl_window_survives_eviction_without_replay(self):
        perl = ROOT.parent/'vendor/strawberry-perl/perl/bin/perl.exe'
        if not perl.exists():
            perl = shutil.which('perl')
        if not perl:
            self.skipTest('Perl unavailable')
        script = r'''
use M4RequestWindow;
my $w = M4RequestWindow->new(128);
for (1..1500) {
    my ($s) = $w->admit("c_$_"); die "not new" unless $s eq 'new';
    $w->finish("c_$_", {status => 'completed'});
}
die "unbounded" unless $w->size == 128;
my ($s) = $w->admit('c_1'); die "old replay" unless $s eq 'retired';
my ($s2, $r) = $w->admit('c_1500'); die "duplicate" unless $s2 eq 'cached' && $r->{status} eq 'completed';
die "sequence" unless $w->next_serial == 1501;
print "ok";
'''
        result = subprocess.run([str(perl), '-I'+str(ROOT/'bridge/lib'), '-e', script], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'ok')

    def test_rotation_is_bounded_and_restart_appends(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'events.jsonl'
            log = RingLog(path, limit=64, backups=2)
            for i in range(100):
                log.write(json.dumps({'i': i})+'\n')
            log.close()
            previous = path.read_text()
            log = RingLog(path, limit=64, backups=2)
            log.write('{}\n'); log.close()
            self.assertTrue(path.read_text().startswith(previous))
            self.assertLessEqual(len(list(Path(directory).iterdir())), 3)
            self.assertTrue(all(p.stat().st_size <= 64 for p in Path(directory).iterdir()))

    def controller(self):
        controller = Continuous.__new__(Continuous)
        controller.offline = set()
        controller.last_send = {'agent': 0}
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE live_intents(session TEXT,id TEXT,action TEXT,status TEXT,created REAL,retired INTEGER DEFAULT 0,PRIMARY KEY(session,id))')
        controller.community = SimpleNamespace(memories={'agent': SimpleNamespace(db=db)})
        bridge = SimpleNamespace(session='boot:1', latest={'session': 'boot:1', 'time_ms': time.time()*1000, 'data': {'connected': True, 'hp': 10}}, next_serial=1)
        bridge.serial_id = lambda: Bridge.serial_id(bridge)
        controller.bridges = {'agent': bridge}
        return controller, bridge, db

    def test_journal_bounded_unknown_preserved_and_never_resent(self):
        controller, bridge, db = self.controller()
        sent = []
        def proposal(action, **kwargs):
            # Durable write must precede the network write.
            self.assertEqual(db.execute('SELECT status FROM live_intents WHERE id=?', (kwargs['request_id'],)).fetchone()[0], 'unknown')
            sent.append(kwargs['request_id'])
        bridge.proposal = proposal
        for i in range(1100):
            controller.last_send['agent'] = 0
            request = controller.send_now('agent', {'type': 'move'})
            db.execute("UPDATE live_intents SET status='completed' WHERE id=?", (request,))
        self.assertLessEqual(db.execute('SELECT COUNT(*) FROM live_intents').fetchone()[0], 512)
        controller.last_send['agent'] = 0
        controller.send_now('agent', {'type': 'trade_commit'})
        controller.last_send['agent'] = 0
        with self.assertRaises(RuntimeError):
            controller.send_now('agent', {'type': 'trade_commit'})
        self.assertEqual(len(sent), 1101)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM live_intents WHERE status='unknown'").fetchone()[0], 1)
        db.close()

    def test_failed_send_stays_unknown(self):
        controller, bridge, db = self.controller()
        def failed(*args, **kwargs):
            raise ConnectionError('lost after write')
        bridge.proposal = failed
        with self.assertRaises(ConnectionError):
            controller.send_now('agent', {'type': 'take', 'target': 'abc'})
        self.assertEqual(db.execute('SELECT status,retired FROM live_intents').fetchone(), ('unknown', 0))
        db.close()

    def test_stale_reply_is_discarded_and_chat_waits_for_target(self):
        controller = Continuous.__new__(Continuous)
        controller.suspended = False
        controller.bridges = {who: SimpleNamespace(session='new') for who in ('agent', 'third')}
        controller.pending_replies = {'agent': ('old', {'ready_at': time.monotonic(), 'text': 'stale'})}
        controller.manual = deque([{'sender': 'agent', 'target': 'third', 'text': 'Hello', 'created': time.time()}])
        controller.last_patrol = time.monotonic()
        controller.available = lambda who: who == 'agent'
        controller.data = lambda who: {'deal': {'name': ''}}
        controller.send_now = lambda *args: self.fail('No chat may be sent to an unavailable target or from an old epoch')
        notes = []
        controller.note = lambda kind, **kwargs: notes.append(kind)
        controller.background()
        self.assertEqual(notes, ['reply_discarded'])
        self.assertEqual(len(controller.manual), 1)
        self.assertFalse(controller.pending_replies)

    def test_trade_skips_insufficient_perceived_funds_without_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = Continuous.__new__(Continuous)
            controller.runtime = Path(directory)
            (controller.runtime/'m4').mkdir()
            controller.data = lambda who: {'inventory': [{'name_id': 909, 'amount': 2}], 'zeny': 9}
            notes = []
            controller.note = lambda kind, **kwargs: notes.append(kind)
            self.assertEqual(controller.trade(), {'skipped': True})
            self.assertEqual(notes, ['trade_skipped'])

    def test_inference_circuit_recovery_requires_idle_and_new_turn(self):
        config = json.loads((ROOT/'config/m2-operating.json').read_text())
        release = Future()
        calls = []
        def transport(*args):
            calls.append(1)
            if len(calls) == 1:
                raise ConnectionError('offline')
            release.result(2)
            return {'content': '{"text":"ok"}'}
        service = BoundedInference(config, config['model'], transport)
        try:
            self.assertIn('error', service.submit('agent', [], 1).result(2))
            self.assertTrue(service.recover_idle_circuit())
            future = service.submit('agent', [], 1)
            self.assertFalse(service.recover_idle_circuit())
            release.set_result(None)
            self.assertNotIn('error', future.result(2))
            self.assertEqual(len(calls), 2)
        finally:
            release.set_result(None) if not release.done() else None
            service.close()
