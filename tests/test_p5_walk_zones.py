"""Walk reachability inside maps (P5 walk zones), on the pinned OpenKore data.

Regression for resume-20261101-unique-1: travel c_384 planned prontera -> prt_castle ->
prt_gld -> prt_fild01 and failed/unreachable at prt_castle (102,20), because the plan
only knew that the castle's exit portal (102,181) exists, not that it cannot be walked
to from where the entrance lands.
"""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from agent import hunting, walk

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT.parent/'vendor/openkore'
HAVE_DATA = (VENDOR/'fields/prt_castle.fld2.gz').exists() and (VENDOR/'tables/portals.txt').exists()
SHOP = {'x': 104, 'y': 51}

# Real OpenKore portals table and field files through the Perl contract module.
SCRIPT = r'''
use JSON::PP;
use IO::Uncompress::Gunzip qw(gunzip);
use FileParsers;
use M1Travel;
my ($root, $vendor) = @ARGV;
my %lut;
FileParsers::parsePortals("$vendor/tables/portals.txt", \%lut);
open my $fh, '<:raw', "$root/config/walk-zones.json" or die; local $/; my $doc = decode_json(<$fh>); close $fh;
my $zones = M1Travel::zone_table($doc);
my $g = M1Travel::walk_graph(\%lut, $zones);
my %grid;
my $walkable = sub {
    my ($map) = @_;
    unless ($grid{$map}) { gunzip("$vendor/fields/$map.fld2.gz" => \my $raw) or die; $grid{$map} = $raw }
    my $raw = $grid{$map};
    my ($w, $h) = unpack 'vv', substr($raw, 0, 4);
    sub { my ($x, $y) = @_; $x >= 0 && $y >= 0 && $x < $w && $y < $h && ord(substr($raw, 4 + $y * $w + $x, 1)) & 1 };
};
my $zone = sub { my ($map, $x, $y) = @_; M1Travel::zone_at($zones->{anchors}{$map} || {}, $walkable->($map), {x => $x, y => $y}) };
my $route = sub {
    my ($from, $fx, $fy, $to, $tx, $ty) = @_;
    my ($legs, $why) = M1Travel::route($g, $from, {x => $fx, y => $fy}, $to, {x => $tx, y => $ty},
        {zones => 1, start_zone => $zone->($from, $fx, $fy), dest_zone => $zone->($to, $tx, $ty)});
    $legs ? {legs => $legs} : {reason => $why};
};
my %edges;
for my $map (keys %$g) { $edges{"$map $_->{x} $_->{y} $_->{to_map} $_->{to}{x} $_->{to}{y}"} = [$_->{zone}, $_->{to_zone}] for @{$g->{$map}} }
print JSON::PP->new->canonical->encode({
    edges => \%edges,
    castle_entrance => $zone->('prt_castle', 102, 20), castle_exit => $zone->('prt_castle', 102, 181),
    castle_to_gld => $route->('prt_castle', 102, 20, 'prt_gld', 159, 30),
    c_384 => $route->('prontera', 156, 352, 'prt_fild01', 49, 331),
    to_fild08 => $route->('prontera', 104, 51, 'prt_fild08', 178, 367),
    from_fild08 => $route->('prt_fild08', 178, 367, 'prontera', 104, 51),
    to_fild06 => $route->('prontera', 104, 51, 'prt_fild06', 33, 186),
    to_fild05 => $route->('prontera', 104, 51, 'prt_fild05', 363, 200),
    from_fild05 => $route->('prt_fild05', 130, 298, 'prontera', 104, 51),
    to_izlude => $route->('prontera', 104, 51, 'izlude', 93, 104),
    isolated_start => $route->('prt_castle', 199, 0, 'prontera', 104, 51),
    isolated_dest => $route->('prontera', 104, 51, 'prt_castle', 199, 0),
});
'''


@unittest.skipUnless(HAVE_DATA, 'pinned OpenKore data absent')
class WalkZoneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.walk = walk.load()
        perl = ROOT.parent/'vendor/strawberry-perl/perl/bin/perl.exe'
        perl = str(perl) if perl.exists() else shutil.which('perl')
        if not perl:
            raise unittest.SkipTest('Perl unavailable')
        result = subprocess.run([perl, '-I'+str(ROOT/'bridge/lib'), '-I'+str(VENDOR/'src'), '-I'+str(VENDOR/'src/deps'),
                                 '-e', SCRIPT, str(ROOT), str(VENDOR)], capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.perl = json.loads(result.stdout)

    def test_castle_exit_is_not_walkable_from_the_entrance(self):
        here = walk.zone_at(self.walk, 'prt_castle', (102, 20))
        self.assertNotEqual(here, walk.zone_at(self.walk, 'prt_castle', (102, 181)))
        self.assertNotEqual(self.perl['castle_entrance'], self.perl['castle_exit'])
        self.assertEqual(self.perl['castle_entrance'], here)
        # Walking only (no inner door), prt_gld is unreachable from the entrance zone.
        no_doors = dict(self.walk, edges={k: [e for e in v if e[2] != k[0]] for k, v in self.walk['edges'].items()})
        self.assertIsNone(walk.route(no_doors, 'prt_castle', 'prt_gld', here))

    def test_castle_route_goes_through_its_inner_doors(self):
        legs = self.perl['castle_to_gld']['legs']
        self.assertEqual([(l['map'], l['x'], l['y'], l.get('to_map')) for l in legs], [
            ('prt_castle', 102, 73, 'prt_castle'), ('prt_castle', 102, 129, 'prt_castle'),
            ('prt_castle', 102, 181, 'prt_gld'), ('prt_gld', 159, 30, None)])
        self.assertEqual(legs[0]['to'], {'x': 102, 'y': 88})
        r = walk.route(self.walk, 'prt_castle', 'prt_gld', walk.zone_at(self.walk, 'prt_castle', (102, 20)))
        self.assertEqual((r['hops'], r['inner']), (1, 2))

    def test_c_384_destination_now_avoids_the_castle(self):
        legs = self.perl['c_384']['legs']
        self.assertNotIn('prt_castle', [l['map'] for l in legs])
        self.assertEqual(legs[-1], {'map': 'prt_fild01', 'x': 49, 'y': 331})

    def test_live_verified_routes_stay_valid(self):
        p = self.perl
        self.assertEqual([l['map'] for l in p['to_fild08']['legs']], ['prontera', 'prt_fild08'])
        self.assertEqual([l['map'] for l in p['from_fild08']['legs']], ['prt_fild08', 'prontera'])
        self.assertEqual([l['map'] for l in p['to_fild06']['legs']], ['prontera', 'prt_fild06'])
        self.assertEqual([l['map'] for l in p['to_fild05']['legs']], ['prontera', 'prt_fild05'])
        self.assertEqual([l['map'] for l in p['from_fild05']['legs']], ['prt_fild05', 'prontera'])
        self.assertEqual([l['map'] for l in p['to_izlude']['legs']], ['prontera', 'prt_fild08', 'izlude'])
        self.assertEqual(p['to_fild08']['legs'][0], {'map': 'prontera', 'x': 156, 'y': 22, 'to_map': 'prt_fild08'})

    def test_routes_without_a_walk_path_are_rejected_with_a_reason(self):
        self.assertEqual(walk.zone_at(self.walk, 'prt_castle', (199, 0)), walk.ISOLATED)
        self.assertEqual(self.perl['isolated_start'], {'reason': 'start_isolated'})
        self.assertEqual(self.perl['isolated_dest'], {'reason': 'destination_unreachable'})
        self.assertIsNone(walk.route(self.walk, 'prt_castle', 'prontera', walk.ISOLATED))

    def test_perl_graph_matches_the_table_and_python_routes(self):
        table = {' '.join(map(str, p[:6])): p[6:] for p in json.loads(walk.ZONES.read_text(encoding='utf-8'))['portals']}
        self.assertEqual(self.perl['edges'], table)
        for name, start, goal in (('to_fild05', ('prontera', 104, 51), ('prt_fild05', 363, 200)),
                                  ('to_izlude', ('prontera', 104, 51), ('izlude', 93, 104)),
                                  ('castle_to_gld', ('prt_castle', 102, 20), ('prt_gld', 159, 30))):
            r = walk.route(self.walk, start[0], goal[0], walk.zone_at(self.walk, start[0], start[1:]),
                           walk.zone_at(self.walk, goal[0], goal[1:]))
            self.assertEqual([n[0] for n in r['nodes']], [l['map'] for l in self.perl[name]['legs']], name)

    def test_field_options_are_reachable_on_foot(self):
        from test_p5_hunting import EQUIPMENT, TABLES, tarin
        isolated, _ = hunting.options(tarin(map='prt_castle', position={'x': 199, 'y': 0}), 'prt_fild05',
                                      TABLES, EQUIPMENT, {}, 'Nilo', 0)
        self.assertEqual([o['field_id'] for o in isolated], ['prt_fild05'])  # Only keeping the current field.
        opts, _ = hunting.options(tarin(map='prt_castle', position={'x': 102, 'y': 20}), 'prt_fild05',
                                  TABLES, EQUIPMENT, {}, 'Nilo', 0)
        start = walk.zone_at(self.walk, 'prt_castle', (102, 20))
        shop = walk.zone_at(self.walk, 'prontera', (SHOP['x'], SHOP['y']))
        for o in opts:
            if o['current']:
                continue
            zone = walk.zone_at(self.walk, o['field_id'], (o['entry']['x'], o['entry']['y']))
            self.assertTrue(walk.route(self.walk, 'prt_castle', o['field_id'], start, zone), o['field_id'])
            self.assertTrue(walk.route(self.walk, o['field_id'], 'prontera', zone, shop), o['field_id'])
            self.assertTrue(walk.route(self.walk, 'prontera', o['field_id'], shop, zone), o['field_id'])

    def test_regeneration_is_identical(self):
        from scripts import build_walk_zones
        self.assertEqual(json.loads(json.dumps(build_walk_zones.build())),
                         json.loads(walk.ZONES.read_text(encoding='utf-8')))


if __name__ == '__main__':
    unittest.main()
