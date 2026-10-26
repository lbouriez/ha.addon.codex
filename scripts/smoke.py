"""Exercise the built image without HA, credentials, or model requests."""
import json
import os
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
    result = subprocess.run(['docker', *args], capture_output=True, text=True)
    if result.returncode:
        print(result.stdout + result.stderr, file=sys.stderr)
        result.check_returncode()
    return result.stdout.strip()


def check_ha_access(image):
    suffix = uuid.uuid4().hex[:10]
    network, supervisor, addon = (f'codex-network-{suffix}', f'codex-supervisor-{suffix}', f'codex-api-{suffix}')
    docker('network', 'create', network)
    try:
        docker('create', '--name', supervisor, '--network', network, '--network-alias', 'supervisor',
               '--entrypoint', 'python3', image, '/tmp/fake_supervisor.py')
        docker('cp', str(ROOT / 'codex/tests/fake_supervisor.py'), f'{supervisor}:/tmp/fake_supervisor.py')
        docker('start', supervisor)
        for _ in range(30):
            ready = subprocess.run(['docker', 'exec', supervisor, 'python3', '-c',
                                    'import socket; socket.create_connection(("127.0.0.1",80),1).close()'], capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise AssertionError('Mock Supervisor failed to start')
        docker('create', '--name', addon, '--network', network,
               '-e', 'SUPERVISOR_TOKEN=smoke-test-supervisor-token', image)
        options = yaml.safe_load((ROOT / 'codex/config.yaml').read_text())['options']
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'options.json'
            path.write_text(json.dumps(options), encoding='utf-8')
            docker('cp', str(path), f'{addon}:/data/options.json')
        docker('cp', str(ROOT / 'codex/tests/check_ha_connection.py'), f'{addon}:/tmp/check_ha_connection.py')
        docker('start', addon)
        for _ in range(60):
            ready = subprocess.run(['docker', 'exec', addon, 'curl', '-fsS', 'http://127.0.0.1:7681/'], capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise AssertionError('Add-on failed to start with the mock Supervisor')
        print(docker('exec', addon, 'env', '-i', 'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                     'HOME=/tmp', 'su-exec', '22000:0', 'python3', '/tmp/check_ha_connection.py'))
    except Exception:
        for name in (supervisor, addon):
            logs = subprocess.run(['docker', 'logs', name], capture_output=True, text=True)
            print(logs.stdout + logs.stderr, file=sys.stderr)
        raise
    finally:
        for name in (addon, supervisor):
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, check=False)
        subprocess.run(['docker', 'network', 'rm', network], capture_output=True, check=False)


def check_daemon(image):
    name = f'codex-daemon-{uuid.uuid4().hex[:10]}'
    profile = os.environ.get('CODEX_TEST_APPARMOR')
    security = ['--security-opt', f'apparmor={profile}'] if profile else []
    try:
        docker('create', '--name', name, '--init', '--network', 'none', *security,
               '-e', 'HOME=/data/codex-home/users/anonymous',
               '-e', 'CODEX_HOME=/data/codex-home/users/anonymous/.codex',
               '--entrypoint', 'sh', image, '-ec',
               'mkdir -p "$CODEX_HOME"; chown -R 22000:0 "$HOME"; '
               'exec su-exec 22000:0 python3 /tmp/check_daemon.py')
        docker('cp', str(ROOT / 'codex/tests/check_daemon.py'), f'{name}:/tmp/check_daemon.py')
        print(docker('start', '--attach', name))
        assert docker('inspect', '--format', '{{.State.ExitCode}}', name) == '0'
        print(f'PASS daemon AppArmor profile: {profile or "not enforced by this test"}')
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, check=False)


def main(image):
    version = re.search(r'^ARG CODEX_VERSION=(.+)$', (ROOT / 'codex/Dockerfile').read_text(), re.M)[1]
    assert docker('run', '--rm', '--entrypoint', 'codex', image, '--version') == f'codex-cli {version}'
    assert docker('run', '--rm', '--entrypoint', 'su-exec', image, '22000:0', 'codex', '--version') == f'codex-cli {version}'
    options = yaml.safe_load((ROOT / 'codex/config.yaml').read_text())['options']
    for enabled in (False, True):
        name = f'codex-smoke-{uuid.uuid4().hex[:10]}'
        options['enable_mcp'] = enabled
        if enabled:
            options['yolo_mode'] = True
        else:
            options.pop('yolo_mode', None)  # Existing pre-YOLO installations.
        options['session_persistence'] = enabled
        if enabled:
            options.update(reasoning_effort='high', terminal_scrollback=20000, preserve_terminal_history=True)
        options['default_model'] = 'gpt-5.4'
        try:
            profile = os.environ.get('CODEX_TEST_APPARMOR')
            security = ['--security-opt', f'apparmor={profile}'] if profile else []
            docker('create', '--name', name, *security, image)
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
            expected = 'Official Home Assistant MCP registered' if enabled else 'Home Assistant MCP disabled'
            assert expected in logs, logs
            assert 'Migrating legacy gpt-5.4' in logs, logs
            docker('exec', name, '/usr/local/bin/codex-merge-config', '/tmp/codex-smoke/config.toml', '', str(enabled).lower(), 'workspace', 'on-request')
            docker('exec', name, 'env', 'CODEX_HOME=/tmp/codex-smoke', 'codex', 'mcp', 'list')
            docker('cp', str(ROOT / 'codex/tests/check_terminal.py'), f'{name}:/tmp/check_terminal.py')
            print(docker('exec', name, 'python3', '/tmp/check_terminal.py'))
            print(f'PASS {image}: terminal ready; MCP={enabled}; legacy model migration')
        except Exception:
            logs = subprocess.run(['docker', 'logs', name], capture_output=True, text=True)
            print(logs.stdout + logs.stderr, file=sys.stderr)
            raise
        finally:
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, check=False)
    check_ha_access(image)
    check_daemon(image)


if __name__ == '__main__':
    main(sys.argv[1])
