"""Real managed daemon lifecycle, without credentials or model requests."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from tempfile import TemporaryDirectory


def daemon(command):
    result = subprocess.run(['codex', 'app-server', 'daemon', command],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def check_sqlite_index_build(home):
    assert os.environ.get('SQLITE_TMPDIR') == '/tmp'
    with TemporaryDirectory(dir=home) as directory:
        with closing(sqlite3.connect(Path(directory) / 'index-test.sqlite')) as database:
            # A small page cache and wide index keys force the sorter to use a temp file.
            database.executescript('''
                PRAGMA temp_store = FILE;
                PRAGMA cache_size = -64;
                CREATE TABLE threads (id INTEGER PRIMARY KEY, sort_key BLOB NOT NULL);
                WITH RECURSIVE ids(id) AS (SELECT 1 UNION ALL SELECT id + 1 FROM ids WHERE id < 8192)
                INSERT INTO threads SELECT id, randomblob(512) FROM ids;
                CREATE INDEX thread_listing ON threads(sort_key);
            ''')
            assert database.execute('PRAGMA integrity_check').fetchone() == ('ok',)
    print('PASS SQLite index build with disk-backed temporary storage')


assert os.getuid() == 22000
home = Path(os.environ['CODEX_HOME'])
assert not (home / 'auth.json').exists()
assert not (home / 'packages/app-server-daemon/current').exists()
check_sqlite_index_build(home)
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
