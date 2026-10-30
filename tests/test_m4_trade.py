from pathlib import Path
import tempfile
import unittest

from agent.trade import TradeLedger, reconcile


class TradeTests(unittest.TestCase):
    before = {'agent': {'jellopy': 2, 'zeny': 100}, 'peer': {'jellopy': 0, 'zeny': 100}}
    after = {'agent': {'jellopy': 1, 'zeny': 110}, 'peer': {'jellopy': 1, 'zeny': 90}}

    def snapshot(self, who, session='new', ready=True):
        balance = self.after[who]
        return {'id': who+'-fresh', 'session': session, 'data': {'connected': True, 'inventory_ready': ready,
            'inventory': [{'name_id': 909, 'amount': balance['jellopy']}], 'zeny': balance['zeny'], 'deal': {'name': ''}}}

    def test_both_sides_required_and_partial_changes_ambiguous(self):
        self.assertEqual(reconcile(self.before, self.after), 'completed')
        self.assertEqual(reconcile(self.before, self.before), 'not_applied')
        self.assertEqual(reconcile(self.before, {**self.after, 'peer': self.before['peer']}), 'ambiguous')

    def test_unknown_survives_restart_blocks_retry_until_full_fresh_login(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'trade.sqlite'
            ledger = TradeLedger(path)
            key = ledger.begin(self.before, {'agent': 'old', 'peer': 'old'})
            ledger.close()
            ledger = TradeLedger(path)
            with self.assertRaises(RuntimeError):
                ledger.begin(self.before, {'agent': 'new', 'peer': 'new'})
            with self.assertRaises(ValueError):
                ledger.finish(key, {'agent': self.snapshot('agent'), 'peer': self.snapshot('peer', session='old')}, self.after)
            with self.assertRaises(ValueError):
                ledger.finish(key, {'agent': self.snapshot('agent'), 'peer': self.snapshot('peer', ready=False)}, self.after)
            with self.assertRaises(ValueError):
                ledger.finish(key, {who: self.snapshot(who) for who in ('agent', 'peer')}, self.before)
            result = ledger.finish(key, {who: self.snapshot(who) for who in ('agent', 'peer')}, self.after)
            self.assertEqual(result['reconciliation'], 'completed')
            self.assertEqual(ledger.unresolved(), [])
            ledger.close()
