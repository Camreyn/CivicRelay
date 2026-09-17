import {createWorkspace} from '/workspace.js';
import {registerPageTools} from '/page-tools.mjs';
import {createCampaignView,campaignLabels} from '/equipment-campaign.js';
import {createGeneralWorkspace} from '/general-workspace.js';
const $=id=>document.getElementById(id);
const labels={none:'No prepared request',routing:'Routing needed',draft:'Draft',waiting:'Awaiting reply',new:'New reply',attention:'Action needed',ready:'Ready for review',submitted:'Submitted',closed:'Closed'};
let data,geometry,selected='IN',selectedCase=null,mode='records',showGeneralMap=false;
const recordCases=()=>data.catalog.cases.filter(c=>mode==='general'?!!c.general_campaign_id:!c.campaign_id);
const mapLabel=s=>mode==='equipment'?(campaignLabels[s]||s):(labels[s]||s);
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function badge(status){const n=el('span',undefined,'badge');n.append(el('i',undefined,`dot ${status}`),el('span',labels[status]));return n;}
function status(c){return c.status || (c.recipient?'draft':'routing');}
function aggregate(code){if(mode==='equipment')return data.equipment_campaign?.states.find(s=>s.state===code)?.status||'not_started';const all=recordCases().filter(c=>c.state===code).map(status);return ['new','attention','routing','ready','waiting','draft','submitted','closed'].find(s=>all.includes(s))||'none';}
function notice(text,error=false){$('notice').textContent=text;$('notice').className=error?'error':'';}
async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Records-Desk':'1'},body:JSON.stringify(body)});const j=await r.json();if(!r.ok||j.ok===false){const e=Error(j.error||'The operation could not be completed.');e.sendNotStarted=j.send_not_started===true;throw e;}return j;}
function selectState(code){selected=code;$('state-select').value=code;renderMap();renderState();}
function renderMap(){
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 870 560');
 for(const state of geometry.states){const g=document.createElementNS(ns,'g');g.setAttribute('class',`state ${selected===state.code?'selected':''}`);g.dataset.status=aggregate(state.code);g.setAttribute('tabindex','0');g.setAttribute('role','button');g.setAttribute('aria-label',`${state.name}: ${mapLabel(aggregate(state.code))}`);g.setAttribute('aria-pressed',String(selected===state.code));
 const title=document.createElementNS(ns,'title');title.textContent=`${state.name} · ${mapLabel(aggregate(state.code))}`;g.append(title);
 const path=document.createElementNS(ns,'path');path.setAttribute('d',state.path);g.append(path);
 if(state.callout){const line=document.createElementNS(ns,'line');['x1','y1','x2','y2'].forEach((k,i)=>line.setAttribute(k,[...state.anchor,state.x-14,state.y-4][i]));g.append(line);}
 const text=document.createElementNS(ns,'text');text.setAttribute('x',state.x);text.setAttribute('y',state.y);text.setAttribute('text-anchor','middle');text.textContent=state.code;g.append(text);
 g.addEventListener('click',()=>selectState(state.code));g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectState(state.code);}});svg.append(g);}
 $('map').replaceChildren(svg);
}
function renderState(){if(mode==='equipment'&&data.equipment_campaign){campaign.renderState(selected);return;}const s=data.catalog.states.find(s=>s.code===selected);if(!s)return;$('state-name').textContent=s.name;$('state-code').textContent=s.code;const box=$('cases');box.replaceChildren();box.className='';const cases=recordCases().filter(c=>c.state===selected);if(!cases.length){box.append(el('p','No saved request in this workflow for this state. Federal and other targets remain in the campaign list.', 'empty'));return;}for(const c of cases){const card=el('div',undefined,'case-card');card.append(badge(status(c)),el('h3',c.family_label),el('p',`${c.request_ids.length} tracking ${c.request_ids.length===1?'reference':'references'}${c.year?' · '+c.year:''}`));const b=el('button','Open request');b.onclick=()=>openCase(c.id).catch(()=>{});card.append(b);box.append(card);}}
function renderQueue(){
 const body=$('queue');body.replaceChildren();const filter=$('filter').value;
 body.closest('table').querySelector('thead th').textContent=mode==='general'?'Jurisdiction':'State';
 const steps={routing:'Verify custodian / portal',draft:'Personalize and review',waiting:'Await reply or prepare follow-up',new:'Review incoming reply',attention:'Review routing, clarification, or fees',ready:'Review public intake',submitted:'Normal maintainer review',closed:'No follow-up scheduled'};
 for(const c of recordCases()){
  if(filter!=='all'&&status(c)!==filter)continue;const tr=el('tr'),state=el('td'),family=el('td'),st=el('td');
  state.append(el('span',c.target?.label||c.state_name,'state-title'),el('small',c.target?.level||c.state));family.append(el('span',c.family_label),el('small',c.general_campaign_id?`Template v${c.template_snapshot.version} · Coverage: ${(c.tracking?.coverage||'not_assessed').replaceAll('_',' ')}`:`${c.year} · ${c.request_ids.length} tracking references`));st.append(badge(status(c)));
  const next=el('td',steps[status(c)]),action=el('td'),b=el('button','Open');b.onclick=()=>{if(data.catalog.states.some(s=>s.code===c.state))selectState(c.state);openCase(c.id).catch(()=>{});};action.append(b);tr.append(state,family,st,next,action);body.append(tr);
 }
 if(!body.children.length){const tr=el('tr'),td=el('td','No requests match this filter.');td.colSpan=5;tr.append(td);body.append(tr);}
}
function renderStats(){const cases=recordCases(),counts=data.equipment_campaign?.counts;const stats=mode==='equipment'&&counts?[['States + DC tracked',counts.jurisdictions_tracked],['Started',counts.states_started],['Not started',counts.states_not_started],['Requests with send receipt',counts.requests_with_send_confirmation]]:[['Prepared requests',cases.length],['Awaiting reply',cases.filter(c=>status(c)==='waiting').length],['New replies',cases.filter(c=>status(c)==='new').length],mode==='general'?['Records received',cases.filter(c=>c.tracking?.coverage==='received').length]:['Ready for review',cases.filter(c=>status(c)==='ready').length]];$('stats').replaceChildren(...stats.map(([label,value])=>{const n=el('div',undefined,'stat');n.append(el('strong',String(value)),el('span',label));return n;}));$('state-count').textContent=mode==='equipment'?`${counts?.states_started||0} started · ${counts?.states_not_started??51} not started`:`${new Set(cases.map(c=>c.state).filter(Boolean)).size} states with requests`;}
const op=async(tool,args={})=>(await api('/api/operation',{tool,arguments:args})).result;
async function refresh(){data=await api('/api/bootstrap');if($('workspace-brand'))$('workspace-brand').textContent=(data.workspace?.organization||data.workspace?.name||'CivicRelay')+' / PRIVATE WORKSPACE';renderStats();renderMap();renderState();renderQueue();campaign.renderQueue();workspace.renderInbox();}
const workspace=createWorkspace({$,el,op,notice,labels,badge,getData:()=>data,refresh,selectState});
const campaign=createCampaignView({$,el,getData:()=>data,selectState,openCase});
const general=createGeneralWorkspace({$,el,op,notice,openCase,beforeNavigate:()=>{workspace.assertClean();$('case-workspace').hidden=true;},afterChange:refresh,toggleMap:()=>{showGeneralMap=!showGeneralMap;document.querySelector('.desk-grid').hidden=!showGeneralMap;}});
async function changeMode(value){
 try{workspace.assertClean();}catch(e){$('campaign-mode').value=mode;throw e;}
 const changed=mode!==value;mode=value;$('campaign-mode').value=mode;const isGeneral=mode==='general';
 $('existing-queue').hidden=mode==='equipment';$('campaign-panel').hidden=mode!=='equipment';$('general-workspace').hidden=!isGeneral;$('campaign-policy').hidden=mode!=='equipment';document.querySelector('.desk-grid').hidden=isGeneral&&!showGeneralMap;$('stats').hidden=false;if(changed)$('case-workspace').hidden=true;document.querySelector('.inbox-panel').hidden=false;
 const legend=mode==='equipment'?campaignLabels:labels;$('legend').replaceChildren(...Object.entries(legend).map(([k,v])=>{const n=el('span');n.append(el('i',undefined,`dot ${k}`),el('span',v));return n;}));
 renderStats();renderMap();renderState();renderQueue();campaign.renderQueue();if(isGeneral)await general.load();
}
async function openCase(id){try{workspace.assertClean();await workspace.openCase(id);selectedCase=id;}catch(e){notice(e.message,true);throw e;}}
async function sync(){notice('Checking new project mailbox headers. No mail will be sent.');const r=await op('desk_sync_mail');await refresh();await workspace.refreshDetail();notice(`${r.new_headers} new headers synced. ${r.folders.some(f=>f.more)?'More mail remains; check again to continue.':'Mailbox check complete.'} Proton read flags were not changed.`);return r;}
async function registerTools(){
 const life=new AbortController();window.addEventListener('pagehide',()=>life.abort(),{once:true});
 const report=await registerPageTools(document.modelContext,{
  workspace,
  overview:()=>({workflow:mode,equipment_campaign_counts:data.equipment_campaign?.counts,selected_state:selected,queue_filter:$('filter').value,cases:data.catalog.cases.map(c=>({id:c.id,state:c.state,status:c.status,revision:c.revision,unread_count:c.unread_count})),states:data.catalog.states.map(s=>({code:s.code,name:s.name,status:aggregate(s.code)})),unassigned_total:data.unassigned_total}),
  openCase:async id=>{if(!data.catalog.cases.some(c=>c.id===id))throw Error('Choose a known case ID.');await openCase(id);return workspace.snapshot();},
  selectState:code=>{if(!data.catalog.states.some(s=>s.code===code))throw Error('Choose a known state code.');selectState(code);return {selected_state:selected};},
  filterQueue:value=>{if(!Array.from($('filter').options).some(o=>o.value===value))throw Error('Choose an available queue filter.');$('filter').value=value;renderQueue();return {queue_filter:value};},
  backend:async(name,args,readOnly)=>{
   const result=await op(name,args);
   if(!readOnly){try{await refresh();await workspace.afterOperation();}catch{notice('The operation completed but the view could not refresh. Inspect its saved receipt; do not retry a send or publication.',true);return {...result,dashboard_refresh_warning:'Operation completed; visible refresh failed. Do not retry external writes.'};}}
   if(name==='desk_list_cases')return {cases:result.catalog.cases.map(c=>({id:c.id,state:c.state,family:c.family_label,status:c.status,revision:c.revision,unread_count:c.unread_count})),unassigned:result.unassigned,unassigned_total:result.unassigned_total,sync:result.sync};
   return result;
  },
 },{signal:life.signal,onError:()=>notice('Some page tools could not register. Native Records Desk tools remain available.',true)});
 if(report.supported&&!report.failed.length)$('connection').textContent='Local workspace · Assistant tools ready';
}
async function boot(){try{[data,geometry]=await Promise.all([api('/api/bootstrap'),fetch('/map.json').then(r=>r.json())]);$('state-select').replaceChildren(...data.catalog.states.map(s=>{const o=el('option',s.name);o.value=s.code;return o;}));$('state-select').onchange=e=>selectState(e.target.value);$('filter').onchange=renderQueue;for(const s of ['draft','attention','ready','submitted','closed']){const o=el('option',labels[s]);o.value=s;$('filter').append(o);}const active=data.equipment_campaign?.states.find(s=>s.phase!=='not_started');if(active)selected=active.state;$('campaign-mode').onchange=e=>changeMode(e.target.value).catch(e=>notice(e.message,true));await changeMode(active?'equipment':data.workspace?.starter_pack==='blank'?'general':'records');if($('workspace-brand'))$('workspace-brand').textContent=(data.workspace?.organization||data.workspace?.name||'CivicRelay')+' / PRIVATE WORKSPACE';selectState(selected);workspace.renderInbox();$('sync').disabled=false;$('sync').onclick=async()=>{const b=$('sync');b.disabled=true;try{await sync();}catch(e){notice(e.message,true);}finally{b.disabled=false;}};notice('Private records workspace ready. Exact previews, saved receipts, and separate publication tracking are available.');registerTools();}catch(e){notice(e.message,true);}}
boot();
