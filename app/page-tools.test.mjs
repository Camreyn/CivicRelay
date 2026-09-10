import test from 'node:test';
import assert from 'node:assert/strict';
import {TOOLS,validateInput} from './static/tool-contracts.mjs';
import {createPageTools,registerPageTools} from './static/page-tools.mjs';

function example(schema){
 if(Object.hasOwn(schema,'const'))return schema.const;
 if(schema.enum)return schema.enum[0];
 if(schema.type==='object')return Object.fromEntries((schema.required||[]).map(k=>[k,example(schema.properties[k])]));
 if(schema.type==='array')return [];
 if(schema.type==='integer')return schema.minimum||0;
 if(schema.type==='boolean')return false;
 return 'synthetic';
}
function fixture(){
 const calls=[],state={case_id:null,filter:'all',workspace_version:1,fields:{}};
 const actions={backend:async(name,args,readOnly)=>{calls.push({name,args,readOnly});return {operation:name,messages_sent:0};},
  overview:()=>({case_id:state.case_id,filter:state.filter}),
  openCase:async id=>{state.case_id=id;return {...state};},
  selectState:code=>({selected_state:code}),filterQueue:status=>{state.filter=status;return {...state};},
  workspace:{snapshot:()=>structuredClone(state),stageCorrespondence:input=>{if(input.workspace_version!==state.workspace_version)throw Error('stale');state.fields=input.fields;state.workspace_version++;return structuredClone(state);},
   stageIntake:input=>({staged:input}),startReply:async(id,version)=>({reply_message_id:id,workspace_version:version}),saveCurrent:async input=>({saved:input}),prepareCurrentEmail:async input=>({prepared:input}),prepareCurrentIntake:async input=>({prepared:input})}};
 return {actions,calls,state};
}
test('all 20 backend tasks have shared page schemas, annotations and validation',async()=>{
 const {actions,calls}=fixture(),page=createPageTools(actions);
 assert.equal(page.length,32);assert.equal(new Set(page.map(t=>t.name)).size,32);
 for(const contract of TOOLS){const tool=page.find(t=>t.name===contract.name);assert.deepEqual(tool.inputSchema,contract.schema);assert.equal(tool.annotations.readOnlyHint,contract.readOnly);assert.equal(tool.annotations.untrustedContentHint,true);
  const args=example(contract.schema);await tool.execute(args);assert.equal(calls.at(-1).name,contract.name);
  const count=calls.length;await assert.rejects(()=>tool.execute({...args,approval_bypass:true}));assert.equal(calls.length,count);
 }
});
test('external page tools retain exact confirmations and cannot approve desktop windows',async()=>{
 const {actions,calls}=fixture(),page=createPageTools(actions);
 for(const name of ['desk_send_email','desk_publish_intake']){const tool=page.find(t=>t.name===name),args=example(tool.inputSchema);delete args.confirmation;await assert.rejects(()=>tool.execute(args));assert.equal(calls.length,0);assert.ok(tool.inputSchema.required.includes('expected_digest'));}
 assert.deepEqual(Object.keys(page.find(t=>t.name==='desk_export_package').inputSchema.properties),['issue_id']);
});
test('page helpers stage visible state, reject stale state and do not silently save',async()=>{
 const {actions,calls,state}=fixture(),page=createPageTools(actions),tool=name=>page.find(t=>t.name===name);
 await tool('records_open_case').execute({case_id:'case-one'});
 await tool('records_stage_correspondence').execute({case_id:'case-one',workspace_version:1,fields:{body:'Synthetic draft'}});
 const result=await tool('records_read_workspace').execute({});assert.equal(result.fields.body,'Synthetic draft');assert.equal(result.workspace_version,2);assert.equal(calls.length,0);
 await assert.rejects(()=>tool('records_stage_correspondence').execute({case_id:'case-one',workspace_version:1,fields:{body:'stale overwrite'}}));assert.equal(state.fields.body,'Synthetic draft');
 await assert.rejects(()=>tool('records_stage_correspondence').execute({case_id:'case-one',workspace_version:2,fields:{routing_verified:'yes'}}));
 await tool('records_filter_queue').execute({status:'waiting'});assert.equal((await tool('records_read_overview').execute({})).filter,'waiting');
 await assert.rejects(()=>tool('records_filter_queue').execute({status:'fabricated'}));
});
test('registration feature-detects, reports failures and forwards abort lifecycle',async()=>{
 const {actions}=fixture();assert.deepEqual(await registerPageTools(undefined,actions),{supported:false,registered:[]});
 const controller=new AbortController(),seen=[],errors=[];
 const context={registerTool:async(tool,options)=>{assert.equal(options.signal,controller.signal);if(tool.name==='desk_status')throw Error('synthetic failure');seen.push(tool);}};
 const r=await registerPageTools(context,actions,{signal:controller.signal,onError:name=>errors.push(name)});
 assert.equal(r.registered.length,31);assert.deepEqual(r.failed,['desk_status']);assert.deepEqual(errors,['desk_status']);assert.equal(seen.length,31);
 controller.abort();assert.deepEqual((await registerPageTools(context,actions,{signal:controller.signal})).registered,[]);
});
test('in-flight page tool blocks concurrent operations without retrying them',async()=>{
 const {actions}=fixture();let release;actions.backend=()=>new Promise(resolve=>release=resolve);
 const page=createPageTools(actions),first=page.find(t=>t.name==='desk_sync_mail').execute({});
 await assert.rejects(()=>page.find(t=>t.name==='desk_status').execute({}),/Another Records Desk/);
 release({ok:true});await first;
});
test('shared argument validation is strict and rejects nested unknown keys',()=>{
 assert.throws(()=>validateInput(TOOLS.find(t=>t.name==='desk_get_workflow').schema,[]));
 const schema=TOOLS.find(t=>t.name==='desk_prepare_intake').schema;
 assert.throws(()=>validateInput(schema,{case_id:'case',fields:{password:'forbidden'}}));
 assert.throws(()=>validateInput(schema,{case_id:'case',fields:{},artifact_ids:Array(31).fill('x')}));
 assert.throws(()=>validateInput(TOOLS.find(t=>t.name==='desk_list_messages').schema,{limit:true}));
});
