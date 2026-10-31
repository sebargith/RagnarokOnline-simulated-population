from collections import deque
from concurrent.futures import Future
import json
from pathlib import Path
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from agent.community import Community
from agent.continuous import Continuous, ResourceGuardError
from agent.prototype import Prototype
from scripts import live_m4

ROOT = Path(__file__).resolve().parents[1]


class TelemetryTests(unittest.TestCase):
    def controller(self):
        controller = Continuous.__new__(Continuous)
        controller.started = time.monotonic()
        controller.last_resource = -10
        controller.telemetry_valid = True
        controller.telemetry_failures = 0
        controller.telemetry_error = None
        controller.resources = deque(maxlen=120)
        controller.error = None
        controller.note = Mock()
        # No network/clients/database are created in these tests.
        controller.bridges = {'agent': SimpleNamespace(latest=None)}
        return controller

    def test_timeout_pauses_admissions_then_valid_retry_recovers(self):
        controller = self.controller()
        with patch('agent.continuous.ram_sample', return_value={'ram_available': 3*1024**3}), \
             patch('agent.continuous.subprocess.check_output', side_effect=[subprocess.TimeoutExpired('nvidia-smi', 3), '10000\n']) as probe:
            controller.sample_resources()
            self.assertFalse(controller.telemetry_valid)
            self.assertFalse(controller.available('agent'))
            self.assertIsNone(controller.resources[-1]['gpu_used_mib'])
            self.assertEqual(controller.telemetry_failures, 1)
            self.assertEqual(controller.telemetry_error['type'], 'TimeoutExpired')
            controller.sample_resources()
            self.assertTrue(controller.telemetry_valid)
            self.assertEqual(controller.resources[-1]['gpu_used_mib'], 10000)
            self.assertEqual(controller.telemetry_failures, 0)
            self.assertIsNone(controller.telemetry_error)
            self.assertEqual(probe.call_count, 2)
            self.assertTrue(all(call.kwargs['timeout'] == 3 for call in probe.call_args_list))
            self.assertIn('gpu_telemetry_recovered', [call.args[0] for call in controller.note.call_args_list])

    def test_second_failure_fails_closed_instead_of_retrying_or_using_old_value(self):
        controller = self.controller()
        controller.resources.append({'gpu_used_mib': 9000})
        with patch('agent.continuous.ram_sample', return_value={'ram_available': 3*1024**3}), \
             patch('agent.continuous.subprocess.check_output', side_effect=subprocess.TimeoutExpired('nvidia-smi', 3)) as probe:
            controller.sample_resources()
            with self.assertRaisesRegex(ResourceGuardError, 'two consecutive probes'):
                controller.sample_resources()
            self.assertFalse(controller.telemetry_valid)
            self.assertEqual(probe.call_count, 2)
            self.assertIsNone(controller.resources[-1]['gpu_used_mib'])
            # This must escape the existing generic trade/routine handlers.
            self.assertNotIsInstance(ResourceGuardError(), (RuntimeError, OSError, TimeoutError, ValueError))

    def test_pump_drains_results_while_waiting_for_its_single_retry(self):
        controller = self.controller()
        clock = SimpleNamespace(now=200.0)
        controller.started = 200
        controller.controls = Mock()
        controller.suspended = True
        controller.live = Path('unused-mocked-status')
        controller.last_status = 0
        controller.offline = set()
        controller.event_count = 0
        controller.events = deque(maxlen=2048)
        controller.raw = Mock()
        controller.results = {}
        controller.reply_requests = set()
        controller.counters = {'completed': 0}
        controller.snapshot_status = Mock(return_value={'running': True})
        controller.journal = Mock(return_value=Mock())
        event = {'agent_id': 'agent', 'session': 'epoch', 'kind': 'action_result',
                 'data': {'request_id': 'c_1', 'status': 'completed'}}
        controller.bridges = {'agent': Mock()}
        controller.bridges['agent'].poll.side_effect = lambda _: [event] if controller.event_count == 0 else []
        controller.community = Mock()
        controller.community.poll.return_value = None
        controller.community.service.circuit.is_set.return_value = False
        probes = []
        def probe(*args, **kwargs):
            probes.append(clock.now)
            if len(probes) == 1:
                clock.now += 3  # simulate the real timeout without waiting
                raise subprocess.TimeoutExpired('nvidia-smi', 3)
            return '10000'
        def advance(_):
            clock.now += .1
        with patch('agent.continuous.time.monotonic', side_effect=lambda: clock.now), \
             patch('agent.continuous.time.sleep', side_effect=advance), \
             patch('agent.continuous.ram_sample', return_value={'ram_available': 3*1024**3}), \
             patch('agent.continuous.subprocess.check_output', side_effect=probe), \
             patch('agent.continuous.atomic_json'):
            controller.pump(5)
        self.assertEqual(controller.counters['completed'], 1)
        controller.community.observe.assert_called_once_with('agent', event, allow_dialogue=False)
        self.assertEqual(len(probes), 2)
        self.assertGreaterEqual(probes[1]-probes[0], 4)  # timeout + one-second pause
        self.assertTrue(controller.telemetry_valid)

    def test_invalid_output_and_missing_or_failed_tool_are_unknown(self):
        for failure in ('N/A\n', '-1', FileNotFoundError('missing nvidia-smi'), subprocess.CalledProcessError(1, 'nvidia-smi')):
            with self.subTest(failure=failure):
                controller = self.controller()
                with patch('agent.continuous.ram_sample', return_value={'ram_available': 3*1024**3}), \
                     patch('agent.continuous.subprocess.check_output') as probe:
                    if isinstance(failure, Exception):
                        probe.side_effect = failure
                    else:
                        probe.return_value = failure
                    controller.sample_resources()
                    self.assertFalse(controller.telemetry_valid)
                    self.assertIsNone(controller.resources[-1]['gpu_used_mib'])

    def test_resource_limits_are_unchanged_and_checked_on_retry(self):
        for ram, gpu in ((2*1024**3-1, '10000'), (3*1024**3, '14337')):
            with self.subTest(ram=ram, gpu=gpu):
                controller = self.controller()
                with patch('agent.continuous.ram_sample', return_value={'ram_available': ram}), \
                     patch('agent.continuous.subprocess.check_output', return_value=gpu) as probe:
                    with self.assertRaises(ResourceGuardError):
                        controller.sample_resources()
                    self.assertEqual(probe.call_count, int(ram >= 2*1024**3))
        controller = self.controller()
        with patch('agent.continuous.ram_sample', return_value={'ram_available': 2*1024**3}), \
             patch('agent.continuous.subprocess.check_output', return_value='14336'):
            controller.sample_resources()
            self.assertTrue(controller.telemetry_valid)
        controller = self.controller()
        with patch('agent.continuous.ram_sample', return_value={'ram_available': 3*1024**3}), \
             patch('agent.continuous.subprocess.check_output', side_effect=[subprocess.TimeoutExpired('nvidia-smi', 3), '14337']):
            controller.sample_resources()
            with self.assertRaises(ResourceGuardError):
                controller.sample_resources()
            self.assertEqual(controller.resources[-1]['gpu_used_mib'], 14337)
            self.assertFalse(controller.telemetry_valid)
            self.assertIsNone(controller.telemetry_error)  # known over-budget usage, not a stale timeout

    def test_paused_chat_is_observed_but_not_admitted_or_replayed(self):
        class Service:
            def __init__(self):
                self.submit = Mock(return_value=Future())
            def close(self):
                pass
        with tempfile.TemporaryDirectory() as directory:
            service = Service()
            community = Community(ROOT, directory, {'agent': SimpleNamespace(session='epoch')},
                                  identities={'agent': {'persona': 'I am Alden.'}}, service=service)
            event = {'agent_id': 'agent', 'id': 'chat-1', 'session': 'epoch', 'kind': 'chat',
                     'data': {'speaker': 'Visitor', 'text': 'M4:agent:Hello', 'self': 0}}
            community.observe('agent', event, allow_dialogue=False)
            service.submit.assert_not_called()
            self.assertIn('Hello', json.dumps(community.memories['agent'].retrieve()))
            self.assertIsNone(community.poll('agent'))
            event['id'] = 'chat-2'
            community.observe('agent', event)
            service.submit.assert_called_once()
            community.close()

    def test_cli_fatal_status_survives_successful_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            controller = self.controller()
            controller.live = runtime/'m4/live'
            controller.cycle = 12
            controller.run = Mock(side_effect=subprocess.TimeoutExpired('nvidia-smi', 3))
            controller.snapshot_status = lambda: {'running': True, 'error': controller.error}
            args = SimpleNamespace(runtime=runtime, run_id='test-only', seconds=None)
            with patch('scripts.live_m4.subprocess.run') as lifecycle, \
                 patch('scripts.live_m4.Continuous', return_value=controller), \
                 patch.object(Prototype, 'close') as cleanup:
                with self.assertRaises(subprocess.TimeoutExpired):
                    live_m4.run(args)
                # Both calls are fake: no live lifecycle operation is run.
                lifecycle.assert_called_once()
                cleanup.assert_called_once()
            status = json.loads((controller.live/'status.json').read_text())
            self.assertFalse(status['running'])
            self.assertEqual(status['phase'], 'failed')
            self.assertEqual(status['error']['type'], 'TimeoutExpired')
            self.assertIn('nvidia-smi', status['error']['message'])

    def test_normal_stop_and_cleanup_failure_have_truthful_final_status(self):
        for fatal, cleanup_failure in ((None, None), (None, OSError('cleanup failed')), (ValueError('original failure'), OSError('cleanup failed'))):
            with self.subTest(fatal=fatal, cleanup_failure=cleanup_failure), tempfile.TemporaryDirectory() as directory:
                controller = self.controller()
                controller.live = Path(directory)
                controller.cycle = 0
                controller.snapshot_status = lambda: {'running': True, 'error': controller.error}
                if fatal:
                    controller.record_failure(fatal)
                with patch.object(Prototype, 'close', side_effect=cleanup_failure):
                    if cleanup_failure:
                        with self.assertRaises(OSError):
                            controller.close()
                    else:
                        controller.close()
                status = json.loads((controller.live/'status.json').read_text())
                self.assertFalse(status['running'])
                self.assertEqual(status['phase'], 'failed' if (fatal or cleanup_failure) else 'stopped')
                self.assertEqual(status['error'], controller.error)
                if fatal:
                    self.assertEqual(status['error']['type'], 'ValueError')
                if cleanup_failure:
                    self.assertEqual(status['cleanup_error']['type'], 'OSError')
