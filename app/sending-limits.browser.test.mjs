// Real Settings -> HTTP -> shared service -> isolated send ledger. No real mail.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {chromium} from 'playwright';
import {pythonExecutable} from '../runtime-config.mjs';

const fixture=spawn(pythonExecutable(),['-E','-s','-S',fileURLToPath(new URL('./sending_limits_browser_fixture.py',import.meta.url))],{cwd:fileURLToPath(new URL('.',import.meta.url)),windowsHide:true,stdio:['ignore','pipe','pipe']});
let browser,stderr='';fixture.stderr.on('data',c=>stderr+=c.toString());
try {
  const ready=await new Promise((resolve,reject)=>{
    let output='';const timer=setTimeout(()=>reject(Error('Fixture timeout: '+stderr)),20000);
    fixture.stdout.on('data',c=>{output+=c;if(output.includes('\n')){clearTimeout(timer);resolve(JSON.parse(output.split('\n')[0]));}});
    fixture.on('error',reject);fixture.on('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+': '+stderr));});
  });
  assert.equal(ready.synthetic,true);const origin=`http://127.0.0.1:${ready.port}`;
  browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1150,height:1000}});
  const errors=[],external=[],operations=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{if(new URL(route.request().url()).origin!==origin){external.push(route.request().url());return route.abort();}return route.continue();});
  page.on('request',r=>{if(r.url().endsWith('/api/operation'))operations.push(r.postDataJSON());});
  await page.goto(origin);await page.getByText('Private records workspace ready.',{exact:false}).waitFor();
  const open=async()=>{
    await page.getByRole('button',{name:'Settings',exact:true}).click();
    await page.getByRole('tab',{name:'Sending limits',exact:true}).click();
    await page.getByRole('button',{name:'Save sending limits',exact:true}).waitFor();
  };
  await open();
  const panel=page.locator('#settings-panel-sending'), max=panel.getByLabel('Maximum send attempts',{exact:false}), interval=panel.getByLabel('Minimum seconds',{exact:false});
  const save=panel.getByRole('button',{name:'Save sending limits',exact:true});
  const reload=panel.getByRole('button',{name:'Reload saved limits (discard edits)',exact:true});
  await panel.getByText('Using the default limits.',{exact:false}).waitFor();
  assert.match(await panel.innerText(),/Used: 10; remaining: 0/);
  assert.equal(operations.some(x=>x.tool==='desk_save_send_limits'),false);
  assert.equal(await max.inputValue(),'10');assert.equal(await interval.inputValue(),'60');
  assert.equal(await panel.getByRole('link').getAttribute('href'),'https://proton.me/support/email-sending-limits');
  await max.fill('25');await interval.fill('30');await save.click();
  await panel.getByText('Sending limits saved.',{exact:false}).waitFor();
  assert.match(await panel.innerText(),/Used: 10; remaining: 15/);
  assert.deepEqual(operations.find(x=>x.tool==='desk_save_send_limits').arguments,{revision:0,max_attempts_per_24h:25,minimum_interval_seconds:30});
  await page.reload();await page.getByText('Private records workspace ready.',{exact:false}).waitFor();await open();
  await panel.getByText('Saved limits loaded.',{exact:false}).waitFor();assert.equal(await max.inputValue(),'25');
  // Bad input is not sent. Closing/reopening preserves edits and their original revision.
  const saves=()=>operations.filter(x=>x.tool==='desk_save_send_limits').length;
  const before=saves();await max.fill('0');await save.click();
  await panel.getByText('Enter whole numbers within the displayed ranges.',{exact:true}).waitFor();assert.equal(saves(),before);
  await max.fill('40');await page.getByRole('button',{name:'Close settings',exact:true}).click();await open();
  await panel.getByText('Unsaved edits preserved.',{exact:false}).waitFor();assert.equal(await max.inputValue(),'40');
  // Simulate another authorized window changing the revision, through the real API.
  const api=async(tool,args)=>page.evaluate(async({tool,args})=>{
    const response=await fetch('/api/operation',{method:'POST',headers:{'Content-Type':'application/json','X-Records-Desk':'1'},body:JSON.stringify({tool,arguments:args})});
    return response.json();
  },{tool,args});
  let response=await api('desk_save_send_limits',{revision:1,max_attempts_per_24h:26,minimum_interval_seconds:30});assert.equal(response.ok,true);
  await save.click();await panel.getByText('Sending limits changed.',{exact:false}).waitFor();assert.equal(await max.inputValue(),'40');
  await reload.click();await panel.getByText('Saved limits loaded.',{exact:false}).waitFor();assert.equal(await max.inputValue(),'26');
  // A lost response must not trigger another save or a send; reload recovers the committed value.
  let dropped=false;
  await page.route('**/api/operation',async route=>{
    if(!dropped&&route.request().postDataJSON().tool==='desk_save_send_limits'){
      dropped=true;await route.fetch();return route.abort();
    }
    return route.continue();
  });
  await max.fill('30');await save.click();await panel.getByRole('status').filter({hasText:/fetch/i}).waitFor();
  assert.equal(saves(),before+3); // other-window save, stale save, lost-response save; no automatic retry
  await reload.click();await panel.getByText('Saved limits loaded.',{exact:false}).waitFor();assert.equal(await max.inputValue(),'30');
  // Lowering below usage preserves the count and reports a blocked rolling window.
  await max.fill('5');await save.click();await panel.getByText('Sending limits saved.',{exact:false}).waitFor();
  assert.match(await panel.innerText(),/Used: 10; remaining: 0/);
  response=await api('desk_status',{});assert.equal(response.result.connector.send_window.max_attempts,5);
  assert.equal(response.result.connector.send_window.reason,'daily_limit');assert.equal(response.result.connector.sending_enabled,false);
  await page.getByRole('tab',{name:'Sending limits',exact:true}).press('Home');
  await page.getByRole('tab',{name:'Sources',exact:true}).press('End');
  assert.equal(await page.getByRole('tab',{name:'Updates',exact:true}).getAttribute('aria-selected'),'true');
  await page.getByRole('tab',{name:'Updates',exact:true}).press('ArrowLeft');
  assert.equal(await page.getByRole('tab',{name:'Sending limits',exact:true}).getAttribute('aria-selected'),'true');
  const screenshot=path.join(tmpdir(),'civicrelay-sending-limits-synthetic.png');await page.screenshot({path:screenshot});
  assert.equal(operations.some(x=>/sync_mail|send_email|send_draft|publish|capture|export/.test(x.tool)),false);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  console.log(JSON.stringify({ok:true,synthetic:true,stories:['default-10-attempt-cap','save-through-real-api','persistent-policy','invalid-input','stale-edit','lost-response-recovery','lower-cap-preserves-history','keyboard-tabs'],screenshot,live_mail_accessed:false}));
} finally {await browser?.close();fixture.kill();}
