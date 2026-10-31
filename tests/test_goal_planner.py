from concurrent.futures import Future
import json
from pathlib import Path
import tempfile
import unittest
import time
from types import SimpleNamespace
from unittest.mock import patch

from agent.goal_planner import GoalPlanner, apply_proposal, apply_proposal_locked, fingerprint, validate
from agent.solo_cycle import SoloCycle
from agent.live_io import exclusive
from scripts.run_p2_cycle import Runner


class Service:
    def __init__(self):
        self.future = Future()
        self.calls = []

    def submit(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.future


class PlannerTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.temp = tempfile.TemporaryDirectory(dir=root.parent/'runtime')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'state.json'
        self.lock = Path(self.temp.name)/'cycle.lock'
        self.cycle = SoloCycle(self.path, 1)
        self.service = Service()
        self.planner = GoalPlanner(self.service, self.path)
        self.observation = {'time_ms':1000, 'data':{'connected':True,'name':'Tarin',
            'native_task':None,'executor':'openkore_route','dead':False}}

    def proposal(self, kind='hunt', count=2):
        return {'status':'proposed','proposal':{'type':kind,'additional_kills':count},
                'fingerprint':fingerprint(self.path)}

    def test_closed_schema_rejects_command_injection_and_boolean_count(self):
        for value in ({'type':'hunt','additional_kills':True},
                      {'type':'hunt','additional_kills':4},
                      {'type':'hunt','additional_kills':1,'command':'eval'},
                      {'type':'ask_help','additional_kills':1},
                      {'type':[],'additional_kills':1}):
            with self.assertRaises(ValueError):
                validate(value)

    def test_inference_is_nonblocking_and_called_once(self):
        self.planner.request('Keep progressing')
        schema = self.service.calls[0][1]['response_format']
        self.assertNotIn('hunt',schema['properties']['type']['enum'])
        self.assertEqual(schema['properties']['additional_kills']['maximum'],0)
        self.assertIsNone(self.planner.poll())
        with self.assertRaises(RuntimeError):
            self.planner.request('Again')
        self.service.future.set_result({'content':json.dumps({'type':'continue_current','additional_kills':0})})
        self.assertEqual(self.planner.poll()['status'], 'proposed')
        self.assertEqual(len(self.service.calls), 1)
        self.assertIsNone(self.planner.poll())

    def test_delayed_response_rejects_changed_checkpoint(self):
        self.planner.request('Progress')
        self.cycle.block('unknown_action')
        self.service.future.set_result({'content':'{"type":"hunt","additional_kills":1}'})
        self.assertEqual(self.planner.poll()['reason'], 'checkpoint_changed')

    def test_failed_inference_leaves_game_state_untouched(self):
        before = self.path.read_bytes()
        self.planner.request('Progress')
        self.service.future.set_exception(ConnectionError('offline'))
        self.assertEqual(self.planner.poll()['status'], 'unavailable')
        self.assertEqual(self.path.read_bytes(), before)

    def test_new_goal_requires_completed_checkpoint_and_cannot_apply_twice(self):
        with self.assertRaises(RuntimeError):
            apply_proposal(self.path,self.lock,self.proposal(),self.observation,1100)
        self.cycle.state.update(status='complete',kills=1,reason='confirmed_kill_goal')
        self.cycle.save()
        proposal = self.proposal()
        self.assertEqual(apply_proposal(self.path,self.lock,proposal,self.observation,1100)['goal_kills'],3)
        with self.assertRaises(RuntimeError):
            apply_proposal(self.path,self.lock,proposal,self.observation,1100)
        self.assertEqual(SoloCycle(self.path).state['kills'],1)

    def test_stale_perception_or_changed_checkpoint_never_applies(self):
        proposal = self.proposal('continue_current',0)
        with self.assertRaises(ValueError):
            apply_proposal(self.path,self.lock,proposal,self.observation,4000)
        self.cycle.block('unknown')
        with self.assertRaises(RuntimeError):
            apply_proposal(self.path,self.lock,proposal,self.observation,1100)

    def test_hunt_cannot_relabel_an_identical_active_goal_as_saved(self):
        self.cycle.state.update(kills=1,goal_kills=3)
        self.cycle.save()
        before = self.path.read_bytes()
        with self.assertRaises(RuntimeError):
            apply_proposal(self.path,self.lock,self.proposal('hunt',2),self.observation,1100)
        self.assertEqual(self.path.read_bytes(),before)

    def test_continue_and_help_have_no_game_side_effects(self):
        before = self.path.read_bytes()
        self.assertEqual(apply_proposal(self.path,self.lock,self.proposal('continue_current',0),
                                       self.observation,1100)['status'],'continued')
        self.assertEqual(apply_proposal(self.path,self.lock,self.proposal('ask_help',0),
                                       self.observation,1100)['status'],'help_requested')
        self.assertEqual(self.path.read_bytes(),before)

    def test_locked_application_updates_the_runners_own_object(self):
        self.cycle.state.update(status='complete',kills=1,reason='confirmed_kill_goal')
        self.cycle.save()
        proposal = self.proposal()
        with exclusive(self.lock):
            result = apply_proposal_locked(self.cycle,proposal,self.observation,1100)
        self.assertEqual(result['status'],'goal_saved')
        self.assertEqual(self.cycle.state['goal_kills'],3)
        self.cycle.save()
        self.assertEqual(SoloCycle(self.path).state['goal_kills'],3)

    def runner(self):
        observation = {'time_ms':int(time.time()*1000),'data':self.observation['data']}
        bridge = SimpleNamespace(latest=observation)
        runner = Runner(self.cycle,bridge,Path(self.temp.name),self.planner,'Continue the current goal')
        self.addCleanup(runner.log.close)
        return runner

    def test_runner_polls_slow_inference_without_waiting_or_resubmitting(self):
        runner = self.runner()
        with patch.object(runner,'resource_guard'):
            runner.planning_tick()
            runner.planning_tick()
            self.assertFalse(runner.planning_done)
            self.assertEqual(runner.inference_calls,1)
            self.service.future.set_result({'content':'{"type":"continue_current","additional_kills":0}'})
            runner.planning_tick()
            runner.planning_tick()
        self.assertEqual(runner.planning_result['status'],'continued')
        self.assertEqual(len(self.service.calls),1)

    def test_runner_submit_failure_preserves_active_goal(self):
        runner = self.runner()
        before = self.path.read_bytes()
        with patch.object(runner,'resource_guard'), patch.object(self.service,'submit',side_effect=RuntimeError('busy')):
            runner.planning_tick()
        self.assertTrue(runner.planning_done)
        self.assertEqual(runner.inference_calls,0)
        self.assertEqual(self.path.read_bytes(),before)

    def test_gameplay_progresses_while_model_future_is_pending(self):
        from test_p2_cycle import FakeBridge, snapshot

        class GameplayBridge(FakeBridge):
            def proposal(self, action, **kwargs):
                self.proposals.append(action)
                self.events.append({'kind':'action_result','data':{
                    'request_id':kwargs['request_id'],'status':'completed','reason':'killed'}})

        bridge = GameplayBridge(snapshot())
        runner = Runner(self.cycle,bridge,Path(self.temp.name),self.planner,'Continue')
        runner.inventory_session, runner.inventory_ready_after = bridge.session, 0
        with patch.object(runner,'resource_guard'):
            result = runner.run(.1,max_actions=1)
        self.assertEqual(result['actions_sent'],1)
        self.assertEqual(self.cycle.state['kills'],1)
        self.assertFalse(self.service.future.done())
        self.assertEqual(result['inference_calls'],1)


if __name__ == '__main__':
    unittest.main()
