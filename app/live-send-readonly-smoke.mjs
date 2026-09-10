// Explicit read-only smoke of an already running local app. Never sends mail,
// opens desktop approval, syncs the mailbox, or logs case/mail content.
import assert from 'node:assert/strict';
import {chromium} from 'playwright';

const origin = 'http://127.0.0.1:8766';
const readOps = new Set(['desk_status', 'desk_get_case']);
const allowedPaths = new Set(['/', '/app.js', '/workspace.js', '/send-controls.mjs',
  '/page-tools.mjs', '/tool-contracts.mjs', '/style.css', '/status.css', '/map.json', '/api/bootstrap']);
const browser = await chromium.launch({headless: true});
const errors = [], blocked = [], operations = [];
try {
  const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => {if (m.type() === 'error') errors.push(m.text());});
  await page.route('**/*', route => {
    const req = route.request(), url = new URL(req.url());
    if (url.origin === origin && url.pathname === '/favicon.ico') return route.fulfill({status: 204});
    if (url.origin === origin && req.method() === 'GET' && allowedPaths.has(url.pathname)) return route.continue();
    if (url.origin === origin && req.method() === 'POST' && url.pathname === '/api/operation') {
      const payload = req.postDataJSON();
      if (readOps.has(payload.tool) && (payload.tool !== 'desk_get_case' || payload.arguments?.case_id === 'electronic-PA-2024')) {
        operations.push(payload.tool); return route.continue();
      }
    }
    blocked.push(req.method() + ' ' + url.pathname); return route.abort();
  });
  await page.goto(origin);
  await page.locator('#state-select option').first().waitFor({state: 'attached'});
  assert.equal(await page.locator('#map svg g.state').count(), 51);
  await page.locator('#state-select').selectOption('PA');
  await page.getByRole('button', {name: 'Open request', exact: true}).click();
  await page.waitForFunction(() => {const s = document.querySelector('.send-status'); return s && !s.textContent.startsWith('Checking');});
  const control = page.locator('.send-controls');
  assert.equal(await control.count(), 1);
  const status = await control.locator('.send-status').innerText();
  const quota = await control.locator('.help').innerText();
  assert.match(status, /Ready for your review|Waiting period|Daily sending limit/);
  assert.match(quota, /\d+ of 10 send attempts available/);
  assert.equal(await control.locator('.send-error').isVisible(), false);
  assert.deepEqual(errors, []); assert.deepEqual(blocked, []);
  assert.deepEqual(operations, ['desk_get_case', 'desk_status']);
  console.log(JSON.stringify({ok: true, live_read_only: true, state_shapes: 51,
    status, quota, send_disabled: await control.locator('button.primary').isDisabled(),
    operations, emails_sent: 0, approvals_opened: 0, user_tabs_changed: false}));
} finally {await browser.close();}
