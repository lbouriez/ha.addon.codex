"""Run inside the add-on as the unprivileged Codex user against the fixture."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import runpy
import subprocess

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def call(*args, body=None):
    result = subprocess.run(['ha-api', *args], input=body, text=True, capture_output=True, timeout=40)
    assert result.returncode == 0, result.stderr
    assert 'smoke-test-supervisor-token' not in result.stdout + result.stderr
    return result.stdout


async def main():
    assert os.getuid() == 22000
    assert 'SUPERVISOR_TOKEN' not in os.environ
    assert importlib.util.find_spec('hass_mcp') is None
    try:
        Path('/tmp/codex/ha-token').read_text()
    except PermissionError:
        pass
    else:
        raise AssertionError('Session user can read the token file')
    # Exercise actual config permissions granted at startup, not root file access.
    probe = Path('/homeassistant/.codex-access-smoke')
    probe.write_text('test')
    assert probe.read_text() == 'test'
    probe.unlink()
    status = json.loads(call('status'))
    assert status['official_mcp'] == status['core_api'] == status['supervisor_api'] == 'available', status
    assert json.loads(call('core', 'GET', '/states'))[0]['state'] == '21'
    assert 'fixture log entry' in call('supervisor', 'GET', '/core/logs')
    assert json.loads(call('supervisor', 'POST', '/core/check'))['result'] == 'ok'
    assert json.loads(call('check'))['result'] == 'ok'
    assert json.loads(call('reload', 'automation')) == []
    assert json.loads(call('restart'))['result'] == 'ok'
    assert json.loads(call('core', 'POST', '/services/light/turn_on', body='{"entity_id":"light.fixture"}'))['received']['entity_id'] == 'light.fixture'
    assert json.loads(call('ws', body='{"type":"get_states"}'))['success']
    events = call('ws', '--follow', body='{"type":"subscribe_events","event_type":"state_changed"}')
    assert json.loads(events.splitlines()[-1])['type'] == 'event'
    for path in ('/redirect', '/denied'):
        result = subprocess.run(['ha-api', 'core', 'GET', path], capture_output=True, text=True)
        assert result.returncode != 0
        assert 'smoke-test-supervisor-token' not in result.stdout + result.stderr

    async with stdio_client(StdioServerParameters(command='/usr/local/bin/ha-mcp')) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            assert (await session.list_tools()).tools[0].name == 'GetLiveContext'
            assert (await session.call_tool('GetLiveContext', {})).content[0].text == 'sensor.fixture = 21'
            assert (await session.list_resources()).resources[0].name == 'State'
            assert (await session.read_resource('homeassistant://assist/context-snapshot')).contents[0].text == 'fixture state'
            assert (await session.list_prompts()).prompts == []
    helper = runpy.run_path('/usr/local/bin/codex-ha-helper')
    for endpoint, expected in (('/denied', 'access_denied'), ('/missing', 'absent')):
        detected = await helper['probe_official']('smoke-test-supervisor-token', 'http://supervisor/core/api' + endpoint)
        assert detected == expected, (endpoint, detected, expected)
    for status, expected in ((404, 'absent'), (403, 'access_denied'), (503, 'unreachable')):
        call('core', 'POST', '/test/mcp-status', body=json.dumps({'status': status}))
        failure = subprocess.run(['ha-mcp'], input='', capture_output=True, text=True, timeout=15)
        assert failure.returncode != 0 and expected in failure.stderr, failure.stderr
        assert 'smoke-test-supervisor-token' not in failure.stdout + failure.stderr
    call('core', 'POST', '/test/mcp-status', body='{"status":0}')
    print('PASS official MCP tools/resources/prompts, REST, WebSocket, Supervisor, file access and credential isolation')


asyncio.run(main())
