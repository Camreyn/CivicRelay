import assert from 'node:assert/strict';
import test from 'node:test';
import {mkdtemp,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Client} from '@modelcontextprotocol/client';
import {StdioClientTransport} from '@modelcontextprotocol/client/stdio';
import {TOOLS} from './tools.mjs';
const directory=path.dirname(fileURLToPath(import.meta.url));
test('68 narrow schemas have no credential, shell, path, host, or transport policy override',()=>{
 assert.equal(TOOLS.length,68);
 for(const t of TOOLS){assert.equal(t.schema.additionalProperties,false);for(const key of Object.keys(t.schema.properties))assert.doesNotMatch(key,/password|command|path|host|approve|confirm_send/);}
 for(const name of ['desk_send_email','desk_publish_intake']){const t=TOOLS.find(t=>t.name===name);assert.equal(t.readOnly,false);assert.ok(t.schema.required.includes('expected_digest'));assert.equal(Object.hasOwn(t.schema.properties,'confirmation'),false);}
});
for(const negotiationMode of ['legacy','auto'])test(`actual MCP STDIO handshake and safe unconfigured status (${negotiationMode})`,async()=>{
 const temporary=await mkdtemp(path.join(os.tmpdir(),'records-desk-mcp-test-'));
 const transport=new StdioClientTransport({command:process.execPath,args:[path.join(directory,'tools.mjs')],cwd:directory,env:{...process.env,LOCALAPPDATA:temporary},stderr:'pipe'});
 const client=new Client({name:'records-desk-synthetic',version:'1.0.0'},{capabilities:{},negotiationMode});let errors='';transport.stderr?.on('data',c=>errors+=c.toString());
 try{await client.connect(transport);const list=await client.listTools();assert.deepEqual(list.tools.map(t=>t.name),TOOLS.map(t=>t.name));
  const status=await client.callTool({name:'desk_status',arguments:{}});assert.equal(status.structuredContent.ok,true);assert.equal(status.structuredContent.result.connector.configured,false);
  assert.equal(status.structuredContent.result.requires_desktop_confirmation,false);
  const scope=await client.callTool({name:'desk_get_mail_scope',arguments:{}});assert.equal(scope.structuredContent.ok,true);assert.equal(scope.structuredContent.result.scope.configured,false);assert.equal(scope.structuredContent.result.network_accessed,false);
  const limits=await client.callTool({name:'desk_get_send_limits',arguments:{}});assert.equal(limits.structuredContent.ok,true);assert.equal(limits.structuredContent.result.configured,false);assert.equal(limits.structuredContent.result.max_attempts_per_24h,10);
  const blockedLimits=await client.callTool({name:'desk_save_send_limits',arguments:{revision:0,max_attempts_per_24h:25,minimum_interval_seconds:30}});assert.equal(blockedLimits.structuredContent.ok,false);assert.match(blockedLimits.structuredContent.error,/Not configured/);
  const blocked=await client.callTool({name:'desk_sync_mail',arguments:{}});assert.equal(blocked.structuredContent.ok,false);assert.match(blocked.structuredContent.error,/mailbox scope/);
  const guide=await client.callTool({name:'desk_get_state_guide',arguments:{state:'MA'}});assert.equal(guide.structuredContent.result.display.default_collapsed,true);assert.equal(guide.structuredContent.result.guides.length,2);
  const sources=await client.callTool({name:'desk_get_sources',arguments:{}});assert.equal(sources.structuredContent.result.network_accessed,false);assert.equal(sources.structuredContent.result.sources[0].record_count,0);
  const municipalities=await client.callTool({name:'desk_get_municipal_contacts',arguments:{state:'MA'}});assert.equal(municipalities.structuredContent.result.coverage.municipalities,351);assert.equal(municipalities.structuredContent.result.coverage.collected,0);
  const ma=await client.callTool({name:'desk_get_ma_follow_up',arguments:{}});assert.equal(ma.structuredContent.ok,true);assert.equal(ma.structuredContent.result.network_accessed,false);assert.deepEqual(ma.structuredContent.result.cases,[]);
  const cases=await client.callTool({name:'desk_list_cases',arguments:{}});assert.equal(cases.structuredContent.result.cases.length,0,'fresh installs start blank');
  assert.equal(cases.structuredContent.result.unassigned_total,0);
  assert.equal(cases.structuredContent.result.mail_privacy.scope.configured,false);
  const deadlines=await client.callTool({name:'desk_get_deadlines',arguments:{}});assert.equal(deadlines.structuredContent.ok,true);assert.equal(deadlines.structuredContent.result.network_accessed,false);assert.deepEqual(deadlines.structuredContent.result.cases,[]);
  const workspace=await client.callTool({name:'desk_get_workspace',arguments:{}});assert.equal(workspace.structuredContent.result.workspace.starter_pack,'blank');
  const saved=await client.callTool({name:'desk_save_workspace',arguments:{revision:0,name:'Synthetic workspace',starter_pack:'civicresultmaps'}});assert.equal(saved.structuredContent.ok,true);
  const legacy=await client.callTool({name:'desk_list_cases',arguments:{}});assert.equal(legacy.structuredContent.result.cases.length,14,'opt-in pack retains exact legacy cases');
  const campaign=await client.callTool({name:'desk_get_equipment_campaign',arguments:{}});assert.equal(campaign.structuredContent.ok,true);assert.equal(campaign.structuredContent.result.states.length,51);assert.equal(campaign.structuredContent.result.counts.states_not_started,51);
  const workflow=await client.callTool({name:'desk_get_workflow',arguments:{}});assert.equal(workflow.structuredContent.ok,true);assert.equal(workflow.structuredContent.result.states.length,51);assert.equal(workflow.structuredContent.result.intake.template,'records-response.yml');
  const inbox=await client.callTool({name:'desk_list_messages',arguments:{case_id:'',limit:10}});assert.equal(inbox.structuredContent.result.messages.length,0);assert.equal(inbox.structuredContent.result.network_accessed,false);
  const researchCall=async(name,args={})=>{const r=await client.callTool({name,arguments:args});assert.equal(r.structuredContent.ok,true,r.structuredContent.error);return r.structuredContent.result;};
  assert.equal((await researchCall('desk_list_counties',{state:'MI'})).counties.length,83);
  const batch=(await researchCall('desk_create_contact_batch',{state:'MI',county_ids:['county:26001'],roles:['public_records'],request_key:'synthetic-native'})).batch;
  const task=(await researchCall('desk_claim_contact_tasks',{batch_id:batch.id,worker_id:'synthetic-native-worker',limit:1})).tasks[0];
  const day=new Date().toISOString().slice(0,10);
  await researchCall('desk_complete_contact_task',{batch_id:batch.id,task_id:task.id,lease_token:task.lease_token,result:{outcome:'blocked',checked_on:day,contacts:[],sources:[],note:'Synthetic unavailable source; no browser or real research attempted.'}});
  const progress=(await researchCall('desk_get_contact_batch',{batch_id:batch.id})).batch;assert.equal(progress.status,'complete');assert.equal(progress.unresolved_tasks,1);
  assert.equal((await researchCall('desk_get_contact',{county_id:'county:26001',role:'public_records'})).history.length,1);
  const missing=await client.callTool({name:'desk_get_intake',arguments:{issue_id:'does-not-exist'}});assert.equal(missing.isError,true);
  for(const [name,args] of [['desk_status',{password:'forbidden'}],['desk_send_email',{case_id:'source-IN-2024'}],['desk_get_case',{}]]){const r=await client.callTool({name,arguments:args});assert.equal(r.isError,true);}
  for(const [name,args,expected] of [
    ['desk_send_email',{case_id:'source-IN-2024',draft_id:'00000000-0000-4000-8000-000000000001',expected_digest:'a'.repeat(64)},/latest reviewed draft/],
    ['desk_publish_intake',{issue_id:'synthetic-missing',expected_digest:'a'.repeat(64)},/already attempted or missing/],
    ['desk_export_package',{issue_id:'synthetic-missing'},/Prepare an intake preview/]]) {
    const result=await client.callTool({name,arguments:args});
    // Valid schemas reach isolated, unconfigured workers; no external action is possible.
    assert.equal(result.structuredContent.ok,false);assert.match(result.structuredContent.error,expected);
    const legacy=await client.callTool({name,arguments:{...args,confirmation:'obsolete'}});assert.equal(legacy.isError,true);
  }
  assert.equal(errors,'');
 }finally{await client.close();assert.ok(path.resolve(temporary).startsWith(path.resolve(os.tmpdir())+path.sep));await rm(temporary,{recursive:true,force:true});}
});
