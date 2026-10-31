from collections import deque
import gzip
from pathlib import Path
import struct
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from agent.field import FieldController, Geometry, FIELD, segment


class FieldTests(unittest.TestCase):
    def geometry(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'map.gz'
            path.write_bytes(gzip.compress(struct.pack('<HH', len(rows[0]), len(rows))+bytes(v for row in rows for v in row)))
            return Geometry(path)

    def test_obstacle_and_occupied_detour_no_corner_cut(self):
        geometry = self.geometry([[1]*5, [1, 0, 1, 1, 1], [1]*5, [1]*5])
        path = geometry.path((0, 0), (4, 0), {(2, 0)})
        self.assertNotIn((2, 0), path)
        self.assertNotIn((1, 1), path)
        self.assertEqual(path[-1], (4, 0))
        for a, b in zip(path, path[1:]):
            if a[0] != b[0] and a[1] != b[1]:
                self.assertTrue(geometry.walkable((a[0], b[1])))
                self.assertTrue(geometry.walkable((b[0], a[1])))
        self.assertEqual(segment([(x, 0) for x in range(20)]), (8, 0))
        self.assertEqual(segment([(0, 0), (1, 0), (1, 1)]), (1, 0))
        straight = self.geometry([[1]*10 for _ in range(10)])
        self.assertEqual(straight.path((5, 9), (5, 0)), [(5, y) for y in range(9, -1, -1)])

    def test_unreachable_geometry_fails(self):
        geometry = self.geometry([[1, 0, 1]])
        with self.assertRaises(RuntimeError):
            geometry.path((0, 0), (2, 0))

    def test_configured_return_enters_walkable_warp_edge(self):
        root = Path(__file__).resolve().parents[2]
        path = root/'vendor/openkore/fields/prt_fild08.fld2.gz'
        if not path.exists():
            self.skipTest('Installed static map unavailable')
        geometry = Geometry(path)
        self.assertFalse(geometry.walkable((170, 378)))
        self.assertEqual(geometry.path((168, 357), (170, 376))[-1], (170, 376))

    def controller(self):
        c = FieldController.__new__(FieldController)
        c.events = deque()
        c.bridges = {a: SimpleNamespace(session='epoch1') for a in ('agent', 'peer')}
        c.data = Mock(return_value={'map': FIELD, 'hp': 500, 'hp_max': 500,
                                  'destination': {'x': 170, 'y': 350}, 'monsters': []})
        c.walk_to = Mock()
        c.pump = Mock()
        c.action = Mock()
        return c

    def test_eligibility_uses_only_local_perception_and_health(self):
        c = self.controller()
        data = c.data.return_value
        data['monsters'] = [{'id': 'a', 'name_id': 1002, 'x': 170, 'y': 351},
                            {'id': 'b', 'name_id': 1002, 'x': 195, 'y': 350},
                            {'id': 'c', 'name_id': 1008, 'x': 170, 'y': 351}]
        self.assertEqual([m['id'] for m in c.eligible('agent')], ['a'])
        data['hp'] = 100
        self.assertEqual(c.eligible('agent'), [])
        data['hp'] = 0
        with self.assertRaises(RuntimeError):
            c.eligible('agent')

    def test_shared_target_requires_both_perceptions(self):
        c = self.controller()
        c.eligible = lambda who: [{'id': who, 'name_id': 1002}]
        with self.assertRaises(RuntimeError):
            c.search_target(('agent', 'peer'))
        self.assertFalse(c.action.called)
        self.assertEqual(c.walk_to.call_count, 14)

    def test_encounter_abandons_missing_or_changed_epoch_without_attack(self):
        for epoch_changed in (False, True):
            c = self.controller()
            c.search_target = lambda actors: {'id': 'a', 'name': 'Poring', 'name_id': 1002}
            if epoch_changed:
                c.bridges['agent'].session = 'new'
                # Change after the encounter has captured its original epoch.
                c.healthy = lambda who: setattr(c.bridges[who], 'session', 'changed') or True
            with self.assertRaises(RuntimeError):
                c.field_encounter(False)
            self.assertFalse(c.action.called)

    def test_agreement_must_be_received_from_expected_speaker(self):
        c = self.controller()
        c.events.append({'agent_id': 'peer', 'kind': 'chat', 'time_ms': 100,
                         'data': {'self': 0, 'speaker': 'Visitor', 'text': 'goal'}})
        self.assertFalse(c.perceived_chat('peer', 'M4 Alden', 'goal', 90))
        c.events[-1]['data']['speaker'] = 'M4 Alden'
        self.assertTrue(c.perceived_chat('peer', 'M4 Alden', 'goal', 90))
        self.assertFalse(c.perceived_chat('peer', 'M4 Alden', 'goal', 101))

    def test_fourth_approach_move_gets_a_final_range_check(self):
        c = self.controller()
        data = c.data.return_value
        data.update(destination={'x': 0, 'y': 0}, players=[],
                    monsters=[{'id': 'a', 'name_id': 1002, 'x': 5, 'y': 0}])
        c.geometry = {FIELD: SimpleNamespace(path=lambda start, *args, **kw: [start, (start[0]+1, 0)])}
        def move(who, x, y):
            data['destination'] = {'x': x, 'y': y}
        c.walk_to.side_effect = move
        c.approach('agent', 'a')
        self.assertEqual(c.walk_to.call_count, 4)
        self.assertEqual(data['destination'], {'x': 4, 'y': 0})

    def test_town_recovery_does_not_send_untouched_peer_to_gate(self):
        c = self.controller()
        c.data.return_value['map'] = 'prontera'
        c.home('peer')
        c.walk_to.assert_called_once_with('peer', 153, 180)

    def test_reconnect_during_approach_cannot_authorize_old_target(self):
        c = self.controller()
        c.search_target = lambda actors: {'id': 'a', 'name': 'Poring', 'name_id': 1002}
        c.approach = lambda *args: setattr(c.bridges['agent'], 'session', 'new-epoch')
        c.submit = Mock()
        with self.assertRaisesRegex(RuntimeError, 'epoch changed during approach'):
            c.field_encounter(False)
        c.submit.assert_not_called()

    def test_peer_rendezvous_leaves_room_for_leader(self):
        c = self.controller()
        c.outbound('peer')
        c.walk_to.assert_called_once_with('peer', 170, 366, within=2)
