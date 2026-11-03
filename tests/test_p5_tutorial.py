"""P5 step 4: leaving the training grounds by NPC. The Perl dialog/portal contract,
the transcribed script checked against the vendor NPC scripts and walk data, the
checkpointed step machine, the destination planner and the runner hand-off into
the cycle. No game services are used."""
import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent import build_policy, hunting, tutorial
from agent.goal_planner import DestinationPlanner, validate_destination
from agent.solo_cycle import SoloCycle
from agent.tutorial import Tutorial
from scripts.build_p5_hunting import walk_map
from scripts.run_p2_cycle import P5Planning, Runner, TutorialPlanning
from test_p3_runner import ControlledBridge
from test_p5_build import Service, snapshot as p5_snapshot

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT.parent/'vendor'
NOVICE = VENDOR/'rathena/npc/pre-re/jobs/novice/novice.txt'
SCRIPT = tutorial.load()
TABLES = {'monsters': hunting.load_monsters(), 'fields': hunting.load_fields()}
BUILDS = build_policy.load_builds()

PERL = r'''
use JSON::PP;
use M1Travel;
my $ctx = sub { my %o = @_; {manual_ai => 1, hp => 40, recovering => 0, talking => 0, npc => {x => 100, y => 29},
    pos => {x => 100, y => 27}, %o} };
my $sc = sub { my %o = @_; {type => 'npc_script', x => 100, y => 29, choices => ['Apply for training.'], name_reply => 1,
    timeout_s => 60, expect => {map => 'new_1-2', x => 100, y => 70}, %o} };
my $long = 'x' x 65;
my %v = (
    valid => M1Travel::validate_script($sc->(), $ctx->()),
    no_expect => M1Travel::validate_script({%{$sc->()}, expect => undef}, $ctx->()),
    expect_extra => M1Travel::validate_script($sc->(expect => {map => 'new_1-2', x => 1, y => 2, via => 3}), $ctx->()),
    expect_bad_map => M1Travel::validate_script($sc->(expect => {map => 'New 1', x => 1, y => 2}), $ctx->()),
    name_text => M1Travel::validate_script($sc->(name_reply => 'Nilo'), $ctx->()),
    extra_key => M1Travel::validate_script({%{$sc->()}, text => 'hi'}, $ctx->()),
    long_label => M1Travel::validate_script($sc->(choices => [$long]), $ctx->()),
    label_64 => M1Travel::validate_script($sc->(choices => ['x' x 64]), $ctx->()),
    many => M1Travel::validate_script($sc->(choices => [('Yes.') x 33]), $ctx->()),
    timeout => M1Travel::validate_script($sc->(timeout_s => 241), $ctx->()),
    far => M1Travel::validate_script($sc->(), $ctx->(pos => {x => 100, y => 20})),
    talk_unchanged => M1Travel::validate_talk({type => 'npc_talk', x => 100, y => 29, choices => [], timeout_s => 60}, $ctx->()),
);
my $d = sub { my %o = @_; [M1Travel::dialog_step({choices => [], pages => 0, responses => [], %o})] };
my %d = (
    name => $d->(state => 'text', name_reply => 1, name_sent => 0),
    name_twice => $d->(state => 'text', name_reply => 1, name_sent => 1),
    text_not_declared => $d->(state => 'text', name_reply => 0),
    number => $d->(state => 'number', name_reply => 1),
    talk_text => $d->(state => 'text'),
    long_script => $d->(state => 'next', pages => 100, max_pages => 160),
    long_talk => $d->(state => 'next', pages => 12),
);
my $e = {map => 'new_1-3', x => 96, y => 21};
my %o = (
    warped => [M1Travel::script_outcome('completed', 'conversation_closed', $e, {map => 'new_1-3', x => 96, y => 22})],
    wrong_map => [M1Travel::script_outcome('completed', 'conversation_closed', $e, {map => 'new_1-1', x => 96, y => 21})],
    far => [M1Travel::script_outcome('completed', 'conversation_closed', $e, {map => 'new_1-3', x => 99, y => 21})],
    undeclared => [M1Travel::script_outcome('completed', 'conversation_closed', undef, {map => 'new_1-3', x => 96, y => 21})],
    no_warp => [M1Travel::script_outcome('completed', 'conversation_closed', $e, undef)],
    failed => [M1Travel::script_outcome('failed', 'unexpected_menu', $e, undef)],
    closed => [M1Travel::script_outcome('completed', 'conversation_closed', undef, undef)],
);
my $ws = {};
my $obs = {inventory_ready => 0, map => 'new_1-2', inventory => undef, zeny => 0, exp => '1,0,1,0'};
my @settle;
push @settle, M1Travel::stable_warp_snapshot($ws, $obs, 1, 10);
$obs->{inventory_ready} = 1; $obs->{inventory} = '1201:1';
push @settle, M1Travel::stable_warp_snapshot($ws, $obs, 2, 10);
$obs->{inventory} = '1201:1,2301:1';
push @settle, M1Travel::stable_warp_snapshot($ws, $obs, 3, 10);
push @settle, M1Travel::stable_warp_snapshot($ws, $obs, 3.5, 10);
push @settle, M1Travel::stable_warp_snapshot($ws, $obs, 4, 10);
push @settle, M1Travel::stable_warp_snapshot($ws, $obs, 10, 10);
my $walk = sub { my ($m, $x, $y) = @_; {map => $m, x => $x, y => $y, cost => 0, steps => '', enabled => 1} };
my %lut = (
    'new_1-2 73 106' => {source => {map => 'new_1-2', x => 73, y => 106}, dest => {'new_1-2 41 172' => $walk->('new_1-2', 41, 172)}},
    'new_1-2 100 29' => {source => {map => 'new_1-2', x => 100, y => 29}, dest => {
        'new_1-2 100 70' => {%{$walk->('new_1-2', 100, 70)}, steps => 'c r0 c c'}}},
    'new_1-1 148 112' => {source => {map => 'new_1-1', x => 148, y => 112}, dest => {'new_1-2 100 9' => $walk->('new_1-2', 100, 9)}},
);
my $portals = M1Travel::same_map_portals(\%lut);
my $pc = sub { my %o = @_; {manual_ai => 1, hp => 40, map => 'new_1-2', %o} };
my $pa = sub { my %o = @_; {type => 'portal', map => 'new_1-2', x => 73, y => 106, timeout_s => 60, %o} };
my %p = (
    valid => M1Travel::validate_portal($pa->(), $pc->(), $portals),
    npc_warp => M1Travel::validate_portal($pa->(x => 100, y => 29), $pc->(), $portals),
    other_map => M1Travel::validate_portal($pa->(), $pc->(map => 'new_1-1'), $portals),
    extra => M1Travel::validate_portal({%{$pa->()}, to => 'x'}, $pc->(), $portals),
);
my $leg = {map => 'new_1-2', x => 73, y => 106, to_map => 'new_1-2', to => {x => 41, y => 172}};
my $s = sub { my %o = @_; [M1Travel::leg_step({map => 'new_1-2', leg => $leg, phase => 'enter', task_state => 'done',
    pos_to => {x => 73, y => 105}, calc => {x => 73, y => 105}, enter_elapsed => 1, %o})] };
my %l = (
    waiting => $s->(),
    hopped => $s->(warped => {map => 'new_1-2', x => 41, y => 172}),
    elsewhere => $s->(warped => {map => 'new_1-2', x => 100, y => 70}),
    not_taken => $s->(enter_elapsed => 6),
);
print JSON::PP->new->canonical->encode({validate => \%v, dialog => \%d, outcome => \%o, settle => \@settle, portals => $portals,
    portal => \%p, leg => \%l});
'''


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        perl = VENDOR/'strawberry-perl/perl/bin/perl.exe'
        perl = str(perl) if perl.exists() else shutil.which('perl')
        if not perl:
            raise unittest.SkipTest('Perl unavailable')
        result = subprocess.run([perl, '-I'+str(ROOT/'bridge/lib'), '-e', PERL], capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.data = json.loads(result.stdout)

    def test_script_validation(self):
        v = self.data['validate']
        self.assertIsNone(v['valid'])
        self.assertIsNone(v['label_64'])
        for key in ('no_expect', 'expect_extra', 'expect_bad_map', 'name_text', 'extra_key', 'long_label', 'many'):
            self.assertEqual(v[key], 'invalid_npc_script', key)
        self.assertEqual((v['timeout'], v['far'], v['talk_unchanged']), ('invalid_timeout', 'npc_too_far', None))

    def test_only_the_declared_own_name_is_typed(self):
        d = self.data['dialog']
        self.assertEqual(d['name'], ['name'])
        for key in ('name_twice', 'text_not_declared', 'number', 'talk_text'):
            self.assertEqual(d[key], ['cancel', 'failed', 'input_not_allowed'], key)
        self.assertEqual((d['long_script'], d['long_talk']), (['continue'], ['cancel', 'failed', 'too_many_pages']))

    def test_only_the_declared_warp_completes(self):
        o = self.data['outcome']
        self.assertEqual(o['warped'], ['completed', 'warped'])
        for key in ('wrong_map', 'far', 'undeclared'):
            self.assertEqual(o[key], ['unknown', 'unexpected_warp'], key)
        self.assertEqual(o['no_warp'], ['failed', 'warp_not_observed'])
        self.assertEqual(o['failed'], ['failed', 'unexpected_menu'])
        self.assertEqual(o['closed'], ['completed', 'conversation_closed'])
        self.assertEqual(self.data['settle'], ['waiting', 'waiting', 'waiting', 'waiting', 'stable', 'timeout'])

    def test_same_map_portal(self):
        self.assertEqual(self.data['portals'], {'new_1-2 73 106': {'x': 41, 'y': 172}})
        p = self.data['portal']
        self.assertEqual((p['valid'], p['npc_warp'], p['other_map'], p['extra']),
                         (None, 'not_a_same_map_portal', 'wrong_map', 'invalid_portal'))
        l = self.data['leg']
        self.assertEqual((l['waiting'], l['hopped'], l['elsewhere'], l['not_taken']),
                         ([], ['hopped'], ['final', 'unknown', 'unexpected_warp'], ['final', 'failed', 'portal_not_taken']))

    def test_bridge_wiring(self):
        bridge = (ROOT/'bridge/openkore/m1_bridge.pl').read_text(encoding='utf-8')
        self.assertIn("sendTalkText($p->{npc_bin}, $char->{name})", bridge)
        self.assertEqual(bridge.count('sendTalkText'), 1)  # No other text input path.
        self.assertIn("'Network::Receive::map_changed', \\&map_changed", bridge)
        self.assertIn('877[0-3]', bridge)  # 8772/8773: R1 profiles


def npc_block(text, map_name, x, y):
    lines = text.splitlines()
    head = re.compile(rf'^{re.escape(map_name)},{x},{y},\d+\tscript\t')
    start = next(i for i, l in enumerate(lines) if head.match(l))
    end = next((i for i in range(start+1, len(lines)) if re.match(r'^[a-z0-9_-]+,\d+,\d+', lines[i])), len(lines))
    return '\n'.join(lines[start:end])


def selects(block):
    return [s.split(':') for s in re.findall(r'select\(\s*"([^"]*)"', block)]


def walk_component(name, start):
    width, height, cells = walk_map(name)
    ok = lambda x, y: 0 <= x < width and 0 <= y < height and cells[y*width + x] & 1
    seen, todo = {start}, [start]
    while todo:
        x, y = todo.pop()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                c = (x+dx, y+dy)
                if c not in seen and ok(*c):
                    seen.add(c); todo.append(c)
    return seen


@unittest.skipUnless(NOVICE.exists(), 'vendor rAthena unavailable')
class ScriptTableTests(unittest.TestCase):
    """The hand transcription is checked against the vendor scripts, not trusted."""
    @classmethod
    def setUpClass(cls):
        cls.text = NOVICE.read_text(encoding='latin-1')
        cls.steps = {s['id']: s for s in SCRIPT['steps']}

    def block(self, step):
        return npc_block(self.text, step['map'].replace('{n}', '1'), step['x'], step['y'])

    def test_labels_warps_and_rewards_come_from_the_npc_scripts(self):
        for step in SCRIPT['steps']:
            if step['kind'] != 'script':
                continue
            block = self.block(step)
            labels = {l for s in selects(block) for l in s}
            for c in step['choices']:
                if c not in ('{answers}', '{job}'):
                    self.assertIn(c, labels, step['id'])
            if isinstance(step.get('expect'), dict):
                e = step['expect']
                self.assertIn(f'warp "{e["map"]}",{e["x"]},{e["y"]};', block, step['id'])
            for item, amount in step['rewards'].items():
                self.assertRegex(block, rf'getitem {item},{amount};', step['id'])
            self.assertEqual(bool(step['name_reply']), 'input .@charname$' in block, step['id'])

    def test_personality_answers_follow_hansons_questions(self):
        hanson = selects(self.block(self.steps['hanson']))
        start = next(i for i, s in enumerate(hanson) if "I'll take the course." in s)
        answers = SCRIPT['personality_answers']
        self.assertEqual(len(answers), 22)
        for i, answer in enumerate(answers):
            self.assertIn(answer, hanson[start+1+i], i)
        self.assertTrue(all('My own choice!' in s for s in hanson if len(s) == 2 and s[0].endswith('!')))

    def test_destinations_match_the_own_choice_menu(self):
        section = self.text[self.text.index('S_UserJobchoice:'):]
        section = section[:section.index('return;')]
        jobs = selects(section)[0]
        self.assertEqual([d['job'] for d in SCRIPT['destinations']], jobs)
        for d in SCRIPT['destinations']:
            self.assertRegex(section, rf'savepoint "{d["town"]}",{d["save"]["x"]},{d["save"]["y"]},1,1;\s*'
                                      rf'warp "{d["landing"]["map"]}",{d["landing"]["x"]},{d["landing"]["y"]};')

    def test_stand_cells_are_reachable_and_in_talk_range(self):
        arrivals = {'new_1-2': [(100, 9), (41, 172)], 'new_1-3': [(96, 21)], 'new_1-4': [(99, 10)]}
        for step in SCRIPT['steps']:
            if step['kind'] != 'script':
                continue
            m = step['map'].replace('{n}', '1')
            zone = 'new_zone0' + m[-1]  # OpenKore's map alias: new_N-K -> new_zoneK.
            reach = set().union(*(walk_component(zone, a) for a in arrivals[m]))
            stand = (step['stand']['x'], step['stand']['y'])
            self.assertIn(stand, reach, step['id'])
            self.assertLessEqual(max(abs(stand[0]-step['x']), abs(stand[1]-step['y'])), tutorial.STAND_RANGE)
        # The inner door is needed: the Helper is not walkable from the receptionist's warp.
        self.assertNotIn((19, 180), walk_component('new_zone02', (100, 70)))
        self.assertIn((73, 106), walk_component('new_zone02', (100, 70)))

    def test_portals_exist_in_openkore_and_rathena(self):
        portals = (VENDOR/'openkore/tables/portals.txt').read_text(encoding='latin-1')
        self.assertIn('new_1-2 73 106 new_1-2 41 172', portals)
        self.assertIn('new_1-1 148 112 new_1-2 100 9', portals)
        warps = (VENDOR/'rathena/npc/warps/other/jobquests.txt').read_text(encoding='latin-1')
        self.assertIn('new_1-2,73,106,0\twarp\tnewwarp6005a\t2,2,new_1-2,41,172', warps)


def nilo(**changes):
    snap = p5_snapshot(points_free=48, stats={k: {'value': 1, 'cost': 2} for k in ('str', 'agi', 'vit', 'int', 'dex', 'luk')})
    snap['level'] = {'base': 1, 'job': 1, 'exp': 0, 'exp_max': 9, 'job_exp': 0, 'job_exp_max': 10}
    snap.update(name='Nilo', hp=40, hp_max=40, map='new_3-1', position={'x': 53, 'y': 111}, executor='openkore_route',
                recovery='none', zeny=0, weight=10, weight_max=2030, ground_items=[], monsters=[], npcs=[],
                explore_candidates=[])
    snap.update(changes)
    return snap


def evidence(before='1201:1,2301:1', after=None, warped=None, zeny=0, **extra):
    return {'before': {'inventory': before, 'zeny': zeny}, 'after': {'inventory': after or before, 'zeny': zeny},
            'warped': warped, 'changed': [], 'chosen': [], 'pages': 3, **extra}


class TutorialTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)/'tutorial.json'
        self.t = Tutorial(self.path, 'Nilo')
        self.n = 0

    def act(self, snap, status='completed', reason=None, ev=None):
        action = self.t.plan(snap)
        self.assertIsNotNone(action, self.t.state)
        self.n += 1
        self.t.prepare(action, f'r{self.n}', 'boot:1')
        default = {'travel': 'arrived', 'portal': 'arrived', 'navigate': 'arrived', 'npc_script':
                   'warped' if action.get('expect') else 'conversation_closed'}[action['type']]
        self.t.result({'request_id': f'r{self.n}', 'status': status, 'reason': reason or default, 'evidence': ev or {}})
        return action

    def npc(self, step_id, **pos):
        step = next(s for s in SCRIPT['steps'] if s['id'] == step_id)
        return nilo(map=step['map'].replace('{n}', '3'), position=pos or step['stand'],
                    npcs=[{'name': step['npc'], 'x': step['x'], 'y': step['y']}])

    def walk_to_decision(self):
        a = self.act(nilo())
        self.assertEqual(a, {'type': 'travel', 'map': 'new_3-2', 'x': 100, 'y': 27, 'timeout_s': 120})
        self.assertEqual(self.t.state['steps_done'][-1]['step'], 'enter_castle')
        a = self.act(self.npc('receptionist'), ev=evidence(warped={'map': 'new_1-2', 'x': 100, 'y': 70}))
        self.assertEqual(a, {'type': 'npc_script', 'x': 100, 'y': 29, 'choices': ['Apply for training.'], 'name_reply': 1,
                             'timeout_s': 60, 'expect': {'map': 'new_1-2', 'x': 100, 'y': 70}})
        a = self.act(nilo(map='new_1-2', position={'x': 100, 'y': 70}),
                     ev={'map': 'new_1-2', 'pos_to': {'x': 41, 'y': 172}})
        self.assertEqual(a['type'], 'portal')
        a = self.act(self.npc('helper', x=41, y=172))
        self.assertEqual(a, {'type': 'navigate', 'map': 'new_1-2', 'x': 19, 'y': 180, 'timeout_s': 40})
        a = self.act(self.npc('helper'), ev=evidence())
        self.assertEqual((a['choices'], 'expect' in a), (['Yes', 'Quit.'], False))
        gifts = '1201:1,2301:1,569:300,601:9,602:1,611:2,1243:1,2112:1'
        self.act(self.npc('entrance_guard'), ev=evidence(after=gifts, warped={'map': 'new_1-3', 'x': 96, 'y': 21}))
        self.act(self.npc('test_examiner'), ev=evidence(before=gifts, warped={'map': 'new_1-4', 'x': 99, 'y': 10}))
        self.act(self.npc('bruce'), ev=evidence(before=gifts))
        self.assertTrue(self.t.needs_decision())
        self.assertIsNone(self.t.plan(self.npc('hanson')))
        return gifts

    def test_arrival_snapshot_selects_npc_instead_of_repeating_navigation(self):
        self.act(nilo())
        # Reproduces the observed arrival at (100,26), while OpenKore's raw
        # movement origin was still (100,17) and pos_to was (100,27).
        action = self.t.plan(self.npc('receptionist', x=100, y=26))
        self.assertEqual(action['type'], 'npc_script')
        source = (ROOT/'bridge/openkore/m1_bridge.pl').read_text(encoding='utf-8')
        snapshot = source.split('sub snapshot {', 1)[1].split('sub nav_evidence', 1)[0]
        self.assertIn('Utils::calcPosFromPathfinding($field, $char)', snapshot)
        self.assertIn('$position->{y}', snapshot)

    def test_openkore_position_at_rest_and_during_motion(self):
        perl = VENDOR/'strawberry-perl/perl/bin/perl.exe'
        code = r'''use Utils; use JSON::PP; use Time::HiRes ();
my $t = Time::HiRes::time(); my $a = {pos=>{x=>100,y=>17}, pos_to=>{x=>100,y=>27},
    time_move=>$t, solution_calc_time=>$t, walk_speed=>1,
    solution=>[map {{x=>100,y=>$_}} 17..27]};
print JSON::PP->new->encode([
    Utils::calcPosFromPathfinding(undef, {pos=>{x=>100,y=>27},pos_to=>{x=>100,y=>27}}),
    Utils::calcPosFromPathfinding(undef, $a, 5.4, 0)]);'''
        result = subprocess.run([perl, '-I'+str(VENDOR/'openkore/src'),
                                 '-I'+str(VENDOR/'openkore/src/deps'), '-e', code],
                                capture_output=True, text=True, timeout=10, check=True)
        self.assertEqual(json.loads(result.stdout), [{'x': 100, 'y': 27}, {'x': 100, 'y': 22}])

    def test_recover_only_known_receptionist_rejections(self):
        self.t.state.update(step=1, instance=2, status='blocked', reason='two_consecutive_action_failures', failures=2)
        action = {'type': 'navigate', 'map': 'new_2-2', 'x': 100, 'y': 27, 'timeout_s': 40}
        self.t.state['history'] = [
            {'step': 0, 'action': {'type': 'travel'}, 'request_id': 'c1', 'result':
             {'request_id': 'c1', 'status': 'completed', 'reason': 'arrived'}},
            *[{'step': 1, 'action': copy.deepcopy(action), 'request_id': rid, 'session': 'old',
               'result': {'request_id': rid, 'status': 'rejected', 'reason': 'already_at_destination'}}
              for rid in ('c2', 'c3')]]
        snap = nilo(map='new_2-2', position={'x': 100, 'y': 27}, destination={'x': 100, 'y': 27},
                    connected=True, inventory_ready=True, dead=False, native_task=None, navigation=None,
                    ai_queue=[], npcs=[{'x': 100, 'y': 29}])
        events = [{'session': 'new', 'time_ms': t, 'data': copy.deepcopy(snap)} for t in (10000, 11000)]
        ready = {'session': 'new', 'time_ms': 9999, 'data': {'pending_request_id': None}}
        original = copy.deepcopy(self.t.state)
        for kind in ('identity', 'map', 'cause', 'stale', 'task', 'movement', 'inflight', 'uncertain', 'pending', 'session'):
            with self.subTest(kind=kind):
                self.t.state = copy.deepcopy(original)
                obs, rd, now = copy.deepcopy(events), copy.deepcopy(ready), 11500
                if kind == 'identity': obs[0]['data']['name'] = 'Other'
                if kind == 'map': obs[0]['data']['map'] = 'prontera'
                if kind == 'cause': self.t.state['reason'] = 'npc_script:unknown/x'
                if kind == 'stale': now = 20000
                if kind == 'task': obs[1]['data']['native_task'] = {'id': 'x'}
                if kind == 'movement': obs[1]['data']['destination']['y'] = 28
                if kind == 'inflight': self.t.state['inflight'] = {'request_id': 'x'}
                if kind == 'uncertain': self.t.state['history'][-1]['result']['status'] = 'unknown'
                if kind == 'pending': rd['data']['pending_request_id'] = 'x'
                if kind == 'session': obs[1]['session'] = 'other'
                with self.assertRaises(RuntimeError): self.t.recover_receptionist_navigation(obs, rd, now)
        self.t.state = copy.deepcopy(original)
        self.t.recover_receptionist_navigation(events, ready, 11500)
        self.assertEqual(self.t.state['history'], original['history'])
        self.assertEqual(self.t.state['step'], 1)
        self.assertEqual(self.t.plan(snap)['type'], 'npc_script')
        self.assertEqual(self.t.state['recoveries'][0]['request_ids'], ['c2', 'c3'])

    def test_reconcile_receptionist_warp_preserves_result_and_rejects_uncertainty(self):
        self.t.state.update(step=1, instance=2, status='blocked', reason='reward_mismatch:receptionist',
                            recoveries=[{'session': 'old'}])
        warp = {'map': 'new_1-2', 'x': 100, 'y': 70, 'elapsed_ms': 4661}
        before = {'map': 'new_2-2', 'zeny': 0, 'inventory': '1201:1,2301:1', 'exp': '1,0,1,0'}
        after = {'map': 'new_1-2', 'zeny': 0, 'inventory': '', 'exp': '1,0,1,0'}
        action = {'type': 'npc_script', 'x': 100, 'y': 29, 'choices': ['Apply for training.'],
                  'name_reply': 1, 'timeout_s': 60, 'expect': {'map': 'new_1-2', 'x': 100, 'y': 70}}
        ev = {'npc': 'Receptionist#nv2', 'chosen': ['Apply for training.'], 'name_sent': 1,
              'warped': warp, 'before': before, 'after': after}
        self.t.state['history'] = [{'step': 1, 'action': action, 'request_id': 'c_1', 'session': 'old',
                                    'result': {'request_id': 'c_1', 'status': 'completed', 'reason': 'warped', 'evidence': ev}}]
        self.t.state['steps_done'] = [{'step': 'receptionist', 'items': {'1201': -1, '2301': -1}, 'warp': warp}]
        items = [{'name_id': 1201, 'amount': 1}, {'name_id': 2301, 'amount': 1}]
        snap = nilo(map='new_1-2', position={'x': 100, 'y': 70}, destination={'x': 100, 'y': 70},
                    connected=True, inventory_ready=True, inventory_truncated=0, inventory=items, dead=False,
                    native_task=None, navigation=None, ai_queue=[], zeny=0)
        events = [{'session': 'new', 'time_ms': t, 'data': copy.deepcopy(snap)} for t in (10000, 11000)]
        ready = {'session': 'new', 'time_ms': 9999, 'data': {'pending_request_id': None}}
        original = copy.deepcopy(self.t.state)
        for kind in ('identity', 'map', 'cause', 'stale', 'task', 'movement', 'inflight', 'history',
                     'pending', 'session', 'inventory', 'truncated', 'zeny', 'unstable', 'warp', 'exp'):
            with self.subTest(kind=kind):
                self.t.state = copy.deepcopy(original)
                obs, rd, now = copy.deepcopy(events), copy.deepcopy(ready), 11500
                if kind == 'identity': obs[0]['data']['name'] = 'Other'
                if kind == 'map': obs[0]['data']['map'] = 'prontera'
                if kind == 'cause': self.t.state['reason'] = 'other'
                if kind == 'stale': now = 20000
                if kind == 'task': obs[1]['data']['native_task'] = {'id': 'x'}
                if kind == 'movement': obs[1]['data']['destination']['y'] = 71
                if kind == 'inflight': self.t.state['inflight'] = {'request_id': 'x'}
                if kind == 'history': self.t.state['history'][-1]['result']['status'] = 'unknown'
                if kind == 'pending': rd['data']['pending_request_id'] = 'x'
                if kind == 'session': obs[1]['session'] = 'other'
                if kind == 'inventory': obs[1]['data']['inventory'].append({'name_id': 501, 'amount': 1})
                if kind == 'truncated': obs[1]['data']['inventory_truncated'] = 1
                if kind == 'zeny': obs[1]['data']['zeny'] = 1
                if kind == 'unstable': obs[1]['data']['inventory'].reverse()
                if kind == 'warp': self.t.state['history'][-1]['result']['evidence']['warped']['x'] = 99
                if kind == 'exp': obs[1]['data']['level']['exp'] = 1
                with self.assertRaises(RuntimeError): self.t.reconcile_receptionist_warp(obs, rd, now)
        self.t.state = copy.deepcopy(original)
        self.t.reconcile_receptionist_warp(events, ready, 11500)
        self.assertEqual(self.t.state['history'], original['history'])
        self.assertEqual(self.t.state['steps_done'][0], original['steps_done'][0])
        self.assertEqual((self.t.state['step'], self.t.state['status']), (2, 'active'))
        self.assertEqual(self.t.plan(snap)['type'], 'portal')

    def test_full_path_to_the_chosen_town(self):
        gifts = self.walk_to_decision()
        opts = tutorial.destinations(nilo(), SCRIPT, TABLES, BUILDS)
        self.assertEqual([o['job'] for o in opts if o['offered']], ['Swordsman', 'Acolyte'])
        with self.assertRaises(RuntimeError):
            self.t.decide(next(o for o in opts if o['job'] == 'Thief'), {})
        self.t.decide(next(o for o in opts if o['job'] == 'Swordsman'), {'decision': 'planner', 'reason': 'Melee build.'})
        a = self.t.plan(self.npc('hanson'))
        self.assertEqual(a['choices'], ["I'll take the course."] + SCRIPT['personality_answers'] + ['My own choice!', 'Swordsman'])
        self.assertEqual(a['expect'], {'map': 'izlude_in', 'x': 74, 'y': 167})
        self.t.prepare(a, 'h', 'boot:1')
        after = gifts + ',2305:1,501:4,503:2,506:2,7059:5,7060:5'
        self.t.result({'request_id': 'h', 'status': 'completed', 'reason': 'warped',
                       'evidence': evidence(before=gifts, after=after, warped={'map': 'izlude_in', 'x': 74, 'y': 167})})
        s = self.t.state
        self.assertEqual((s['status'], s['reason'], s['destination']['town']), ('complete', 'tutorial_left', 'izlude'))
        self.assertEqual(s['steps_done'][-1]['items'], {'2305': 1, '501': 4, '503': 2, '506': 2, '7059': 5, '7060': 5})
        self.assertEqual(Tutorial(self.path, 'Nilo').state['status'], 'complete')  # Checkpointed.

    def test_reward_mismatch_and_undeclared_warp_stop_for_review(self):
        self.act(nilo())
        self.act(self.npc('receptionist'), ev=evidence(warped={'map': 'new_1-2', 'x': 100, 'y': 70}))
        self.act(nilo(map='new_1-2', position={'x': 100, 'y': 70}), ev={'map': 'new_1-2', 'pos_to': {'x': 41, 'y': 172}})
        self.act(self.npc('helper'), ev=evidence())
        self.act(self.npc('entrance_guard'), ev=evidence(after='1201:1,2301:1,569:300',
                                                         warped={'map': 'new_1-3', 'x': 96, 'y': 21}))
        self.assertEqual(self.t.state['reason'], 'reward_mismatch:entrance_guard')
        other = Tutorial(Path(self.path.parent)/'b.json', 'Nilo')
        self.t = other
        self.act(nilo())
        self.act(self.npc('receptionist'), status='unknown', reason='unexpected_warp',
                 ev=evidence(warped={'map': 'prontera', 'x': 1, 'y': 1}))
        self.assertEqual((other.state['status'], other.state['reason']), ('blocked', 'npc_script:unknown/unexpected_warp'))

    def test_unconfirmed_inventory_after_warp_blocks_without_advancing(self):
        self.act(nilo())
        action = self.t.plan(self.npc('receptionist'))
        self.t.prepare(action, 'warp', 'boot:1')
        self.t.result({'request_id': 'warp', 'status': 'unknown', 'reason': 'warp_inventory_unconfirmed',
                       'evidence': {'warped': {'map': 'new_1-2', 'x': 100, 'y': 70},
                                    'observation_complete': 0, 'after': {'inventory': None}}})
        self.assertEqual((self.t.state['status'], self.t.state['step'], self.t.state['reason']),
                         ('blocked', 1, 'npc_script:unknown/warp_inventory_unconfirmed'))
        self.assertEqual(self.t.state['history'][-1]['result']['evidence']['warped']['map'], 'new_1-2')

    def test_failed_dialog_retries_once_then_blocks_and_wrong_places_block(self):
        self.act(nilo())
        self.act(self.npc('receptionist'), status='failed', reason='unexpected_menu', ev=evidence())
        self.assertEqual(self.t.state['status'], 'active')
        self.act(self.npc('receptionist'), status='failed', reason='unexpected_menu', ev=evidence())
        self.assertEqual(self.t.state['reason'], 'two_consecutive_action_failures')
        t = Tutorial(self.path.parent/'c.json', 'Nilo')
        self.assertIsNone(t.plan(nilo(map='prontera')))
        self.assertEqual(t.state['reason'], 'not_at_a_training_start')
        t = Tutorial(self.path.parent/'d.json', 'Nilo')
        t.plan(nilo())
        t.state['step'] = 1
        self.assertIsNone(t.plan(nilo(map='new_3-2', position={'x': 100, 'y': 27})))
        self.assertEqual(t.state['reason'], 'npc_not_seen:receptionist')

    def test_identity_and_inflight_are_respected(self):
        self.assertIsNone(self.t.plan(nilo(name='Tarin')))
        self.assertEqual(self.t.state['reason'], 'identity_or_executor_mismatch')
        with self.assertRaises(ValueError):
            Tutorial(self.path, 'Tarin')


class DestinationTests(unittest.TestCase):
    def test_options_reject_unreachable_towns_with_reasons(self):
        opts = {o['job']: o for o in tutorial.destinations(nilo(), SCRIPT, TABLES, BUILDS)}
        self.assertEqual(opts['Swordsman']['fields'][0], 'prt_fild08')
        self.assertTrue(opts['Swordsman']['build_for_job'])
        self.assertTrue(opts['Acolyte']['build_for_job'])
        for option in opts.values():
            if option['offered']:
                self.assertTrue(option['build_for_job'])
                self.assertTrue(option['fields'])
                for place in (option['town'], option['landing']['map'], *option['fields']):
                    self.assertTrue(tutorial.supply_route(tutorial.hunting.walk_table(TABLES), place))
        self.assertIn('no_supply_route:morocc', opts['Thief']['rejected'])
        self.assertEqual(tutorial.fallback_choice(list(opts.values()), 'Nilo')['offered'], True)

    def test_planner_schema_prompt_and_validation(self):
        opts = tutorial.destinations(nilo(), SCRIPT, TABLES, BUILDS)
        service = Service({'job': 'Swordsman', 'reason': 'Melee build and fields near Izlude.'})
        planner = DestinationPlanner(service)
        planner.request({'level': {'base': 1, 'job': 1}}, opts, 'explorer')
        result = planner.poll()
        self.assertEqual((result['status'], result['proposal']['job']), ('proposed', 'Swordsman'))
        (identity, messages, seed), kwargs = service.calls[0]
        self.assertEqual(kwargs['response_format']['properties']['job']['enum'], ['Swordsman', 'Acolyte'])
        self.assertNotIn('Nilo', messages[1]['content'])
        self.assertLess(sum(len(m['content']) for m in messages), 5000)
        with self.assertRaises(ValueError):
            validate_destination({'job': 'Thief', 'reason': 'x'}, opts)
        for service in (Service({'job': 'Thief', 'reason': 'x'}), Service(error='RoleUnavailable')):
            planner = DestinationPlanner(service)
            planner.request({}, opts, 'explorer')
            self.assertEqual(planner.poll()['status'], 'failed')


class HandOffTests(unittest.TestCase):
    """The runner drives the tutorial to its decision, then the cycle starts with no field."""
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)

    def at_decision(self):
        t = Tutorial(self.directory/'tutorial.json', 'Nilo')
        t.state.update(instance=1, step=next(i for i, s in enumerate(SCRIPT['steps']) if s['id'] == 'destination'))
        t.save()
        return t

    def drive(self, service):
        t = self.at_decision()
        step = next(s for s in SCRIPT['steps'] if s['id'] == 'hanson')
        snap = nilo(map='new_1-4', position=step['stand'], npcs=[{'name': 'Hanson', 'x': 100, 'y': 29}])
        bridge = ControlledBridge(snap)
        bridge.events.insert(0, {'kind': 'ready', 'data': {'next_serial': bridge.next_serial}})
        runner = Runner(t, bridge, self.directory, p5=TutorialPlanning(t, service, TABLES, BUILDS))
        runner.inventory_session, runner.inventory_ready_after = bridge.session, 0
        with patch.object(runner, 'resource_guard'):
            out = runner.run(.05, max_actions=1)
        return t, bridge, out

    def test_planner_choice_reaches_hanson(self):
        t, bridge, out = self.drive(Service({'job': 'Acolyte', 'reason': 'Prontera has the shop and three fields.'}))
        done = t.state['steps_done'][-1]
        self.assertEqual((done['decision'], done['job'], done['reason']),
                         ('planner', 'Acolyte', 'Prontera has the shop and three fields.'))
        self.assertEqual(bridge.proposals[0][0]['choices'][-1], 'Acolyte')
        self.assertEqual(bridge.proposals[0][0]['expect'], {'map': 'prt_church', 'x': 172, 'y': 19})
        self.assertEqual(out['inference_calls'], 1)
        kinds = [json.loads(l)['kind'] for l in (self.directory/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertIn('destination_result', kinds)

    def test_failed_planner_uses_marked_local_fallback(self):
        t, bridge, out = self.drive(Service(error='RoleUnavailable'))
        done = t.state['steps_done'][-1]
        self.assertEqual(done['decision'], 'local_fallback')
        self.assertIn(done['job'], ('Swordsman', 'Acolyte'))
        self.assertTrue(done['reason'].startswith('planner failed'))

    def test_destination_constrains_build_choices(self):
        p5 = {'tables': TABLES, 'equipment': build_policy.load_equipment(), 'build': None}
        cycle = SoloCycle(self.directory/'state.json', 1, p5, 'Nilo')
        for target, expected in (('Swordman', 'novice-swordman'), ('Acolyte', 'novice-acolyte')):
            planning = P5Planning(cycle, Service({}), self.directory, target)
            self.assertEqual(list(planning.builds), [expected])

    def test_cycle_for_a_new_character_waits_for_its_own_field(self):
        p5 = {'tables': TABLES, 'equipment': build_policy.load_equipment(), 'build': None}
        cycle = SoloCycle(self.directory/'state.json', 6, p5, 'Nilo')
        self.assertIsNone(cycle.state['field']['id'])
        snap = nilo(map='izlude_in', position={'x': 74, 'y': 167}, inventory_truncated=0)
        self.assertIsNone(cycle.plan(snap))  # No build yet: nothing to spend, no field: wait.
        self.assertEqual(cycle.state['status'], 'active')
        self.assertEqual(cycle.field_due(snap), 'no_decision')
        with self.assertRaises(ValueError):
            SoloCycle(self.directory/'state.json', 6, p5, 'Tarin')
        (self.directory/'build.json').write_text(json.dumps({'build_id': 'novice-swordman'}), encoding='utf-8')
        service = Service({'field_id': 'prt_fild08', 'reason': 'Porings and Lunatics, two hops.'})
        planning = P5Planning(cycle, service, self.directory)
        bridge = ControlledBridge(snap)
        bridge.events.insert(0, {'kind': 'ready', 'data': {'next_serial': bridge.next_serial}})
        runner = Runner(cycle, bridge, self.directory, p5=planning)
        runner.inventory_session, runner.inventory_ready_after = bridge.session, 0
        with patch.object(runner, 'resource_guard'):
            runner.run(.05, max_actions=1)
        self.assertEqual(bridge.proposals[0][0]['type'], 'stat_up')  # The build spends its 48 points first.
        kinds = [json.loads(l)['kind'] for l in (self.directory/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertNotIn('field_proposal', kinds)  # Danger is judged after the starting points are spent.
        self.assertEqual((service.calls, cycle.state['field_decisions']), ([], []))
        # Points spent (simulated): the same decision is applied and the cycle travels there.
        snap = nilo(map='izlude_in', position={'x': 74, 'y': 167}, inventory_truncated=0)
        snap['progress'].update(points_free=0, stats={**snap['progress']['stats'], 'str': {'value': 9, 'cost': 2},
                                                      'vit': {'value': 9, 'cost': 2}})
        cycle.state['inflight'] = None
        cycle.save()
        planning = P5Planning(cycle, Service({'field_id': 'prt_fild08', 'reason': 'Porings, two hops.'}), self.directory)
        bridge = ControlledBridge(snap)
        bridge.events.insert(0, {'kind': 'ready', 'data': {'next_serial': bridge.next_serial}})
        runner = Runner(cycle, bridge, self.directory, p5=planning)
        runner.inventory_session, runner.inventory_ready_after = bridge.session, 0
        with patch.object(runner, 'resource_guard'):
            runner.run(.05, max_actions=1)
        decision = cycle.state['field_decisions'][-1]
        self.assertEqual((decision['decision'], decision['field_id'], decision['previous']), ('change', 'prt_fild08', None))
        self.assertEqual(bridge.proposals[0][0]['type'], 'travel')
        self.assertEqual(bridge.proposals[0][0]['map'], 'prt_fild08')


if __name__ == '__main__':
    unittest.main()
