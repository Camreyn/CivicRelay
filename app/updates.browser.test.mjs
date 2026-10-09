// Synthetic update UI only. Public network, installer execution and real stores are blocked.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {chromium} from 'playwright';
const origin = 'http://updates.test';
const assets = new Map();
for (const name of ['updates.js', 'settings.css', 'style.css']) assets.set('/' + name, await readFile(new URL('./static/' + name, import.meta.url), 'utf8'));
const initial = {installed_version: '0.9.0', automatic_checks: false, last_checked_at: null, latest: null, last_error: null, approved: null, update_available: false, check_interval_seconds: 86400};
const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/settings.css"></head><body><main id="host"></main><script type="module">
import {createUpdates} from '/updates.js';
window.state=${JSON.stringify(initial)};window.calls=[];window.available=false;window.fail=false;
window.ui=createUpdates({host:document.querySelector('#host'),onAvailable:value=>window.available=value,request:async(action,args)=>{
 window.calls.push({action,args}); if(window.hold)await window.hold;if(window.fail)throw Error('Synthetic unavailable response');
 if(action==='preferences')window.state.automatic_checks=args.automatic_checks;
 if(action==='check'){window.state.last_checked_at=Date.now()/1000;window.state.latest={version:'0.10.0',notes:'<img src=x onerror=window.injected=true> Fictional release notes',package:{sha256:'a'.repeat(64)}};window.state.update_available=true;}
 if(action==='approve'){window.state.approved={stage:'ready',destination:'C:\\Synthetic\\CivicRelay-v0.10.0-fixture'};}
 return structuredClone(window.state);
}});window.ui.start(window.state);
</script></body></html>`;
let browser;
try {
  browser = await chromium.launch({headless: true});
  const page = await browser.newPage({viewport: {width: 1100, height: 1200}}), errors = [], external = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) { external.push(url.href); return route.abort(); }
    if (url.pathname === '/') return route.fulfill({status: 200, contentType: 'text/html', body: html});
    if (assets.has(url.pathname)) return route.fulfill({status: 200, contentType: url.pathname.endsWith('.js') ? 'text/javascript' : 'text/css', body: assets.get(url.pathname)});
    return route.fulfill({status: 404, body: ''});
  });
  await page.goto(origin);
  await page.getByText('Installed version: 0.9.0', {exact: false}).waitFor();
  assert.equal(await page.evaluate(() => window.calls.length), 0, 'No startup network action when checks are disabled');
  const preference = page.getByRole('checkbox');
  assert.equal(await preference.isChecked(), false);
  assert.equal(await page.getByRole('button', {name: 'Approve and download update'}).isDisabled(), true);
  await page.getByRole('button', {name: 'Check for updates', exact: true}).click();
  await page.getByRole('heading', {name: 'Version 0.10.0 is available'}).waitFor();
  assert.equal(await page.evaluate(() => window.available), true);
  assert.equal(await page.locator('img').count(), 0);
  assert.equal(await page.evaluate(() => window.injected), undefined);
  assert.match(await page.locator('.settings-update-notes').innerText(), /<img/);
  await preference.check();
  await page.getByRole('button', {name: 'Reload update status'}).click();
  await page.waitForFunction(() => !document.querySelector('main').getAttribute('aria-busy') || document.querySelector('main').getAttribute('aria-busy') === 'false');
  assert.equal(await preference.isChecked(), true, 'Unsaved preference survives status reload');
  assert.equal(await page.evaluate(() => window.state.automatic_checks), false);
  await page.getByRole('button', {name: 'Save update preference'}).click();
  await page.getByText('Update preference saved.', {exact: false}).waitFor();
  assert.equal(await page.evaluate(() => window.state.automatic_checks), true);
  assert.equal(await page.evaluate(() => window.calls.filter(call => call.action === 'approve').length), 0);
  // Automatic checks only check metadata; recent checks are throttled.
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  assert.equal(await page.evaluate(() => window.calls.filter(call => call.action === 'check').length), 1);
  await page.evaluate(() => { window.state.last_checked_at = 0; });
  await page.getByRole('button', {name: 'Reload update status'}).click();
  await page.getByText('Update status loaded.', {exact: false}).waitFor();
  await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
  await page.waitForFunction(() => window.calls.some(call => call.action === 'check' && call.args.automatic === true));
  assert.equal(await page.evaluate(() => window.calls.filter(call => call.action === 'approve').length), 0);
  await page.evaluate(() => { window.hold = new Promise(resolve => window.release = resolve); });
  await page.getByRole('button', {name: 'Approve and download update'}).click();
  await page.getByText('Downloading and verifying', {exact: false}).waitFor();
  assert.equal(await page.getByRole('button', {name: 'Check for updates', exact: true}).isDisabled(), true);
  await page.evaluate(() => { window.release(); window.hold = null; });
  await page.getByText('It has NOT been installed', {exact: false}).waitFor();
  assert.match(await page.locator('ol').innerText(), /close the dashboard SERVER/i);
  assert.match(await page.locator('ol').innerText(), /type INSTALL/i);
  assert.match(await page.locator('ol').innerText(), /preserving tool allowlists and permissions/i);
  await page.evaluate(() => { window.fail = true; });
  await page.getByRole('button', {name: 'Check for updates', exact: true}).click();
  await page.getByText('Could not confirm the update action.', {exact: false}).waitFor();
  assert.equal(await page.getByRole('heading', {name: 'Approved package is ready'}).count(), 1);
  assert.equal(await page.evaluate(() => window.calls.filter(call => call.action === 'approve').length), 1);
  assert.deepEqual(errors, []); assert.deepEqual(external, []);
  console.log(JSON.stringify({ok: true, automatic_checks_opt_in: true, explicit_download_only: true, no_install_execution: true, preserved_edits: true, unsafe_notes_literal: true}));
} finally { if (browser) await browser.close(); }
