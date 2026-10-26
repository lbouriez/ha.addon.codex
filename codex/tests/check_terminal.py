"""Exercise the real session launcher using a harmless long-running fake CLI."""
import json
import os
from pathlib import Path
import pty
import signal
import subprocess
import time
import tomllib

options = json.loads(Path('/data/options.json').read_text())
enabled = options.get('yolo_mode', False)
persist = options['session_persistence']
env = dict(os.environ)
for entry in Path('/proc/1/environ').read_bytes().split(b'\0'):
    key, sep, value = entry.partition(b'=')
    if sep and key.startswith(b'CODEX_'):
        env[key.decode()] = value.decode()
assert env['CODEX_YOLO_MODE'] == str(enabled).lower()
assert env['CODEX_PERMISSIONS'] == ('full_access' if enabled else options['codex_permissions'])
assert env['CODEX_APPROVAL_POLICY'] == ('never' if enabled else options['codex_approval_policy'])
root = Path('/data/codex-home/users/anonymous')
fake = root / '.local/bin/codex'
fake.parent.mkdir(parents=True, exist_ok=True)
fake.write_text('''#!/usr/local/bin/python3
import json, os, sys, time
from pathlib import Path
if '--version' in sys.argv:
    print('codex-cli 999.0.0')
    raise SystemExit
root=Path(os.environ['HOME'])
(root/'launch.json').write_text(json.dumps({'pid':os.getpid(),'args':sys.argv[1:]}))
while True:
    (root/'heartbeat').write_text(str(time.monotonic()))
    time.sleep(0.1)
''')
fake.chmod(0o755)
clients = []


def wait_for(predicate):
    for _ in range(100):
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError('Terminal check timed out')


def connect():
    master, slave = pty.openpty()
    process = subprocess.Popen(['/usr/local/bin/codex-session'], env=env,
                               stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    clients.append((process, master))
    return process


def disconnect(process):
    os.killpg(process.pid, signal.SIGHUP)
    process.wait(timeout=10)


def tmux(*args):
    return subprocess.run(['su-exec', '22000:0', 'tmux', '-S', str(root/'tmux.sock'), *args],
                          capture_output=True, text=True)


try:
    first = connect()
    wait_for(lambda: (root/'heartbeat').exists())
    launch = json.loads((root/'launch.json').read_text())
    expected = ['--no-alt-screen'] if options.get('preserve_terminal_history', True) else []
    if options.get('reasoning_effort', 'default') != 'default':
        expected += ['-c', 'model_reasoning_effort="' + options['reasoning_effort'] + '"']
    if enabled:
        expected += ['--dangerously-bypass-approvals-and-sandbox']
    assert launch['args'] == expected, launch
    config = tomllib.loads((root/'.codex/config.toml').read_text())
    assert config['sandbox_mode'] == ('danger-full-access' if enabled else 'workspace-write')
    assert config['approval_policy'] == ('never' if enabled else 'on-request')
    disconnect(first)
    if persist:
        assert tmux('show-options', '-gv', 'mouse').stdout.strip() == 'off'
        assert tmux('show-options', '-gv', 'history-limit').stdout.strip() == str(options.get('terminal_scrollback', 10000))
        if options.get('preserve_terminal_history', True):
            assert tmux('show-options', '-gv', 'alternate-screen').stdout.strip() == 'off'
        wait_for(lambda: tmux('display-message', '-p', '#{session_attached}').stdout.strip() == '0')
        before = (root/'heartbeat').read_text()
        wait_for(lambda: (root/'heartbeat').read_text() != before)
        second = connect()
        wait_for(lambda: tmux('display-message', '-p', '#{session_attached}').stdout.strip() == '1')
        assert json.loads((root/'launch.json').read_text()) == launch
        disconnect(second)
    print(f'PASS launch YOLO={enabled}; tmux disconnect/reattach={persist}')
finally:
    for process, master in clients:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)
        os.close(master)
    if persist:
        tmux('kill-server')
