// Real browser + actual static app, but synthetic HTTP data only. No private
// store, Proton connection, desktop approval, or external write is reachable.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const assets = new Map(['index.html', 'app.js', 'workspace.js', 'send-controls.mjs',
  'style.css', 'status.css', 'tool-contracts.mjs', 'page-tools.mjs', 'map.json']
  .map(name => ['/' + (name === 'index.html' ? '' : name), name]));
const geometry = JSON.parse(await readFile(new URL('./static/map.json', import.meta.url)));
const base = {id: 'synthetic-case', revision: 1, state: 'IN', state_name: 'Indiana',
  family_label: 'Synthetic send-flow test', status: 'draft', stage: 'draft', year: 2024,
  recipient: 'records@example.gov', subject: 'Synthetic request — never sent',
  body: 'Hello,\n\nThis is a synthetic browser test. No real email is sent.\n\nSynthetic Records Staff',
  routing_verified: true, routing_evidence: 'https://example.gov/synthetic',
  note: 'Synthetic fixture only.', request_ids: ['TEST-REQUEST'], custodian: 'Synthetic Office',
  portal_url: 'https://example.gov', lookup_url: 'https://example.gov',
  routing_notes: 'No real custodian or mailbox is used by this test.', catalog_date: '2026-09-09'};
let record, draft, mode = 'cooldown', outcome = 'cancel', until = null, sendCalls = 0, statusCalls = 0;
let releaseSend = null;
function reset(nextMode = 'ready', nextOutcome = 'cancel') {
  record = structuredClone(base); mode = nextMode; outcome = nextOutcome; until = null; releaseSend = null;
  draft = {draft_id: '00000000-0000-4000-8000-000000000001', digest: 'a'.repeat(64),
    state: 'draft', to: [record.recipient], from: 'synthetic@example.test',
    subject: record.subject, body: record.body, in_reply_to: null, receipt: null};
}
reset('cooldown');
const json = (res, value) => {res.writeHead(200, {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}); res.end(JSON.stringify(value));};
const server = createServer(async (req, res) => {
  try {
    if (req.method === 'GET' && req.url === '/api/bootstrap') return json(res, {ok: true,
      email: 'synthetic@example.test', unassigned: [], unassigned_total: 0, sync: [],
      catalog: {states: geometry.states.map(({code, name}) => ({code, name})), cases: [record], issue: {fields: []}}});
    if (req.method === 'POST' && req.url === '/api/operation') {
      let body = ''; for await (const chunk of req) body += chunk;
      const {tool, arguments: args} = JSON.parse(body);
      if (tool === 'desk_get_case') return json(res, {ok: true, result: {case: record, drafts: [draft],
        messages: [], artifacts: [], issues: [], events: [], next_artifact_offset: null}});
      if (tool === 'desk_status') {
        statusCalls++;
        if (mode === 'cooldown' && until === null) until = Date.now() + 3000;
        const wait = mode === 'daily' ? 3661 : mode === 'cooldown' ? Math.max(0, Math.ceil((until - Date.now()) / 1000)) : 0;
        return json(res, {ok: true, result: {connector: {configured: true, sending_enabled: mode !== 'disabled',
          send_window: {ready: wait === 0, checked_at: Date.now() / 1000,
            retry_after_seconds: wait, attempts_remaining: mode === 'daily' ? 0 : 9,
            max_attempts: 10, reason: !wait ? 'ready' : mode === 'daily' ? 'daily_limit' : 'cooldown'}}}});
      }
      if (tool === 'desk_send_email') {
        sendCalls++;
        assert.equal(args.draft_id, draft.draft_id); assert.equal(args.expected_digest, draft.digest);
        assert.equal(args.confirmation, 'SEND_REVIEWED_EMAIL');
        if (outcome === 'preflight') return json(res, {ok: false, send_not_started: true, error: 'Synthetic routing review is stale. No approval opened.'});
        if (outcome === 'deferred') await new Promise(resolve => {releaseSend = resolve;});
        if (outcome === 'error') return json(res, {ok: false, error: 'Synthetic transport failure. Check saved receipts before retrying.'});
        const state = outcome === 'cancel' ? 'draft' : outcome === 'uncertain' ? 'uncertain' : 'accepted';
        draft.state = state;
        if (state !== 'draft') draft.receipt = {meaning: state === 'accepted'
          ? 'Accepted by local Proton Bridge; recipient delivery is not verified.'
          : 'Check Proton Sent before any manual retry. No automatic retry is available.'};
        record.stage = record.status = state === 'accepted' ? 'waiting' : state === 'uncertain' ? 'attention' : 'draft';
        return json(res, {ok: true, result: {state}});
      }
      return json(res, {ok: false, error: 'Operation is not part of the synthetic browser fixture.'});
    }
    if (req.url === '/favicon.ico') {res.writeHead(204); return res.end();}
    const file = assets.get(req.url);
    if (!file) {res.writeHead(404); return res.end();}
    const type = file.endsWith('.css') ? 'text/css' : file.endsWith('.html') ? 'text/html' : file.endsWith('.json') ? 'application/json' : 'text/javascript';
    res.writeHead(200, {'Content-Type': type, 'Cache-Control': 'no-store'});
    res.end(await readFile(new URL('./static/' + file, import.meta.url)));
  } catch {res.writeHead(500); res.end('Synthetic fixture error');}
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
const errors = [];
try {
  browser = await chromium.launch({headless: true});
  const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => {if (m.type() === 'error') errors.push(m.text());});
  // Deny every non-fixture network request, even if a future UI change tries one.
  await page.route('**/*', route => route.request().url().startsWith(origin + '/') ? route.continue() : route.abort());
  async function open() {
    await page.goto(origin);
    assert.match(await page.title(), /^CivicRelay/);
    assert.equal(await page.getByRole('heading', {name:'CivicRelay', exact:true}).count(),1);
    await page.locator('#map svg g.state').first().waitFor({state:'attached'});
    assert.equal(await page.locator('#map svg g.state').count(),51);
    await page.getByRole('button', {name: 'Open request', exact: true}).click();
    await page.waitForFunction(() => {const status = document.querySelector('.send-status'); return status && !status.textContent.startsWith('Checking');});
  }
  async function reopen() {
    const previous = await page.locator('.send-controls').elementHandle();
    await page.getByRole('button', {name: 'Open request', exact: true}).click();
    await page.waitForFunction(node => !node.isConnected, previous);
    await page.waitForFunction(() => {const status = document.querySelector('.send-status'); return status && !status.textContent.startsWith('Checking');});
    await previous.dispose();
  }
  const send = page.locator('.send-controls button.primary');
  async function waitForPending() {
    for (let i = 0; i < 200 && !releaseSend; i++) await new Promise(resolve => setTimeout(resolve, 10));
    assert.equal(typeof releaseSend, 'function', 'synthetic send should be pending');
  }
  await open(); assert.equal(await send.isDisabled(), true);
  assert.match(await page.locator('.send-status').innerText(), /Waiting period/);
  await page.locator('#case-workspace').screenshot({path: fileURLToPath(new URL('./send-flow-cooldown.png', import.meta.url))});
  await page.waitForFunction(() => document.querySelector('.send-controls button.primary')?.disabled === false);
  assert.equal(sendCalls, 0, 'countdown must never send');

  mode = 'daily'; await page.getByRole('button', {name: 'Check sending availability', exact: true}).click();
  await page.waitForFunction(() => document.querySelector('.send-status')?.textContent.includes('Daily sending limit'));
  assert.equal(await send.isDisabled(), true); assert.match(await page.locator('.send-controls .help').innerText(), /0 of 10/);
  assert.equal(sendCalls, 0);

  reset('disabled'); await open();
  assert.equal(await send.isDisabled(), true);
  assert.match(await page.locator('.send-error').innerText(), /Sending is disabled/);
  assert.equal(sendCalls, 0);

  reset(); await open(); await send.click();
  await page.locator('.send-feedback:not([hidden])').waitFor();
  assert.match(await page.locator('.send-feedback').innerText(), /cancelled or expired/);
  assert.equal(sendCalls, 1); assert.equal(await page.locator('.send-error').isVisible(), false);

  reset('ready', 'error'); await open(); await send.click();
  await page.locator('.send-error:not([hidden])').waitFor();
  assert.match(await page.locator('.send-error').innerText(), /Synthetic transport failure/);
  assert.equal(await send.isDisabled(), true); assert.equal(sendCalls, 2);
  assert.equal(await page.getByRole('button', {name: 'Reload saved receipt'}).isVisible(), true);
  await page.locator('#case-workspace').screenshot({path: fileURLToPath(new URL('./send-flow-inline-error.png', import.meta.url))});

  reset('ready', 'deferred'); await open(); await send.click();
  await waitForPending();
  await page.locator('#body').fill('Unsaved text typed while the synthetic send was in flight.');
  releaseSend();
  await page.waitForFunction(() => document.querySelector('#send-previews')?.textContent.includes('State: accepted'));
  assert.equal(await page.locator('#body').inputValue(), 'Unsaved text typed while the synthetic send was in flight.');
  assert.equal(await send.count(), 0); assert.equal(sendCalls, 3);

  reset('ready', 'uncertain'); await open(); await send.click();
  await page.waitForFunction(() => document.querySelector('#send-previews')?.textContent.includes('State: uncertain'));
  assert.equal(await send.count(), 0); assert.equal(sendCalls, 4);

  for (const state of ['accepted', 'uncertain']) {
    reset('ready', 'deferred'); await open(); await send.click(); await waitForPending();
    // Replace the exact pane while its earlier send control awaits an outcome.
    await reopen();
    outcome = state; releaseSend();
    await page.waitForFunction(expected => document.querySelector('#send-previews')?.textContent.includes(`State: ${expected}`), state);
    assert.equal(await send.count(), 0);
  }

  reset('ready', 'preflight'); await open(); await send.click();
  await page.locator('.send-error:not([hidden])').waitFor();
  assert.match(await page.locator('.send-error').innerText(), /Synthetic routing review is stale/);
  assert.match(await page.locator('.send-status').innerText(), /No send was started/);
  assert.equal(await page.getByRole('button', {name: 'Check sending availability', exact: true}).isDisabled(), false);
  assert.equal(sendCalls, 7);

  reset('ready', 'deferred'); await open(); await send.click(); await waitForPending();
  await reopen();
  outcome = 'error'; releaseSend();
  await page.locator('.send-error:not([hidden])').waitFor();
  assert.match(await page.locator('.send-error').innerText(), /send outcome is unconfirmed/);
  assert.equal(await send.isDisabled(), true);
  await reopen();
  assert.equal(await send.isDisabled(), true);
  assert.match(await page.locator('.send-status').innerText(), /No automatic retry/);
  assert.equal(sendCalls, 8);
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ok: true, browser: 'Chromium', synthetic_only: true,
    real_messages_sent: 0, synthetic_send_calls: sendCalls, local_status_checks: statusCalls,
    checks: ['countdown', 'no auto-send at expiry', 'daily quota', 'disabled connector', 'cancellation feedback', 'inline error',
      'single immutable send', 'receipt reload', 'unsaved edits preserved', 'uncertain state locked',
      'replaced pane reconciles accepted and uncertain results', 'pre-approval rejection is not an uncertain send',
      'unknown outcome warning survives pane navigation', 'no console errors'],
    screenshots: ['send-flow-cooldown.png', 'send-flow-inline-error.png']}));
} finally {
  if (browser) await browser.close();
  server.closeAllConnections(); await new Promise(resolve => server.close(resolve));
}
