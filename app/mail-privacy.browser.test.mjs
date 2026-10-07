// Fictional Settings interactions only. Every request is intercepted; no mail account.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {tmpdir} from 'node:os';
import {chromium} from 'playwright';

const origin = 'http://mail-privacy.test';
const assets = new Map();
for(const name of ['mail-privacy.js','sending-limits.js','settings.js','settings.css','style.css'])assets.set('/'+name,await readFile(new URL('./static/'+name,import.meta.url),'utf8'));
const html = `<!doctype html><html lang="en"><meta charset="utf-8"><title>Synthetic privacy test</title><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/settings.css"><main id="host"></main><script type="module">
import {createSettings} from '/settings.js';
window.calls=[];window.changed=0;window.fail=false;window.hold=null;
window.saved={scope:{configured:false,revision:0,folders:{}},hidden_imports:2};
window.api=async(tool,args)=>{
  window.calls.push({tool,args});
  if(tool==='desk_get_sources')return {sources:[]};
  if(window.hold)await window.hold;
  if(window.fail)throw Error('Synthetic stale preview. Nothing was removed.');
  if(tool==='desk_get_mail_scope')return structuredClone(window.saved);
  if(tool==='desk_preview_mail_scope')return {preview_id:'a'.repeat(32),digest:'b'.repeat(64),scope:{mode:args.mode,import_history:args.import_history,folders:{INBOX:{remote_folder:args.incoming_folder||'INBOX',minimum_uid:45,existing_messages_at_preview:45}}},warning:'Synthetic selected-folder preview only.'};
  if(tool==='desk_apply_mail_scope'){window.saved.scope={configured:true,mode:'folders',folders:{INBOX:{remote_folder:'Folders/CivicRelay'}}};return structuredClone(window.saved);}
  if(tool==='desk_preview_mail_cleanup')return {preview_id:'c'.repeat(32),digest:'d'.repeat(64),count:1,remaining_hidden_candidates:0,protected_count:3,warning:'Local copies only; originals and send history stay unchanged.',candidates:[{from:'example@example.test',subject:'<img src=x onerror=window.injected=true>',date:'Synthetic date',body_loaded:true}]};
  if(tool==='desk_apply_mail_cleanup'){window.saved.hidden_imports=0;return {removed_local_messages:1};}
  throw Error('Unexpected operation '+tool);
};
window.ui=createSettings({host:document.getElementById('host'),api:window.api,onMailChanged:async()=>{window.changed++}});window.ui.open();
</script></html>`;
let browser;
try {
  browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1200,height:1000}}), errors = [], external = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) {external.push(url.href);return route.abort();}
    return route.fulfill({status:200,contentType:url.pathname==='/'?'text/html':url.pathname.endsWith('.css')?'text/css':'text/javascript',body:url.pathname==='/'?html:assets.get(url.pathname)||''});
  });
  await page.goto(origin);
  await page.getByRole('tab',{name:'Mail privacy',exact:true}).click();
  await page.getByText('Mail reading is paused until a scope is selected.',{exact:false}).waitFor();
  assert.equal(await page.getByLabel('Mailbox access mode').inputValue(),'folders');
  assert.equal(await page.getByRole('checkbox').isChecked(),false);
  assert.deepEqual(await page.evaluate(()=>window.calls.map(x=>x.tool)),['desk_get_sources','desk_get_mail_scope']);
  // A preview does not apply scope, sync mail or read headers; inputs invalidate it.
  await page.getByRole('button',{name:'Preview mail scope',exact:true}).click();
  await page.getByRole('heading',{name:'Review before activating'}).waitFor();
  assert.equal(await page.evaluate(()=>window.calls.at(-1).args.import_history),false);
  assert.match(await page.locator('body').innerText(),/Existing history will be skipped/);
  await page.getByLabel('Incoming Bridge folder path').fill('Labels/CivicRelay');
  assert.equal(await page.getByRole('button',{name:'Apply reviewed mail scope'}).count(),0);
  await page.getByLabel('Incoming Bridge folder path').fill('Folders/CivicRelay');
  await page.getByRole('button',{name:'Preview mail scope',exact:true}).click();
  await page.getByRole('button',{name:'Apply reviewed mail scope'}).click();
  await page.getByText('Mail scope saved.',{exact:false}).waitFor();
  assert.equal(await page.evaluate(()=>window.changed),1);
  assert.deepEqual(await page.evaluate(()=>window.calls.find(x=>x.tool==='desk_apply_mail_scope').args),{preview_id:'a'.repeat(32),expected_digest:'b'.repeat(64)});
  // Untrusted header text is rendered as text; no markup or remote image loads.
  await page.getByRole('button',{name:'Preview cleanup of hidden imports'}).click();
  await page.getByRole('heading',{name:'1 local imports proposed for removal'}).waitFor();
  assert.equal(await page.locator('img').count(),0);assert.equal(await page.evaluate(()=>window.injected),undefined);
  assert.equal(await page.evaluate(()=>window.calls.some(x=>x.tool==='desk_apply_mail_cleanup')),false);
  await page.evaluate(()=>{window.fail=true});
  await page.getByRole('button',{name:'Remove listed local imports'}).click();
  await page.getByText('Synthetic stale preview. Nothing was removed.',{exact:true}).waitFor();
  await page.evaluate(()=>{window.fail=false;window.hold=new Promise(resolve=>window.release=resolve)});
  await page.getByRole('button',{name:'Remove listed local imports'}).click();
  assert.equal(await page.getByRole('button',{name:'Remove listed local imports'}).isDisabled(),true);
  await page.evaluate(()=>{window.release();window.hold=null});
  await page.getByText('Removed 1 local imports.',{exact:false}).waitFor();
  assert.equal(await page.evaluate(()=>window.changed),2);
  // Dedicated mode must be deliberate; history remains off unless explicitly checked.
  await page.getByLabel('Mailbox access mode').selectOption('dedicated');
  assert.equal(await page.getByLabel('Incoming Bridge folder path').isVisible(),false);
  await page.getByRole('checkbox').check();
  await page.getByRole('button',{name:'Preview mail scope',exact:true}).click();
  await page.getByText('Existing history WILL be included.',{exact:false}).waitFor();
  assert.deepEqual(await page.evaluate(()=>window.calls.at(-1).args),{mode:'dedicated',import_history:true});
  assert.equal(await page.evaluate(()=>window.calls.some(x=>/sync_mail|read_message|send_email/.test(x.tool))),false);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  const screenshot=path.join(tmpdir(),'civicrelay-mail-privacy-synthetic.png');
  await page.screenshot({path:screenshot,fullPage:true});
  console.log('Synthetic privacy screenshot: '+screenshot);
  console.log('Synthetic mail privacy UI passed: safe defaults, exact previews, stale cleanup, no HTML execution or automatic mail access.');
} finally {await browser?.close();}
