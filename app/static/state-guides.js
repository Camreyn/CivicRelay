// Automatically presented, never auto-expanded. No remote fetch on navigation.
const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
function link(label,url){const a=el('a',label);try{const u=new URL(url);if(u.protocol!=='https:'||u.username||u.password)throw Error();a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';}catch{a.removeAttribute('href');}return a;}
export function createStateGuides({host,op,openSettings}){
 let state='',generation=0,payload=null,contacts=null,query='',offset=0,contactGeneration=0;
 const panel=el('details');panel.id='state-guides';panel.className='panel state-guides';panel.hidden=true;
 const title=el('summary'),body=el('div');panel.append(title,body);host.append(panel);
 const directory=el('details');directory.id='municipal-contacts';directory.className='panel';directory.hidden=true;
 const dt=el('summary','Massachusetts city & town contacts'),db=el('div');directory.append(dt,db);host.append(directory);
 const coverage=el('p'),meta=el('p'),search=el('input'),rows=el('div'),paging=el('div'),error=el('p');error.setAttribute('role','status');
 search.type='search';search.id='municipal-search';search.placeholder='City or town name';search.maxLength=100;
 const form=el('form'),label=el('label','Find a municipality');label.htmlFor=search.id;const submit=el('button','Search');submit.type='submit';
 const settings=el('button','Manage sources in Settings');settings.type='button';settings.onclick=openSettings;
 form.append(label,search,submit,settings);form.onsubmit=e=>{e.preventDefault();query=search.value;offset=0;loadContacts();};
 db.append(coverage,el('p','These are elections records-holder contacts, not verified designated Records Access Officers. Municipalities are separate from counties. Nothing here creates or sends requests.'),meta,form,error,rows,paging);
 directory.addEventListener('toggle',()=>{if(directory.open&&state==='MA'&&!contacts)loadContacts();});
 async function loadContacts(){
  const serial=++contactGeneration,current=state;error.textContent='Loading saved contacts…';
  try{
   const r=await op('desk_get_municipal_contacts',{state:'MA',query,offset,limit:25});
   if(serial!==contactGeneration||state!==current||state!=='MA')return;
   contacts=r;coverage.textContent=`${r.coverage.collected} / ${r.coverage.municipalities} municipalities collected · ${r.coverage.with_email} with email · ${r.coverage.designated_raos_verified} designated RAOs verified`;
   meta.replaceChildren(link('Official directory',r.source.url),el('span',` · Source checked: ${r.source.checked_on||'not yet'} · Last collected: ${r.source.last_success_at||'not yet'} · ${r.source.collection_mode==='reviewed_text_import'?'Reviewed text import':r.source.collection_mode==='direct_fetch'?'Direct fetch':'Not collected'}${r.source.stale?' · Source review overdue':''}`));
   rows.replaceChildren();for(const c of r.contacts){const card=el('article');card.className='municipal-card';card.append(el('h3',c.municipality),el('p',c.office||'Not collected'),el('p',c.emails.length?c.emails.join(' · '):'No collected email'),el('p',c.phone||''),el('p','Designated RAO: not verified'),link('Contact source',c.source_url),el('small',`Checked ${c.checked_on||'not yet'} · Collected ${c.collected_at||'not yet'}${c.stale?' · Recheck needed':''}`));if(c.email_context)card.append(el('p',`Directory email labels: ${c.email_context}`));rows.append(card);}
   paging.replaceChildren(el('span',`${r.total?offset+1:0}–${Math.min(offset+25,r.total)} of ${r.total} matches`));
   for(const [caption,next] of [['Previous',offset-25],['Next',r.next_offset]]){const b=el('button',caption);b.disabled=next===null||next<0;b.onclick=()=>{offset=next;loadContacts();};paging.append(b);}error.textContent='';
  }catch(e){if(serial===contactGeneration)error.textContent=e.message;}
 }
 async function show(code,{force=false}={}){
  if(state===code&&!force)return;
  const changed=state!==code;state=code;const serial=++generation;
  if(changed){panel.open=false;directory.open=false;contacts=null;query='';offset=0;search.value='';++contactGeneration;rows.replaceChildren();coverage.textContent='';meta.textContent='';paging.replaceChildren();error.textContent='';}
  directory.hidden=code!=='MA';panel.hidden=false;title.textContent=`${code} · loading state guide…`;body.replaceChildren();payload=null;
  try{const r=await op('desk_get_state_guide',{state:code});if(serial!==generation)return;payload=r;panel.hidden=!r.available;title.textContent=`${r.state_name} guides & official sources (${r.guides.length})`;
   for(const guide of r.guides){const section=el('section');section.append(el('h3',guide.title),el('p',`Guidance checked: ${guide.checked_on}. Recheck current official sources before relying on a rule or contact.`));for(const item of guide.sections)section.append(el('h4',item.title),el('p',item.text));const list=el('ul');for(const s of guide.sources){const li=el('li');li.append(link(s.label,s.url));list.append(li);}section.append(list);body.append(section);}
  }catch(e){if(serial===generation){title.textContent=`${code} guide unavailable`;body.append(el('p',e.message));}}
 }
 return {show,async refreshContacts(){contacts=null;if(state==='MA'&&directory.open)await loadContacts();},snapshot:()=>({state,available:payload?.available??null,default_collapsed:true,automatic_on_state_selection:true,expanded:panel.open,guide_ids:payload?.guides.map(g=>g.id)||[],municipal_directory_visible:!directory.hidden})};
}
