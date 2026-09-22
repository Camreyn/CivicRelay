// Local, read-only clock refresh. Mail synchronization and evidence edits are explicit.
export function createDeadlineView({$,el,op,notice,getData,afterChange,guard,openCase,onClockChange}) {
 let detail=null, baseline='', busy=false, refreshing=false, timer, loadVersion=0;
 const values=()=>Object.fromEntries([...$('deadline-editor').querySelectorAll('[data-timing]')].map(n=>[n.dataset.timing,n.type==='checkbox'?n.checked:n.value]));
 const dirty=()=>!!detail && JSON.stringify(values())!==baseline;
 function assertClean(){if(dirty())throw Error('Save timing evidence or close it with “Discard timing edits” first.');}
 function link(label,url){const a=el('a',label);try{const u=new URL(url);if(u.protocol!=='https:'||u.username||u.password)return el('span',label+' (invalid source URL)');a.href=u.href;}catch{return el('span',label);}a.target='_blank';a.rel='noopener noreferrer';return a;}
 function badge(row){const n=el('span',row.label,'timing-badge');n.dataset.timingStatus=row.status;return n;}
 function detailsFor(row){
  const box=el('div',undefined,'timing-explanation');
  box.append(badge(row),el('p',`${row.due_date||'No calculated due date'} · as of ${row.as_of} (${row.time_zone})`,'help'));
  if(row.rule){box.append(link(row.rule.citation,row.rule.url),el('p',row.rule.summary,'help'));if(row.rule.guidance_url)box.append(link('Official guidance',row.rule.guidance_url));}
  box.append(el('p',`Source review: ${row.source_checked_date} · recheck by ${row.source_review_due}.`,'help'));
  for(const check of row.checks){const item=el('div',undefined,'timing-check');item.append(el('strong',`${check.label} · ${check.date}`),el('p',`${check.confidence.replaceAll('_',' ')} · ${check.resolved?'resolved locally':check.review_required?'needs evidence review':check.status.replaceAll('_',' ')}`,'help'),el('p',check.basis,'help'));if(check.source)item.append(link('Source for this checkpoint',check.source));box.append(item);}
  const warnings=el('ul');for(const warning of row.warnings)warnings.append(el('li',warning));box.append(warnings,link('Planning calendar reference',row.calendar_source));return box;
 }
 function render(){
  const d=getData()?.deadlines;if(!d)return;
  const c=d.counts;$('deadline-counts').textContent=`${c.overdue} past dates · ${c.due_today+c.due_soon} due soon · ${c.reply_review} need reply review`;
  const checked=new Date(d.checked_at).toLocaleString();
  $('deadline-freshness').textContent=`Clocks checked ${checked}. Last inbox sync: ${d.mail_last_synced_at?new Date(d.mail_last_synced_at*1000).toLocaleString():'never'}.${d.mail_stale?' Mail may be stale — use “Check for replies”.':''}${d.mail_sync_incomplete?' More inbox headers remain; finish syncing before assessing nonresponse.':''}${d.unassigned_incoming?` ${d.unassigned_incoming} unassigned/conflicting incoming messages need review.`:''} No automatic mail sync or sending.`;
  $('deadline-freshness').className=d.mail_stale||d.mail_sync_incomplete||d.unassigned_incoming?'warning':'help';
  const filter=$('deadline-filter').value;
  const rows=d.cases.filter(r=>filter==='all'||filter==='attention'&&r.attention||filter==='overdue'&&r.status==='overdue'||filter==='soon'&&['due_today','due_soon'].includes(r.status)||filter==='review'&&['reply_review','needs_basis'].includes(r.status));
  const priority={overdue:0,due_today:1,due_soon:2,reply_review:3};rows.sort((a,b)=>(priority[a.status]??4)-(priority[b.status]??4)||(a.due_date||'9999').localeCompare(b.due_date||'9999')||a.case_id.localeCompare(b.case_id));
  const body=$('deadline-queue');body.replaceChildren();
  for(const row of rows){const tr=el('tr');tr.dataset.deadlineCase=row.case_id;const jurisdiction=el('td',row.jurisdiction),request=el('td',row.request),state=el('td'),date=el('td',row.due_date||'—'),action=el('td'),b=el('button','Sources & timing');state.append(badge(row));date.append(el('small',row.days_remaining===null?'No automatic day count':row.days_remaining<0?`${-row.days_remaining} calendar days past`:row.days_remaining===0?'Today':`In ${row.days_remaining} calendar days`));b.onclick=()=>inspect(row.case_id).catch(e=>notice(e.message,true));action.append(b);tr.append(jurisdiction,request,state,date,action);body.append(tr);}
  if(!rows.length){const td=el('td','No requests in this view. Choose “All requests” to inspect coverage and sources.');td.colSpan=5;const tr=el('tr');tr.append(td);body.append(tr);}
  const rules=$('deadline-rules');rules.replaceChildren();
  for(const [code,rule] of Object.entries(d.rules.rules)){const p=el('p');p.append(link(`${code} · ${rule.citation}`,rule.url),el('span',' — '+rule.label));rules.append(p);}
  $('deadline-coverage').textContent=`Bundled profiles: ${Object.keys(d.rules.rules).filter(k=>k!=='US').length} states and federal agencies. Other jurisdictions need a sourced, manually recorded date. ${d.rules.calendar_note}`;
  if(detail){const row=d.cases.find(r=>r.case_id===detail.case.id);if(row){$('timing-current').replaceChildren(detailsFor(row));$('timing-revision').textContent=row.revision===detail.case.revision?'Evidence form uses the current saved revision.':'This request changed elsewhere. Your edits are preserved; discard and reopen before saving.';}}
 }
 async function inspect(id){
  guard();assertClean();
  const version=++loadVersion;const loaded=await op('desk_get_case',{case_id:id});if(version!==loadVersion)return;guard();assertClean();detail=loaded;
  const c=detail.case,t=c.deadline_tracking||{},box=$('deadline-editor');box.hidden=false;box.replaceChildren();
  const head=el('div',undefined,'panel-heading'),heading=el('div');heading.append(el('p','TIMING EVIDENCE / PRIVATE','eyebrow'),el('h2',c.family_label||c.subject));const close=el('button','Discard timing edits');close.onclick=()=>{loadVersion++;detail=null;baseline='';box.replaceChildren();box.hidden=true;};head.append(heading,close);box.append(head);
  const current=el('div');current.id='timing-current';current.append(detailsFor(c.deadline));box.append(current);
  const open=el('button','Open correspondence');open.onclick=()=>{try{assertClean();openCase(id).catch(()=>{});}catch(e){notice(e.message,true);}};box.append(open);
  const formDetails=el('details');formDetails.append(el('summary','Record receipt, response or next checkpoint'));
  const form=el('form');form.addEventListener('submit',e=>e.preventDefault());formDetails.append(form);box.append(formDetails);
  const revision=el('p','Evidence form uses the current saved revision.','help');revision.id='timing-revision';form.append(revision,el('p','Review actual receipt, routing and the notice before changing dates. Saving here does not send an email, accept fees or file an appeal. Automatic calculations remain estimates.','warning'));
  const inbox=detail.messages.filter(m=>m.folder==='INBOX'&&!m.thread_conflict);
  const mailChoices=[['','No linked notice'],...inbox.map(m=>[m.id,`${m.id} · ${m.subject||'Incoming message'}`])];
  for(const key of ['receipt_message_id','response_message_id','next_message_id'])if(t[key]&&!mailChoices.some(o=>o[0]===t[key]))mailChoices.push([t[key],`${t[key]} · saved evidence (inspect older mail)`]);
  function field(key,label,{type='text',options,help}={}){
   const wrap=el('div',undefined,'timing-field'),l=el('label',label),input=el(options?'select':type==='textarea'?'textarea':'input');input.id='timing-'+key;input.dataset.timing=key;l.htmlFor=input.id;
   if(options)for(const [v,text] of options){const o=el('option',text);o.value=v;input.append(o);}else if(type!=='textarea')input.type=type;
   if(type==='textarea')input.rows=3;
   if(type==='checkbox')input.checked=t[key]===true;else input.value=key==='excluded_dates'?(t[key]||[]).join(', '):(t[key]??(options?.[0]?.[0]||''));
   if(!options&&type==='text')input.maxLength=key.endsWith('_message_id')?150:key==='next_source'?1500:2500;
   if(type==='textarea')input.maxLength=2500;
   wrap.append(l,input);if(help)wrap.append(el('p',help,'help'));form.append(wrap);
  }
  field('filing_status','Filing status',{options:[['unverified','Not yet verified'],['formal','Formal filing / custodian verified'],['inquiry','Information inquiry — do not assert statutory clock']]});
  field('received_date','Reviewed statutory receipt / start date',{type:'date',help:'Optional override. Enter the legal start date after any email-receipt adjustment; the adjustment is not applied again.'});
  field('receipt_basis','Receipt evidence and calculation basis',{type:'textarea'});field('receipt_message_id','Receipt evidence message',{options:mailChoices});
  field('time_zone','Custodian planning time zone',{options:[['','Use profile default'],...['Eastern','Central','Mountain','Pacific','Alaska','Hawaii','Arizona','UTC'].map(v=>[v,v])]});
  field('excluded_dates','Additional custodian nonworking dates',{help:'YYYY-MM-DD dates separated by commas. Federal holiday exclusions are already applied; state and local calendars may differ.'});
  field('initial_response','Initial-response requirement',{options:[['unreviewed','Not yet reviewed as satisfied'],['satisfied','Reviewed as satisfied by linked notice']]});
  field('response_message_id','Reviewed response message',{options:mailChoices});field('response_basis','Why this response satisfies the initial requirement',{type:'textarea'});
  field('next_kind','Next checkpoint kind',{options:[['','None'],['agency_commitment','Agency-promised response'],['extension','Reviewed extension'],['appeal','Case-specific appeal deadline'],['follow_up','Internal follow-up reminder (not a legal deadline)']]});
  field('next_date','Next checkpoint date',{type:'date'});field('next_source','Official legal / procedure source (HTTPS)');field('next_checked_date','Source checked on',{type:'date'});
  field('next_message_id','Agency commitment / extension notice',{options:mailChoices});field('next_basis','Checkpoint basis (including trigger date and counting method)',{type:'textarea'});field('next_completed','This checkpoint is completed',{type:'checkbox'});
  const save=el('button','Save timing evidence','primary');save.type='button';save.onclick=async()=>{
   if(busy)return;busy=true;save.disabled=true;
   const submitted=JSON.stringify(values()),owner=detail;let saved=false;
   const args=values();args.excluded_dates=args.excluded_dates.split(/[\s,]+/).filter(Boolean);
   // Only changed fields are patched. Saving a reminder must not silently review new mail.
   const prior=JSON.parse(baseline);const patch=Object.fromEntries(Object.entries(args).filter(([k,v])=>k==='excluded_dates'?JSON.stringify(v)!==JSON.stringify((prior[k]||'').split(/[\s,]+/).filter(Boolean)):v!==prior[k]));
   try{guard();const result=await op('desk_save_deadline_tracking',{case_id:id,revision:c.revision,...patch});saved=true;if(detail===owner){c.revision=result.case.revision;baseline=submitted;}await afterChange();if(detail!==owner||JSON.stringify(values())!==submitted){notice('Submitted timing evidence was saved. Any newer edits were preserved; no external action occurred.');return;}await inspect(id);$('deadline-editor').querySelector('details').open=true;notice('Timing evidence saved privately. No email sent, fees accepted or appeal filed.');}
   catch(e){notice((saved?'Timing evidence was saved, but the form could not reload. ':'')+e.message,true);}finally{busy=false;save.disabled=false;}
  };form.append(save);baseline=JSON.stringify(values());box.scrollIntoView({behavior:'smooth',block:'start'});
 }
 async function refreshClocks(manual=false){
  if(refreshing||(!manual&&document.hidden))return;refreshing=true;
  try{const d=await op('desk_get_deadlines');getData().deadlines=d;const byId=new Map(d.cases.map(r=>[r.case_id,r]));for(const c of getData().catalog.cases)c.deadline=byId.get(c.id)||c.deadline;render();onClockChange();if(manual)notice('Deadline estimates recalculated from saved records. No mailbox connection or sends.');}
  catch(e){$('deadline-freshness').textContent='Deadline refresh failed. Displayed dates may be stale. '+e.message;$('deadline-freshness').className='warning';if(manual)notice(e.message,true);}
  finally{refreshing=false;}
 }
 function start(){render();$('deadline-filter').onchange=render;$('deadline-refresh').onclick=()=>refreshClocks(true);timer=setInterval(()=>refreshClocks(),60000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshClocks();});window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});window.addEventListener('beforeunload',e=>{if(dirty()){e.preventDefault();e.returnValue='';}});}
 return {render,inspect,assertClean,refreshClocks,start};
}
