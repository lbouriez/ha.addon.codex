import os
import runpy
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'rootfs/usr/local/bin/codex-select-cli'
select_cli = runpy.run_path(str(SCRIPT))['select_cli']


@unittest.skipIf(os.name == 'nt', 'Executable fixtures require a POSIX shell')
class CliSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def cli(self, name, version=None):
        path = self.root / name
        body = f'echo "codex-cli {version}"' if version else 'exit 127'
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)
        return str(path)

    def test_stale_persistent_cli_does_not_hide_image_upgrade(self):
        candidate = self.cli('persistent', '0.100.0')
        bundled = self.cli('bundled', '0.164.0')
        self.assertEqual(select_cli(candidate, bundled), bundled)

    def test_newer_persistent_cli_survives_image_restart(self):
        candidate = self.cli('persistent', '0.165.0')
        bundled = self.cli('bundled', '0.164.0')
        self.assertEqual(select_cli(candidate, bundled), candidate)

    def test_broken_persistent_cli_falls_back(self):
        candidate = self.cli('persistent')
        bundled = self.cli('bundled', '0.164.0')
        self.assertEqual(select_cli(candidate, bundled), bundled)

    def test_missing_persistent_binary_falls_back(self):
        bundled = self.cli('bundled', '0.164.0')
        self.assertEqual(select_cli(str(self.root / 'missing'), bundled), bundled)
