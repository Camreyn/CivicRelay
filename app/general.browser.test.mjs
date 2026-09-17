// Real browser/HTTP/storage; temporary fake mailbox and fake GitHub only.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {readFile,stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
import {pythonExecutable} from '../runtime-config.mjs';

const fixture=spawn(pythonExecutable(),['-E','-s','-S',fileURLToPath(new URL('./general_browser_fixture.py',import.meta.url))],
 {windowsHide:true,shell:false,stdio:['ignore','pipe','pipe'],env:{...process.env,RECORDS_DESK_NODE:process.execPath}});
let browser,page,stderr='';fixture.stderr.on('data',x=>stderr+=x.toString());
const stopped=()=>new Promise(resolve=>{if(fixture.exitCode!==null)return resolve();fixture.once('exit',resolve);fixture.kill();});
const errors=[],stories=[];
try {
 const ready=await new Promise((resolve,reject)=>{
  let out='';const timer=setTimeout(()=>reject(Error(`Fixture startup timed out: ${stderr}`)),20000);
  fixture.stdout.on('data',x=>{out+=x;if(out.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(out.split('\n')[0]));}catch(e){reject(e);}}});
  fixture.once('error',reject);fixture.once('exit',code=>{clearTimeout(timer);reject(Error(`Fixture exited ${code}: ${stderr}`));});
 });
 assert.equal(ready.synthetic,true);const origin=`http://127.0.0.1:${ready.port}`;
 browser=await chromium.launch({headless:true});page=await browser.newPage({viewport:{width:1440,height:1050}});
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 page.on('dialog',async d=>{errors.push(`Unexpected dialog: ${d.message()}`);await d.dismiss();});
 await page.route('**/*',route=>route.request().url().startsWith(origin+'/')?route.continue():route.abort());
 const button=name=>page.getByRole('button',{name,exact:true});
 async function operation(tool,action){
  const waiting=page.waitForResponse(r=>r.url()===origin+'/api/operation'&&r.request().method()==='POST'&&r.request().postDataJSON()?.tool===tool);
  await action();const response=await waiting;const body=await response.json();assert.equal(body.ok,true,`${tool}: ${body.error}`);return body.result;
 }
 async function api(tool,args={}){
  const response=await page.request.post(origin+'/api/operation',{headers:{Origin:origin,'X-Records-Desk':'1'},data:{tool,arguments:args}});
  const body=await response.json();assert.equal(body.ok,true,`${tool}: ${body.error}`);return body.result;
 }
 async function hook(path,data={}){const r=await page.request.post(origin+'/__fixture__/'+path,{headers:{'X-Relay-Fixture-Token':ready.token},data});const body=await r.json();assert.equal(body.ok,true,body.error);return body;}
 async function home(){await page.goto(origin);await button('Workspace settings').waitFor();}
 async function openCampaign(){await home();await button('Synthetic campaign').click();await button('Create request').first().waitFor();}
 async function openRequest(){await openCampaign();await button('Open correspondence').first().click();await page.locator('#recipient').waitFor();}

 await home();assert.equal(await page.locator('#campaign-mode').inputValue(),'general');assert.equal((await api('desk_list_cases')).catalog.cases.length,0);
 await button('Workspace settings').click();await page.locator('#ws-name').fill('Synthetic desk');await page.locator('#ws-org').fill('Synthetic organization');await page.locator('#ws-rname').fill('Synthetic private requester');
 await operation('desk_save_workspace',()=>button('Save private workspace').click());await home();await button('Workspace settings').click();assert.equal(await page.locator('#ws-name').inputValue(),'Synthetic desk');await home();stories.push('blank-profile-persistence');

 await button('New template').click();await page.locator('#td-title').fill('Synthetic request');await page.locator('#td-subject').fill('Request {{topic}}');await page.locator('#td-body').fill('Synthetic body {{topic}}');
 await button('Add Field').click();let row=page.locator('#template-fields > div');await row.locator('input').nth(0).fill('topic');await row.locator('input').nth(1).fill('Topic');await row.locator('input[type=checkbox]').check();
 await button('Add Source').click();row=page.locator('#template-sources > div');await row.locator('input').nth(0).fill('Official records page');await row.locator('input').nth(1).fill('https://example.gov/records');await row.locator('input').nth(2).fill('2026-09-17');
 const saved=await operation('desk_save_template',()=>button('Create template').click());const templateId=saved.template.id;await home();await button('Synthetic request').click();await page.locator('#tv-topic').fill('Preview only');await operation('desk_preview_template',()=>button('Preview').click());assert.match(await page.locator('#template-preview').innerText(),/Preview only/);
 const downloading=page.waitForEvent('download');await button('Export definition').click();const download=await downloading;const exported=JSON.parse(await readFile(await download.path(),'utf8'));assert.equal(exported.title,'Synthetic request');assert.ok(!JSON.stringify(exported).includes('Synthetic private requester'));
 await button('Duplicate').click();await page.locator('#td-title').fill('Duplicate request');await operation('desk_save_template',()=>button('Create template').click());await home();await button('Duplicate request').click();await button('Edit as new version').click();await page.locator('#td-archived').check();await operation('desk_save_template',()=>button('Save new version').click());
 await home();const choosing=page.waitForEvent('filechooser');await button('Import definition').click();const chooser=await choosing;await operation('desk_import_template',()=>chooser.setFiles({name:'template.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({...exported,title:'Imported request'}))}));
 assert.equal((await api('desk_list_templates')).templates.length,3);stories.push('template-preview-duplicate-archive-export-import');

 await home();await button('New campaign').click();await page.locator('#ca-name').fill('Synthetic campaign');await page.locator('#ca-template').selectOption(templateId);await page.locator('#ca-start').fill('2026-09-01');await page.locator('#ca-end').fill('2026-10-01');
 await button('Add Target').click();await button('Add Target').click();const targets=page.locator('#campaign-targets > div');
 for(const [index,id,label] of [[0,'federal-test','Synthetic federal agency'],[1,'county-test','Synthetic County']]){await targets.nth(index).locator('input').nth(0).fill(id);await targets.nth(index).locator('input').nth(1).fill(label);}
 await targets.nth(1).locator('select').selectOption('county');await targets.nth(1).locator('input').nth(2).fill('PA');await operation('desk_save_campaign',()=>button('Create campaign').click());
 await openCampaign();assert.match(await page.locator('#general-workspace').innerText(),/2 target\(s\) not started/);await button('Create request').first().click();await page.locator('#rq-name').fill('Synthetic custodian');await page.locator('#tv-topic').fill('Synthetic topic');
 const created=await operation('desk_create_request',()=>button('Create private request').click());const caseId=created.case.id;await page.locator('#case-workspace').waitFor();assert.equal(await page.locator('#body').inputValue(),'Synthetic body Synthetic topic');
 await home();await button('Synthetic request').click();await button('Edit as new version').click();await page.locator('#td-body').fill('NEW version {{topic}}');await operation('desk_save_template',()=>button('Save new version').click());await openRequest();assert.equal(await page.locator('#body').inputValue(),'Synthetic body Synthetic topic');
 assert.equal((await api('desk_get_template',{template_id:templateId})).template.versions.length,2);assert.equal((await api('desk_list_campaigns')).campaigns[0].remaining_targets,1);stories.push('campaign-targets-frozen-version-reopen');

 await page.locator('#recipient').fill('records@example.test');await page.locator('#routing-evidence').fill('https://example.gov/records');await page.locator('#routing-verified').check();await operation('desk_save_case',()=>button('Save privately').click());
 await operation('desk_prepare_email',()=>button('Prepare exact send preview').click());await button('Send this one email').waitFor();const sent=await operation('desk_send_email',()=>button('Send this one email').click());assert.equal(sent.state,'accepted');
 await openRequest();assert.match(await page.locator('#send-previews').innerText(),/State: accepted/);assert.equal((await api('desk_list_campaigns')).campaigns[0].target_progress[0].requests[0].stage,'waiting');stories.push('routing-exact-draft-fake-smtp-receipt');

 const seeded=await hook('seed-inbox',{case_id:caseId,unassigned:true});await home();await page.locator('#unassigned select').selectOption(caseId);await operation('desk_link_message',()=>page.locator('#unassigned').getByRole('button',{name:'Assign',exact:true}).click());
 await openRequest();await operation('desk_read_message',()=>page.locator('#conversation').getByRole('button',{name:'Read',exact:true}).click());
 // Wait for the body-read render before clicking a control it replaces.
 await page.locator('#conversation pre').waitFor();await operation('desk_capture_attachments',()=>button('Capture returned files').click());await page.getByRole('heading',{name:'synthetic.csv',exact:true}).waitFor();
 let detail=await api('desk_get_case',{case_id:caseId});assert.equal(detail.artifacts.length,1);const artifactId=detail.artifacts[0].id;
 await page.locator('#artifact-'+artifactId).check();const zipped=await operation('desk_export_case',()=>button('Export private case package').click());assert.equal(zipped.exported,true);assert.ok((await stat(zipped.path)).size>100);assert.equal(zipped.publicly_uploaded,false);
 await openCampaign();await button('Track response').first().click();await page.locator('#gp-response').selectOption('records_received');await page.locator('#gp-message').selectOption(seeded.message_id);await page.locator('#gp-coverage').selectOption('received');await operation('desk_save_request_progress',()=>button('Save progress').click());
 detail=await api('desk_get_case',{case_id:caseId});assert.equal(detail.case.tracking.response_stage,'records_received');assert.equal(detail.case.publication_status,'none');stories.push('inbox-assignment-read-capture-export-evidence-progress');

 await home();await button('Publication destinations').click();await button('New destination').click();await page.locator('#de-name').fill('Synthetic intake');await page.locator('#de-repo').fill('synthetic/example');await page.locator('#de-template').fill('synthetic.yml');
 const target=await operation('desk_save_destination',()=>button('Save destination').click());const destinationId=target.destination.id;
 await openRequest();await page.locator('#intake-destination').selectOption(destinationId);await page.locator('#intake-summary').fill('Synthetic reviewed summary');const prepared=await operation('desk_prepare_publication',()=>button('Prepare public preview — no publishing').click());await page.getByRole('heading',{name:'Exact public submission preview',exact:true}).waitFor();
 assert.equal(prepared.issue.target_snapshot.repository,'synthetic/example');assert.equal((await hook('publication')).publications,0);
 // Changing the mapping invalidates the visible and backend old preview.
 await home();await button('Publication destinations').click();await button('Edit destination').click();await page.locator('#de-name').fill('Renamed synthetic intake');await operation('desk_save_destination',()=>button('Save destination').click());
 await openRequest();assert.equal(await button('Publish this public issue').count(),0);assert.match(await page.locator('#intake').innerText(),/destination has changed/);
 await operation('desk_prepare_publication',()=>button('Prepare public preview — no publishing').click());await button('Publish this public issue').waitFor();const published=await operation('desk_publish_intake',()=>button('Publish this public issue').click());assert.equal(published.state,'published');assert.equal((await hook('publication')).publications,1);
 detail=await api('desk_get_case',{case_id:caseId});assert.equal(detail.case.tracking.response_stage,'records_received');assert.equal(detail.case.publication_status,'published');assert.equal(detail.case.stage,'waiting');
 // A fake accepted issue with a lost response becomes uncertain; link, never retry.
 await openRequest();await page.locator('#intake-summary').fill('Synthetic second reviewed update');const second=await operation('desk_prepare_publication',()=>button('Prepare public preview — no publishing').click());await hook('publication',{lose_next_response:true});
 await button('Publish this public issue').waitFor();const uncertain=await operation('desk_publish_intake',()=>button('Publish this public issue').click());assert.equal(uncertain.state,'uncertain');
 await openRequest();assert.equal(await button('Publish this public issue').count(),0);const remote=await hook('publication');assert.equal(remote.publications,2);await page.locator('#issue-url').fill(remote.urls.at(-1));const reconciled=await operation('desk_link_issue',()=>button('Verify and link existing issue').click());assert.equal(reconciled.issue.id,second.issue.id);assert.equal(reconciled.issue.state,'published');
 stories.push('explicit-destination-invalidation-fake-publication-uncertainty-reconciliation');
 await home();await page.screenshot({path:fileURLToPath(new URL('./general-synthetic.png',import.meta.url))});await page.setViewportSize({width:720,height:1000});await page.screenshot({path:fileURLToPath(new URL('./general-synthetic-mobile.png',import.meta.url))});
 assert.deepEqual(errors,[]);assert.equal(stderr,'');console.log(JSON.stringify({ok:true,synthetic:true,stories,real_emails_sent:0,real_issues_created:0,external_network:0,console_errors:0}));
} catch(error) {
 if(page){console.error('Synthetic failure notice:',await page.locator('#notice').innerText().catch(()=>''));await page.screenshot({path:fileURLToPath(new URL('./general-synthetic-failure.png',import.meta.url))}).catch(()=>{});}
 throw error;
} finally {if(browser)await browser.close();await stopped();}
