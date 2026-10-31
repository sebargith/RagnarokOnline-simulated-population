import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.p2_supply import buy_plan, decide

# Recorded states exercised against the real Perl contract module. Inventory
# mirrors Tarin's: Knife and Cotton Shirt equipped, Clover and Jellopy loot.
SCRIPT = r'''
use JSON::PP;
use M1Supply;
my $inv = [{name_id => 1201, amount => 1, type => 5, equipped => 1}, {name_id => 2301, amount => 1, type => 4, equipped => 1},
    {name_id => 705, amount => 2, type => 3, equipped => 0}, {name_id => 909, amount => 5, type => 3, equipped => 0},
    {name_id => 512, amount => 1, type => 0, equipped => 0}];
my $ctx = sub { my %o = @_; {manual_ai => 1, hp => 40, recovering => 0, talking => 0, npc => {x => 104, y => 49},
    pos => {x => 104, y => 51}, zeny => 25, inventory => $inv, %o} };
my $sell = sub { my %o = @_; {type => 'npc_sell', x => 104, y => 49, timeout_s => 20,
    items => [{name_id => 909, amount => 5}, {name_id => 705, amount => 2}], %o} };
my $buy = sub { my %o = @_; {type => 'npc_buy', x => 104, y => 49, timeout_s => 20, max_zeny => 15,
    items => [{name_id => 512, amount => 1}], %o} };
my %v = (
    sell_ok => M1Supply::validate_sell($sell->(), $ctx->()),
    sell_extra => M1Supply::validate_sell({%{$sell->()}, price => 1}, $ctx->()),
    sell_empty => M1Supply::validate_sell($sell->(items => []), $ctx->()),
    sell_dup => M1Supply::validate_sell($sell->(items => [{name_id => 909, amount => 1}, {name_id => 909, amount => 1}]), $ctx->()),
    sell_zero => M1Supply::validate_sell($sell->(items => [{name_id => 909, amount => 0}]), $ctx->()),
    sell_lines => M1Supply::validate_sell($sell->(items => [map {{name_id => $_, amount => 1}} 1 .. 9]), $ctx->()),
    sell_equipped => M1Supply::validate_sell($sell->(items => [{name_id => 1201, amount => 1}]), $ctx->()),
    sell_consumable => M1Supply::validate_sell($sell->(items => [{name_id => 512, amount => 1}]), $ctx->()),
    sell_too_many => M1Supply::validate_sell($sell->(items => [{name_id => 909, amount => 6}]), $ctx->()),
    sell_missing => M1Supply::validate_sell($sell->(items => [{name_id => 7001, amount => 1}]), $ctx->()),
    sell_far => M1Supply::validate_sell($sell->(), $ctx->(pos => {x => 104, y => 60})),
    sell_no_npc => M1Supply::validate_sell($sell->(), $ctx->(npc => undef)),
    sell_recovering => M1Supply::validate_sell($sell->(), $ctx->(recovering => 1)),
    sell_legacy => M1Supply::validate_sell($sell->(), $ctx->(manual_ai => 0)),
    buy_ok => M1Supply::validate_buy($buy->(), $ctx->()),
    buy_text_budget => M1Supply::validate_buy($buy->(max_zeny => '15z'), $ctx->()),
    buy_over_wallet => M1Supply::validate_buy($buy->(max_zeny => 1025), $ctx->()),
    buy_broke => M1Supply::validate_buy($buy->(max_zeny => 0), $ctx->(zeny => 0)),
    buy_as_sell => M1Supply::validate_sell($buy->(), $ctx->()),
    buy_timeout => M1Supply::validate_buy($buy->(timeout_s => 61), $ctx->()),
);
my $offers = {909 => 3, 705 => 5};
my %q = (
    sell => [M1Supply::sell_quote($sell->()->{items}, $offers)],
    sell_unlisted => [M1Supply::sell_quote([{name_id => 7001, amount => 1}], $offers)],
);
my $o = sub { my %x = @_; {max_zeny => 15, zeny => 25, weight => 50, weight_max => 400, item_weight => {512 => 20}, %x} };
my $apple = [{name_id => 512, amount => 1}];
my %b = (
    ok => [M1Supply::buy_quote($apple, {512 => 15, 513 => 15}, $o->())],
    not_in_store => [M1Supply::buy_quote([{name_id => 501, amount => 1}], {512 => 15}, $o->())],
    over_budget => [M1Supply::buy_quote([{name_id => 512, amount => 2}], {512 => 15}, $o->())],
    insufficient => [M1Supply::buy_quote($apple, {512 => 15}, $o->(zeny => 10, max_zeny => 15))],
    overweight => [M1Supply::buy_quote($apple, {512 => 15}, $o->(weight => 199))],
    no_capacity => [M1Supply::buy_quote($apple, {512 => 15}, $o->(weight_max => 0))],
);
my %f = map { $_ => [M1Supply::buy_failure($_)] } 1, 2, 4, 9;
my $before = {zeny => 0, items => {909 => 5, 705 => 2, 1201 => 1}};
my $sold = {zeny => 25, items => {1201 => 1}};
my %r = (
    sold => [M1Supply::reconcile('sold', $before, $sold, {zeny => 25, items => {909 => -5, 705 => -2}})],
    short_paid => [M1Supply::reconcile('sold', $before, {%$sold, zeny => 20}, {zeny => 25, items => {909 => -5, 705 => -2}})],
    not_yet => [M1Supply::reconcile('sold', $before, $before, {zeny => 25, items => {909 => -5, 705 => -2}})],
    bought => [M1Supply::reconcile('bought', $sold, {zeny => 10, items => {1201 => 1, 512 => 1}}, {zeny => -15, items => {512 => 1}})],
    extra_item => [M1Supply::reconcile('bought', $sold, {zeny => 10, items => {1201 => 1, 512 => 1, 513 => 1}}, {zeny => -15, items => {512 => 1}})],
);
print JSON::PP->new->canonical->encode({validate => \%v, sell_quote => \%q, buy_quote => \%b, buy_failure => \%f, reconcile => \%r});
'''


class SupplyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        perl = ROOT.parent/'vendor/strawberry-perl/perl/bin/perl.exe'
        perl = str(perl) if perl.exists() else shutil.which('perl')
        if not perl:
            raise unittest.SkipTest('Perl unavailable')
        result = subprocess.run([perl, '-I'+str(ROOT/'bridge/lib'), '-e', SCRIPT],
            capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.data = json.loads(result.stdout)

    def test_admission_keeps_equipment_consumables_and_unowned_money(self):
        self.assertEqual(self.data['validate'], {
            'sell_ok': None, 'sell_extra': 'invalid_npc_sell', 'sell_empty': 'invalid_npc_sell',
            'sell_dup': 'invalid_npc_sell', 'sell_zero': 'invalid_npc_sell', 'sell_lines': 'invalid_npc_sell',
            'sell_equipped': 'item_not_sellable', 'sell_consumable': 'item_not_sellable',
            'sell_too_many': 'insufficient_amount', 'sell_missing': 'insufficient_amount',
            'sell_far': 'npc_too_far', 'sell_no_npc': 'npc_not_found', 'sell_recovering': 'recovering',
            'sell_legacy': 'executor_not_native', 'buy_ok': None, 'buy_text_budget': 'invalid_npc_buy',
            'buy_over_wallet': 'insufficient_zeny', 'buy_broke': 'insufficient_zeny',
            'buy_as_sell': 'invalid_npc_sell', 'buy_timeout': 'invalid_timeout'})

    def test_quotes_use_server_prices_and_limits(self):
        self.assertEqual(self.data['sell_quote'], {'sell': [None, 25], 'sell_unlisted': ['not_in_sell_list']})
        self.assertEqual(self.data['buy_quote'], {
            'ok': [None, 15], 'not_in_store': ['not_in_store'], 'over_budget': ['over_budget'],
            'insufficient': ['insufficient_zeny'], 'overweight': ['overweight_after_buy'],
            'no_capacity': ['overweight_after_buy']})
        self.assertEqual(self.data['buy_failure'], {
            '1': ['failed', 'server_insufficient_zeny'], '2': ['failed', 'server_weight'],
            '4': ['failed', 'server_not_in_store'], '9': ['failed', 'server_buy_failed']})

    def test_reconcile_never_assumes_the_trade(self):
        r = self.data['reconcile']
        self.assertEqual(r['sold'], ['completed', 'sold', {'zeny': 25, 'items': {'705': -2, '909': -5}}])
        self.assertEqual(r['short_paid'][:2], ['unknown', 'state_mismatch'])
        self.assertEqual(r['not_yet'], ['unknown', 'state_mismatch', {'zeny': 0, 'items': {}}])
        self.assertEqual(r['bought'], ['completed', 'bought', {'zeny': -15, 'items': {'512': 1}}])
        self.assertEqual(r['extra_item'][:2], ['unknown', 'state_mismatch'])


def snap(**o):
    inv = [{'name_id': 1201, 'amount': 1, 'type': 5, 'equipped': 1}, {'name_id': 2301, 'amount': 1, 'type': 4, 'equipped': 1},
        {'name_id': 705, 'amount': 2, 'type': 3, 'equipped': 0}, {'name_id': 909, 'amount': 5, 'type': 3, 'equipped': 0}]
    return {'inventory': inv, 'inventory_ready': 1, 'zeny': 0, 'weight': 60, 'weight_max': 400} | o


class SupplyPolicyTests(unittest.TestCase):
    def test_loot_and_no_healing_sends_tarin_to_shop(self):
        d = decide(snap())
        self.assertTrue(d['go'])
        self.assertEqual(d['sell'], [{'name_id': 705, 'amount': 2}, {'name_id': 909, 'amount': 5}])
        self.assertEqual(d['need_heal'], 1)
        self.assertEqual(d['reasons'], ['loot 7 >= 5', 'healing 0 < 1'])

    def test_no_need_stays(self):
        inv = snap()['inventory'][:2] + [{'name_id': 909, 'amount': 2, 'type': 3, 'equipped': 0},
            {'name_id': 512, 'amount': 1, 'type': 0, 'equipped': 0}]
        d = decide(snap(inventory=inv))
        self.assertEqual((d['go'], d['sell'], d['need_heal'], d['reasons']), (False, [], 0, []))

    def test_heavy_bag_sells_even_little_loot(self):
        inv = snap()['inventory'][:2] + [{'name_id': 909, 'amount': 1, 'type': 3, 'equipped': 0},
            {'name_id': 512, 'amount': 1, 'type': 0, 'equipped': 0}]
        d = decide(snap(inventory=inv, weight=170))
        self.assertEqual(d['sell'], [{'name_id': 909, 'amount': 1}])
        self.assertEqual(d['reasons'], ['weight 42.5% >= 40%'])

    def test_need_without_loot_or_money_stays(self):
        inv = snap()['inventory'][:2]
        self.assertFalse(decide(snap(inventory=inv))['go'])
        self.assertTrue(decide(snap(inventory=inv, zeny=15))['go'])

    def test_unobserved_inventory_never_decides(self):
        for s in (snap(inventory=[]), snap(inventory_ready=0)):
            d = decide(s)
            self.assertEqual((d['go'], d['reasons']), (False, ['inventory_not_observed']))

    def test_buy_only_what_observed_zeny_affords(self):
        self.assertEqual(buy_plan({'zeny': 25}, 1), ([{'name_id': 512, 'amount': 1}], 15))
        self.assertEqual(buy_plan({'zeny': 14}, 1), ([], 0))
        self.assertEqual(buy_plan({'zeny': 100}, 2), ([{'name_id': 512, 'amount': 2}], 30))


if __name__ == '__main__':
    unittest.main()
