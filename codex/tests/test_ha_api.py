import runpy
import unittest
from pathlib import Path

HELPER = Path(__file__).resolve().parents[1] / 'rootfs/usr/local/bin/codex-ha-helper'
api_url = runpy.run_path(str(HELPER))['api_url']


class HaApiPathTests(unittest.TestCase):
    def test_core_path_and_query(self):
        self.assertEqual(api_url('core', '/history/period?filter_entity_id=sensor.test'),
                         'http://supervisor/core/api/history/period?filter_entity_id=sensor.test')

    def test_supervisor_path(self):
        self.assertEqual(api_url('supervisor', '/core/check'), 'http://supervisor/core/check')

    def test_rejects_credential_redirects_and_path_traversal(self):
        for path in ('https://example.com/', '//example.com/', '/a/../info', '/%2e%2e/info',
                     '/%252e%252e/info', '/test#fragment', '/a\\b', '/x%0aheader', '/hassio_auth'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                api_url('core', path)

    def test_rejects_unknown_target(self):
        with self.assertRaises(ValueError):
            api_url('external', '/')
