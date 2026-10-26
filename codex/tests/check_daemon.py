"""Real managed daemon lifecycle, without credentials or model requests."""
import json
import os
from pathlib import Path
import subprocess


def daemon(command):
    result = subprocess.run(['codex', 'app-server', 'daemon', command],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


assert os.getuid() == 22000
home = Path(os.environ['CODEX_HOME'])
assert not (home / 'auth.json').exists()
assert not (home / 'packages/app-server-daemon/current').exists()
try:
    started = daemon('start')
    assert started['status'] == 'started', started
    current = home / 'packages/app-server-daemon/current/bin/codex'
    assert current.is_file() and os.access(current, os.X_OK)
    running = daemon('version')
    assert running['status'] == 'running', running
    assert running['cliVersion'] == running['appServerVersion']
    assert daemon('stop')['status'] == 'stopped'
    assert daemon('start')['status'] == 'started'
    assert daemon('version')['status'] == 'running'
    print('PASS daemon install, start, version, stop and restart as UID 22000')
except Exception:
    for log in (home / 'app-server-daemon').glob('*.log'):
        print(log.name + ':\n' + log.read_text(errors='replace')[-8000:], flush=True)
    subprocess.run(['ps', '-p', str(os.getpid()), '-o', 'stat=', '-o', 'lstart='])
    raise
finally:
    daemon('stop')
