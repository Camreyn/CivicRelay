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
test('20 narrow schemas have no credential, shell, path, host, or policy override',()=>{
 assert.equal(TOOLS.length,20);
 for(const t of TOOLS){assert.equal(t.schema.additionalProperties,false);for(const key of Object.keys(t.schema.properties))assert.doesNotMatch(key,/password|command|path|host|approve|confirm_send/);}
 for(const name of ['desk_send_email','desk_publish_intake']){const t=TOOLS.find(t=>t.name===name);assert.equal(t.readOnly,false);assert.ok(t.schema.required.includes('expected_digest'));assert.ok(t.schema.required.includes('confirmation'));}
});
for(const negotiationMode of ['legacy','auto'])test(`actual MCP STDIO handshake and safe unconfigured status (${negotiationMode})`,async()=>{
 const temporary=await mkdtemp(path.join(os.tmpdir(),'records-desk-mcp-test-'));
 const transport=new StdioClientTransport({command:process.execPath,args:[path.join(directory,'tools.mjs')],cwd:directory,env:{...process.env,LOCALAPPDATA:temporary},stderr:'pipe'});
 const client=new Client({name:'records-desk-synthetic',version:'1.0.0'},{capabilities:{},negotiationMode});let errors='';transport.stderr?.on('data',c=>errors+=c.toString());
 try{await client.connect(transport);const list=await client.listTools();assert.deepEqual(list.tools.map(t=>t.name),TOOLS.map(t=>t.name));
  const status=await client.callTool({name:'desk_status',arguments:{}});assert.equal(status.structuredContent.ok,true);assert.equal(status.structuredContent.result.connector.configured,false);
  const cases=await client.callTool({name:'desk_list_cases',arguments:{}});assert.equal(cases.structuredContent.result.cases.length,14);
  assert.equal(cases.structuredContent.result.unassigned_total,0);
  const workflow=await client.callTool({name:'desk_get_workflow',arguments:{}});assert.equal(workflow.structuredContent.ok,true);assert.equal(workflow.structuredContent.result.states.length,51);assert.equal(workflow.structuredContent.result.intake.template,'records-response.yml');
  const inbox=await client.callTool({name:'desk_list_messages',arguments:{case_id:'',limit:10}});assert.equal(inbox.structuredContent.result.messages.length,0);assert.equal(inbox.structuredContent.result.network_accessed,false);
  const missing=await client.callTool({name:'desk_get_intake',arguments:{issue_id:'does-not-exist'}});assert.equal(missing.isError,true);
  for(const [name,args] of [['desk_status',{password:'forbidden'}],['desk_send_email',{case_id:'source-IN-2024'}],['desk_get_case',{}]]){const r=await client.callTool({name,arguments:args});assert.equal(r.isError,true);}
  assert.equal(errors,'');
 }finally{await client.close();assert.ok(path.resolve(temporary).startsWith(path.resolve(os.tmpdir())+path.sep));await rm(temporary,{recursive:true,force:true});}
});
