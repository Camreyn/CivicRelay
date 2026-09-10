// Page tools share the native contracts and call the same guarded backend.
import {TOOLS,PRIVATE_TOOL_RULES,validateInput} from './tool-contracts.mjs';
const object=(properties={},required=[])=>({type:'object',properties,required,additionalProperties:false});
const id={type:'string',minLength:1,maxLength:150};
const version={type:'integer',minimum:0};
const schemaFor=name=>TOOLS.find(t=>t.name===name).schema;
const correspondence=Object.fromEntries(Object.entries(schemaFor('desk_save_case').properties).filter(([k])=>!['case_id','revision'].includes(k)));
const intake=schemaFor('desk_prepare_intake').properties;

export function createPageTools(actions){
 const tools=TOOLS.map(t=>({name:t.name,title:t.name.replace(/^desk_/,'').replaceAll('_',' '),
  description:t.description+' '+PRIVATE_TOOL_RULES,inputSchema:t.schema,
  annotations:{readOnlyHint:t.readOnly,untrustedContentHint:true},
  execute:input=>actions.backend(t.name,input,t.readOnly)}));
 const add=(name,description,schema,execute,readOnly=false)=>tools.push({name,description,inputSchema:schema,execute,annotations:{readOnlyHint:readOnly,untrustedContentHint:true}});
 add('records_read_overview','Read the current map/status totals and selected state/filter. No mail connection.',object(),()=>actions.overview(),true);
 add('records_sync_headers','Check new project mail headers and save them encrypted, then refresh the dashboard. No message body reads, sends or public writes.',object(),()=>actions.backend('desk_sync_mail',{},false));
 add('records_open_case','Open an existing request. Refuses to discard unsaved edits. No sending or publishing.',object({case_id:id},['case_id']),input=>actions.openCase(input.case_id));
 add('records_select_state','Select a state on the visible map. Does not create or modify any request.',object({state:{type:'string',pattern:'^[A-Z]{2}$',minLength:2,maxLength:2}},['state']),input=>actions.selectState(input.state));
 add('records_filter_queue','Change the visible correspondence-status filter. Status is not an election-data finding.',object({status:{type:'string',enum:['all','routing','draft','waiting','new','attention','ready','submitted','closed']}},['status']),input=>actions.filterQueue(input.status));
 add('records_read_workspace','Read the open form, unsaved fields, saved revision and selected reply chain. Read before staging edits; no remote mail or files fetched.',object(),()=>actions.workspace.snapshot(),true);
 add('records_stage_correspondence','Fill selected correspondence/notes fields in the visible form using the workspace version. Does not save, prepare or send.',object({case_id:id,workspace_version:version,fields:object(correspondence)},['case_id','workspace_version','fields']),input=>actions.workspace.stageCorrespondence(input));
 add('records_start_reply','Select a linked incoming or Sent message for reply/follow-up and clear the composer. Refuses unsaved edits; reads that one mail body. Routing must be reviewed again. Does not save or send.',object({message_id:id,workspace_version:version},['message_id','workspace_version']),input=>actions.workspace.startReply(input.message_id,input.workspace_version));
 add('records_save_correspondence','Save the current visible correspondence and notes privately. Requires the exact workspace version; no email is sent.',object({workspace_version:version},['workspace_version']),input=>actions.workspace.saveCurrent(input));
 add('records_prepare_current_email','Save the current visible correspondence, then prepare its immutable exact send preview with the selected reply chain. Does not send.',object({workspace_version:version},['workspace_version']),input=>actions.workspace.prepareCurrentEmail(input));
 add('records_stage_intake','Fill reviewed/redacted public intake fields and selected captured file IDs in the visible form. Does not publish or upload files.',object({workspace_version:version,fields:intake.fields,artifact_ids:intake.artifact_ids},['workspace_version','fields']),input=>actions.workspace.stageIntake(input));
 add('records_prepare_current_intake','Prepare the current visible public intake as a PRIVATE immutable preview. No GitHub publication or file upload.',object({workspace_version:version},['workspace_version']),input=>actions.workspace.prepareCurrentIntake(input));
 // Serialize page-tool executions; UI edits still invalidate workspace versions.
 let busy=false;
 return tools.map(t=>({...t,execute:async input=>{
  validateInput(t.inputSchema,input);
  if(busy)throw Error('Another Records Desk page tool is running. Read its result before continuing.');
  busy=true;
  try{return await t.execute(input);}finally{busy=false;}
 }}));
}

export async function registerPageTools(context,actions,{signal,onError=()=>{}}={}){
 if(!context?.registerTool)return {supported:false,registered:[]};
 const registered=[],failed=[];
 for(const tool of createPageTools(actions)){
  if(signal?.aborted)break;
  try{await context.registerTool(tool,{signal});registered.push(tool.name);}
  catch{failed.push(tool.name);onError(tool.name);}
 }
 return {supported:true,registered,failed};
}
