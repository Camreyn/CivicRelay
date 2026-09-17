// Same-user private configuration. Never render imported definitions as HTML.
export function createGeneralWorkspace({$,el,op,notice,openCase,beforeNavigate=()=>{},afterChange=async()=>{},toggleMap=()=>{}}) {
 let workspace={},account={},templates=[],campaigns=[],destinations=[];
 const host=()=>$('general-workspace'),value=id=>$(id)?.value||'';
 const latest=t=>t.versions.at(-1),definition=t=>latest(t).definition;
 const labelFor=s=>s.replaceAll('_',' ');
 const button=(text,action,cls)=>{const b=el('button',text,cls);b.type='button';b.onclick=async()=>{b.disabled=true;try{await action();}catch(e){notice(e.message,true);}finally{b.disabled=false;}};return b;};
 const actions=(...buttons)=>{const n=el('div',undefined,'general-toolbar');n.append(...buttons);return n;};
 function field(parent,id,label,type='input',initial='') {
  const wrap=el('label',label),input=el(type);if(id)input.id=id;input.value=initial??'';wrap.append(input);parent.append(wrap);return input;
 }
 function select(parent,id,label,options,initial='') {
  const input=field(parent,id,label,'select');
  for(const item of options){const [v,t]=Array.isArray(item)?item:[item,labelFor(item)];const option=el('option',t);option.value=v;input.append(option);}
  input.value=initial;return input;
 }
 function checkbox(parent,label,checked=false,id='') {const wrap=el('label',label,'general-check'),input=el('input');input.type='checkbox';input.checked=checked;if(id)input.id=id;wrap.append(input);parent.append(wrap);return input;}
 function screen(kicker,title){beforeNavigate();host().replaceChildren();const panel=el('section',undefined,'panel general-panel'),heading=el('div',undefined,'panel-heading'),text=el('div');text.append(el('p',kicker,'eyebrow'),el('h2',title));heading.append(text);panel.append(heading);host().append(panel);return panel;}
 function help(parent,text){parent.append(el('p',text,'help'));}
 async function load(){
  const [w,t,c,d]=await Promise.all([op('desk_get_workspace'),op('desk_list_templates'),op('desk_list_campaigns'),op('desk_list_destinations')]);
  workspace=w.workspace;account=w.account||{};templates=t.templates;campaigns=c.campaigns;destinations=d.destinations;
  render();return w;
 }
 async function changed(message){await afterChange();await load();notice(message);}
 function render(){
  const panel=screen('GENERAL RECORDS DESK',workspace.name||'Your public-records workspace');
  help(panel,workspace.revision===0?'Start with Workspace settings, then create or import a template. Mail enrollment is separate; you can prepare your workspace offline.':'Templates, requests and records stay private until you explicitly send, export or publish them.');
  panel.append(actions(button('Workspace settings',settings),button('New template',()=>templateEditor()),button('Import definition',importTemplate),button('New campaign',()=>campaignEditor()),button('Publication destinations',destinationsView),button('Toggle US overview',toggleMap)));
  const grid=el('div',undefined,'general-grid');
  for(const [title,items,draw] of [
   ['Templates',templates,t=>{const li=el('li');li.append(button(t.title,async()=>templateDetail((await op('desk_get_template',{template_id:t.id})).template)),el('small',`Version ${t.version} · ${t.field_count} fields · ${t.archived?'Archived':'Active'}`));return li;}],
   ['Campaigns',campaigns,c=>{const li=el('li');li.append(button(c.name,()=>campaignDetail(c)),el('small',`${c.remaining_targets} not started / ${c.targets.length} targets`));return li;}]
  ]){const part=el('section',undefined,'panel general-panel');part.append(el('h2',title));const list=el('ul',undefined,'general-list');for(const item of items)list.append(draw(item));if(!items.length)list.append(el('li',`No ${title.toLowerCase()} yet.`,'general-empty'));part.append(list);grid.append(part);}
  host().append(grid);
 }
 function settings(){
  const p=screen('LOCAL WORKSPACE','Profile and starter selection');
  help(p,account.configured?`Enrolled sender: ${account.display_name||''} <${account.email}>`:'No mailbox enrolled. Use Open-Proton-Setup.ps1 to enter Bridge credentials only in the local setup window.');
  help(p,'Personal details are optional here. Use them in a request only when required and authorized. Keep addresses out of shared signatures.');
  const f=el('div',undefined,'general-form');
  for(const [id,label,type,key] of [['ws-name','Workspace name','input','name'],['ws-org','Organization','input','organization'],['ws-sign','Signature','textarea','signature'],['ws-rname','Requester name','input','requester_name'],['ws-raddress','Requester address','textarea','requester_address'],['ws-rphone','Requester phone','input','requester_phone']])field(f,id,label,type,workspace[key]);
  select(f,'ws-pack','Starter pack',[['blank','Blank workspace'],['civicresultmaps','CivicResultMaps starter pack']],workspace.starter_pack);
  f.append(actions(button('Save private workspace',async()=>{
   await op('desk_save_workspace',{revision:workspace.revision,name:value('ws-name'),organization:value('ws-org'),signature:value('ws-sign'),requester_name:value('ws-rname'),requester_address:value('ws-raddress'),requester_phone:value('ws-rphone'),starter_pack:value('ws-pack')});
   await changed('Workspace saved privately. Mailbox credentials and identity were not changed.');
  },'primary'),button('Back',render)));p.append(f);
 }
 function rows(parent,id,title,singular,items,build,read){
  parent.append(el('h3',title));const box=el('div',undefined,'general-rows');box.id=id;parent.append(box);
  function add(item={}){const row=el('div',undefined,'general-row');build(row,item);row.append(button('Remove',()=>row.remove()));box.append(row);}
  items.forEach(add);parent.append(button('Add '+singular,()=>add()));return()=>Array.from(box.children).map(read);
 }
 function templateEditor(record=null,copy=false){
  const old=record?structuredClone(definition(record)):{schema_version:1,title:'',fields:[],subject:'',body:'',sources:[]};
  if(copy){old.title='Copy of '+old.title;old.archived=false;}
  const p=screen('TEMPLATE EDITOR',record&&!copy?'New version':'New template'),f=el('div',undefined,'general-form');
  help(p,'Use {{field}} and optional {{#if field}}…{{/if}} blocks. Built-ins include agency, jurisdiction, state, date_start, date_end, organization, signature and requester_email. Personal name/address/phone require explicitly required fields.');
  field(f,'td-title','Title','input',old.title);field(f,'td-category','Category','input',old.category||'');field(f,'td-subject','Subject','input',old.subject);field(f,'td-body','Body','textarea',old.body).rows=12;
  field(f,'td-review','Template review date (optional)','input',old.review_date||'').type='date';
  const getFields=rows(f,'template-fields','Fields','Field',old.fields,(r,x)=>{
   field(r,'','Field ID','input',x.id||'');field(r,'','Label','input',x.label||'');select(r,'','Type',['text','multiline'],x.type||'text');checkbox(r,'Required',!!x.required);
  },r=>{const n=r.querySelectorAll('input,select');return{id:n[0].value.trim(),label:n[1].value.trim(),type:n[2].value,required:n[3].checked};});
  const getSources=rows(f,'template-sources','Official sources','Source',old.sources,(r,x)=>{
   field(r,'','Source title','input',x.title||'');field(r,'','Official URL','input',x.url||'');field(r,'','Review date','input',x.review_date||'').type='date';
  },r=>{const n=r.querySelectorAll('input');return{title:n[0].value.trim(),url:n[1].value.trim(),review_date:n[2].value};});
  const archived=checkbox(f,'Archive template',!!old.archived,'td-archived');
  f.append(actions(button(record&&!copy?'Save new version':'Create template',async()=>{
   const d={schema_version:1,title:value('td-title'),category:value('td-category'),subject:value('td-subject'),body:value('td-body'),fields:getFields(),sources:getSources(),archived:archived.checked};
   if(value('td-review'))d.review_date=value('td-review');
   await op('desk_save_template',{...(record&&!copy?{template_id:record.id,revision:record.revision}:{}),definition:d});await changed('Template saved. Existing requests retain their original version.');
  },'primary'),button('Back',render)));p.append(f);
 }
 function templateDetail(record){
  const d=definition(record),p=screen('TEMPLATE DETAIL',`${d.title} · v${latest(record).version}`);
  p.append(actions(button('Edit as new version',()=>templateEditor(record)),button('Duplicate',()=>templateEditor(record,true)),button('Export definition',async()=>download((await op('desk_export_template',{template_id:record.id})).definition,d.title)),button('Back',render)));
  p.append(el('pre',d.subject+'\n\n'+d.body,'general-definition'));help(p,`${record.versions.length} saved version(s). Definition exports exclude profile and entered values, but literal wording still needs privacy review.`);
  const f=el('div',undefined,'general-form'),read=valueFields(f,record,true);f.append(button('Preview',async()=>{const result=await op('desk_preview_template',{template_id:record.id,values:read()});let preview=$('template-preview');if(!preview){preview=el('pre',undefined,'general-definition');preview.id='template-preview';f.append(preview);}preview.textContent=result.rendered.subject+'\n\n'+result.rendered.body;},'primary'));p.append(f);
 }
 function valueFields(parent,record,preview=false){
  const d=definition(record),fields=[...d.fields];
  if(preview)for(const id of ['agency','jurisdiction','state','date_start','date_end'])if(!fields.some(f=>f.id===id)&&new RegExp('{{\\s*(?:#if\\s+)?'+id+'\\s*}}').test(d.subject+'\n'+d.body))fields.push({id,label:'Preview '+labelFor(id),required:false,type:'text'});
  const profileKeys=new Set(['organization','signature','requester_name','requester_address','requester_phone','requester_email']);
  for(const f of fields){const initial=profileKeys.has(f.id)?(f.id==='requester_email'?account.email:workspace[f.id])||'':'';field(parent,'tv-'+f.id,f.label+(f.required?' *':''),f.type==='multiline'?'textarea':'input',initial);}
  return()=>Object.fromEntries(fields.map(f=>[f.id,value('tv-'+f.id)]).filter(([key,v])=>v!==''||!['agency','jurisdiction','state','date_start','date_end'].includes(key)));
 }
 function download(data,title){
  const a=el('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)+'\n'],{type:'application/json'}));a.download=(title||'template').replace(/[^a-z0-9]+/gi,'-')+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
  notice('Definition downloaded. Review literal text before sharing; profile and case values were not included.');
 }
 function importTemplate(){
  const input=el('input');input.type='file';input.accept='.json,application/json';input.onchange=async()=>{try{const file=input.files?.[0];if(!file)return;if(file.size>250000)throw Error('Template import exceeds 250 KB.');await op('desk_import_template',{definition:JSON.parse(await file.text())});await changed('Template imported as a new private definition. No account, destination or permissions changed.');}catch(e){notice(e.message,true);}};input.click();
 }
 function campaignEditor(record=null){
  if(!templates.some(t=>!t.archived))throw Error('Create an active template before creating a campaign.');
  const c=record||{name:'',description:'',template_id:templates.find(t=>!t.archived).id,date_start:'',date_end:'',targets:[]};
  const p=screen('CAMPAIGN EDITOR',record?'Edit campaign':'New campaign'),f=el('div',undefined,'general-form');
  field(f,'ca-name','Campaign name','input',c.name);field(f,'ca-description','Description','textarea',c.description);
  select(f,'ca-template','Default template',templates.filter(t=>!t.archived).map(t=>[t.id,`${t.title} · v${t.version}`]),c.template_id);
  field(f,'ca-start','Start date (optional)','input',c.date_start).type='date';field(f,'ca-end','End date (optional)','input',c.date_end).type='date';
  const getTargets=rows(f,'campaign-targets','Targets','Target',c.targets,(r,t)=>{
   field(r,'','Target ID','input',t.id||'');field(r,'','Label','input',t.label||'');select(r,'','Level',['federal','state','county','municipality','other'],t.level||'federal');field(r,'','State code (optional)','input',t.state||'');
  },r=>{const n=r.querySelectorAll('input,select');return{id:n[0].value.trim(),label:n[1].value.trim(),level:n[2].value,...(n[3].value.trim()?{state:n[3].value.trim().toUpperCase()}:{})};});
  help(f,'Use stable target IDs such as federal-agency or county-example. Targets with saved requests cannot be removed or retargeted.');
  f.append(actions(button(record?'Save campaign':'Create campaign',async()=>{
   await op('desk_save_campaign',{...(record?{campaign_id:record.id,revision:record.revision}:{}),name:value('ca-name'),description:value('ca-description'),template_id:value('ca-template'),date_start:value('ca-start'),date_end:value('ca-end'),targets:getTargets()});await changed('Campaign saved privately. No requests were sent.');
  },'primary'),button('Back',render)));p.append(f);
 }
 function campaignDetail(c){
  const p=screen('CAMPAIGN DETAIL',c.name);p.append(actions(button('Edit campaign',()=>campaignEditor(c)),button('Refresh progress',async()=>{await load();campaignDetail(campaigns.find(x=>x.id===c.id));}),button('Back',render)));help(p,`${c.remaining_targets} target(s) not started. Response, coverage and publication are separate.`);
  const table=el('table',undefined,'general-cases'),head=el('thead'),hr=el('tr');for(const h of ['Target','Level','Requests / responses','Actions'])hr.append(el('th',h));head.append(hr);table.append(head);const body=el('tbody');
  for(const t of c.targets){const pg=c.target_progress.find(x=>x.target_id===t.id)||{request_count:0,response_stages:[],requests:[]},tr=el('tr'),cell=el('td');tr.append(el('td',t.label),el('td',t.level),el('td',pg.request_count?`${pg.request_count} request(s) · ${pg.response_stages.map(labelFor).join(', ')}`:'Not started'));
   for(const request of pg.requests){cell.append(button('Open correspondence',()=>openCase(request.case_id)),button('Track response',()=>progress(request.case_id,c)));}
   cell.append(button('Create request',()=>requestForm(c,t)));tr.append(cell);body.append(tr);
  }table.append(body);p.append(table);
 }
 async function requestForm(c,t){
  const record=(await op('desk_get_template',{template_id:c.template_id})).template,p=screen('NEW PRIVATE REQUEST',t.label),f=el('div',undefined,'general-form');
  help(p,`Template: ${definition(record).title} · version ${latest(record).version}. This creates a saved request only. Routing and exact email review follow in the correspondence workspace.`);
  field(f,'rq-name','Agency / custodian');const read=valueFields(f,record);
  f.append(actions(button('Create private request',async()=>{const result=await op('desk_create_request',{campaign_id:c.id,template_id:record.id,target_id:t.id,agency:value('rq-name'),values:read()});await afterChange();await openCase(result.case.id);notice(result.created?'Private request created. Verify routing before preparing an email.':'Matching saved request reopened. Nothing was resent.');},'primary'),button('Back',()=>campaignDetail(c))));p.append(f);
 }
 async function progress(caseId,campaign){
  const detail=await op('desk_get_case',{case_id:caseId}),c=detail.case,t=c.tracking||{},p=screen('REQUEST PROGRESS',c.agency?.name||c.family_label),f=el('div',undefined,'general-form');
  help(p,`Correspondence: ${labelFor(c.status)} · Publication: ${c.publication_status||'none'}. No fee acceptance or deadline calculation is performed here.`);
  select(f,'gp-response','Response stage',['none','acknowledged','partial_response','records_received','fee_notice','clarification','denied','closed'],t.response_stage||'none');
  const picker=select(f,'gp-message','Linked incoming message',[['','Select incoming evidence'],...detail.messages.filter(m=>m.folder==='INBOX').map(m=>[m.id,`${m.date||''} · ${m.subject||m.id}`])],t.response_message_id||'');
  help(f,'Only an incoming message assigned to this case establishes a response stage.');
  if(detail.next_before_message_id){let cursor=detail.next_before_message_id;const older=button('Load older response evidence',async()=>{const page=await op('desk_get_case',{case_id:caseId,before_message_id:cursor});for(const m of page.messages.filter(m=>m.folder==='INBOX')){const option=el('option',`${m.date||''} · ${m.subject||m.id}`);option.value=m.id;picker.append(option);}cursor=page.next_before_message_id;if(!cursor)older.hidden=true;});f.append(older);}
  select(f,'gp-coverage','Records coverage',['not_assessed','partial','received','unavailable','not_applicable'],t.coverage||'not_assessed');
  for(const [id,label,key] of [['gp-note','Private progress note','note'],['gp-fee','Fee note — no fee accepted','fee_note'],['gp-procedure','Procedure note','procedure_note'],['gp-basis','Deadline starting event / calculation basis','deadline_basis']])field(f,id,label,'textarea',t[key]||'');
  field(f,'gp-deadline','Verified deadline','input',t.deadline_date||'').type='date';select(f,'gp-kind','Deadline kind',[['','No deadline'],'response','appeal'],t.deadline_kind||'');field(f,'gp-source','Official deadline source URL','input',t.deadline_source||'');field(f,'gp-checked','Source checked date','input',t.deadline_checked_date||'').type='date';
  f.append(actions(button('Save progress',async()=>{await op('desk_save_request_progress',{case_id:c.id,revision:c.revision,response_stage:value('gp-response'),coverage:value('gp-coverage'),response_message_id:picker.value,note:value('gp-note'),fee_note:value('gp-fee'),procedure_note:value('gp-procedure'),deadline_date:value('gp-deadline'),deadline_kind:value('gp-kind'),deadline_source:value('gp-source'),deadline_basis:value('gp-basis'),deadline_checked_date:value('gp-checked')});await afterChange();await progress(caseId,campaign);notice('Progress saved privately. No email, fee or publication action occurred.');},'primary'),button('Open correspondence',()=>openCase(c.id)),button('Export private case package',async()=>{const r=await op('desk_export_case',{case_id:c.id});notice(`Private plaintext ZIP saved: ${r.path}. Review before sharing.`);}),button('Back',async()=>{await load();campaignDetail(campaigns.find(x=>x.id===campaign.id));})));p.append(f);
 }
 function destinationsView(){const p=screen('OPTIONAL INTEGRATIONS','Publication destinations');p.append(actions(button('New destination',()=>destinationEditor()),button('Back',render)));help(p,'No destination is required for local tracking or export. These are operator-configured mappings, not automatically verified remote forms.');for(const d of destinations){const item=el('article',undefined,'message');item.append(el('h3',d.name),el('p',`${d.repository} · ${d.enabled?'Enabled':'Disabled'} · revision ${d.revision}`),button('Edit destination',()=>destinationEditor(d)));p.append(item);}}
 function destinationEditor(record=null){
  const d=record||{name:'',repository:'',template:'',labels:[],fields:[{id:'summary',label:'Records summary',type:'textarea',required:true,options:[]}],enabled:true},p=screen('DESTINATION EDITOR',record?'Edit mapping':'New GitHub mapping'),f=el('div',undefined,'general-form');
  field(f,'de-name','Name','input',d.name);field(f,'de-repo','GitHub repository owner/name','input',d.repository);field(f,'de-template','Issue form filename (optional)','input',d.template);field(f,'de-labels','Labels, comma-separated','input',d.labels.join(', '));
  const getFields=rows(f,'destination-fields','Issue fields','Issue field',d.fields,(r,x)=>{field(r,'','Field ID','input',x.id||'');field(r,'','Heading','input',x.label||'');select(r,'','Type',['input','textarea','dropdown'],x.type||'textarea');checkbox(r,'Required',!!x.required);field(r,'','Dropdown options, one per line','textarea',(x.options||[]).join('\n'));},r=>{const n=r.querySelectorAll('input,select,textarea');return{id:n[0].value.trim(),label:n[1].value.trim(),type:n[2].value,required:n[3].checked,options:n[4].value.split('\n').map(x=>x.trim()).filter(Boolean)};});
  const enabled=checkbox(f,'Enabled',d.enabled,'de-enabled');help(f,'Changing or disabling this mapping invalidates prepared previews. Use response_url as the field ID for a reviewed public file link when publishing a file manifest.');
  f.append(actions(button('Save destination',async()=>{await op('desk_save_destination',{...(record?{destination_id:record.id,revision:record.revision}:{}),name:value('de-name'),repository:value('de-repo'),template:value('de-template'),labels:value('de-labels').split(',').map(x=>x.trim()).filter(Boolean),fields:getFields(),enabled:enabled.checked});await changed('Destination saved locally. Nothing published; old previews require review again.');},'primary'),button('Back',destinationsView)));p.append(f);
 }
 return {load,render};
}
