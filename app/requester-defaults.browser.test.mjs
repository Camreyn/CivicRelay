// Settings -> HTTP -> encrypted synthetic workspace -> template -> frozen draft. No live mail.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {chromium} from 'playwright';
import {pythonExecutable} from '../runtime-config.mjs';

const fixture=spawn(pythonExecutable(),['-E','-s','-S',fileURLToPath(new URL('./general_browser_fixture.py',import.meta.url))],
  {windowsHide:true,stdio:['ignore','pipe','pipe'],env:{...process.env,RECORDS_DESK_NODE:process.execPath}});
let browser,stderr='';fixture.stderr.on('data',value=>stderr+=value.toString());
try {
  const ready=await new Promise((resolve,reject)=>{
    let output='';const timer=setTimeout(()=>reject(Error('Synthetic fixture timeout: '+stderr)),20000);
    fixture.stdout.on('data',value=>{output+=value;if(output.includes('\n')){clearTimeout(timer);resolve(JSON.parse(output.split('\n')[0]));}});
    fixture.on('error',reject);fixture.on('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+': '+stderr));});
  });
  assert.equal(ready.synthetic,true);const origin=`http://127.0.0.1:${ready.port}`;
  browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1200,height:1050}});
  const errors=[],external=[],operations=[];page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>{if(new URL(route.request().url()).origin!==origin){external.push(route.request().url());return route.abort();}return route.continue();});
  page.on('request',request=>{if(request.url().endsWith('/api/operation'))operations.push(request.postDataJSON());});
  const api=async(tool,args={})=>{
    const response=await page.request.post(origin+'/api/operation',{headers:{Origin:origin,'X-Records-Desk':'1'},data:{tool,arguments:args}});
    const body=await response.json();assert.equal(body.ok,true,body.error);return body.result;
  };
  const open=async()=>{
    await page.getByRole('button',{name:'Settings',exact:true}).click();
    await page.getByRole('tab',{name:'Requester defaults',exact:true}).click();
  };
  await page.goto(origin);await page.getByRole('button',{name:'Workspace settings',exact:true}).waitFor();await open();
  const panel=page.locator('#settings-panel-requester'), save=panel.getByRole('button',{name:'Save requester defaults',exact:true});
  const reload=panel.getByRole('button',{name:'Reload saved defaults (discard edits)',exact:true});
  await panel.getByText('Saved requester defaults loaded.',{exact:false}).waitFor();
  assert.equal(operations.some(value=>value.tool==='desk_save_workspace'),false);
  assert.equal(await panel.getByLabel('Use postal address by default',{exact:true}).isChecked(),false);
  const defaults={rname:'Example Requester',raddress:'123 Synthetic Street',rphone:'555-0100',remail:'contact@example.test',org:'Example Organization',rtitle:'Records coordinator',sign:'Example Requester\nExample Organization'};
  for(const [suffix,value] of Object.entries(defaults))await page.locator('#defaults-'+suffix).fill(value);
  for(const checkbox of await panel.getByRole('checkbox').all())await checkbox.check();
  // Invalid contact email never reaches the save tool.
  await page.locator('#defaults-remail').fill('invalid');await save.click();
  await panel.getByText('Check the contact email',{exact:false}).waitFor();
  assert.equal(operations.some(value=>value.tool==='desk_save_workspace'),false);
  await page.locator('#defaults-remail').fill(defaults.remail);await save.click();
  await panel.getByText('Requester defaults saved privately.',{exact:false}).waitFor();
  let current=(await api('desk_get_workspace')).workspace;
  assert.equal(current.requester_email,defaults.remail);assert.equal((await api('desk_get_workspace')).account.email,'synthetic.relay@example.test');
  assert.equal(current.identity_enabled.requester_address,true);
  await page.getByRole('button',{name:'Close settings',exact:true}).click();await page.reload();
  await page.getByRole('button',{name:'Workspace settings',exact:true}).waitFor();await open();
  await panel.getByText('Saved requester defaults loaded.',{exact:false}).waitFor();assert.equal(await page.locator('#defaults-rtitle').inputValue(),defaults.rtitle);
  // Unsaved values/revision survive reopening; a concurrent edit cannot be overwritten.
  await page.locator('#defaults-org').fill('Unsaved org');await page.getByRole('button',{name:'Close settings',exact:true}).click();await open();
  await panel.getByText('Unsaved edits preserved.',{exact:false}).waitFor();assert.equal(await page.locator('#defaults-org').inputValue(),'Unsaved org');
  await api('desk_save_workspace',{revision:current.revision,name:'Another window'});
  await save.click();await panel.getByText('Workspace changed in another window.',{exact:false}).waitFor();
  assert.equal(await page.locator('#defaults-org').inputValue(),'Unsaved org');
  await reload.click();await panel.getByText('Saved requester defaults loaded.',{exact:false}).waitFor();
  assert.equal(await page.locator('#defaults-org').inputValue(),defaults.org);
  // Exercise all built-ins through the real service, then inspect the browser preview.
  const definition={schema_version:1,title:'Identity defaults fixture',fields:[],subject:'Synthetic identity request',body:'Identity: {{requester_name}} | {{organization}} | {{requester_title}} | {{requester_email}} | {{requester_phone}}\n{{#if requester_address}}Address: {{requester_address}}{{/if}}\n{{signature}}',sources:[]};
  const template=(await api('desk_save_template',{definition})).template;
  const campaign=(await api('desk_save_campaign',{name:'Identity fixture',description:'',template_id:template.id,targets:[{id:'a',label:'Synthetic Agency',level:'other'}]})).campaign;
  const before=(await api('desk_create_request',{campaign_id:campaign.id,target_id:'a',agency:'Synthetic Agency',values:{}})).case;
  assert.match(before.body,/Example Requester/);assert.match(before.body,/123 Synthetic Street/);
  await api('desk_save_case',{case_id:before.id,revision:before.revision,recipient:'records@example.test',subject:before.subject,body:before.body,routing_verified:true,routing_evidence:'https://agency.example.test/records'});
  const draft=(await api('desk_prepare_email',{case_id:before.id})).draft;
  current=(await api('desk_get_workspace')).workspace;
  await api('desk_save_workspace',{revision:current.revision,organization:'Changed Organization',signature:'',identity_enabled:{requester_address:false,requester_phone:false}});
  const after=(await api('desk_get_case',{case_id:before.id}));
  assert.equal(after.case.body,before.body);assert.deepEqual(after.drafts[0],draft);
  const rendered=(await api('desk_preview_template',{template_id:template.id,values:{}})).rendered.body;
  assert.match(rendered,/Changed Organization/);assert.doesNotMatch(rendered,/123 Synthetic Street|555-0100|Staff/);
  const oneoff=(await api('desk_preview_template',{template_id:template.id,values:{requester_address:'One-off address',organization:''}})).rendered.body;
  assert.match(oneoff,/One-off address/);assert.doesNotMatch(oneoff,/Changed Organization/);
  const exported=await api('desk_export_template',{template_id:template.id});
  assert.equal(JSON.stringify(exported).includes('identity_enabled'),false);
  assert.equal(JSON.stringify(exported).includes(defaults.rname),false);
  await page.getByRole('button',{name:'Close settings',exact:true}).click();await page.reload();
  await page.getByRole('button',{name:definition.title,exact:true}).click();
  await page.getByRole('button',{name:'Preview',exact:true}).click();
  await page.locator('#template-preview').filter({hasText:'Changed Organization'}).waitFor();
  assert.doesNotMatch(await page.locator('#template-preview').innerText(),/123 Synthetic Street|555-0100|Staff/);
  // Referenced identity built-ins expose one-off controls even without declared fields.
  await page.locator('#tv-override-requester_name').check();
  await page.locator('#tv-requester_name').fill('UI Preview Name');
  await page.locator('#tv-override-organization').check();
  await page.locator('#tv-organization').fill('');
  await page.getByRole('button',{name:'Preview',exact:true}).click();
  await page.locator('#template-preview').filter({hasText:'UI Preview Name'}).waitFor();
  assert.doesNotMatch(await page.locator('#template-preview').innerText(),/Changed Organization/);
  // Saving Settings refreshes inherited values, preserving explicit edits and blanks.
  await open();await reload.click();await panel.getByText('Saved requester defaults loaded.',{exact:false}).waitFor();
  await page.locator('#defaults-rtitle').fill('Updated title');await save.click();
  await panel.getByText('Requester defaults saved privately.',{exact:false}).waitFor();
  await page.getByRole('button',{name:'Close settings',exact:true}).click();
  assert.equal(await page.locator('#tv-requester_title').inputValue(),'Updated title');
  assert.equal(await page.locator('#tv-requester_name').inputValue(),'UI Preview Name');
  assert.equal(await page.locator('#tv-organization').inputValue(),'');
  await page.getByRole('button',{name:'Preview',exact:true}).click();
  await page.locator('#template-preview').filter({hasText:'Updated title'}).waitFor();
  // The create-request form uses the same controls and preserves explicit blank overrides.
  await page.reload();await page.getByRole('button',{name:campaign.name,exact:true}).click();
  await page.getByRole('button',{name:'Create request',exact:true}).click();
  await page.locator('#rq-name').fill('Synthetic UI agency');
  await page.locator('#tv-override-requester_name').check();await page.locator('#tv-requester_name').fill('UI Request Name');
  await page.locator('#tv-override-organization').check();await page.locator('#tv-organization').fill('');
  const createdResponse=page.waitForResponse(response=>response.url().endsWith('/api/operation')&&response.request().postDataJSON()?.tool==='desk_create_request');
  await page.getByRole('button',{name:'Create private request',exact:true}).click();
  const createdBody=await (await createdResponse).json();assert.equal(createdBody.ok,true,createdBody.error);
  assert.match(createdBody.result.case.body,/UI Request Name/);assert.doesNotMatch(createdBody.result.case.body,/Changed Organization/);
  // An uncertain save response is recovered by explicit reload, never auto-retried.
  await open();await reload.click();await panel.getByText('Saved requester defaults loaded.',{exact:false}).waitFor();
  let dropped=false;
  await page.route('**/api/operation',async route=>{
    if(!dropped&&route.request().postDataJSON().tool==='desk_save_workspace'){dropped=true;await route.fetch();return route.abort();}
    return route.continue();
  });
  const saves=()=>operations.filter(value=>value.tool==='desk_save_workspace').length;
  const count=saves();await page.locator('#defaults-org').fill('Recovered Organization');await save.click();
  await panel.getByRole('status').filter({hasText:/fetch/i}).waitFor();assert.equal(saves(),count+1);
  await reload.click();await panel.getByText('Saved requester defaults loaded.',{exact:false}).waitFor();
  assert.equal(await page.locator('#defaults-org').inputValue(),'Recovered Organization');
  await page.locator('#civic-settings').evaluate(node=>{node.scrollTop=0;});
  const screenshot=path.join(tmpdir(),'civicrelay-requester-defaults-synthetic.png');await page.locator('#civic-settings').screenshot({path:screenshot});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.locator('#civic-settings').evaluate(node=>node.scrollWidth<=node.clientWidth+1),true);
  await page.locator('#civic-settings').evaluate(node=>{node.scrollTop=0;});
  const mobileScreenshot=path.join(tmpdir(),'civicrelay-requester-defaults-mobile-synthetic.png');await page.locator('#civic-settings').screenshot({path:mobileScreenshot});
  assert.equal(operations.some(value=>/sync_mail|send_email|send_draft|publish|capture|export_package/.test(value.tool)),false);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  console.log(JSON.stringify({ok:true,synthetic:true,stories:['private-defaults-real-api','all-fields-and-switches','sender-email-separation','persistent-settings','stale-edits-preserved','template-preview','disabled-defaults-and-overrides','case-and-draft-immutability','definition-export-privacy','undeclared-builtins-ui-overrides','settings-refresh-preserves-one-off-edits','new-request-ui-overrides','uncertain-save-recovery','mobile-layout'],screenshot,mobileScreenshot,live_mail_accessed:false}));
} finally {await browser?.close();fixture.kill();}
