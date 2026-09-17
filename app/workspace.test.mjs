// Lightweight synthetic element tree: verifies form state, not browser rendering/WebMCP.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createWorkspace} from './static/workspace.js';

class Element{
 constructor(tag,text=''){this.tag=tag;this.textContent=text;this.children=[];this.value='';this.checked=false;this.type='';this.id='';this.listeners={};}
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(...nodes){this.children=[...nodes];}
 addEventListener(name,fn){this.listeners[name]=fn;}
 setAttribute(){}
 scrollIntoView(){}
 focus(){}
 querySelectorAll(selector){const tags=selector.split(',');return this.children.flatMap(n=>[...(tags.includes(n.tag)?[n]:[]),...n.querySelectorAll(selector)]);}
}
function fixture(){
 const root=new Element('section');root.id='case-workspace';
 const $=id=>id===root.id?root:root.querySelectorAll('input,textarea,select,div,p').find(n=>n.id===id);
 const el=(tag,text='',cls)=>Object.assign(new Element(tag,text),{className:cls||''});
 const record={id:'synthetic-case',revision:1,state:'IN',state_name:'Indiana',family_label:'Synthetic records',status:'draft',year:2024,
  recipient:'records@example.gov',subject:'Synthetic request',body:'Saved text',routing_verified:false,routing_evidence:'',note:'',stage:'draft',
  request_ids:['TEST-REQUEST'],custodian:'Synthetic Office',portal_url:'https://example.gov',lookup_url:'https://example.gov',routing_notes:'Synthetic only',catalog_date:'2026-09-09'};
 const fields=['state','request_id','custodian','response_date','response_status','response_url','files_received','response_summary','follow_up_needed'].map(id=>({id,label:id,type:'input',required:false,options:[]}));
 const data={email:'synthetic@example.test',catalog:{cases:[record],issue:{fields}},unassigned:[],sync:[]};
 let drafts=[],issues=[],hook=null,artifacts=[];const calls=[];
 const detail=(offset=0)=>structuredClone({case:record,drafts,issues,messages:[],artifacts:artifacts.slice(offset,offset+100),next_artifact_offset:artifacts.length>offset+100?offset+100:null});
 const op=async(name,args)=>{
  calls.push({name,args:structuredClone(args)});if(hook)await hook(name,args);
  if(name==='desk_get_case')return detail(args.artifact_offset||0);
  if(name==='desk_save_case'){if(args.revision!==record.revision)throw Error('stale revision');Object.assign(record,args,{id:record.id,revision:record.revision+1});delete record.case_id;return {case:structuredClone(record),messages_sent:0};}
  if(name==='desk_read_message')return {message:{id:args.message_id,case_id:record.id,folder:'INBOX',subject:'Agency answer',reply_to:'Office <records@example.gov>',from:'Office <records@example.gov>',message_id:'<reply@example.gov>'}};
  if(name==='desk_prepare_email'){const d={draft_id:'synthetic-draft',state:'draft',to:[record.recipient],from:data.email,subject:record.subject,body:record.body,digest:'a'.repeat(64),in_reply_to:args.reply_message_id?'reply':null};drafts=[d];record.revision++;return {draft:d,messages_sent:0};}
  if(name==='desk_prepare_intake'){const issue={id:'synthetic-intake',state:'prepared',fields:args.fields,artifacts:[],artifact_ids:[],title:'Synthetic intake',body:'Public preview',digest:'b'.repeat(64),form_url:'https://example.gov'};issues=[issue];record.stage='ready';record.revision++;return {issue,published:false};}
  if(name==='desk_prepare_publication'){const target=data.destinations.find(d=>d.id===args.destination_id);assert.ok(target);const issue={id:'synthetic-publication',destination_id:target.id,target_snapshot:structuredClone(target),state:'prepared',fields:args.fields,artifacts:[],artifact_ids:args.artifact_ids,title:'Synthetic general intake',body:'Public preview',digest:'c'.repeat(64),form_url:'https://github.com/example/records/issues/new'};issues=[issue];record.revision++;return {issue,published:false};}
  throw Error('Unexpected synthetic operation: '+name);
 };
 const workspace=createWorkspace({$,el,op,notice:()=>{},labels:{},badge:()=>el('span'),getData:()=>data,refresh:async()=>{},selectState:()=>{}});
 return {$,root,data,record,workspace,calls,setHook:fn=>hook=fn,setArtifacts:rows=>artifacts=rows};
}
test('actual workspace preserves unsaved correspondence/intake and refuses stale overwrite',async()=>{
 const f=fixture(),w=f.workspace;await w.openCase(f.record.id,false);
 let s=w.snapshot();assert.equal(s.unsaved_changes,false);
 w.stageCorrespondence({case_id:s.case_id,workspace_version:s.workspace_version,fields:{body:'Unsaved personal edits'}});
 s=w.snapshot();w.stageIntake({workspace_version:s.workspace_version,fields:{response_summary:'Unsaved response summary'}});
 f.record.body='New content saved elsewhere';f.record.revision++;
 await w.afterOperation();s=w.snapshot();assert.equal(s.correspondence.body,'Unsaved personal edits');assert.equal(s.intake.fields.response_summary,'Unsaved response summary');assert.equal(s.revision,1);assert.equal(s.current_saved_revision,2);
 await assert.rejects(()=>w.saveCurrent({workspace_version:s.workspace_version}),/stale revision/);
 assert.throws(()=>w.assertClean(),/Unsaved/);assert.equal(f.record.body,'New content saved elsewhere');
});

test('generic publication is synchronous, explicitly selected and independent of correspondence',async()=>{
 const f=fixture(),w=f.workspace;f.record.general_campaign_id='campaign-synthetic';f.record.campaign_id='campaign-synthetic';
 f.data.destinations=[{id:'destination-synthetic',name:'Synthetic',repository:'example/records',template:'records.yml',revision:1,enabled:true,template_sha256:'d'.repeat(64),fields:[{id:'summary',label:'Summary',type:'textarea',required:true,options:[]}]}];
 f.setArtifacts([{id:'artifact-synthetic',filename:'synthetic.txt',bytes:20,content_type:'text/plain',sha256:'e'.repeat(64)}]);
 await w.openCase(f.record.id,false);assert.equal(w.snapshot().unsaved_changes,false);assert.equal(w.snapshot().intake.destination_id,'');assert.deepEqual(w.snapshot().intake.artifact_ids,[]);
 const choose=f.$('intake-destination');choose.value='destination-synthetic';choose.onchange();
 let s=w.snapshot();w.stageCorrespondence({case_id:s.case_id,workspace_version:s.workspace_version,fields:{body:'Unsaved generic correspondence'}});
 s=w.snapshot();w.stageIntake({workspace_version:s.workspace_version,fields:{summary:'Reviewed generic summary'},artifact_ids:[]});
 assert.throws(()=>w.stageIntake({workspace_version:w.snapshot().workspace_version,fields:{private_unknown:'Rejected'}}),/Unknown/);
 await w.prepareCurrentIntake({workspace_version:w.snapshot().workspace_version});
 const call=f.calls.find(c=>c.name==='desk_prepare_publication');assert.equal(call.args.destination_id,'destination-synthetic');assert.deepEqual(call.args.fields,{summary:'Reviewed generic summary'});assert.deepEqual(call.args.artifact_ids,[]);
 s=w.snapshot();assert.equal(f.record.stage,'draft');assert.equal(s.correspondence.body,'Unsaved generic correspondence');assert.equal(s.unsaved_changes,true);
 assert.ok(f.root.querySelectorAll('button').some(b=>b.textContent==='Publish this public issue'));
 f.data.destinations[0].template_sha256='f'.repeat(64);await w.refreshDetail();
 assert.ok(!f.root.querySelectorAll('button').some(b=>b.textContent==='Publish this public issue'));assert.equal(w.snapshot().correspondence.body,'Unsaved generic correspondence');
});

test('generic workspace needs no destination or remote calls to offer a private export',async()=>{
 const f=fixture();f.record.general_campaign_id='campaign-synthetic';f.data.destinations=[];await f.workspace.openCase(f.record.id,false);
 assert.equal(f.workspace.snapshot().unsaved_changes,false);assert.deepEqual(f.workspace.snapshot().intake.fields,{});
 assert.ok(f.root.querySelectorAll('button').some(b=>b.textContent==='Export private case package'));
 assert.deepEqual(f.calls.map(c=>c.name),['desk_get_case']);
});
test('saved form can start a threaded reply and tool refresh preserves that chain',async()=>{
 const f=fixture(),w=f.workspace;await w.openCase(f.record.id,false);let s=w.snapshot();
 w.stageCorrespondence({case_id:s.case_id,workspace_version:s.workspace_version,fields:{body:'Personalized draft'}});
 await w.saveCurrent({workspace_version:w.snapshot().workspace_version});assert.equal(w.snapshot().unsaved_changes,false);
 await w.startReply('INBOX:1:1',w.snapshot().workspace_version);s=w.snapshot();assert.equal(s.reply_message_id,'INBOX:1:1');assert.equal(s.correspondence.body,'');assert.equal(s.correspondence.routing_verified,false);
 w.stageCorrespondence({case_id:s.case_id,workspace_version:s.workspace_version,fields:{body:'Synthetic reply',routing_verified:true,routing_evidence:'https://example.gov/records'}});
 await w.prepareCurrentEmail({workspace_version:w.snapshot().workspace_version});await w.afterOperation();
 assert.equal(w.snapshot().reply_message_id,'INBOX:1:1');assert.equal(f.calls.find(c=>c.name==='desk_prepare_email').args.reply_message_id,'INBOX:1:1');
});
test('intake preparation never marks unsaved correspondence as saved',async()=>{
 const f=fixture(),w=f.workspace;await w.openCase(f.record.id,false);let s=w.snapshot();
 w.stageCorrespondence({case_id:s.case_id,workspace_version:s.workspace_version,fields:{body:'Do not lose this draft'}});
 s=w.snapshot();w.stageIntake({workspace_version:s.workspace_version,fields:{response_summary:'Synthetic response'}});
 await w.prepareCurrentIntake({workspace_version:w.snapshot().workspace_version});s=w.snapshot();assert.equal(s.correspondence.body,'Do not lose this draft');assert.equal(s.unsaved_changes,true);assert.equal(s.revision,1);
 assert.throws(()=>w.stageCorrespondence({case_id:s.case_id,workspace_version:s.workspace_version,fields:{body:'partial bad edit',stage:'submitted'}}),/receipt/);assert.equal(w.snapshot().correspondence.body,'Do not lose this draft');
});
test('edits during async save stop prepare and edits during load are never replaced',async()=>{
 const f=fixture(),w=f.workspace;await w.openCase(f.record.id,false);let changed=false;
 f.setHook(async name=>{if(name==='desk_save_case'&&!changed){changed=true;const s=w.snapshot();w.stageCorrespondence({case_id:s.case_id,workspace_version:s.workspace_version,fields:{body:'Typed while saving'}});}});
 await assert.rejects(()=>w.prepareCurrentEmail({workspace_version:w.snapshot().workspace_version}),/Form changed/);
 assert.equal(w.snapshot().correspondence.body,'Typed while saving');assert.equal(f.calls.filter(c=>c.name==='desk_prepare_email').length,0);
 f.setHook(async name=>{if(name==='desk_get_case'){const s=w.snapshot();w.stageCorrespondence({case_id:s.case_id,workspace_version:s.workspace_version,fields:{note:'Typed while loading'}});}});
 await assert.rejects(()=>w.openCase(f.record.id,false),/workspace changed/);assert.equal(w.snapshot().correspondence.note,'Typed while loading');
});
test('artifact pagination preserves unsaved intake, selected files and existing issue URL',async()=>{
 const f=fixture(),w=f.workspace;
 f.setArtifacts(Array.from({length:101},(_,i)=>({id:'artifact-'+i,filename:'synthetic-'+i+'.csv',bytes:20,content_type:'text/csv',sha256:'c'.repeat(64)})));
 await w.openCase(f.record.id,false);await w.prepareCurrentIntake({workspace_version:w.snapshot().workspace_version});
 let s=w.snapshot();w.stageIntake({workspace_version:s.workspace_version,fields:{response_summary:'Unfinished intake summary'},artifact_ids:['artifact-0']});
 f.$('issue-url').value='https://github.com/Camreyn/civicresultmaps/issues/123';const before=w.snapshot().workspace_version;
 await w.loadMoreArtifacts();s=w.snapshot();assert.equal(s.intake.fields.response_summary,'Unfinished intake summary');assert.deepEqual(s.intake.artifact_ids,['artifact-0']);assert.equal(f.$('issue-url').value,'https://github.com/Camreyn/civicresultmaps/issues/123');assert.ok(f.$('artifact-artifact-100'));assert.ok(s.workspace_version>before);assert.equal(s.unsaved_changes,true);
 w.stageIntake({workspace_version:s.workspace_version,fields:{},artifact_ids:['artifact-0','artifact-100']});await w.afterOperation();s=w.snapshot();assert.deepEqual(s.intake.artifact_ids,['artifact-0','artifact-100']);assert.equal(s.intake.fields.response_summary,'Unfinished intake summary');
});
