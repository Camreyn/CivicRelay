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
test('40 narrow schemas have no credential, shell, path, host, or policy override',()=>{
 assert.equal(TOOLS.length,40);
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
  const cases=await client.callTool({name:'desk_list_cases',arguments:{}});assert.equal(cases.structuredContent.result.cases.length,0,'fresh installs start blank');
  assert.equal(cases.structuredContent.result.unassigned_total,0);
  const workspace=await client.callTool({name:'desk_get_workspace',arguments:{}});assert.equal(workspace.structuredContent.result.workspace.starter_pack,'blank');
  const saved=await client.callTool({name:'desk_save_workspace',arguments:{revision:0,name:'Synthetic workspace',starter_pack:'civicresultmaps'}});assert.equal(saved.structuredContent.ok,true);
  const legacy=await client.callTool({name:'desk_list_cases',arguments:{}});assert.equal(legacy.structuredContent.result.cases.length,14,'opt-in pack retains exact legacy cases');
  const campaign=await client.callTool({name:'desk_get_equipment_campaign',arguments:{}});assert.equal(campaign.structuredContent.ok,true);assert.equal(campaign.structuredContent.result.states.length,51);assert.equal(campaign.structuredContent.result.counts.states_not_started,51);
  const workflow=await client.callTool({name:'desk_get_workflow',arguments:{}});assert.equal(workflow.structuredContent.ok,true);assert.equal(workflow.structuredContent.result.states.length,51);assert.equal(workflow.structuredContent.result.intake.template,'records-response.yml');
  const inbox=await client.callTool({name:'desk_list_messages',arguments:{case_id:'',limit:10}});assert.equal(inbox.structuredContent.result.messages.length,0);assert.equal(inbox.structuredContent.result.network_accessed,false);
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
