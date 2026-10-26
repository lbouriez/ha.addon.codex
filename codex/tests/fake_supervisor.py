"""Local protocol fixture: never connects to a real Home Assistant or device."""
import json
from aiohttp import web

TOKEN = 'smoke-test-supervisor-token'


async def handle(request):
    if request.headers.get('Authorization') != 'Bearer ' + TOKEN:
        return web.Response(status=401)
    if request.path == '/core/api/test/mcp-status' and request.method == 'POST':
        request.app['mcp_status'] = (await request.json())['status']
        return web.json_response({'result': 'ok'})
    if request.path == '/core/api/mcp':
        if status := request.app.get('mcp_status'):
            return web.Response(status=status)
        if request.method != 'POST':
            return web.Response(status=405)
        message = await request.json()
        if 'id' not in message:
            return web.Response(status=202)
        method = message['method']
        if method == 'initialize':
            result = {'protocolVersion': message['params']['protocolVersion'],
                      'capabilities': {'tools': {}, 'resources': {}, 'prompts': {}},
                      'serverInfo': {'name': 'Home Assistant protocol fixture', 'version': '1.0'}}
        elif method == 'tools/list':
            result = {'tools': [{'name': 'GetLiveContext', 'description': 'Read fixture state',
                                'inputSchema': {'type': 'object', 'properties': {}}}]}
        elif method == 'tools/call':
            result = {'content': [{'type': 'text', 'text': 'sensor.fixture = 21'}]}
        elif method == 'resources/list':
            result = {'resources': [{'uri': 'homeassistant://assist/context-snapshot', 'name': 'State'}]}
        elif method == 'resources/read':
            result = {'contents': [{'uri': message['params']['uri'], 'text': 'fixture state'}]}
        elif method == 'prompts/list':
            result = {'prompts': []}
        elif method == 'ping':
            result = {}
        else:
            return web.json_response({'jsonrpc': '2.0', 'id': message['id'],
                                      'error': {'code': -32601, 'message': 'Method not found'}})
        return web.json_response({'jsonrpc': '2.0', 'id': message['id'], 'result': result})
    if request.path == '/core/api/states':
        return web.json_response([{'entity_id': 'sensor.fixture', 'state': '21'}])
    if request.path == '/core/logs':
        return web.Response(text='fixture log entry')
    if request.path == '/core/check' and request.method == 'POST':
        return web.json_response({'result': 'ok', 'data': {}})
    if request.path == '/core/restart' and request.method == 'POST':
        return web.json_response({'result': 'ok'})
    if request.path == '/core/api/services/automation/reload' and request.method == 'POST':
        return web.json_response([])
    if request.path == '/core/api/services/light/turn_on':
        return web.json_response({'received': await request.json()})
    if request.path == '/core/api/redirect':
        raise web.HTTPFound('http://example.com/')
    if request.path == '/core/api/denied':
        return web.Response(status=403)
    if request.path in ('/core/api/', '/core/info'):
        return web.json_response({'result': 'ok'})
    return web.Response(status=404)


async def websocket(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    await ws.send_json({'type': 'auth_required', 'ha_version': 'fixture'})
    auth = await ws.receive_json()
    if auth != {'type': 'auth', 'access_token': TOKEN}:
        await ws.send_json({'type': 'auth_invalid'})
        return ws
    await ws.send_json({'type': 'auth_ok', 'ha_version': 'fixture'})
    command = await ws.receive_json()
    await ws.send_json({'id': command['id'], 'type': 'result', 'success': True,
                       'result': [{'entity_id': 'sensor.fixture', 'state': '21'}]})
    if command['type'] == 'subscribe_events':
        await ws.send_json({'id': command['id'], 'type': 'event', 'event': {'event_type': 'state_changed'}})
    await ws.close()
    return ws


app = web.Application()
app['mcp_status'] = 0
app.router.add_get('/core/websocket', websocket)
app.router.add_route('*', '/{path:.*}', handle)
web.run_app(app, host='0.0.0.0', port=80, print=None)
