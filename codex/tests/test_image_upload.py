"""Exercise the real HTTP upload boundary and Linux filesystem writes."""
import base64
import importlib.util
import io
import os
from pathlib import Path
import stat
import tempfile
import unittest

from aiohttp.test_utils import TestClient, TestServer

spec = importlib.util.spec_from_file_location('codex_upload', Path(__file__).parents[1] / 'rootfs/usr/local/lib/codex_upload.py')
upload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upload)
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==')


@unittest.skipUnless(os.name == 'posix', 'Linux directory-fd and permissions behavior')
class ImageUploadTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.client = TestClient(TestServer(upload.create_app(self.root)))
        await self.client.start_server()
        response = await self.client.get('/token')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertNotIn('Access-Control-Allow-Origin', response.headers)
        self.headers = {'X-Codex-Upload-Token': (await response.json())['token'], 'Content-Type': 'image/png'}

    async def asyncTearDown(self):
        await self.client.close()
        self.temp.cleanup()

    async def test_round_trip_unique_paths_no_client_filename_or_download(self):
        paths = []
        for _ in range(2):
            response = await self.client.post('/image?filename=../../configuration.yaml', data=PNG, headers=self.headers)
            self.assertEqual(response.status, 200)
            path = Path((await response.json())['path'])
            self.assertEqual(path.parent, self.root / 'tmp/codex')
            self.assertRegex(path.name, r'^[a-f0-9]{32}\.png$')
            self.assertEqual(path.read_bytes(), PNG)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            paths.append(path)
        self.assertNotEqual(*paths)
        self.assertEqual((await self.client.get('/image')).status, 405)
        self.assertEqual((await self.client.get('/tmp/codex/' + paths[0].name)).status, 404)

    async def test_reject_missing_token_cross_site_invalid_format_and_oversize(self):
        for headers in ({'Content-Type': 'image/png'}, {**self.headers, 'Sec-Fetch-Site': 'cross-site'}):
            self.assertEqual((await self.client.post('/image', data=PNG, headers=headers)).status, 403)
        for data, kind in ((b'not an image', 'image/png'), (b'<svg/>', 'image/svg+xml'), (PNG, 'text/plain')):
            self.assertEqual((await self.client.post('/image', data=data, headers={**self.headers, 'Content-Type': kind})).status, 415)
        self.assertEqual((await self.client.post('/image', data=io.BytesIO(PNG + bytes(upload.MAX_BYTES)), headers=self.headers)).status, 413)
        async def chunks():
            for _ in range(11):
                yield bytes(1024 * 1024)
        self.assertEqual((await self.client.post('/image', data=chunks(), headers=self.headers)).status, 413)
        self.assertFalse((self.root / 'tmp').exists())

    async def test_refuses_symlink_directory(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.root / 'tmp').symlink_to(outside, target_is_directory=True)
        response = await self.client.post('/image', data=PNG, headers=self.headers)
        self.assertEqual(response.status, 503)
        self.assertEqual(list(outside.iterdir()), [])
