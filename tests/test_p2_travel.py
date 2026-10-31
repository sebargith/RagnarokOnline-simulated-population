import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]

# Recorded states exercised against the real Perl contract module. The portal
# table mirrors OpenKore's parsed portals.txt shape (walk, paid Kafra, NPC talk).
SCRIPT = r'''
use JSON::PP;
use M1Travel;
my $walk = sub { my ($m, $x, $y) = @_; {map => $m, x => $x, y => $y, cost => 0, steps => '', enabled => 1} };
my %lut = (
    'prt_fild08 170 378' => {source => {map => 'prt_fild08', x => 170, y => 378}, dest => {'prontera 156 22' => $walk->('prontera', 156, 22)}},
    'prt_fild08 16 187' => {source => {map => 'prt_fild08', x => 16, y => 187}, dest => {'prt_fild07 385 186' => $walk->('prt_fild07', 385, 186)}},
    'prt_fild08 16 239' => {source => {map => 'prt_fild08', x => 16, y => 239}, dest => {'prt_fild07 383 239' => $walk->('prt_fild07', 383, 239)}},
    'prontera 156 22' => {source => {map => 'prontera', x => 156, y => 22}, dest => {'prt_fild08 170 378' => $walk->('prt_fild08', 170, 378)}},
    'prontera 146 89' => {source => {map => 'prontera', x => 146, y => 89}, dest => {
        'geffen 120 39' => {map => 'geffen', x => 120, y => 39, cost => 1200, steps => 'c r2 c r1', enabled => 1}}},
    'prontera 160 30' => {source => {map => 'prontera', x => 160, y => 30}, dest => {
        'izlude 94 103' => {map => 'izlude', x => 94, y => 103, cost => 0, steps => 'c r0', enabled => 1}}},
    'prontera 1 1' => {source => {map => 'prontera', x => 1, y => 1}, dest => {
        'payon 1 1' => {%{$walk->('payon', 1, 1)}, dynamicPortalGroup => 'event'}}},
    'prt_fild07 1 1' => {source => {map => 'prt_fild07', x => 1, y => 1}, dest => {'a 1 1' => $walk->('a', 1, 1)}},
    'a 1 1' => {source => {map => 'a', x => 1, y => 1}, dest => {'b 1 1' => $walk->('b', 1, 1)}},
    'b 1 1' => {source => {map => 'b', x => 1, y => 1}, dest => {'c 1 1' => $walk->('c', 1, 1)}},
);
my $g = M1Travel::walk_graph(\%lut);
my $plan = sub { [M1Travel::plan($g, @_)] };
my %p = (
    to_prontera => $plan->('prt_fild08', {x => 200, y => 300}, 'prontera', {x => 157, y => 31}),
    back => $plan->('prontera', {x => 157, y => 31}, 'prt_fild08', {x => 170, y => 365}),
    nearest_portal => $plan->('prt_fild08', {x => 20, y => 230}, 'prt_fild07', {x => 300, y => 200}),
    three_hops => $plan->('prt_fild08', {x => 20, y => 230}, 'b', {x => 5, y => 5}),
    four_hops => $plan->('prt_fild08', {x => 20, y => 230}, 'c', {x => 5, y => 5}),
    paid_only => $plan->('prontera', {x => 150, y => 150}, 'geffen', {x => 120, y => 100}),
    npc_free => $plan->('prontera', {x => 150, y => 150}, 'izlude', {x => 120, y => 100}),
    dynamic => $plan->('prontera', {x => 150, y => 150}, 'payon', {x => 120, y => 100}),
);
my $ctx = sub { my %o = @_; {manual_ai => 1, hp => 40, map => 'prt_fild08', %o} };
my $tr = sub { my %o = @_; {type => 'travel', map => 'prontera', x => 157, y => 31, timeout_s => 120, %o} };
my %v = (
    valid => M1Travel::validate($tr->(), $ctx->()),
    extra_key => M1Travel::validate({%{$tr->()}, via => 'kafra'}, $ctx->()),
    bad_map => M1Travel::validate($tr->(map => 'Prontera!'), $ctx->()),
    long_timeout => M1Travel::validate($tr->(timeout_s => 301), $ctx->()),
    legacy_owner => M1Travel::validate($tr->(), $ctx->(manual_ai => 0)),
    dead => M1Travel::validate($tr->(), $ctx->(hp => 0)),
    same_map => M1Travel::validate($tr->(map => 'prt_fild08'), $ctx->()),
);
my $portal = {map => 'prt_fild08', x => 170, y => 378, to_map => 'prontera'};
my $final = {map => 'prontera', x => 157, y => 31};
my $s = sub { my %o = @_; [M1Travel::leg_step({map => 'prt_fild08', leg => $portal, phase => 'route',
    task_state => 'running', pos_to => {x => 170, y => 377}, calc => {x => 170, y => 377}, %o})] };
my %l = (
    walking => $s->(),
    hopped => $s->(map => 'prontera'),
    elsewhere => $s->(map => 'izlude'),
    next_to_portal => $s->(task_state => 'done'),
    off_target => $s->(task_state => 'done', pos_to => {x => 160, y => 370}),
    no_route => $s->(task_state => 'done', error => {code => 1}),
    stuck => $s->(task_state => 'done', error => {code => 2}),
    lost => $s->(task_state => 'missing'),
    entering => $s->(phase => 'enter', enter_elapsed => 2),
    not_taken => $s->(phase => 'enter', enter_elapsed => 5),
    final_arrived => $s->(map => 'prontera', leg => $final, task_state => 'done',
        pos_to => {x => 157, y => 31}, calc => {x => 157, y => 31}),
    final_walking => $s->(map => 'prontera', leg => $final),
    final_left_map => $s->(map => 'prt_fild08', leg => $final),
);
my $gat = sub { my ($x, $y) = @_; !($x == 170 && $y == 378) && !($y > 378) };
my %ap = (
    walkable => M1Travel::approach_cell({x => 156, y => 22}, sub { 1 }),
    blocked_portal => M1Travel::approach_cell({x => 170, y => 378}, $gat),
    enclosed => M1Travel::approach_cell({x => 170, y => 378}, sub { 0 }),
);
my $tctx = sub { my %o = @_; {manual_ai => 1, hp => 40, recovering => 0, talking => 0,
    npc => {x => 160, y => 29}, pos => {x => 157, y => 31}, %o} };
my $talk = sub { my %o = @_; {type => 'npc_talk', x => 160, y => 29, choices => ['Cancel'], timeout_s => 30, %o} };
my %tv = (
    valid => M1Travel::validate_talk($talk->(), $tctx->()),
    no_choices => M1Travel::validate_talk($talk->(choices => []), $tctx->()),
    text_input => M1Travel::validate_talk($talk->(choices => [{text => 'x'}]), $tctx->()),
    too_many => M1Travel::validate_talk($talk->(choices => [('a') x 5]), $tctx->()),
    long_label => M1Travel::validate_talk($talk->(choices => ['x' x 41]), $tctx->()),
    extra_key => M1Travel::validate_talk({%{$talk->()}, buy => 1}, $tctx->()),
    long_timeout => M1Travel::validate_talk($talk->(timeout_s => 61), $tctx->()),
    recovering => M1Travel::validate_talk($talk->(), $tctx->(recovering => 1)),
    talking => M1Travel::validate_talk($talk->(), $tctx->(talking => 1)),
    missing => M1Travel::validate_talk($talk->(), $tctx->(npc => undef)),
    far => M1Travel::validate_talk($talk->(), $tctx->(pos => {x => 170, y => 29})),
);
my $menu = ['City Guide.', 'Remove Marks from Mini-Map', 'Notice', 'Cancel', 'Cancel Chat'];
my $d = sub { my %o = @_; [M1Travel::dialog_step({state => 'initiated', choices => ['Cancel'], pages => 0, responses => [], %o})] };
my %ds = (
    text => $d->(),
    next => $d->(state => 'next'),
    paging_limit => $d->(state => 'next', pages => 12),
    menu => $d->(state => 'select', responses => $menu),
    unplanned_menu => $d->(state => 'select', responses => $menu, choices => ['Notice board']),
    local_cancel_only => $d->(state => 'select', responses => $menu, choices => ['Cancel Chat']),
    menu_without_plan => $d->(state => 'select', responses => $menu, choices => []),
    number => $d->(state => 'number'),
    text_box => $d->(state => 'text'),
    shop => $d->(state => 'buy_or_sell'),
    closed => $d->(state => 'close', choices => []),
    closed_early => $d->(state => 'close'),
);
my $before = {map => 'prontera', zeny => 0, inventory => '1201:1,2301:1'};
my %to = (
    same => [M1Travel::talk_outcome('completed', 'conversation_closed', $before, {%$before})],
    paid => [M1Travel::talk_outcome('completed', 'conversation_closed', $before, {%$before, zeny => -1})],
    warped => [M1Travel::talk_outcome('failed', 'unexpected_menu', $before, {%$before, map => 'izlude'})],
);
print JSON::PP->new->canonical->encode({plan => \%p, validate => \%v, leg => \%l,
    talk_validate => \%tv, dialog => \%ds, talk_outcome => \%to, approach => \%ap});
'''


class TravelContractTests(unittest.TestCase):
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

    def test_plan_uses_only_free_walk_portals(self):
        p = self.data['plan']
        self.assertEqual(p['to_prontera'], [
            {'map': 'prt_fild08', 'x': 170, 'y': 378, 'to_map': 'prontera'},
            {'map': 'prontera', 'x': 157, 'y': 31}])
        self.assertEqual(p['back'], [
            {'map': 'prontera', 'x': 156, 'y': 22, 'to_map': 'prt_fild08'},
            {'map': 'prt_fild08', 'x': 170, 'y': 365}])
        self.assertEqual(p['nearest_portal'][0], {'map': 'prt_fild08', 'x': 16, 'y': 239, 'to_map': 'prt_fild07'})
        self.assertEqual([leg['map'] for leg in p['three_hops']], ['prt_fild08', 'prt_fild07', 'a', 'b'])
        # Beyond the hop limit, paid Kafra, scripted NPC and dynamic portals: no plan.
        for name in ('four_hops', 'paid_only', 'npc_free', 'dynamic'):
            self.assertEqual(p[name], [], name)

    def test_approach_cell_for_unwalkable_portal(self):
        self.assertEqual(self.data['approach'], {
            'walkable': {'x': 156, 'y': 22}, 'blocked_portal': {'x': 170, 'y': 377}, 'enclosed': None})

    def test_admission(self):
        self.assertEqual(self.data['validate'], {
            'valid': None, 'extra_key': 'invalid_travel', 'bad_map': 'invalid_travel',
            'long_timeout': 'invalid_timeout', 'legacy_owner': 'executor_not_native',
            'dead': 'dead', 'same_map': 'same_map_use_navigate'})

    def test_hops_only_on_observed_map_change(self):
        self.assertEqual(self.data['leg'], {
            'walking': [], 'hopped': ['hopped'], 'elsewhere': ['final', 'unknown', 'unexpected_map'],
            'next_to_portal': ['enter'], 'off_target': ['final', 'unknown', 'route_ended_off_target'],
            'no_route': ['final', 'failed', 'unreachable'], 'stuck': ['final', 'failed', 'blocked'],
            'lost': ['final', 'unknown', 'route_task_lost'], 'entering': [],
            'not_taken': ['final', 'failed', 'portal_not_taken'],
            'final_arrived': ['final', 'completed', 'arrived'], 'final_walking': [],
            'final_left_map': ['final', 'unknown', 'unexpected_map']})

    def test_talk_admission(self):
        self.assertEqual(self.data['talk_validate'], {
            'valid': None, 'no_choices': None, 'text_input': 'invalid_npc_talk', 'too_many': 'invalid_npc_talk',
            'long_label': 'invalid_npc_talk', 'extra_key': 'invalid_npc_talk', 'long_timeout': 'invalid_timeout',
            'recovering': 'recovering', 'talking': 'already_talking', 'missing': 'npc_not_found',
            'far': 'npc_too_far'})

    def test_dialog_sends_only_planned_steps(self):
        self.assertEqual(self.data['dialog'], {
            'text': [], 'next': ['continue'], 'paging_limit': ['cancel', 'failed', 'too_many_pages'],
            'menu': ['respond', 4], 'unplanned_menu': ['cancel', 'failed', 'unexpected_menu'],
            'local_cancel_only': ['cancel', 'failed', 'unexpected_menu'],
            'menu_without_plan': ['cancel', 'failed', 'unexpected_menu'],
            'number': ['cancel', 'failed', 'input_not_allowed'], 'text_box': ['cancel', 'failed', 'input_not_allowed'],
            'shop': ['cancel', 'failed', 'shop_not_allowed'], 'closed': ['close', 'completed', 'conversation_closed'],
            'closed_early': ['close', 'failed', 'closed_before_choices']})

    def test_dialog_never_hides_state_changes(self):
        self.assertEqual(self.data['talk_outcome'], {
            'same': ['completed', 'conversation_closed', []],
            'paid': ['unknown', 'state_changed', ['zeny']],
            'warped': ['unknown', 'state_changed', ['map']]})


if __name__ == '__main__':
    unittest.main()
