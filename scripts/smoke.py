"""Exercise the built image without HA, credentials, or model requests."""
import json
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def docker(*args):
    return subprocess.run(['docker', *args], check=True, capture_output=True, text=True).stdout.strip()


def main(image):
    version = re.search(r'^ARG CODEX_VERSION=(.+)$', (ROOT / 'codex/Dockerfile').read_text(), re.M)[1]
    assert docker('run', '--rm', '--entrypoint', 'codex', image, '--version') == f'codex-cli {version}'
    assert docker('run', '--rm', '--entrypoint', 'su-exec', image, '22000:0', 'codex', '--version') == f'codex-cli {version}'
    options = yaml.safe_load((ROOT / 'codex/config.yaml').read_text())['options']
    for enabled in (False, True):
        name = f'codex-smoke-{uuid.uuid4().hex[:10]}'
        options['enable_mcp'] = enabled
        options['default_model'] = 'gpt-5.4'
        try:
            docker('create', '--name', name, image)
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / 'options.json'
                path.write_text(json.dumps(options), encoding='utf-8')
                docker('cp', str(path), f'{name}:/data/options.json')
            docker('start', name)
            for _ in range(60):
                result = subprocess.run(['docker', 'exec', name, 'curl', '-fsS', 'http://127.0.0.1:7681/'], capture_output=True)
                if result.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise AssertionError('Terminal did not become ready within 60 seconds')
            logs = docker('logs', name)
            expected = 'Bundled MCP server registered' if enabled else 'Bundled MCP server disabled'
            assert expected in logs, logs
            assert 'Migrating legacy gpt-5.4' in logs, logs
            docker('exec', name, '/usr/local/bin/codex-merge-config', '/tmp/codex-smoke/config.toml', '', str(enabled).lower(), 'workspace', 'on-request')
            docker('exec', name, 'env', 'CODEX_HOME=/tmp/codex-smoke', 'codex', 'mcp', 'list')
            print(f'PASS {image}: terminal ready; MCP={enabled}; legacy model migration')
        except Exception:
            logs = subprocess.run(['docker', 'logs', name], capture_output=True, text=True)
            print(logs.stdout + logs.stderr, file=sys.stderr)
            raise
        finally:
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, check=False)


if __name__ == '__main__':
    main(sys.argv[1])
