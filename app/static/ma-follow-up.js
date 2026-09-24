// Explicit review of untrusted response evidence; no automatic mail actions.
export function createMaFollowUp({parent,data,el,op,notice,link,guard,onSave,usePreview}) {
 let current=data,row=data.cases[0],baseline='',busy=false,preview=null;
 const box=el('details');box.id='ma-follow-up';parent.append(box);
 let controls,selector,editor,history,previewBox,selected='';
 const values=()=>Object.fromEntries(Array.from(editor?.querySelectorAll('[data-ma-field]')||[]).map(n=>[n.dataset.maField,n.value]));
 const categories=()=>row.checklist.map(r=>({key:r.key,status:editor.querySelector(`[data-ma-status="${r.key}"]`).value,note:editor.querySelector(`[data-ma-note="${r.key}"]`).value}));
 const review=()=>({...values(),categories:categories(),response_message_id:selected});
 const dirty=()=>!!baseline&&JSON.stringify(review())!==baseline;
 function assertClean(){if(busy)throw Error('A Massachusetts review operation is running.');if(dirty())throw Error('Save or discard the Massachusetts response-review edits first.');}
 function button(label,action){const b=el('button',label);b.type='button';b.onclick=async()=>{if(busy)return;try{await action();}catch(e){notice(e.message,true);}};return b;}
 function field(key,label,{options,value='',type='text',max=2500}={}){
  const l=el('label',label,'field-label'),n=el(options?'select':type==='textarea'?'textarea':'input');n.id='ma-'+key;n.dataset.maField=key;n.dataset.maReview='true';l.htmlFor=n.id;
  if(options)for(const [v,label] of options){const o=el('option',label);o.value=v;n.append(o);}else if(type!=='textarea')n.type=type;
  n.value=value;n.className='full-width';n.maxLength=max;if(type==='textarea')n.rows=2;editor.append(l,n);return n;
 }
 function updateHistory(){
  history.replaceChildren(el('h4','Saved reviews and timing watches'));
  for(const r of row.reviews)history.append(el('p',`${r.response_message_id}: ${r.response_kind.replaceAll('_',' ')} — ${r.summary}${r.evidence_valid?'':' [Evidence no longer linked or valid; review required]'}`,'help'));
  for(const w of row.appeal_watches){const p=el('p',`${w.evidence_valid?'Appeal planning estimate':'Invalid evidence — do not rely on date'}: ${w.candidate_date} (${w.days_remaining} calendar days from today). ${w.basis} `,'warning');p.append(link('Official appeal procedure',w.source));history.append(p);}
  for(const r of row.internal_reminders)history.append(el('p',`Internal reminder: ${r.date} · ${r.message_id}. Not a statutory deadline.`,'help'));
  if(!row.reviews.length)history.append(el('p','No response review saved. No appeal date is inferred from an unread header.','help'));
  history.append(el('p',`Original submission: ${row.original_submission.at||row.original_submission.date||row.original_submission.kind}. A reply or referral does not restart it. ${row.unreviewed_message_ids.length} incoming message(s) still need this review.`,'help'));
 }
 function loadReview(){
  const saved=row.reviews.find(r=>r.response_message_id===selected)||{};
  editor.replaceChildren();preview=null;previewBox.replaceChildren();baseline='';
  if(!selected)return;
  const m=row.incoming.find(m=>m.id===selected);
  editor.append(el('p',`Evidence: ${m?.date||selected}. Read the complete message in the conversation before saving. This review does not mark it reviewed or determine legal sufficiency.`,'help'));
  if(!m?.body_loaded||m?.body_truncated||m?.thread_conflict)editor.append(el('p','Read or resolve this message in the conversation first. Saving requires a complete, conflict-free linked body.','warning'));
  field('response_kind','Response type',{value:saved.response_kind||'',options:[['','Choose after reading'],['internal_referral','Internal referral / receiving division pending'],['local_referral','City/town routing suggestion'],['no_records','Agency reports no records'],['partial_response','Partial response'],['records_received','Records received — scope still needs review'],['withheld','Records withheld'],['clarification','Clarification needed']]});
  field('summary','Response assessment (private)',{value:saved.summary||'',type:'textarea'});
  field('referral_level','Referral jurisdiction level',{value:saved.referral_level||'',options:[['','No referral'],['state','Within state government'],['municipality','City or town — not county'],['unknown','Unresolved']]});
  field('referral_target','Referred division or suggested municipality',{value:saved.referral_target||'',max:250});
  field('referral_status','Referral evidence status',{value:saved.referral_status||'',options:[['','No referral'],['reported_forwarded','Respondent reports forwarding (receipt unconfirmed)'],['suggested_routing','Suggested routing only — not submitted'],['receipt_confirmed','Receipt confirmed by reviewed evidence']]});
  field('referral_note','Referral evidence / remaining routing gaps',{value:saved.referral_note||'',type:'textarea'});
  const scope=el('details');scope.open=true;scope.append(el('summary','Requested categories — assess separately'));
  for(const c of row.checklist){const r=saved.categories?.find(x=>x.key===c.key),wrap=el('div',undefined,'message');wrap.append(el('h4',c.label));
   const status=el('select');status.dataset.maStatus=c.key;status.dataset.maReview='true';status.setAttribute('aria-label',c.label+' disposition');
   for(const [key,label] of [['not_addressed','Not addressed / not yet assessed'],['pending','Still pending'],['partial','Partly received'],['received','Received within reviewed scope'],['agency_reports_not_held','Agency says not held — not statewide nonexistence'],['withheld','Withheld — record the stated basis'],['not_requested','Not in this case’s actual request']]){const o=el('option',label);o.value=key;status.append(o);}status.value=r?.status||'not_addressed';
   const note=el('textarea');note.dataset.maNote=c.key;note.dataset.maReview='true';note.setAttribute('aria-label',c.label+' evidence note');note.value=r?.note||'';note.rows=2;note.maxLength=1500;wrap.append(status,note);scope.append(wrap);
  }editor.append(scope);
  field('response_date','Reviewed response date (optional)',{value:saved.response_date||'',type:'date'});
  field('date_basis','Response-date evidence and applicability review',{value:saved.date_basis||'',type:'textarea',max:1500});
  editor.append(el('p','A saved date produces a 90-calendar-day appeal planning estimate, not a verified legal deadline. Check applicability and filing rules. Earlier watches remain when a later response is reviewed.','help'));
  field('follow_up_on','Internal follow-up reminder (optional; not legal)',{value:saved.follow_up_on||'',type:'date'});
  const actions=el('div',undefined,'actions');actions.append(button('Save MA response review',save),button('Discard MA review edits',()=>{loadReview();notice('Unsaved MA review edits discarded.');}));editor.append(actions);
  const purpose=el('select');purpose.id='ma-purpose';purpose.dataset.maReview='true';purpose.setAttribute('aria-label','MA follow-up purpose');for(const [v,l] of [['clarify_categories','Clarify category coverage / local routing'],['confirm_referral','Confirm internal referral handoff']]){const o=el('option',l);o.value=v;purpose.append(o);}purpose.value=saved.response_kind==='internal_referral'?'confirm_referral':'clarify_categories';
  const prepare=button('Preview MA follow-up text',async()=>{assertClean();guard();busy=true;controls(true);try{preview=await op('desk_preview_ma_follow_up',{case_id:row.case_id,revision:row.revision,response_message_id:selected,purpose:purpose.value});previewBox.replaceChildren(el('h4','Draft text only — nothing saved or sent'),el('p',preview.routing_note,'warning'),el('pre',preview.body,'preview'),button('Use MA preview in composer',()=>{assertClean();guard();usePreview(preview);notice('Follow-up staged in the composer with its exact reply chain. Verify routing, review and save separately; nothing sent.');}));}finally{busy=false;controls(false);}});
  editor.append(purpose,prepare);baseline=JSON.stringify(review());
 }
 async function save(){
  guard();busy=true;controls(true);let saved=false;
  try{const result=await op('desk_save_ma_review',{case_id:row.case_id,revision:row.revision,...review()});saved=true;current=result.ma_follow_up;row=current.cases[0];loadReview();updateHistory();await onSave();notice('MA review saved privately. No mail sent, case closed, fee accepted or appeal filed.');}
  catch(e){notice((saved?'Review saved, but the view could not fully refresh. ':'')+e.message,true);}
  finally{busy=false;controls(false);}
 }
 function render(){
  box.replaceChildren(el('summary','Massachusetts response review & follow-up'));
  box.append(el('p',current.profile.limits,'help'),el('p',current.profile.municipal_routing,'warning'));
  const sources=el('details');sources.append(el('summary',`Official routing sources · checked ${current.profile.checked_date}${current.profile.source_stale?' · RECHECK NEEDED':''}`));
  for(const c of current.profile.contacts){const p=el('p',`${c.office}: ${c.email}. ${c.scope} `);p.append(link('Official contact source',c.source));sources.append(p);}
  for(const s of current.profile.sources){const p=el('p');p.append(link(s.label,s.url));sources.append(p);}
  sources.append(el('h4','Suggested records holders — not verified municipal custodians'));
  for(const h of current.profile.suggested_holders)sources.append(el('p',`${h.role}: ${h.records}`,'help'));box.append(sources);
  history=el('section');history.id='ma-history';box.append(history);updateHistory();
  if(!row.supported){box.append(el('p','This template needs the general workflow tools. The MA helper currently supports electronic starter-pack and equipment requests.','help'));return;}
  selector=el('select');selector.id='ma-message';selector.dataset.maReview='true';selector.setAttribute('aria-label','MA response message');
  for(const m of row.incoming){const o=el('option',`${m.id} · ${m.subject||'Incoming response'}`);o.value=m.id;selector.append(o);}
  selected=row.incoming.some(m=>m.id===selected)?selected:(row.incoming[0]?.id||'');selector.value=selected;
  selector.onchange=()=>{try{assertClean();selected=selector.value;loadReview();}catch(e){selector.value=selected;notice(e.message,true);}};
  editor=el('section');editor.id='ma-review-editor';previewBox=el('section');previewBox.id='ma-preview';box.append(selector,editor,previewBox);
  if(!selected)box.append(el('p','No incoming response is linked. Check mail separately; this panel never syncs automatically.','help'));
  controls=disabled=>box.querySelectorAll('input,textarea,select,button').forEach(n=>n.disabled=disabled);
  loadReview();
 }
 function refresh(value){if(!value||busy||dirty())return;current=value;row=current.cases[0];render();}
 render();return {assertClean,dirty,refresh};
}
