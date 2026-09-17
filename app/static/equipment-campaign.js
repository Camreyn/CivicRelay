// Private workflow display. Agency text is rendered as text, never executable HTML.
export const campaignLabels={not_started:'Not started',researching:'Researching',requests_prepared:'Requests prepared',
 follow_up:'Follow-up needed',paused:'Paused',scoped_review_complete:'Selected scope reviewed',
 draft_prepared:'Draft prepared',new_reply:'New reply',uncertain:'Send needs reconciliation',
 fee_notice:'Fee estimate — approval needed',denied:'Denial — review needed',clarification:'Clarification requested',
 partial_response:'Partial response',records_received:'Records received — review needed',
 acknowledged:'Acknowledged',awaiting_response:'Awaiting response',closed:'Selected request closed'};
const coverageLabel={not_assessed:'Not assessed',partial:'Partial evidence',received:'Records received',unavailable:'Reported unavailable',not_applicable:'Not applicable in selected scope'};
export function createCampaignView({$,el,getData,selectState,openCase}){
 const campaign=()=>getData().equipment_campaign;
 function renderQueue(){
  const box=$('campaign-queue');box.replaceChildren();const value=$('campaign-filter').value;
  for(const row of campaign()?.states||[]){
   if(value==='active'&&row.phase==='not_started'||value==='remaining'&&row.phase!=='not_started')continue;
   const tr=el('tr'),name=el('td'),button=el('button',row.state_name);button.onclick=()=>selectState(row.state);name.append(button,el('small',row.state));
   const current=el('td',campaignLabels[row.status]||row.status);current.className='campaign-status';
   tr.append(name,current,el('td',String(row.requests.length)),el('td',row.county_scope_selected?'Selected locality only':'County / municipality not selected'),el('td',row.next_action));box.append(tr);
  }
  if(!box.children.length){const tr=el('tr'),td=el('td','No states match this view.');td.colSpan=5;tr.append(td);box.append(tr);}
 }
 function renderState(code){
  const row=campaign()?.states.find(s=>s.state===code);if(!row)return;
  $('state-name').textContent=row.state_name;$('state-code').textContent=code;
  const box=$('cases');box.replaceChildren();box.className='campaign-state';
  box.append(el('h3',campaignLabels[row.status]||row.status),el('p',row.scope_note||'This state is tracked, but research has not started.'),
   el('p','Next: '+row.next_action,'campaign-next'),el('p','Selected scope only; no statewide completeness claim.','help'));
  for(const [key,title] of Object.entries(campaign().categories)){
   const c=row.coverage[key];const item=el('div',undefined,'campaign-category');item.append(el('strong',title),el('p',coverageLabel[c.status]),el('small',c.note||'No assessment recorded.'));box.append(item);
  }
  for(const request of row.requests){
   const card=el('div',undefined,'case-card');card.append(el('h3',request.jurisdiction),el('p',campaignLabels[request.status]),
    el('p',request.routing_fresh?'Official email routing reviewed (recheck before sending).':'Email routing needs verification or renewal.','help'));
   if(request.receipts.length)card.append(el('p','Saved Bridge acceptance receipt; recipient delivery is not proven.','help'));
   const t=request.tracking;
   if(t?.fee_note)card.append(el('p','Fees: '+t.fee_note));
   if(t?.procedure_note)card.append(el('p','Procedure: '+t.procedure_note));
   if(t?.deadline_date)card.append(el('p',`${t.deadline_kind} deadline: ${t.deadline_date} — ${t.deadline_basis}`));
   if(t?.note)card.append(el('p',t.note));
   const b=el('button','Open request');b.onclick=()=>openCase(request.id);card.append(b);box.append(card);
  }
  const sources=el('details');sources.append(el('summary',`${row.sources.length} dated official-source notes`));
  for(const source of row.sources){const article=el('div',undefined,'campaign-source'),a=el('a',source.title);a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';article.append(a,el('small','Checked '+source.checked_date),el('p',source.summary));sources.append(article);}
  box.append(sources);
 }
 $('campaign-filter').onchange=renderQueue;
 return {renderQueue,renderState};
}
