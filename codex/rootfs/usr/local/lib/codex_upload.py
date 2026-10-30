"""Small ingress-only image upload service. Never accepts a client filesystem path."""
import asyncio
import hmac
import os
import secrets
import uuid
from pathlib import Path

from aiohttp import web

MAX_BYTES = 10 * 1024 * 1024
CONFIG_ROOT = Path('/homeassistant')


def image_extension(data, content_type):
    if content_type == 'image/png' and data.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if content_type == 'image/jpeg' and data.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if content_type == 'image/gif' and data[:6] in (b'GIF87a', b'GIF89a'):
        return '.gif'
    if content_type == 'image/webp' and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return '.webp'
    raise web.HTTPUnsupportedMediaType(text='Use a PNG, JPEG, GIF or WebP image.')


def save_image(root, data, extension):
    # Open each directory without following symlinks, including on a writable HA
    # config mount. Random names and exclusive creation avoid path injection and
    # overwrites. Only the Codex OS user needs to read the new file.
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in ('tmp', 'codex'):
            try:
                os.mkdir(part, mode=0o700, dir_fd=directory)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        name = uuid.uuid4().hex + extension
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
        try:
            with os.fdopen(descriptor, 'wb') as output:
                output.write(data)
        except BaseException:
            os.unlink(name, dir_fd=directory)
            raise
        return str(root / 'tmp' / 'codex' / name)
    finally:
        os.close(directory)


def create_app(root=CONFIG_ROOT):
    app = web.Application(client_max_size=MAX_BYTES)
    token = secrets.token_urlsafe(32)
    slots = asyncio.Semaphore(2)

    async def get_token(request):
        # Same-origin policy protects this token; deliberately no CORS headers.
        return web.json_response({'token': token}, headers={'Cache-Control': 'no-store'})

    async def upload(request):
        if not hmac.compare_digest(request.headers.get('X-Codex-Upload-Token', '').encode(), token.encode()):
            raise web.HTTPForbidden(text='Reopen the terminal and try again.')
        if request.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise web.HTTPForbidden()
        if request.content_length is not None and request.content_length > MAX_BYTES:
            raise web.HTTPRequestEntityTooLarge(max_size=MAX_BYTES, actual_size=request.content_length)
        if slots.locked():
            raise web.HTTPTooManyRequests(text='Another image is uploading. Try again.')
        async with slots:
            try:
                async with asyncio.timeout(30):
                    data = await request.read()
            except TimeoutError:
                raise web.HTTPRequestTimeout() from None
            extension = image_extension(data, request.content_type)
            try:
                path = await asyncio.to_thread(save_image, root, data, extension)
            except OSError:
                raise web.HTTPServiceUnavailable(text='Cannot save the image in /homeassistant/tmp/codex. Check folder permissions and free space.') from None
        return web.json_response({'path': path}, headers={'Cache-Control': 'no-store'})

    app.router.add_get('/token', get_token)
    app.router.add_post('/image', upload)
    return app


if __name__ == '__main__':
    web.run_app(create_app(), host='127.0.0.1', port=7683, access_log=None)
