import copy
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from agent.solo_cycle import SoloCycle
from scripts.run_p2_cycle import Runner


def snapshot(**changes):
    s = dict(connected=True, name='Tarin', executor='openkore_route', inventory_ready=True,
        inventory_truncated=False, inventory=[dict(name_id=1201, amount=1, type=5, equipped=1)],
        native_task=None, recovery='none', dead=False, hp=50, hp_max=57,
        map='prt_fild08', position={'x': 170, 'y': 250}, zeny=10, weight=10, weight_max=2000,
        monsters=[dict(id='01000000', x=171, y=250)], ground_items=[])
    s.update(changes)
    return s


class CycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'state.json'
        self.c = SoloCycle(self.path, 1)
        self.serial = 0

    def finish(self, action, reason, status='completed'):
        self.serial += 1
        rid = f'c_{self.serial}'
        self.c.prepare(action, rid, 'boot:1', now=100)
        result = dict(request_id=rid, status=status, reason=reason)
        self.c.result(result, now=101)
        return result

    def test_quiet_attack_reconciliation_never_claims_or_replays_kill(self):
        self.c.state['macro_goal'] = 'train_first_job'
        action = {'type': 'attack', 'target': '01000000', 'timeout_s': 45}
        self.c.prepare(action, 'c_1', 'boot:1', now=100)
        result = {'request_id': 'c_1', 'status': 'unknown', 'reason': 'attack_ended',
                  'evidence': {'hits': 0, 'damage_dealt': 0}}
        self.c.result(result, now=101)
        snap = snapshot(position={'x': 170, 'y': 250}, destination={'x': 170, 'y': 250}, ai_queue=[])
        observations = [{'session': 'boot:1', 'time_ms': t, 'data': copy.deepcopy(snap)} for t in (10000, 11000)]
        bad = copy.deepcopy(observations)
        bad[1]['data']['native_task'] = {'kind': 'attack'}
        with self.assertRaises(RuntimeError): self.c.reconcile_quiet_attack(bad, 11000)
        bad = copy.deepcopy(observations)
        bad[1]['session'] = 'other:1'
        with self.assertRaises(RuntimeError): self.c.reconcile_quiet_attack(bad, 11000)
        self.c.state['history'][-1]['result']['evidence']['hits'] = 1
        with self.assertRaises(RuntimeError): self.c.reconcile_quiet_attack(observations, 11000)
        self.c.state['history'][-1]['result']['evidence']['hits'] = 0
        self.c.state['history'].append(copy.deepcopy(self.c.state['history'][-1]))
        self.c.state['history'][-1]['result']['reason'] = 'other'
        with self.assertRaises(RuntimeError): self.c.reconcile_quiet_attack(observations, 11000)
        self.c.state['history'][-1] = copy.deepcopy(self.c.state['history'][-2])
        self.c.reconcile_quiet_attack(observations, 11000)
        self.assertEqual(self.c.state['kills'], 0)
        self.assertEqual(self.c.state['retired_attack_targets'], ['01000000'])
        self.assertEqual(self.c.state['history'][-1]['result']['status'], 'unknown')
        self.assertIsNone(self.c.state['inflight'])
        self.assertEqual(self.c.state['status'], 'active')

    def test_new_goal_preserves_history_and_is_idempotent(self):
        self.c.state.update(status='complete', kills=1, reason='confirmed_kill_goal', history=[{'old': 1}])
        self.c.save()
        self.assertTrue(self.c.set_goal(3))
        self.assertFalse(self.c.set_goal(3))
        saved = SoloCycle(self.path)
        self.assertEqual((saved.state['kills'], saved.state['goal_kills'], saved.state['status']), (1, 3, 'active'))
        self.assertEqual(saved.state['history'], [{'old': 1}])
        with self.assertRaises(RuntimeError):
            saved.set_goal(4)

    def test_reconcile_ended_navigation_keeps_unknown_and_progress(self):
        action = dict(type='navigate', map='prt_fild08', x=122, y=217, timeout_s=25)
        self.finish(action, 'route_ended_off_target', 'unknown')
        snap = snapshot(position={'x':131, 'y':226}, destination={'x':131, 'y':226}, ai_queue=[])
        obs = [dict(session='new:1', time_ms=10000, data=snap),
               dict(session='new:1', time_ms=11000, data=copy.deepcopy(snap))]
        self.c.reconcile_navigation(obs, 11100)
        saved = SoloCycle(self.path)
        self.assertEqual(saved.state['status'], 'active')
        self.assertIsNone(saved.state['inflight'])
        self.assertEqual(saved.state['kills'], 0)
        self.assertEqual(saved.state['history'][-1]['result']['status'], 'unknown')
        self.assertEqual(saved.state['reconciliations'][-1]['disposition'], 'retired_unknown_not_arrived')

    def test_reconcile_rejects_non_navigation_or_unstable_observations(self):
        self.finish(dict(type='npc_buy', x=104, y=49, items=[], max_zeny=15, timeout_s=20), 'result_not_confirmed', 'unknown')
        with self.assertRaises(RuntimeError):
            self.c.reconcile_navigation([], 11100)
        self.c.state.update(status='active', inflight=None)
        self.finish(dict(type='navigate', map='prt_fild08', x=122, y=217, timeout_s=25), 'route_ended_off_target', 'unknown')
        snap = snapshot(position={'x':131,'y':226}, destination={'x':131,'y':226}, ai_queue=[])
        obs = [dict(session='new:1',time_ms=10000,data=copy.deepcopy(snap)), dict(session='new:1',time_ms=11000,data=copy.deepcopy(snap))]
        for change in (dict(ai_queue=['route']), dict(map='prontera'), dict(native_task={'id':'x'}),
                       dict(destination={'x':122,'y':217}), dict(connected=False)):
            bad = copy.deepcopy(obs)
            bad[1]['data'].update(change)
            with self.assertRaises(RuntimeError):
                self.c.reconcile_navigation(bad, 11100)
        with self.assertRaises(RuntimeError):
            self.c.reconcile_navigation(obs, 20000)
        self.assertEqual(self.c.state['status'], 'blocked')

    def test_new_goal_rejects_uncertainty_and_invalid_targets(self):
        self.c.state.update(status='complete', kills=1, reason='confirmed_kill_goal', inflight={'request_id': 'c_1'})
        with self.assertRaises(RuntimeError):
            self.c.set_goal(2)
        self.c.state['inflight'] = None
        for target in (0, 101, True):
            with self.assertRaises(ValueError):
                self.c.set_goal(target)
        self.c.state['status'] = 'blocked'
        with self.assertRaises(RuntimeError):
            self.c.set_goal(2)

    def test_full_hunt_loot_supply_return_goal_with_reload(self):
        s = snapshot()
        a = self.c.plan(s, now=100)
        self.assertEqual(a['type'], 'attack')
        r = self.finish(a, 'killed')
        self.assertFalse(self.c.result(r))  # Duplicate terminal event is not a second kill.
        s['ground_items'] = [dict(id='02000000', x=171, y=250)]
        a = self.c.plan(s, now=102)
        self.assertEqual(a['type'], 'take')
        self.finish(a, 'picked_up')
        s['ground_items'] = []
        s['inventory'].append(dict(name_id=909, amount=5, type=3, equipped=0))
        a = self.c.plan(s, now=104)
        self.assertEqual(a['type'], 'travel')
        self.finish(a, 'arrived')
        self.c = SoloCycle(self.path, 99)  # Existing goal must not change.
        self.assertEqual(self.c.state['goal_kills'], 1)
        s.update(map='prontera', position={'x':104, 'y':51})
        a = self.c.plan(s, now=105)
        self.assertEqual(a['type'], 'npc_sell')
        self.finish(a, 'sold')
        s['inventory'] = s['inventory'][:1]
        s['zeny'] = 25
        a = self.c.plan(s, now=106)
        self.assertEqual((a['type'], a['max_zeny']), ('npc_buy', 15))
        self.finish(a, 'bought')
        s['inventory'].append(dict(name_id=512, amount=1, type=0, equipped=0))
        s['zeny'] = 10
        a = self.c.plan(s, now=107)
        self.assertEqual(a['map'], 'prt_fild08')
        self.finish(a, 'arrived')
        s.update(map='prt_fild08', position={'x':170, 'y':250})
        self.assertIsNone(self.c.plan(s, now=108))
        self.assertEqual(self.c.state['status'], 'complete')
        self.assertEqual(self.c.state['kills'], 1)

    def test_unknown_financial_result_retains_intent_and_blocks(self):
        a = dict(type='npc_buy', items=[{'name_id':512, 'amount':1}], x=104,y=49,max_zeny=15,timeout_s=20)
        self.finish(a, 'result_not_confirmed', 'unknown')
        restarted = SoloCycle(self.path)
        self.assertEqual(restarted.state['status'], 'blocked')
        self.assertIsNotNone(restarted.state['inflight'])
        self.assertIsNone(restarted.plan(snapshot()))

    def test_rejected_travel_never_advances_to_shop(self):
        self.c.state['phase'] = 'to_shop'
        self.finish(dict(type='travel',map='prontera',x=104,y=51,timeout_s=150), 'no_walk_route', 'rejected')
        self.assertEqual(self.c.state['phase'], 'to_shop')
        self.assertEqual(self.c.state['status'], 'blocked')

    def test_recovery_busy_dead_partial_inventory(self):
        for change in [dict(recovery='rest'), dict(native_task={'id':'other'}), dict(hp=10), dict(connected=False)]:
            self.assertIsNone(self.c.plan(snapshot(**change)))
        self.assertIsNone(self.c.plan(snapshot(inventory_truncated=True)))
        self.assertEqual(self.c.state['reason'], 'incomplete_inventory')

    def test_buy_recomputes_current_healing_after_sale(self):
        self.c.state['phase'] = 'buy'
        s = snapshot(map='prontera',zeny=25)
        s['inventory'].append(dict(name_id=512,amount=1,type=0,equipped=0))
        self.assertEqual(self.c.plan(s)['type'], 'travel')  # Return, no unnecessary buy.
        self.c.state['phase'] = 'buy'
        s['inventory'].pop()  # Native recovery consumed the Apple.
        self.assertEqual(self.c.plan(s)['type'], 'npc_buy')

    def test_write_ahead_failure_prevents_proposal(self):
        fake = FakeBridge(snapshot())
        runner = Runner(self.c, fake, Path(self.temp.name))
        runner.inventory_session, runner.inventory_ready_after = fake.session, 0
        with patch.object(runner, 'resource_guard'), patch.object(self.c, 'save', side_effect=OSError('disk')):
            with self.assertRaises(OSError):
                runner.run(1)
        self.assertEqual(fake.proposals, [])

    def test_two_failures_stop_and_missing_target_is_not_a_kill(self):
        for _ in range(2):
            self.finish(dict(type='attack',target='01000000',timeout_s=45),'target_lost','failed')
        self.assertEqual(self.c.state['kills'], 0)
        self.assertEqual(self.c.state['status'], 'blocked')

    def test_inventory_settling_starts_at_first_ready_observation(self):
        fake = FakeBridge(snapshot())
        fake.freeze = True
        runner = Runner(self.c, fake, Path(self.temp.name))
        with patch.object(runner, 'resource_guard'):
            runner.run(.02)
        self.assertEqual(runner.inventory_ready_after, fake.latest['time_ms']+1500)
        self.assertEqual(fake.proposals, [])


class FakeBridge:
    def __init__(self, snap, result=None, session='boot:1', available=True):
        self.session, self.next_serial = session, 10
        self.latest = {'time_ms': int(time.time()*1000), 'data': snap}
        self.events = [{'kind':'ready','data':{'next_serial':10, 'pending_request_id': None}}]
        self.result, self.available = result, available
        self.proposals, self.queries = [], []
        self.freeze = False

    def poll(self, timeout):
        if not self.freeze:
            self.latest['time_ms'] = max(int(time.time()*1000), self.latest['time_ms']+1)

    def drain(self):
        events, self.events = self.events, []
        return [{**e, 'session': e.get('session', self.session),
                 'time_ms': e.get('time_ms', self.latest['time_ms'])} for e in events]

    def send(self, query):
        self.queries.append(query)
        self.events.append(dict(kind='request_status', data=dict(request_id=query['request_id'],
            session=query['session'], result=self.result, available=self.available)))

    def proposal(self, action, **kwargs):
        self.proposals.append(action)
        raise AssertionError('No new proposal expected in restart tests')

    def serial_id(self):
        self.next_serial += 1
        return 'c_'+str(self.next_serial-1)

    def close(self):
        pass


class RestartTests(unittest.TestCase):
    def test_cross_session_result_cannot_resolve_saved_intent(self):
        with tempfile.TemporaryDirectory() as folder:
            cycle = SoloCycle(Path(folder)/'state.json', 1)
            cycle.prepare(dict(type='attack',target='01000000',timeout_s=45),'c_1','old:1')
            fake = FakeBridge(snapshot(), session='new:1')
            fake.events.append(dict(kind='action_result',data=dict(request_id='c_1',status='completed',reason='killed')))
            runner = Runner(cycle, fake, Path(folder))
            runner.pump()
            self.assertIsNotNone(cycle.state['inflight'])
            self.assertEqual(cycle.state['kills'], 0)
            runner.log.close()

    def test_terminal_result_requires_newer_snapshot_before_planning(self):
        with tempfile.TemporaryDirectory() as folder:
            cycle = SoloCycle(Path(folder)/'state.json', 1)
            cycle.state.update(phase='sell')
            cycle.prepare(dict(type='npc_sell',x=104,y=49,items=[{'name_id':909,'amount':5}],timeout_s=20), 'c_1','boot:1')
            fake = FakeBridge(snapshot(zeny=25))
            fake.freeze = True
            # The old snapshot cannot authorize a buy after this result.
            fake.events.append(dict(kind='action_result',time_ms=fake.latest['time_ms']+1,
                data=dict(request_id='c_1',status='completed',reason='sold')))
            runner = Runner(cycle, fake, Path(folder))
            runner.inventory_session, runner.inventory_ready_after = fake.session, 0
            with patch.object(runner, 'resource_guard'):
                runner.run(.02)
            self.assertEqual(cycle.state['phase'], 'buy')
            self.assertEqual(fake.proposals, [])
            self.assertEqual(cycle.state['observe_after'], fake.latest['time_ms']+1)

    def restart(self, available=True, session='boot:1'):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'state.json'
            cycle = SoloCycle(path, 1)
            cycle.state.update(phase='buy', kills=1)
            cycle.prepare(dict(type='npc_buy',x=104,y=49,items=[{'name_id':512,'amount':1}],
                               max_zeny=15,timeout_s=20), 'c_1', 'boot:1')
            cycle = SoloCycle(path)  # Process dies after write/send, before terminal save.
            snap = snapshot(position={'x':170,'y':365})
            snap['inventory'].append(dict(name_id=512,amount=1,type=0,equipped=0))
            fake = FakeBridge(snap, dict(request_id='c_1', status='completed', reason='bought'), session, available)
            runner = Runner(cycle, fake, Path(folder))
            runner.inventory_session, runner.inventory_ready_after = fake.session, 0
            with patch.object(runner, 'resource_guard'):
                runner.run(2)
            self.assertEqual(fake.proposals, [])
            return copy.deepcopy(cycle.state), fake.queries

    def test_cached_terminal_purchase_reconciles_without_repeating(self):
        state, queries = self.restart()
        self.assertEqual(state['status'], 'complete')
        self.assertEqual(len(queries), 1)
        self.assertIsNone(state['inflight'])

    def test_missing_cache_or_changed_boot_blocks_without_proposing(self):
        for options in [dict(available=False), dict(session='newboot:1')]:
            state, _ = self.restart(**options)
            self.assertEqual(state['status'], 'blocked')
            self.assertIsNotNone(state['inflight'])

    def test_lookup_does_not_admit_or_advance_serial(self):
        root = Path(__file__).resolve().parents[1]
        perl = root.parent/'vendor/strawberry-perl/perl/bin/perl.exe'
        code = "use M4RequestWindow; my $w=M4RequestWindow->new(1); $w->admit('c_1'); $w->finish('c_1',{status=>'completed'}); print $w->lookup('c_1')->{status}; $w->lookup('c_999'); print ':'.$w->next_serial.':'.$w->size;"
        result = subprocess.run([str(perl), '-I'+str(root/'bridge/lib'), '-e', code],
                                capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'completed:2:1')


if __name__ == '__main__':
    unittest.main()
