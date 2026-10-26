import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'rootfs/usr/local/bin/codex-merge-config'


class ModelConfigTests(unittest.TestCase):
    def test_managed_yolo_defaults_return_to_normal(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'config.toml'
            for access, approval, sandbox in [('full_access', 'never', 'danger-full-access'),
                                               ('workspace', 'on-request', 'workspace-write')]:
                subprocess.run([sys.executable, str(SCRIPT), str(path), '', 'false', access, approval], check=True)
                config = tomllib.loads(path.read_text())
                self.assertEqual(config['sandbox_mode'], sandbox)
                self.assertEqual(config['approval_policy'], approval)

    def merge(self, initial, model=''):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'config.toml'
            path.write_text(initial, encoding='utf-8')
            subprocess.run([sys.executable, str(SCRIPT), str(path), model, 'false', 'workspace', 'on-request'], check=True)
            return tomllib.loads(path.read_text())

    def test_removes_previous_managed_model(self):
        result = self.merge('model = "gpt-5.4"\n[__homeassistant_app]\nmanaged_model = "gpt-5.4"\n')
        self.assertNotIn('model', result)

    def test_preserves_manual_model_override(self):
        result = self.merge('model = "custom-model"\n[__homeassistant_app]\nmanaged_model = "gpt-5.4"\n')
        self.assertEqual(result['model'], 'custom-model')

    def test_keeps_unrelated_mcp_and_project_settings(self):
        result = self.merge('[mcp_servers.other]\nurl = "https://example.com/mcp"\n[projects."/homeassistant"]\ntrust_level = "trusted"\n')
        self.assertEqual(result['mcp_servers']['other']['url'], 'https://example.com/mcp')
        self.assertEqual(result['projects']['/homeassistant']['trust_level'], 'trusted')

    def test_explicit_new_model_is_managed(self):
        self.assertEqual(self.merge('', 'gpt-6.1-sol')['model'], 'gpt-6.1-sol')

    def test_official_mcp_replaces_old_transport_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'config.toml'
            path.write_text('[mcp_servers.homeassistant]\ncommand="/usr/local/bin/hass-mcp-wrapper"\n'
                            'url="https://old.invalid/mcp"\nargs=["old"]\n'
                            'bearer_token_env_var="OLD_TOKEN"\n'
                            '[mcp_servers.other]\nurl="https://example.com/mcp"\n')
            subprocess.run([sys.executable, str(SCRIPT), str(path), '', 'true'], check=True)
            config = tomllib.loads(path.read_text())
            server = config['mcp_servers']['homeassistant']
            self.assertEqual(server['command'], '/usr/local/bin/ha-mcp')
            self.assertEqual(server['startup_timeout_sec'], 30)
            self.assertFalse({'url', 'args', 'bearer_token_env_var'} & server.keys())
            self.assertIn('other', config['mcp_servers'])
