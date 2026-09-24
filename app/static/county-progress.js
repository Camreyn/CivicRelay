// Read-only navigation. Request status comes from the shared guarded backend.
import {createMapControls} from '/map-controls.mjs';
export function createCountyProgress({$,el,op,getState,getMode,getStates,selectState,openCase,notice}){
 let initialized=false,scope=null,progress=null,chosen=null,version=0,mapData=null,mapPromise=null;
 const panel=$('county-progress-panel');
 const mapControls=createMapControls({host:$('county-progress-map'),legend:$('county-progress-legend'),id:'county-map',label:'County request map',defaultLabels:false,selectionName:'county'});
 const names={all:'All workflows',equipment:'Equipment & communications',general:'General records desk',records:'Existing records requests'};
 const when=t=>t?new Date(t*1000).toLocaleString():'—';
 function button(label,fn){const b=el('button',label);b.type='button';b.onclick=()=>Promise.resolve().then(fn).catch(e=>notice(e.message,true));return b;}
 function select(parent,label,id,items){const wrap=el('label',label),input=el('select');input.id=id;for(const [value,text] of items){const o=el('option',text);o.value=value;input.append(o);}wrap.append(input);parent.append(wrap);return input;}
 function badge(status,text){const b=el('span',text,'county-badge');b.dataset.status=status;return b;}
 async function geometry(){
  if(mapData)return mapData;
  if(!mapPromise)mapPromise=fetch('/county-map.json').then(r=>{if(!r.ok)throw Error('County shapes unavailable. The complete county list still works.');return r.json();}).then(r=>{if(r.schema_version!==1||!r.states)throw Error('County map format is unavailable. Use the list.');mapData=r;return r;}).finally(()=>{mapPromise=null;});
  return mapPromise;
 }
 function setup(){
  if(initialized)return;initialized=true;
  const controls=$('county-progress-controls');
  const state=select(controls,'State','county-progress-state',getStates().map(s=>[s.code,s.name]));state.value=getState();state.onchange=()=>selectState(state.value);
  const mode=select(controls,'Workflow','county-progress-workflow',Object.entries(names));mode.value=getMode();mode.onchange=()=>{chosen=null;reload();};
  const filter=select(controls,'Request status','county-progress-filter',[['all','All counties'],['active','With requests'],['none','No county request'],['new','New replies'],['attention','Needs attention'],['waiting','Awaiting / acknowledged'],['received','Records received / partial'],['closed','Closed']]);filter.onchange=render;
  const label=el('label','Find county'),search=el('input');search.id='county-progress-search';search.type='search';search.placeholder='County name';label.append(search);controls.append(label);search.oninput=render;
  controls.append(button('Refresh saved status',reload));
 }
 async function reload(){
  if(!panel.open)return;setup();const token=++version,state=getState(),workflow=$('county-progress-workflow').value;
  if(scope!==state+'|'+workflow){chosen=null;progress=null;$('county-progress-search').value='';$('county-progress-filter').value='all';mapControls.clear();mapControls.setLegend([]);$('county-progress-map').replaceChildren();$('county-progress-rows').replaceChildren();$('county-progress-detail').replaceChildren();}
  scope=state+'|'+workflow;$('county-progress-state').value=state;
  $('county-progress-title').textContent=(getStates().find(s=>s.code===state)?.name||state)+' · County requests';
  $('county-progress-freshness').textContent='Loading saved county request status…';panel.setAttribute('aria-busy','true');
  try{
   const result=await op('desk_list_counties',{state,include_requests:true,workflow});if(token!==version)return;
   if(!result.request_progress)throw Error('Restart CivicRelay to load county request status support.');
   progress=result.request_progress;
   render();renderRelated();
   $('county-progress-freshness').textContent='Saved local status as of '+when(progress.as_of)+'. This does not check the inbox. Use “Check for replies” to fetch new headers.';
   try{await geometry();if(token===version)renderMap();}catch(e){if(token===version)$('county-progress-map').replaceChildren(el('p',e.message,'warning'));}
  }catch(e){if(token===version){$('county-progress-freshness').textContent='Could not refresh county status. '+e.message+' Displayed results, if any, may be stale.';}}
  finally{if(token===version)panel.setAttribute('aria-busy','false');}
 }
 function visible(row){
  const q=$('county-progress-search').value.trim().toLocaleLowerCase(),filter=$('county-progress-filter').value;
  if(q&&!row.name.toLocaleLowerCase().includes(q))return false;
  if(filter==='all')return true;if(filter==='none')return !row.request_count;if(filter==='active')return !!row.request_count;
  if(filter==='new')return row.unread_count>0;
  if(filter==='attention')return row.requests.some(r=>['attention','uncertain','partial','routing'].includes(r.status))||!!row.deadline_status;
  if(filter==='waiting')return row.requests.some(r=>['waiting','acknowledged'].includes(r.status));
  if(filter==='received')return row.requests.some(r=>['received','partial'].includes(r.status));
  return row.status==='closed';
 }
 function choose(id){chosen=id;render();$('county-progress-detail').scrollIntoView({block:'nearest'});}
 function render(){
  if(!progress)return;
  const c=progress.counts;
  $('county-progress-counts').textContent=`${c.counties} counties / equivalents · ${c.with_requests} with requests · ${c.without_requests} with no county request · ${c.unread_replies} new replies`;
  const rows=progress.counties.filter(visible),body=$('county-progress-rows');body.replaceChildren();
  $('county-progress-showing').textContent=`Showing ${rows.length} of ${c.counties} counties · ${c.requests} matched county requests in ${names[progress.workflow]}.`;
  for(const row of rows){
   const tr=el('tr');tr.dataset.countyRow=row.id;tr.dataset.selected=String(chosen===row.id);
   const name=el('td'),state=el('td'),count=el('td',String(row.request_count));name.append(button(row.name,()=>choose(row.id)));state.append(badge(row.status,row.label));
   if(Object.keys(row.status_counts).length>1)state.append(el('small','Mixed request statuses'));
   if(row.unread_count)state.append(el('small',`${row.unread_count} new ${row.unread_count===1?'reply':'replies'}`));
   if(row.deadline_status)state.append(el('small',row.deadline_status==='overdue'?'Past timing date — verify':'Timing checkpoint due soon','county-timing'));
   tr.append(name,state,count);body.append(tr);
  }
  if(!rows.length){const tr=el('tr'),td=el('td','No counties match these filters.');td.colSpan=3;tr.append(td);body.append(tr);}
  mapControls.setLegend(Object.entries(progress.status_labels).map(([k,v])=>badge(k,v)));
  renderMap();renderDetail();
 }
 function renderMap(){
  if(!mapData||!progress)return;
  const box=$('county-progress-map'),shapes=mapData.states[progress.state]||[],byId=new Map(progress.counties.map(c=>[c.id,c]));
  const focused=box.contains(document.activeElement)?document.activeElement.dataset.countyId||'canvas':null;
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox',mapData.view_box);svg.setAttribute('aria-label','County request status for '+progress.state);
  for(const shape of shapes){const row=byId.get(shape.id);if(!row||!shape.path)continue;
   const g=document.createElementNS(ns,'g');g.classList.add('county-shape');g.dataset.countyId=row.id;g.dataset.name=row.name;g.dataset.status=row.status;g.dataset.selected=String(chosen===row.id);g.dataset.matched=String(visible(row));g.dataset.deadline=row.deadline_status;
   g.setAttribute('tabindex','0');g.setAttribute('role','button');g.setAttribute('aria-label',`${row.name}: ${row.label}, ${row.request_count} requests`);g.setAttribute('aria-pressed',String(chosen===row.id));
   const title=document.createElementNS(ns,'title');title.textContent=`${row.name} · ${row.label} · ${row.request_count} requests${Object.keys(row.status_counts).length>1?' · Mixed statuses; open county for each request':''}`;g.append(title);
   const path=document.createElementNS(ns,'path');path.setAttribute('d',shape.path);path.setAttribute('fill-rule','evenodd');g.append(path);
   const pick=()=>{if(!visible(row)){$('county-progress-search').value='';$('county-progress-filter').value='all';}choose(row.id);};g.addEventListener('click',pick);g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick();}});svg.append(g);
  }
  box.replaceChildren(svg);
  mapControls.mount(svg,{scope:progress.state,selected:svg.querySelector('[data-selected=true]')});
  if(focused)(Array.from(svg.querySelectorAll('.county-shape')).find(g=>g.dataset.countyId===focused)||svg).focus({preventScroll:true});
  const note=$('county-progress-source');note.replaceChildren();const source=el('a',`Census ${mapData.vintage} simplified county shapes`);source.href=mapData.source_page;source.target='_blank';source.rel='noopener noreferrer';
  note.append(source,el('span',' · Navigation only, not legal or election boundaries. Some county equivalents have no county government. Small areas are also available in the list.'));
 }
 function requestCard(request){
  const card=el('div',undefined,'county-request-card');card.dataset.countyCase=request.id;
  card.append(el('h4',request.title),badge(request.status,request.label));
  if(request.response_stage!=='none')card.append(el('p','Recorded response: '+request.response_stage.replaceAll('_',' ')));
  if(request.response_review_needed)card.append(el('p','Response evidence needs review or has a thread conflict.','warning'));
  card.append(el('p',`${request.unread_count} new replies · ${request.mail_count} saved messages`));
  card.append(el('small',request.send_confirmed?'Saved sending-system acceptance receipt; recipient delivery is not proven.':'No confirmed sending-system acceptance receipt.'));
  if(request.coverage)card.append(el('p','Recorded coverage: '+request.coverage.replaceAll('_',' ')));
  if(request.fee_note)card.append(el('p','Fee note: '+request.fee_note));
  if(request.deadline?.due_date)card.append(el('p',`${request.deadline.label}: ${request.deadline.due_date}. Verify timing evidence.`, 'county-timing'));
  card.append(el('small','Last saved activity: '+when(request.last_activity_at)),button('Open request & replies',()=>openCase(request.id)));
  return card;
 }
 function renderDetail(){
  const box=$('county-progress-detail');box.replaceChildren();const row=progress.counties.find(c=>c.id===chosen);
  if(!row){box.append(el('p','Select a county on the map or in the list to see its requests and replies.','help'));return;}
  box.append(el('h3',row.name),el('p',`${row.request_count} county-specific ${row.request_count===1?'request':'requests'} in this workflow.`, 'help'));
  if(!row.request_count)box.append(el('p','No county-specific request has been created here in this workflow. A state-level request does not count as a county request. Contact research alone does not count as a submitted request.'));
  for(const request of row.requests)box.append(requestCard(request));
 }
 function renderRelated(){
  const root=$('county-progress-related');root.replaceChildren();
  for(const [rows,title] of [[progress.unmatched_county_requests,'County requests needing a name / ID match'],[progress.other_jurisdiction_requests,'State or other jurisdictions — not assigned to counties']]){
   if(!rows.length)continue;const d=el('details');d.append(el('summary',`${title} (${rows.length})`));
   if(rows===progress.unmatched_county_requests){d.open=true;d.append(el('p','These requests remain visible but do not color a county. Review the exact jurisdiction; no fuzzy matching is used.','warning'));}
   for(const r of rows)d.append(requestCard(r));root.append(d);
  }
 }
 function contextChanged(){
  if(!initialized||!panel.open)return;
  if(getMode()!==lastMode){$('county-progress-workflow').value=getMode();lastMode=getMode();}
  reload();
 }
 let lastMode=getMode();
 function open(){setup();if(panel.open)reload();else panel.open=true;panel.scrollIntoView({block:'start',behavior:'smooth'});}
 panel.addEventListener('toggle',()=>{if(panel.open){setup();if(lastMode!==getMode()){$('county-progress-workflow').value=getMode();lastMode=getMode();}reload();}else{version++;panel.removeAttribute('aria-busy');}});
 $('show-county-progress').onclick=open;
 return {contextChanged,refresh:reload,open,snapshot:()=>progress?{state:progress.state,workflow:progress.workflow,selected_county:chosen,counts:progress.counts,as_of:progress.as_of,map_view:mapControls.snapshot()}:null};
}
