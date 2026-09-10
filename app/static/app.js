import {createWorkspace} from '/workspace.js';
import {registerPageTools} from '/page-tools.mjs';
const $=id=>document.getElementById(id);
const labels={none:'No prepared request',routing:'Routing needed',draft:'Draft',waiting:'Awaiting reply',new:'New reply',attention:'Action needed',ready:'Ready for review',submitted:'Submitted',closed:'Closed'};
let data,geometry,selected='IN',selectedCase=null;
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function badge(status){const n=el('span',undefined,'badge');n.append(el('i',undefined,`dot ${status}`),el('span',labels[status]));return n;}
function status(c){return c.status || (c.recipient?'draft':'routing');}
function aggregate(code){const all=data.catalog.cases.filter(c=>c.state===code).map(status);return ['new','attention','routing','ready','waiting','draft','submitted','closed'].find(s=>all.includes(s))||'none';}
function notice(text,error=false){$('notice').textContent=text;$('notice').className=error?'error':'';}
async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-Records-Desk':'1'},body:JSON.stringify(body)});const j=await r.json();if(!r.ok||j.ok===false){const e=Error(j.error||'The operation could not be completed.');e.sendNotStarted=j.send_not_started===true;throw e;}return j;}
function selectState(code){selected=code;$('state-select').value=code;renderMap();renderState();}
function renderMap(){
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 870 560');
 for(const state of geometry.states){const g=document.createElementNS(ns,'g');g.setAttribute('class',`state ${selected===state.code?'selected':''}`);g.dataset.status=aggregate(state.code);g.setAttribute('tabindex','0');g.setAttribute('role','button');g.setAttribute('aria-label',`${state.name}: ${labels[aggregate(state.code)]}`);g.setAttribute('aria-pressed',String(selected===state.code));
 const title=document.createElementNS(ns,'title');title.textContent=`${state.name} · ${labels[aggregate(state.code)]}`;g.append(title);
 const path=document.createElementNS(ns,'path');path.setAttribute('d',state.path);g.append(path);
 if(state.callout){const line=document.createElementNS(ns,'line');['x1','y1','x2','y2'].forEach((k,i)=>line.setAttribute(k,[...state.anchor,state.x-14,state.y-4][i]));g.append(line);}
 const text=document.createElementNS(ns,'text');text.setAttribute('x',state.x);text.setAttribute('y',state.y);text.setAttribute('text-anchor','middle');text.textContent=state.code;g.append(text);
 g.addEventListener('click',()=>selectState(state.code));g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectState(state.code);}});svg.append(g);}
 $('map').replaceChildren(svg);
}
function renderState(){const s=data.catalog.states.find(s=>s.code===selected);$('state-name').textContent=s.name;$('state-code').textContent=s.code;const box=$('cases');box.replaceChildren();const cases=data.catalog.cases.filter(c=>c.state===selected);if(!cases.length){box.append(el('p','No prepared request in the current project catalog. Other states remain visible; no requests are invented.', 'empty'));return;}for(const c of cases){const card=el('div',undefined,'case-card');card.append(badge(status(c)),el('h3',c.family_label),el('p',`${c.request_ids.length} tracking ${c.request_ids.length===1?'reference':'references'} · ${c.year}`));const b=el('button','Open request');b.onclick=()=>openCase(c.id);card.append(b);box.append(card);}}
function renderQueue(){
 const body=$('queue');body.replaceChildren();const filter=$('filter').value;
 const steps={routing:'Verify custodian / portal',draft:'Personalize and review',waiting:'Await reply or prepare follow-up',new:'Review incoming reply',attention:'Review routing, clarification, or fees',ready:'Review public intake',submitted:'Normal maintainer review',closed:'No follow-up scheduled'};
 for(const c of data.catalog.cases){
  if(filter!=='all'&&status(c)!==filter)continue;const tr=el('tr'),state=el('td'),family=el('td'),st=el('td');
  state.append(el('span',c.state_name,'state-title'),el('small',c.state));family.append(el('span',c.family_label),el('small',`${c.year} · ${c.request_ids.length} tracking references`));st.append(badge(status(c)));
  const next=el('td',steps[status(c)]),action=el('td'),b=el('button','Open');b.onclick=()=>{selectState(c.state);openCase(c.id);};action.append(b);tr.append(state,family,st,next,action);body.append(tr);
 }
 if(!body.children.length){const tr=el('tr'),td=el('td','No requests match this filter.');td.colSpan=5;tr.append(td);body.append(tr);}
}
function renderStats(){const cases=data.catalog.cases;const stats=[['Prepared requests',cases.length],['Awaiting reply',cases.filter(c=>status(c)==='waiting').length],['New replies',cases.filter(c=>status(c)==='new').length],['Ready for review',cases.filter(c=>status(c)==='ready').length]];$('stats').replaceChildren(...stats.map(([label,value])=>{const n=el('div',undefined,'stat');n.append(el('strong',String(value)),el('span',label));return n;}));$('state-count').textContent=`${new Set(cases.map(c=>c.state)).size} states with requests`;}
const op=async(tool,args={})=>(await api('/api/operation',{tool,arguments:args})).result;
async function refresh(){data=await api('/api/bootstrap');renderStats();renderMap();renderState();renderQueue();workspace.renderInbox();}
const workspace=createWorkspace({$,el,op,notice,labels,badge,getData:()=>data,refresh,selectState});
async function openCase(id){try{workspace.assertClean();await workspace.openCase(id);selectedCase=id;}catch(e){notice(e.message,true);throw e;}}
async function sync(){notice('Checking new project mailbox headers. No mail will be sent.');const r=await op('desk_sync_mail');await refresh();await workspace.refreshDetail();notice(`${r.new_headers} new headers synced. ${r.folders.some(f=>f.more)?'More mail remains; check again to continue.':'Mailbox check complete.'} Proton read flags were not changed.`);return r;}
async function registerTools(){
 const life=new AbortController();window.addEventListener('pagehide',()=>life.abort(),{once:true});
 const report=await registerPageTools(document.modelContext,{
  workspace,
  overview:()=>({selected_state:selected,queue_filter:$('filter').value,cases:data.catalog.cases.map(c=>({id:c.id,state:c.state,status:c.status,revision:c.revision,unread_count:c.unread_count})),states:data.catalog.states.map(s=>({code:s.code,name:s.name,status:aggregate(s.code)})),unassigned_total:data.unassigned_total}),
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
async function boot(){try{[data,geometry]=await Promise.all([api('/api/bootstrap'),fetch('/map.json').then(r=>r.json())]);$('state-select').replaceChildren(...data.catalog.states.map(s=>{const o=el('option',s.name);o.value=s.code;return o;}));$('state-select').onchange=e=>selectState(e.target.value);$('filter').onchange=renderQueue;for(const s of ['draft','attention','ready','submitted','closed']){const o=el('option',labels[s]);o.value=s;$('filter').append(o);}$('legend').replaceChildren(...Object.entries(labels).map(([k,v])=>{const n=el('span');n.append(el('i',undefined,`dot ${k}`),el('span',v));return n;}));renderStats();selectState(selected);renderQueue();workspace.renderInbox();$('sync').disabled=false;$('sync').onclick=async()=>{const b=$('sync');b.disabled=true;try{await sync();}catch(e){notice(e.message,true);}finally{b.disabled=false;}};notice('Private records workspace ready. Sending and public submissions each require review.');registerTools();}catch(e){notice(e.message,true);}}
boot();
