// Actual UI -> actual HTTP handler -> isolated synthetic database -> refreshed UI.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
import {pythonExecutable} from '../runtime-config.mjs';
const fixture=spawn(pythonExecutable(),['-E','-s','-S',fileURLToPath(new URL('./equipment_browser_fixture.py',import.meta.url))],
 {windowsHide:true,shell:false,stdio:['ignore','pipe','pipe'],env:{...process.env,RECORDS_DESK_NODE:process.execPath}});
let browser,stderr='';fixture.stderr.on('data',c=>stderr+=c.toString());
try{
 const ready=await new Promise((resolve,reject)=>{
  let output='';const timer=setTimeout(()=>reject(Error('Synthetic fixture startup timed out: '+stderr)),20000);
  fixture.stdout.on('data',c=>{output+=c.toString();if(output.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(output.split('\n')[0]));}catch(e){reject(e);}}});
  fixture.on('error',reject);fixture.on('exit',code=>{clearTimeout(timer);reject(Error('Synthetic fixture exited '+code+': '+stderr));});
 });
 assert.equal(ready.synthetic,true);const origin=`http://127.0.0.1:${ready.port}`;
 browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1050}});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 page.on('dialog',async d=>{errors.push('Unexpected dialog');await d.dismiss();});
 await page.route('**/*',r=>r.request().url().startsWith(origin+'/')?r.continue():r.abort());
 await page.goto(origin);await page.locator('#campaign-queue tr').first().waitFor();
 assert.equal(await page.locator('#campaign-mode').inputValue(),'equipment');
 assert.equal(await page.locator('#map g.state').count(),51);
 assert.equal(await page.locator('#campaign-queue tr').count(),51);
 assert.match(await page.locator('#stats').innerText(),/51/);assert.match(await page.locator('#state-count').innerText(),/9 started · 42 not started/);
 await page.selectOption('#campaign-filter','remaining');assert.equal(await page.locator('#campaign-queue tr').count(),42);
 await page.selectOption('#campaign-filter','active');assert.equal(await page.locator('#campaign-queue tr').count(),9);
 await page.selectOption('#state-select','PA');await page.getByRole('button',{name:'Open request',exact:true}).click();
 assert.match(await page.locator('#body').inputValue(),/No fees are authorized/);
 assert.match(await page.locator('#case-workspace').innerText(),/Separate user approval is required/);
 await page.locator('#case-note').fill('Synthetic browser persistence check. No real correspondence.');
 await page.getByRole('button',{name:'Save privately',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('Request saved privately'));
 await page.reload();await page.locator('#campaign-queue tr').first().waitFor();await page.selectOption('#state-select','PA');
 await page.getByRole('button',{name:'Open request',exact:true}).click();
 assert.equal(await page.locator('#case-note').inputValue(),'Synthetic browser persistence check. No real correspondence.');
 await page.selectOption('#campaign-mode','records');assert.equal(await page.locator('#campaign-panel').isVisible(),false);
 assert.equal(await page.locator('#queue tr').count(),14,'legacy catalog requests remain separate');
 await page.selectOption('#campaign-mode','equipment');
 const response=await page.request.post(origin+'/api/operation',{headers:{Origin:origin,'X-Records-Desk':'1'},data:{tool:'desk_get_equipment_campaign',arguments:{}}});
 const result=await response.json();assert.equal(result.ok,true);assert.equal(result.result.counts.requests_with_send_confirmation,0);
 const pa=result.result.states.find(s=>s.state==='PA');
 const invalid=await page.request.post(origin+'/api/operation',{headers:{Origin:origin,'X-Records-Desk':'1'},data:{tool:'desk_save_equipment_progress',arguments:{case_id:pa.requests[0].id,revision:pa.requests[0].revision,response_stage:'none',deadline_date:'2026-10-01'}}});
 assert.equal(invalid.status(),400);assert.match((await invalid.json()).error,/deadline requires/);
 // Screenshot contains synthetic fixtures only; never capture the user's mailbox.
 await page.locator('#case-workspace').evaluate(n=>n.hidden=true);
 await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));
 await page.screenshot({path:fileURLToPath(new URL('./equipment-synthetic.png',import.meta.url))});
 assert.deepEqual(errors,[]);assert.equal(stderr,'');
 console.log(JSON.stringify({ok:true,states:51,started:9,remaining:42,legacy_requests:14,ui_api_database_persistence:true,unverified_deadline_rejected:true,real_emails_sent:0,console_errors:0}));
}finally{if(browser)await browser.close();fixture.kill();}
