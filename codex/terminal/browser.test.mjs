import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright';

// QA inventory: native and fallback clipboard, selection vs Ctrl+C, Unicode /
// multiline paste, history/download/latest, modal close/Escape, ingress iframe,
// disconnected session, narrow/mobile and desktop layouts. No HA/model calls.
const name = `codex-browser-${process.pid}`;
const image = process.env.TEST_IMAGE || 'codex-addon-review:0.5.1';
const basePath = '/api/hassio_ingress/fixture';
const docker = (...args) => execFileSync('docker', args, { encoding: 'utf8' }).trim();
let browser, url;
before(async () => {
  docker('run', '-d', '--rm', '--name', name, '-p', '127.0.0.1::7681',
    '--entrypoint', 'ttyd', image, '-p', '7681', '-W', '-b', basePath,
    '-I', '/usr/share/codex/terminal.html', '-t', 'disableLeaveAlert=true',
    '-t', 'rendererType=dom', '-t', 'scrollback=10000',
    '-t', 'theme={"background":"#1e1e2e","foreground":"#cdd6f4"}',
    'bash', '--noprofile', '--norc');
  url = `http://${docker('port', name, '7681/tcp')}${basePath}/`;
  browser = await chromium.launch({ headless: true });
  await mkdir('test-results', { recursive: true });
});

test('phone swipes scroll history with application mouse reporting, including inside ingress', async () => {
  for (const framed of [false, true]) {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    const page = await context.newPage();
    if (framed) {
      await page.route('**/touch-frame', route => route.fulfill({ contentType: 'text/html',
        body: `<meta name="viewport" content="width=device-width, initial-scale=1"><iframe src="${url}" style="position:fixed;inset:0;border:0;width:100%;height:100%"></iframe>` }));
      await page.goto(new URL('/touch-frame', url).href);
    } else await page.goto(url);
    const terminal = framed ? page.frames().find(f => f.url() === url) : page;
    await terminal.locator('#codex-toolbar').waitFor();
    await command(terminal, "for i in {1..200}; do printf 'Swipe row %s\\n' \"$i\"; done");
    await waitText(terminal, 'Swipe row 200');
    assert.equal(await terminal.evaluate(() => innerWidth), 390, 'phone uses device width');
    const cdp = await context.newCDPSession(page);
    async function swipe(from, to, x = 180) {
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y: from }] });
      for (let i = 1; i <= 12; i++) {
        await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: from + (to - from) * i / 12 }] });
      }
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    }
    for (const mouseMode of [false, true]) {
      await terminal.locator('#latest').click();
      await command(terminal, mouseMode ? "printf '\\033[?1000h\\033[?1006h'" : "printf '\\033[?1000l\\033[?1006l'");
      await terminal.waitForFunction(enabled => (window.term.modes.mouseTrackingMode !== 'none') === enabled, mouseMode);
      // Observe any unintended terminal input caused by a drag (no synthetic scrolling).
      await terminal.evaluate(() => { window.swipeInput = ''; window.swipeProbe = term.onData(data => { window.swipeInput += data; }); });
      const bottom = await terminal.evaluate(() => term.buffer.active.viewportY);
      await swipe(280, 650);
      await terminal.waitForFunction(previous => term.buffer.active.viewportY < previous, bottom);
      const older = await terminal.evaluate(() => term.buffer.active.viewportY);
      assert.ok(bottom - older > 5);
      assert.ok(bottom - older < 40, 'single swipe does not double-scroll');
      assert.match(await terminal.locator('.xterm-rows').innerText(), /Swipe row/);
      await page.screenshot({ path: `test-results/touch-${framed ? 'iframe' : 'direct'}-${mouseMode}.png` });
      await swipe(650, 280);
      await terminal.waitForFunction(previous => term.buffer.active.viewportY > previous, older);
      assert.equal(await terminal.evaluate(() => window.swipeInput), '', 'swipe must not type or send mouse reports');
      await terminal.evaluate(() => window.swipeProbe.dispose());
      await terminal.locator('#latest').tap();
      await terminal.waitForFunction(() => term.buffer.active.viewportY === term.buffer.active.baseY);
    }
    await terminal.locator('#history').tap();
    const field = terminal.locator('#codex-dialog textarea');
    assert.equal(await field.evaluate(el => el.selectionEnd - el.selectionStart), 0, 'history starts scrollable, not selected');
    const box = await field.boundingBox();
    const before = await field.evaluate(el => el.scrollTop);
    await swipe(box.y + box.height - 30, box.y + 30, box.x + box.width / 2);
    await field.evaluate(el => el.scrollTop); // Flush browser scroll/render work before assertion.
    await terminal.waitForFunction(previous => document.querySelector('#codex-dialog textarea').scrollTop > previous, before);
    await terminal.locator('#dialog-close').tap();
    await context.close();
  }
});
after(async () => {
  await browser?.close();
  try { docker('rm', '-f', name); } catch { /* Already removed. */ }
});

async function terminalText(page) {
  return page.evaluate(() => {
    const buffer = window.term.buffer.active;
    return Array.from({ length: buffer.length }, (_, i) => buffer.getLine(i).translateToString(true)).join('\n');
  });
}
async function waitText(page, expected) {
  await page.waitForFunction(value => {
    const buffer = window.term.buffer.active;
    return Array.from({ length: buffer.length }, (_, i) => buffer.getLine(i).translateToString(true)).join('\n').includes(value);
  }, expected);
}
async function command(page, value) {
  await page.locator('.xterm-helper-textarea').focus();
  const keyboard = page.keyboard || page.page().keyboard;
  await keyboard.insertText(value);
  await keyboard.press('Enter');
}
async function fit(page) {
  await page.waitForFunction(() => document.querySelector('#codex-toolbar').getBoundingClientRect().bottom
    <= document.querySelector('#terminal-container').getBoundingClientRect().top + 1);
  const bounds = await page.evaluate(() => {
    const rect = id => {
      const r = document.querySelector(id).getBoundingClientRect();
      return { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
    };
    return { toolbar: rect('#codex-toolbar'), terminal: rect('#terminal-container'),
      width: innerWidth, height: innerHeight, scrollWidth: document.documentElement.scrollWidth };
  });
  assert.ok(bounds.toolbar.bottom <= bounds.terminal.top + 1, JSON.stringify(bounds));
  assert.ok(bounds.terminal.bottom <= bounds.height + 1, JSON.stringify(bounds));
  assert.ok(bounds.scrollWidth <= bounds.width, JSON.stringify(bounds));
}

test('native clipboard, terminal selection, history, responsive layout and reconnect', async () => {
  const context = await browser.newContext({ permissions: ['clipboard-read', 'clipboard-write'], viewport: { width: 1200, height: 800 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(url);
  await page.locator('#codex-toolbar').waitFor();
  await command(page, "printf '\\nCOPY_SENTINEL\\n'");
  await waitText(page, 'COPY_SENTINEL');
  // Select real rendered output with the mouse, then use the Copy button.
  const row = page.locator('.xterm-rows > div').filter({ hasText: /^COPY_SENTINEL$/ }).last();
  const rect = await row.boundingBox();
  await page.mouse.move(rect.x + 1, rect.y + rect.height / 2);
  await page.mouse.down();
  await page.mouse.move(rect.x + 120, rect.y + rect.height / 2, { steps: 10 });
  await page.mouse.up();
  await page.locator('#copy').click();
  assert.match(await page.evaluate(() => navigator.clipboard.readText()), /COPY_SENTINEL/);
  await page.keyboard.press('Control+c');
  assert.match(await page.evaluate(() => navigator.clipboard.readText()), /COPY_SENTINEL/);

  await page.evaluate(() => navigator.clipboard.writeText("printf 'native-%s\\n' 'é😀'"));
  await page.locator('#latest').click();
  await page.keyboard.press('Control+v');
  await page.keyboard.press('Enter');
  await waitText(page, 'native-é😀');
  await page.evaluate(() => navigator.clipboard.writeText("printf 'button-%s\\n' 'collé'"));
  await page.locator('#paste').click();
  await waitText(page, "printf 'button-%s\\n' 'collé'");
  await page.keyboard.press('Enter');
  await waitText(page, 'button-collé');
  await command(page, 'sleep 30');
  await page.keyboard.press('Control+c');
  await command(page, "printf 'interrupt-%s\\n' 'ok'");
  await waitText(page, 'interrupt-ok');
  await command(page, "for i in {1..120}; do printf 'History row %s\\n' \"$i\"; done");
  await waitText(page, 'History row 120');
  await page.locator('#history').click();
  assert.match(await page.locator('#codex-dialog textarea').inputValue(), /History row 1\n/);
  assert.match(await page.locator('#codex-dialog textarea').inputValue(), /History row 120/);
  await page.locator('#dialog-action').click();
  assert.match(await page.evaluate(() => navigator.clipboard.readText()), /History row 120/);
  const download = page.waitForEvent('download');
  await page.locator('#dialog-download').click();
  assert.equal((await download).suggestedFilename(), 'codex-terminal.txt');
  await page.screenshot({ path: 'test-results/history-desktop.png' });
  await page.keyboard.press('Escape');
  await page.locator('#latest').click();
  await fit(page);
  await page.screenshot({ path: 'test-results/terminal-desktop.png' });
  await page.setViewportSize({ width: 360, height: 640 });
  await fit(page);
  await page.locator('#history').click();
  await page.screenshot({ path: 'test-results/history-mobile.png' });
  const modal = await page.locator('#codex-dialog').boundingBox();
  assert.ok(modal.x >= 0 && modal.x + modal.width <= 360);
  assert.ok(modal.y >= 0 && modal.y + modal.height <= 640);
  await page.locator('#dialog-close').click();
  await page.locator('#latest').click();
  await page.screenshot({ path: 'test-results/terminal-mobile.png' });
  await command(page, 'exit');
  await page.getByText('Press ⏎ to Reconnect', { exact: false }).waitFor();
  await page.keyboard.press('Enter');
  await page.waitForFunction(() => {
    const b = window.term.buffer.active;
    return b.length === window.term.rows && b.getLine(0).translateToString(true).includes('bash-');
  });
  await command(page, "printf 'reconnect-%s\\n' 'ok'");
  await waitText(page, 'reconnect-ok');
  assert.deepEqual(errors, []);
  await context.close();
});

test('clipboard denied in HA-style iframe: fallback copy and multiline paste', async () => {
  const context = await browser.newContext({ locale: 'fr-FR', viewport: { width: 390, height: 844 }, hasTouch: true });
  const page = await context.newPage();
  await page.route('**/qa-frame', route => route.fulfill({ contentType: 'text/html',
    body: `<iframe title="Codex" src="${url}" allow="clipboard-read 'none'; clipboard-write 'none'" style="position:fixed;inset:0;border:0;width:100%;height:100%"></iframe>` }));
  await page.goto(new URL('/qa-frame', url).href);
  const frame = page.frameLocator('iframe');
  await frame.locator('#paste').click();
  const field = frame.locator('#codex-dialog textarea');
  await field.fill("printf '%s\\n' 'première ligne' 'deuxième ligne'\n");
  await frame.locator('#dialog-action').click();
  // Bracketed multiline paste stays in readline until Enter is pressed.
  await page.keyboard.press('Enter');
  const child = page.frames().find(f => f.url() === url);
  await waitText(child, 'première ligne\ndeuxième ligne');
  await frame.locator('#history').click();
  assert.match(await field.inputValue(), /deuxième ligne/);
  await frame.locator('#dialog-action').click();
  assert.equal(await field.evaluate(el => el.selectionEnd - el.selectionStart), (await field.inputValue()).length);
  await page.screenshot({ path: 'test-results/clipboard-fallback-fr.png' });
  await frame.locator('#dialog-close').click();
  await frame.locator('#paste').click();
  assert.equal(await field.inputValue(), '');
  await page.keyboard.press('Escape');
  await context.close();
});

