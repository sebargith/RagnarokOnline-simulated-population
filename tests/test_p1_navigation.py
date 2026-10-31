import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]

# Recorded states exercised against the real Perl contract module.
SCRIPT = r'''
use JSON::PP;
use M1Navigation;
my $ctx = sub { my %o = @_; {manual_ai => 1, hp => 40, map => 'prontera', width => 312, height => 392,
    walkable => sub { $_[0] != 10 }, pos_to => {x => 150, y => 180}, %o} };
my $nav = sub { my %o = @_; {type => 'navigate', map => 'prontera', x => 156, y => 191, timeout_s => 60, %o} };
my %v = (
    valid => M1Navigation::validate($nav->(), $ctx->()),
    extra_key => M1Navigation::validate({%{$nav->()}, speed => 2}, $ctx->()),
    text_coord => M1Navigation::validate($nav->(x => '1e3'), $ctx->()),
    short_timeout => M1Navigation::validate($nav->(timeout_s => 4), $ctx->()),
    long_timeout => M1Navigation::validate($nav->(timeout_s => 301), $ctx->()),
    legacy_owner => M1Navigation::validate($nav->(), $ctx->(manual_ai => 0)),
    dead => M1Navigation::validate($nav->(), $ctx->(hp => 0)),
    cross_map => M1Navigation::validate($nav->(map => 'geffen'), $ctx->()),
    bounds => M1Navigation::validate($nav->(x => 312), $ctx->()),
    wall => M1Navigation::validate($nav->(x => 10), $ctx->()),
    here => M1Navigation::validate($nav->(x => 150, y => 180), $ctx->()),
);
my $at = {map => 'prontera', dest_map => 'prontera', pos_to => {x => 156, y => 191},
    calc => {x => 155, y => 191}, dest => {x => 156, y => 191}};
my %o = (
    running => [M1Navigation::outcome('running', undef, $at)],
    arrived => [M1Navigation::outcome('done', undef, $at)],
    coasting => [M1Navigation::outcome('done', undef, {%$at, calc => {x => 150, y => 186}})],
    short => [M1Navigation::outcome('done', undef, {%$at, pos_to => {x => 154, y => 191}})],
    map_changed => [M1Navigation::outcome('done', undef, {%$at, map => 'prt_fild08'})],
    too_long => [M1Navigation::outcome('done', {code => 0}, $at)],
    no_route => [M1Navigation::outcome('done', {code => 1}, $at)],
    stuck => [M1Navigation::outcome('done', {code => 2}, $at)],
    unexpected => [M1Navigation::outcome('done', {code => 3}, $at)],
    stopped => [M1Navigation::outcome('stopped', undef, $at)],
    lost => [M1Navigation::outcome('missing', undef, $at)],
);
print JSON::PP->new->canonical->encode({validate => \%v, outcome => \%o});
'''


class NavigationContractTests(unittest.TestCase):
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

    def test_admission(self):
        self.assertEqual(self.data['validate'], {
            'valid': None, 'extra_key': 'invalid_navigate', 'text_coord': 'invalid_navigate',
            'short_timeout': 'invalid_timeout', 'long_timeout': 'invalid_timeout',
            'legacy_owner': 'executor_not_native', 'dead': 'dead',
            'cross_map': 'cross_map_not_supported', 'bounds': 'out_of_bounds',
            'wall': 'not_walkable', 'here': 'already_at_destination'})

    def test_outcomes_never_invent_arrival(self):
        self.assertEqual(self.data['outcome'], {
            'running': [], 'arrived': ['completed', 'arrived'],
            'coasting': ['unknown', 'route_ended_off_target'],
            'short': ['unknown', 'route_ended_off_target'],
            'map_changed': ['unknown', 'map_changed'],
            'too_long': ['failed', 'timeout'], 'no_route': ['failed', 'unreachable'],
            'stuck': ['failed', 'blocked'], 'unexpected': ['unknown', 'route_error'],
            'stopped': ['unknown', 'route_task_stopped'], 'lost': ['unknown', 'route_task_lost']})


if __name__ == '__main__':
    unittest.main()
