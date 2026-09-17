// Rehearse the configuration users actually generate, not just the server schemas.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {Client} from '@modelcontextprotocol/client';
import {StdioClientTransport} from '@modelcontextprotocol/client/stdio';
import {TOOLS as deskTools} from '../app/static/tool-contracts.mjs';
import {TOOLS as mailTools,workerEnvironment} from '../connector/server.mjs';
import {pythonExecutable} from '../runtime-config.mjs';
import {buildMcpConfig} from './configure-codex.mjs';

const root=fileURLToPath(new URL('..',import.meta.url));
const python=pythonExecutable();
const template=fs.readFileSync(new URL('../docs/mcp-config.example.toml',import.meta.url),'utf8');
const values={ROOT:root.replace(/[\\/]$/,''),NODE:process.execPath,PYTHON:python,GH:process.execPath};
const expected={proton_mail:mailTools,records_desk:deskTools};

function parseConfig(text){
 const result=spawnSync(python,['-E','-s','-S','-c','import json,sys,tomllib; print(json.dumps(tomllib.loads(sys.stdin.read())))'],
  {input:text,encoding:'utf8',windowsHide:true,shell:false,timeout:10000,env:workerEnvironment()});
 assert.equal(result.status,0,result.stderr||result.error?.message);
 return JSON.parse(result.stdout);
}
function assertCoverage(config){
 assert.deepEqual(Object.keys(config.mcp_servers).sort(),Object.keys(expected).sort());
 for(const [name,tools] of Object.entries(expected)){
  const server=config.mcp_servers[name];
  assert.equal(server.enabled,true,name);
  assert.deepEqual([...server.enabled_tools].sort(),tools.map(t=>t.name).sort(),`${name}: every shipped tool must be enabled exactly once`);
  assert.deepEqual(server.disabled_tools||[],[],`${name}: shipped tools must not be denied by the starter config`);
  assert.ok(Object.keys(server.tools||{}).every(tool=>server.enabled_tools.includes(tool)));
 }
}
function temporary(){return fs.mkdtempSync(path.join(os.tmpdir(),'civic-relay-config-test-'));}
function cleanup(directory){
 // Only a direct, test-created child of Windows Temp may be recursively removed.
 assert.equal(path.dirname(path.resolve(directory)),path.resolve(os.tmpdir()));
 assert.ok(path.basename(directory).startsWith('civic-relay-config-test-'));
 assert.equal(fs.lstatSync(directory).isSymbolicLink(),false);
 fs.rmSync(directory,{recursive:true,force:true});
}

test('generated TOML enables every advertised mail/records tool and detects allowlist drift',()=>{
 const config=parseConfig(buildMcpConfig(template,values));
 assertCoverage(config);
 for(const change of [
  c=>c.mcp_servers.records_desk.enabled_tools.pop(),
  c=>c.mcp_servers.records_desk.enabled_tools.push('desk_removed_tool'),
  c=>c.mcp_servers.records_desk.enabled_tools.push('desk_status'),
  c=>c.mcp_servers.records_desk.disabled_tools=['desk_get_workspace'],
  c=>c.mcp_servers.records_desk.enabled=false,
 ]){const changed=structuredClone(config);change(changed);assert.throws(()=>assertCoverage(changed),assert.AssertionError);}
});

test('generated configuration retains explicit local paths and existing host permission policy',()=>{
 const config=parseConfig(buildMcpConfig(template,values));
 assert.deepEqual(Object.keys(config),['mcp_servers']);
 for(const [name,server] of Object.entries(config.mcp_servers)){
  assert.equal(server.command,values.NODE);
  assert.equal(server.env.CRM_PROTON_PYTHON,values.PYTHON);
  assert.equal(server.default_tools_approval_mode,'writes');
  assert.equal(server.required,false);
  assert.ok(path.isAbsolute(server.cwd));
  assert.equal(server.args.length,1);assert.ok(fs.statSync(server.args[0]).isFile());
  assert.equal(server.url,undefined);
  assert.deepEqual(Object.keys(server.tools).sort(),(name==='proton_mail'?['proton_send_draft']:['desk_send_email','desk_publish_intake','desk_export_package']).sort());
  for(const policy of Object.values(server.tools))assert.deepEqual(policy,{approval_mode:'prompt'});
 }
});

test('fresh CLI setup generates parseable complete config and never overwrites an existing file',()=>{
 const directory=temporary();
 try{
  // A minimal, test-owned source fixture; never run the generator against live .codex files.
  for(const file of ['scripts/configure-codex.mjs','runtime-config.mjs','docs/mcp-config.example.toml']){
   const target=path.join(directory,file);fs.mkdirSync(path.dirname(target),{recursive:true});fs.copyFileSync(path.join(root,file),target);
  }
  const invoke=(args=[])=>spawnSync(process.execPath,[path.join(directory,'scripts/configure-codex.mjs'),...args],
   {cwd:directory,encoding:'utf8',windowsHide:true,shell:false,timeout:10000,
    env:{...workerEnvironment(),CRM_PROTON_PYTHON:python,RECORDS_DESK_GH:process.execPath}});
  const initial=invoke();assert.equal(initial.status,0,initial.stderr);assert.match(initial.stdout,/Global settings were not changed/);
  const file=path.join(directory,'.codex/config.toml'),before=fs.readFileSync(file);
  const config=parseConfig(before.toString('utf8'));assertCoverage(config);
  assert.equal(config.mcp_servers.records_desk.cwd,path.join(directory,'app'));
  assert.equal(config.mcp_servers.proton_mail.cwd,path.join(directory,'connector'));
  const repeated=invoke();assert.notEqual(repeated.status,0);assert.match(repeated.stderr,/EEXIST/);
  assert.deepEqual(fs.readFileSync(file),before);
  assert.notEqual(invoke(['--overwrite']).status,0);assert.deepEqual(fs.readFileSync(file),before);
 }finally{cleanup(directory);}
});

for(const negotiationMode of ['legacy','auto'])test(`generated configuration reaches the full private workflow over real MCP (${negotiationMode})`,{timeout:90000},async()=>{
 const directory=temporary(),clients=[];
 try{
  const config=parseConfig(buildMcpConfig(template,values));assertCoverage(config);
  const connected={};
  for(const [name,server] of Object.entries(config.mcp_servers)){
   const transport=new StdioClientTransport({command:server.command,args:server.args,cwd:server.cwd,
    env:{...workerEnvironment(),...server.env,LOCALAPPDATA:directory},stderr:'pipe'});
   const client=new Client({name:'civic-relay-config-rehearsal',version:'1.0.0'},{capabilities:{},negotiationMode});
   clients.push(client);await client.connect(transport);
   const advertised=await client.listTools();
   assert.deepEqual(advertised.tools.map(t=>t.name).sort(),[...server.enabled_tools].sort());
   connected[name]=async(tool,args={})=>{
    assert.ok(server.enabled_tools.includes(tool),`${tool} must be available through the generated host allowlist`);
    const result=await client.callTool({name:tool,arguments:args});
    assert.notEqual(result.isError,true,JSON.stringify(result.structuredContent));
    assert.equal(result.structuredContent?.ok,true);
    return result.structuredContent.result;
   };
  }
  const mail=connected.proton_mail,desk=connected.records_desk;
  assert.equal((await mail('proton_status')).configured,false);
  assert.equal((await desk('desk_status')).connector.configured,false);
  assert.equal((await desk('desk_get_workspace')).workspace.starter_pack,'blank');
  await desk('desk_save_workspace',{revision:0,name:'Synthetic desk',signature:'Synthetic operator'});
  const definition={schema_version:1,title:'Synthetic records',fields:[{id:'topic',label:'Topic',required:true,type:'text'}],
   subject:'Existing records: {{jurisdiction}}',body:'Please provide {{topic}}.\n{{signature}}',sources:[]};
  let saved=(await desk('desk_import_template',{definition})).template;
  assert.equal((await desk('desk_list_templates')).templates.length,1);
  const preview=await desk('desk_preview_template',{template_id:saved.id,values:{topic:'synthetic files',jurisdiction:'Example office'}});
  assert.match(preview.rendered.body,/synthetic files/);assert.match(preview.rendered.body,/Synthetic operator/);
  saved=(await desk('desk_save_template',{template_id:saved.id,revision:saved.revision,definition:{...definition,title:'Synthetic records revised'}})).template;
  assert.equal((await desk('desk_get_template',{template_id:saved.id})).template.versions.length,2);
  const exported=await desk('desk_export_template',{template_id:saved.id});
  assert.equal(exported.definition.title,'Synthetic records revised');assert.doesNotMatch(JSON.stringify(exported),/Synthetic operator/);
  const campaign=(await desk('desk_save_campaign',{name:'Synthetic campaign',description:'Configuration rehearsal only',template_id:saved.id,
   targets:[{id:'one',label:'Example federal office',level:'federal'},{id:'two',label:'Another office',level:'other'}]})).campaign;
  const request=(await desk('desk_create_request',{campaign_id:campaign.id,target_id:'one',agency:'Example agency',values:{topic:'synthetic files'}})).case;
  const progress=await desk('desk_list_campaigns');assert.equal(progress.campaigns[0].remaining_targets,1);
  assert.equal((await desk('desk_get_case',{case_id:request.id})).case.template_snapshot.version,2);
  await desk('desk_save_request_progress',{case_id:request.id,revision:request.revision,response_stage:'none',coverage:'not_assessed',note:'Synthetic tracking only'});
  const destination=(await desk('desk_save_destination',{name:'Synthetic destination',repository:'example/synthetic-records',template:'',labels:[],enabled:true,
   fields:[{id:'summary',label:'Summary',type:'textarea',required:true,options:[]}]})).destination;
  assert.equal((await desk('desk_list_destinations')).destinations.length,1);
  const publication=await desk('desk_prepare_publication',{case_id:request.id,destination_id:destination.id,fields:{summary:'Synthetic text, not a real submission.'}});
  assert.equal(publication.published,false);assert.equal(publication.network_accessed,false);
  const archive=await desk('desk_export_case',{case_id:request.id});
  assert.equal(archive.exported,true);assert.equal(archive.publicly_uploaded,false);
  const relative=path.relative(directory,archive.path);assert.ok(relative&&!relative.startsWith('..')&&!path.isAbsolute(relative));
  assert.equal(fs.readFileSync(archive.path).subarray(0,2).toString(),'PK');
  assert.equal((await desk('desk_get_equipment_campaign')).states.length,51);
  assert.equal((await desk('desk_list_messages',{limit:10})).messages.length,0);
  assert.equal((await mail('proton_status')).configured,false,'no account was enrolled or contacted');
 }finally{
  try{await Promise.all(clients.map(client=>client.close()));}finally{cleanup(directory);}
 }
});
