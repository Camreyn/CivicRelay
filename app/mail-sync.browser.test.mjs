// Real dashboard -> HTTP -> service -> disposable store -> synthetic Bridge.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
import {pythonExecutable} from '../runtime-config.mjs';

const fixture=spawn(pythonExecutable(),['-E','-s','-S',fileURLToPath(new URL('./mail_sync_browser_fixture.py',import.meta.url))],{cwd:fileURLToPath(new URL('.',import.meta.url)),windowsHide:true,stdio:['ignore','pipe','pipe']});
let browser,stderr='';fixture.stderr.on('data',c=>stderr+=c.toString());
try {
  const ready=await new Promise((resolve,reject)=>{
    let output='';const timer=setTimeout(()=>reject(Error('Fixture timeout: '+stderr)),20000);
    fixture.stdout.on('data',c=>{output+=c;if(output.includes('\n')){clearTimeout(timer);resolve(JSON.parse(output.split('\n')[0]));}});
    fixture.on('error',reject);fixture.on('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+': '+stderr));});
  });
  assert.equal(ready.synthetic,true);const origin=`http://127.0.0.1:${ready.port}`;
  browser=await chromium.launch({headless:true});const page=await browser.newPage();
  const errors=[],external=[],operations=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{if(new URL(route.request().url()).origin!==origin){external.push(route.request().url());return route.abort();}return route.continue();});
  page.on('request',r=>{if(r.url().endsWith('/api/operation'))operations.push(r.postDataJSON().tool);});
  const fixtureAction=async action=>{
    const response=await page.request.post(origin+'/__fixture__/mail',{headers:{'X-Relay-Fixture-Token':ready.token},data:{action}});
    assert.equal(response.status(),200);return response.json();
  };
  const sync=async count=>{
    const response=page.waitForResponse(r=>r.url().endsWith('/api/operation')&&r.request().postDataJSON().tool==='desk_sync_mail');
    await page.getByRole('button',{name:'Check for replies',exact:true}).click();
    const body=await (await response).json();assert.equal(body.ok,true);assert.equal(body.result.new_headers,count);
    await page.waitForFunction(n=>document.getElementById('notice').textContent.startsWith(`${n} new headers synced. Mailbox check complete.`),count);
    assert.equal(await page.locator('#notice').getAttribute('class'),'');
  };
  await page.goto(origin);
  try {await page.getByText('Private records workspace ready.',{exact:false}).waitFor();}
  catch(error) {throw Error(`${error.message}\nNotice: ${await page.locator('#notice').innerText()}\nOperations: ${JSON.stringify(operations)}\nFixture: ${stderr}`);}
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  await page.getByRole('tab',{name:'Mail privacy',exact:true}).click();
  await page.getByLabel('Incoming Bridge folder path').fill('Folders/CivicRelay');
  await page.getByLabel('Sent Bridge folder path (optional)').fill('Labels/CivicRelay Sent');
  assert.equal(await page.getByRole('checkbox').isChecked(),false);
  await page.getByRole('button',{name:'Preview mail scope',exact:true}).click();
  await page.getByRole('heading',{name:'Review before activating'}).waitFor();
  await page.getByRole('button',{name:'Apply reviewed mail scope'}).click();
  await page.getByText('Mail scope saved.',{exact:false}).waitFor();
  await page.getByRole('button',{name:'Close settings',exact:true}).click();
  assert.equal(operations.filter(x=>x==='desk_sync_mail').length,0);
  await sync(0);
  let state=await fixtureAction('inspect');assert.deepEqual(state.searches,[]);assert.deepEqual(state.fetches,[]);
  await fixtureAction('arrival');await sync(1);await sync(0);
  state=await fixtureAction('inspect');assert.equal(state.saved_headers,1);
  assert.deepEqual(state.searches,[['Folders/CivicRelay','1:1']]);
  assert.deepEqual(state.fetches.map(x=>x.slice(0,2)),[['Folders/CivicRelay',1]]);
  // A genuine NO in a populated label must remain visible, with no cursor skip.
  await fixtureAction('fail');
  await page.getByRole('button',{name:'Check for replies',exact:true}).click();
  await page.locator('#notice.error').filter({hasText:'Bridge could not search the selected mail folder.'}).waitFor();
  state=await fixtureAction('inspect');assert.equal(state.saved_headers,1);
  await fixtureAction('recover');await sync(1);
  state=await fixtureAction('inspect');assert.equal(state.saved_headers,2);
  assert.ok(state.fetches.every(x=>x[0]==='Folders/CivicRelay'&&x[2].includes('BODY.PEEK')));
  assert.equal(operations.some(x=>/send|publish|cleanup|export/.test(x)),false);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  console.log(JSON.stringify({ok:true,synthetic:true,stories:['preview-empty-labels','empty-sync-no-search','first-arrival-imported-once','real-search-failure-visible','recovery-without-cursor-skip'],live_mail_accessed:false}));
} finally {await browser?.close();fixture.kill();}
