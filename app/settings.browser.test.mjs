// Synthetic Settings component check. No live server, mailbox, network source or private store.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {chromium} from 'playwright';

const origin = 'http://settings.test';
const assets = new Map([
  ['/settings.js', ['text/javascript', await readFile(new URL('./static/settings.js', import.meta.url), 'utf8')]],
  ['/settings.css', ['text/css', await readFile(new URL('./static/settings.css', import.meta.url), 'utf8')]],
  ['/style.css', ['text/css', await readFile(new URL('./static/style.css', import.meta.url), 'utf8')]],
]);
const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/settings.css"><title>Synthetic settings fixture</title></head><body>
<button id="open">Settings</button><main id="settings-host"></main>
<script type="module">
import {createSettings} from '/settings.js';
window.calls = []; window.changed = 0; window.failInventory = false; window.hold = null;
window.sources = [{id:'ma-test',state:'MA',label:'Synthetic municipal directory',description:'Fixture only; no real contact information.',url:'https://agency.example.test/directory',last_attempt_at:'2026-09-01T12:00:00Z',last_success_at:'2026-09-01T12:00:00Z',record_count:351,expected_count:351,checked_on:'2026-09-01',collection_mode:'direct_fetch',last_result:{ok:true,code:'collected',message:'Synthetic collection saved.',debug:[]}},
{id:'safe-link-test',state:'XX',label:'Synthetic unsafe link',description:'URL handling test',url:'javascript:alert(1)',record_count:0}];
window.outcome = {ok:false,code:'source_blocked',message:'The source blocked this request. Saved records are unchanged.',attempted_at:'2026-09-23T12:00:00Z',record_count:351,last_success_at:'2026-09-01T12:00:00Z',debug:['HTTP 200 contained a challenge page.', '<img src=x onerror=window.injected=true>']};
window.api = async (tool,args) => {
  window.calls.push({tool,args});
  if(tool === 'desk_get_sources') {
    if(window.failInventory) throw Error('Synthetic unavailable inventory');
    return structuredClone({sources:window.sources});
  }
  if(tool !== 'desk_refresh_source' && tool !== 'desk_import_source') throw Error('Unexpected operation: '+tool);
  if(window.hold) await window.hold;
  if(window.throwRefresh) throw Error('Synthetic transport failure');
  const result={...structuredClone(window.outcome),source_id:args.source_id};
  window.sources=window.sources.map(s=>s.id===args.source_id?{...s,last_attempt_at:result.attempted_at,last_success_at:result.last_success_at,record_count:result.record_count,collection_mode:result.collection_mode||s.collection_mode,last_result:result}:s);
  return result;
};
window.settings=createSettings({host:document.getElementById('settings-host'),api:window.api,onSourcesChanged:async()=>{window.changed++;}});
document.getElementById('open').onclick=()=>window.settings.open();
</script></body></html>`;

let browser;
try {
  browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1200,height:1000}}), errors = [], external = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {if(message.type()==='error') errors.push(message.text());});
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    if(url.origin !== origin) {external.push(url.href); return route.abort();}
    if(url.pathname === '/') return route.fulfill({status:200,contentType:'text/html',body:html});
    const asset = assets.get(url.pathname);
    if(asset) return route.fulfill({status:200,contentType:asset[0],body:asset[1]});
    return route.fulfill({status:404,body:''});
  });
  await page.goto(origin);
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  await page.getByText('2 supported sources.',{exact:false}).waitFor();
  const settings = page.locator('#civic-settings'), source = settings.locator('[data-source-id="ma-test"]');
  assert.equal(await settings.evaluate(node=>node.open),true);
  assert.equal(await page.evaluate(()=>window.calls.length),1);
  assert.equal(await source.locator('.settings-import').evaluate(node=>node.open),false);
  assert.equal(await settings.locator('a').count(),1);
  assert.equal(await source.getByRole('link').getAttribute('rel'),'noopener noreferrer');
  assert.match(await source.innerText(),/351 of 351 expected entries/);
  assert.match(await source.innerText(),/Official source checked on\s+2026-09-01/);
  await settings.getByRole('tab',{name:'Sources',exact:true}).press('ArrowRight');
  assert.equal(await settings.getByRole('tab',{name:'State guides',exact:true}).getAttribute('aria-selected'),'true');
  assert.match(await settings.locator('#settings-panel-guides').innerText(),/starts collapsed/);
  await settings.getByRole('tab',{name:'State guides',exact:true}).press('Home');
  assert.equal(await settings.getByRole('tab',{name:'Sources',exact:true}).getAttribute('aria-selected'),'true');
  // Refresh is explicit, serial, and blocked failures keep the previous collection visible.
  await page.evaluate(()=>{window.hold=new Promise(resolve=>window.release=resolve);});
  await source.getByRole('button',{name:'Refresh source:',exact:false}).click();
  await page.getByText('Refreshing Synthetic municipal directory…',{exact:false}).waitFor();
  assert.equal(await source.getByRole('button',{name:'Refresh source:',exact:false}).isDisabled(),true);
  await settings.getByRole('button',{name:'Close settings',exact:true}).click();
  await page.evaluate(()=>{window.release();window.hold=null;});
  await page.waitForFunction(()=>document.querySelector('#settings-source-status').textContent.startsWith('Refresh did not complete.'));
  assert.equal(await page.locator('#settings-refresh-result').evaluate(node=>node.open),false);
  await page.locator('#open').click();
  const result = page.locator('#settings-refresh-result');
  await result.getByRole('heading',{name:'Source could not be refreshed'}).waitFor();
  await result.locator('summary').click();
  assert.match(await result.locator('pre').innerText(),/HTTP 200 contained a challenge/);
  assert.equal(await result.locator('img').count(),0);
  assert.equal(await page.evaluate(()=>window.injected),undefined);
  await result.getByRole('button',{name:'Done',exact:true}).click();
  assert.match(await source.innerText(),/Saved records\s+351/);
  assert.match(await source.innerText(),/Last error: The source blocked/);
  assert.equal(await page.evaluate(()=>window.changed),0);
  // Text-import inputs survive a saved-status reload, failure, and closing/reopening Settings.
  await source.getByText('Import reviewed directory text',{exact:true}).click();
  await source.getByLabel('Date the official source was checked (UTC)').fill('2026-09-23');
  await source.getByLabel('Complete reviewed directory text').fill('Existing reviewed text.');
  const picker = source.getByLabel('Choose local .txt file (optional)');
  const beforeFile = await page.evaluate(()=>window.calls.length);
  await picker.setInputFiles({name:'directory.txt',mimeType:'text/plain',buffer:Buffer.from('Synthetic reviewed directory text only.')});
  await source.getByText('Loaded directory.txt into the unsaved text field.',{exact:false}).waitFor();
  assert.equal(await source.getByLabel('Complete reviewed directory text').inputValue(),'Synthetic reviewed directory text only.');
  assert.equal(await page.evaluate(()=>window.calls.length),beforeFile);
  await picker.setInputFiles({name:'not-directory.html',mimeType:'text/html',buffer:Buffer.from('<script>window.fileInjected=true</script>')});
  await source.getByText('Choose a plain-text .txt file, not HTML or another format.',{exact:false}).waitFor();
  assert.equal(await page.evaluate(()=>window.fileInjected),undefined);
  await picker.setInputFiles({name:'too-large.txt',mimeType:'text/plain',buffer:Buffer.alloc(200001,65)});
  await source.getByText('The .txt file must contain 1–200,000 bytes.',{exact:false}).waitFor();
  assert.equal(await source.getByLabel('Complete reviewed directory text').inputValue(),'Synthetic reviewed directory text only.');
  // Check the post-read character bound independently of the pre-read byte bound.
  await page.evaluate(()=>{window.originalFileText=File.prototype.text;File.prototype.text=async()=> 'a'.repeat(200001);});
  await picker.setInputFiles({name:'decoded-too-large.txt',mimeType:'text/plain',buffer:Buffer.from('short')});
  await source.getByText('The file must contain nonempty text of at most 200,000 characters.',{exact:false}).waitFor();
  await page.evaluate(()=>{File.prototype.text=window.originalFileText;delete window.originalFileText;});
  assert.equal(await source.getByLabel('Complete reviewed directory text').inputValue(),'Synthetic reviewed directory text only.');
  assert.equal(await page.evaluate(()=>window.calls.length),beforeFile);
  await settings.getByRole('button',{name:'Reload saved status',exact:true}).click();
  assert.equal(await source.getByLabel('Complete reviewed directory text').inputValue(),'Synthetic reviewed directory text only.');
  await source.getByRole('button',{name:'Import reviewed text',exact:true}).click();
  await result.getByRole('heading',{name:'Source could not be refreshed'}).waitFor();
  await result.getByRole('button',{name:'Done',exact:true}).click();
  assert.equal(await source.getByLabel('Complete reviewed directory text').inputValue(),'Synthetic reviewed directory text only.');
  await settings.getByRole('button',{name:'Close settings',exact:true}).click();
  assert.equal(await page.locator('#open').evaluate(node=>node===document.activeElement),true);
  await page.locator('#open').click();
  await page.getByText('2 supported sources.',{exact:false}).waitFor();
  assert.equal(await source.getByLabel('Complete reviewed directory text').inputValue(),'Synthetic reviewed directory text only.');
  await page.evaluate(()=>{window.failInventory=true;window.outcome={ok:true,code:'imported',message:'Synthetic full directory parsed and saved.',attempted_at:'2026-09-23T13:00:00Z',last_success_at:'2026-09-23T13:00:00Z',checked_on:'2026-09-23',record_count:351,collection_mode:'reviewed_text_import',debug:['351 synthetic municipalities accepted.']};});
  await source.getByRole('button',{name:'Import reviewed text',exact:true}).click();
  await result.getByRole('heading',{name:'Reviewed source text imported'}).waitFor();
  await result.getByRole('button',{name:'Done',exact:true}).click();
  assert.equal(await source.getByLabel('Complete reviewed directory text').inputValue(),'');
  assert.match(await source.innerText(),/Reviewed directory text import/);
  assert.match(await source.innerText(),/Official source checked on\s+2026-09-23/);
  assert.equal(await page.evaluate(()=>window.changed),1);
  // A transport failure is not treated as a failed/no-write receipt and never auto-retries.
  const before = await page.evaluate(()=>window.calls.filter(c=>c.tool==='desk_refresh_source').length);
  await page.evaluate(()=>{window.throwRefresh=true;});
  await source.getByRole('button',{name:'Refresh source:',exact:false}).click();
  await result.getByRole('heading',{name:'Source could not be refreshed'}).waitFor();
  assert.match(await result.innerText(),/could not be confirmed/);
  assert.equal(await page.evaluate(()=>window.calls.filter(c=>c.tool==='desk_refresh_source').length),before+1);
  await result.getByRole('button',{name:'Done',exact:true}).click();
  await page.evaluate(()=>{window.throwRefresh=false;window.failInventory=true;});
  await settings.getByRole('button',{name:'Reload saved status',exact:true}).click();
  await settings.getByText('Could not load saved source status.',{exact:false}).waitFor();
  assert.match(await source.innerText(),/Saved records\s+351/);
  const screenshot = path.join(tmpdir(),'civicrelay-settings-synthetic.png');
  await settings.screenshot({path:screenshot});
  // Small screens retain horizontal room for every panel and usable modal controls.
  await page.setViewportSize({width:390,height:844});
  assert.equal(await settings.evaluate(node=>node.scrollWidth<=node.clientWidth+1),true);
  const mobileScreenshot = path.join(tmpdir(),'civicrelay-settings-mobile-synthetic.png');
  await settings.screenshot({path:mobileScreenshot});
  await page.keyboard.press('Escape');
  assert.equal(await settings.evaluate(node=>node.open),false);
  const calls = await page.evaluate(()=>window.calls);
  assert.deepEqual([...new Set(calls.map(call=>call.tool))].sort(),['desk_get_sources','desk_import_source','desk_refresh_source']);
  const imported = calls.find(call=>call.tool==='desk_import_source').args;
  assert.deepEqual(imported,{source_id:'ma-test',checked_on:'2026-09-23',text:'Synthetic reviewed directory text only.'});
  assert.deepEqual(errors,[]);
  assert.deepEqual(external,[]);
  console.log(JSON.stringify({ok:true,synthetic:true,stories:['read-only-open','keyboard-tabs-focus-return','explicit-serial-source-refresh','closed-panel-retains-result','preserved-old-collection-on-failure','source-link-and-debug-text-safety','local-txt-selection-unsaved','file-type-byte-character-guards','reviewed-import-input-preservation','explicit-import-result-method','receipt-date-fallback-on-reload-failure','uncertain-operation-no-retry','mobile-layout'],screenshot,mobileScreenshot,external_actions:0}));
} finally {
  await browser?.close();
}
