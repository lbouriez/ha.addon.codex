"""A failed check must never be followed by a reload/restart request."""
import runpy
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

HELPER = Path(__file__).resolve().parents[1] / 'rootfs/usr/local/bin/codex-ha-helper'
maintenance = runpy.run_path(str(HELPER))['maintenance']


class MaintenanceTests(unittest.TestCase):
    def test_restart_and_each_reload_check_first(self):
        for action in (['restart'], *(['reload', domain] for domain in
                      ('automation', 'script', 'scene', 'group', 'template', 'core'))):
            with self.subTest(action=action):
                request = Mock(side_effect=['{"result":"ok"}', '{"result":"ok"}'])
                with patch.dict(maintenance.__globals__, request_api=request):
                    maintenance('fixture', action)
                self.assertEqual(request.call_args_list[0].args,
                                 ('fixture', 'supervisor', 'POST', '/core/check'))
                expected = ('supervisor', '/core/restart') if action[0] == 'restart' else (
                    'core', '/services/homeassistant/reload_core_config' if action[1] == 'core'
                    else f'/services/{action[1]}/reload')
                call = request.call_args_list[1]
                self.assertEqual((call.args[1], call.args[3]), expected)

    def test_failure_or_unknown_check_response_blocks_mutation(self):
        for response in ('{"result":"error"}', '{}', 'not json', RuntimeError('timeout')):
            for action in (['restart'], ['reload', 'automation']):
                request = Mock(side_effect=response) if isinstance(response, Exception) else Mock(return_value=response)
                with self.subTest(response=response, action=action), patch.dict(maintenance.__globals__, request_api=request):
                    with self.assertRaises((ValueError, RuntimeError)):
                        maintenance('fixture', action)
                self.assertEqual(request.call_count, 1)

    def test_rejects_unknown_actions_before_any_request(self):
        request = Mock()
        with patch.dict(maintenance.__globals__, request_api=request):
            for args in (['reload', 'shell_command'], ['reload'], ['restart', 'extra']):
                with self.assertRaises(ValueError):
                    maintenance('fixture', args)
        request.assert_not_called()
