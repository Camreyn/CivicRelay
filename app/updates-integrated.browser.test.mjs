// Browser -> guarded HTTP -> real updater state/package verification; all external sources mocked.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
import {pythonExecutable} from '../runtime-config.mjs';
import {workerEnvironment} from '../connector/server.mjs';
const fixture = spawn(pythonExecutable(), ['-B','-E','-s','-S',fileURLToPath(new URL('./updates_browser_fixture.py',import.meta.url))], {env:workerEnvironment(),windowsHide:true,shell:false,stdio:['ignore','pipe','pipe']});
let browser;
try {
  const started = await new Promise((resolve,reject) => {
    let output=''; const timeout=setTimeout(()=>reject(Error('Synthetic update fixture did not start.')),15000);
    fixture.stdout.on('data',chunk=>{output+=chunk; if(output.includes('\n')){clearTimeout(timeout);try{resolve(JSON.parse(output.split('\n')[0]));}catch(error){reject(error);}}});
    fixture.on('error',error=>{clearTimeout(timeout);reject(error);});
    fixture.on('exit',()=>{clearTimeout(timeout);reject(Error('Synthetic fixture stopped before readiness.'));});
  });
  const origin=`http://127.0.0.1:${started.port}`, calls=[], errors=[], external=[];
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage();
  page.on('pageerror',error=>errors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')errors.push(message.text());});
  await page.route('**/*',route=>{
    const request=route.request(), url=new URL(request.url());
    if(url.origin!==origin){external.push(url.href);return route.abort();}
    if(url.pathname==='/api/updates')calls.push(request.postDataJSON());
    return route.continue();
  });
  await page.goto(origin);
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  await page.getByRole('tab',{name:'Updates',exact:true}).click();
  const panel=page.locator('#settings-panel-updates');
  await panel.getByText('Installed version: 0.9.0',{exact:false}).waitFor();
  assert.equal(calls.some(call=>call.action==='check'),false);
  await panel.getByRole('checkbox').check();
  await panel.getByRole('button',{name:'Save update preference'}).click();
  await panel.getByText('Update preference saved.',{exact:false}).waitFor();
  assert.equal(calls.some(call=>call.action==='approve'),false);
  // Opt-in survives a real reload; the startup check uses only public metadata.
  await page.reload();
  await page.getByRole('button',{name:'Settings · Update available',exact:true}).waitFor();
  assert.equal(calls.filter(call=>call.action==='check'&&call.arguments.automatic===true).length,1);
  await page.getByRole('button',{name:'Settings · Update available',exact:true}).click();
  await page.getByRole('tab',{name:'Updates',exact:true}).click();
  await panel.getByRole('heading',{name:'Version 0.10.0 is available'}).waitFor();
  assert.equal(await panel.locator('img').count(),0);
  await panel.getByRole('button',{name:'Approve and download update'}).click();
  await panel.getByText('It has NOT been installed',{exact:false}).waitFor();
  assert.equal(await panel.getByRole('button',{name:'Approve and download update'}).isDisabled(),true);
  assert.match(await panel.locator('ol').innerText(),/Update CivicRelay.cmd/);
  await panel.getByRole('button',{name:'Cancel ready update plan'}).click();
  await panel.getByRole('heading',{name:'Update plan cancelled; files retained'}).waitFor();
  assert.equal(await panel.getByRole('button',{name:'Approve and download update'}).isDisabled(),false);
  assert.equal(calls.filter(call=>call.action==='approve').length,1);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  console.log(JSON.stringify({ok:true,synthetic:true,browser_api_state_package_flow:true,opt_in_reload:true,one_daily_check:true,approval_and_cancellation:true,no_install_activation:true,live_mail_accessed:false}));
} finally {
  await browser?.close();
  if(fixture.exitCode===null){const stopped=once(fixture,'exit');fixture.kill();await stopped;}
}
