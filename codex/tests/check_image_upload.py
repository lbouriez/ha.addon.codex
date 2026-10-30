"""Run as the Codex user against the real (optionally AppArmor-confined) ingress."""
import base64
import json
from pathlib import Path
import urllib.request

base = 'http://127.0.0.1:7681/codex-upload-'
with urllib.request.urlopen(base + 'token') as response:
    token = json.load(response)['token']
data = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==')
request = urllib.request.Request(base + 'image', data=data,
                                 headers={'Content-Type': 'image/png', 'X-Codex-Upload-Token': token})
with urllib.request.urlopen(request) as response:
    path = Path(json.load(response)['path'])
assert path.parent == Path('/homeassistant/tmp/codex'), path
try:
    assert path.read_bytes() == data
    assert path.stat().st_uid == 22000
finally:
    path.unlink()
print('PASS image upload through ingress, saved by and readable to Codex UID 22000')
