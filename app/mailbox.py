"""Read-only IMAP sync and explicit MIME capture; no remote URLs or attachment execution."""
from email import policy
from email.parser import BytesParser
import base64
import hashlib
import re
import time
import uuid
import bridge
from secure_store import ConnectorError

MAX_RAW=20*1024*1024

def identities(text):
    return re.findall(r'<[^<>\s]{1,200}>',str(text))[:100]

def thread_case(message,messages,outgoing):
    """Exact reference matching only. Conflicting references stay unassigned."""
    refs=set(identities(message.get('in_reply_to',''))+identities(message.get('references','')))
    known={}
    for mid,case in outgoing:known.setdefault(mid,set()).add(case)
    for m in messages:
        if m.get('case_id') and m.get('message_id'):
            known.setdefault(m['message_id'],set()).add(m['case_id'])
    hits=set().union(*(known.get(mid,set()) for mid in refs)) if refs else set()
    if message.get('folder')=='Sent':hits.update(known.get(message.get('message_id'),set()))
    return next(iter(hits)) if len(hits)==1 else None

def message_key(folder,validity,uid):return f'{folder}:{validity}:{uid}'

def reconcile_threads(messages,outgoing):
    # Connected components propagate ambiguity as well as matches. New conflicting
    # references remove old automatic assignments; explicit human assignments stay.
    parent={}
    def root(x):
        parent.setdefault(x,x)
        r=x
        while parent[r]!=r:r=parent[r]
        while parent[x]!=x:
            nxt=parent[x];parent[x]=r;x=nxt
        return r
    def union(a,b):
        ra,rb=root(a),root(b)
        if ra!=rb:parent[rb]=ra
    nodes={}
    for m in messages:
        ids=identities(m.get('message_id',''))+identities(m.get('in_reply_to',''))+identities(m.get('references',''))
        if not ids:continue
        nodes[m['id']]=ids[0]
        for i in ids:union(ids[0],i)
    for mid,_ in outgoing:root(mid)
    known={}
    for mid,case_id in outgoing:known.setdefault(root(mid),set()).add(case_id)
    for m in messages:
        if m.get('assignment')=='manual' and m.get('case_id') and m['id'] in nodes:
            known.setdefault(root(nodes[m['id']]),set()).add(m['case_id'])
    changed=[]
    for m in messages:
        hits=known.get(root(nodes[m['id']]),set()) if m['id'] in nodes else set()
        conflict=len(hits)>1
        if m.get('assignment')=='manual' or m.get('manual_unassigned'):
            if m.get('thread_conflict')!=conflict:m['thread_conflict']=conflict;changed.append(m)
            continue
        match=next(iter(hits)) if len(hits)==1 else None
        if m.get('case_id')!=match or m.get('thread_conflict')!=conflict:
            m.update(case_id=match,assignment='thread' if match else None,thread_conflict=conflict);changed.append(m)
    return changed

def sync_folder(settings,db,folder,outgoing):
    cursor=db.get('sync',folder,{})
    with bridge.imap_connection(settings) as con:
        validity=bridge.select_readonly(con,folder)
        epoch_changed=bool(cursor and cursor.get('uid_validity')!=validity)
        last=cursor.get('last_uid',0) if cursor.get('uid_validity')==validity else 0
        status,result=con.uid('search',None,'UID',f'{last+1}:*')
        if status!='OK' or not result or len(result[0])>2*1024*1024:raise ConnectorError('Mailbox search failed or was too large.')
        rawids=result[0].split()
        if any(not re.fullmatch(rb'[0-9]+',i) for i in rawids):raise ConnectorError('Mailbox returned invalid message identifiers.')
        ids=sorted(set(int(x) for x in rawids if int(x)>last))
        chosen=ids[:80]; existing=db.all('mail'); count=0
        for uid in chosen:
            key=message_key(folder,validity,uid)
            if db.get('mail',key):
                last=uid;continue
            status,result=con.uid('fetch',str(uid),'(UID BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE MESSAGE-ID IN-REPLY-TO REFERENCES REPLY-TO)]<0.32769>)')
            if status!='OK':raise ConnectorError('Mailbox changed during sync. Run the sync again.')
            bridge.verify_uid(result,uid); raw=bridge.literal(result,32769)
            if len(raw)>=32769:raise ConnectorError('A message header exceeds the safe limit. Review it in Proton Mail.')
            parsed=BytesParser(policy=policy.default).parsebytes(raw)
            m={**bridge.headers(parsed),'references':bridge.display(str(parsed.get('References','')),12000),
               'reply_to':bridge.display(str(parsed.get('Reply-To','')),1000),
               'id':key,'folder':folder,'uid_validity':validity,'uid':uid,'synced_at':time.time(),
               'read_in_desk':folder=='Sent','body_loaded':False,'case_id':None,'assignment':None,'untrusted_email_content':True}
            db.put('mail',key,m); existing.append(m);count+=1;last=uid
            # Persist per-message: an interrupted sync resumes without skipping unread UIDs.
            db.put('sync',folder,{'folder':folder,'uid_validity':validity,'last_uid':last,'at':time.time(),'more':len(ids)>len(chosen)})
        for m in reconcile_threads(existing,outgoing):
            db.put('mail',m['id'],m)
            for a in db.all('artifact'):
                if a['message_id']==m['id'] and a['case_id']!=m['case_id']:
                    a['case_id']=m['case_id'];db.put('artifact',a['id'],a)
        cursor={'folder':folder,'uid_validity':validity,'last_uid':last,'at':time.time(),'more':len(ids)>len(chosen)}
        db.put('sync',folder,cursor)
        return {'folder':folder,'new_headers':count,'more':cursor['more'],'mailbox_epoch_changed':epoch_changed}

def read_raw(settings,message):
    with bridge.imap_connection(settings) as con:
        if bridge.select_readonly(con,message['folder'])!=message['uid_validity']:
            raise ConnectorError('Mailbox identity changed. Sync again and select a current message; old saved records remain private.')
        status,result=con.uid('fetch',str(message['uid']),'(UID RFC822.SIZE)')
        bridge.verify_uid(result,message['uid'])
        sizes=re.findall(rb'RFC822\.SIZE ([0-9]+)',b' '.join(x for x in result if isinstance(x,bytes)))
        if status!='OK' or len(sizes)!=1:raise ConnectorError('Message size is unavailable.')
        if int(sizes[0])>MAX_RAW:raise ConnectorError('This message exceeds 20 MiB. Download large records in Proton or the agency portal; record their public link in intake.')
        status,result=con.uid('fetch',str(message['uid']),f'(UID BODY.PEEK[]<0.{MAX_RAW+1}>)')
        if status!='OK':raise ConnectorError('Could not read the selected message.')
        bridge.verify_uid(result,message['uid']);raw=bridge.literal(result,MAX_RAW)
        if len(raw)!=int(sizes[0]):raise ConnectorError('Message was truncated or changed during capture.')
        parsed=BytesParser(policy=policy.default).parsebytes(raw)
        if bridge.headers(parsed)['message_id']!=message['message_id']:
            raise ConnectorError('Message identity no longer matches the selected header.')
        return raw

def capture(db,message,raw):
    parsed=BytesParser(policy=policy.default).parsebytes(raw)
    attachments=[]
    for index,part in enumerate(parsed.walk()):
        if part.get_content_disposition()!='attachment' and not part.get_filename():continue
        if len(attachments)>=30:raise ConnectorError('More than 30 attachments. Review this message directly in Proton.')
        content=part.get_payload(decode=True)
        if not isinstance(content,bytes):raise ConnectorError('Nested message attachments require manual inspection; no attachments were published.')
        name=bridge.display(part.get_filename() or 'unnamed',200).replace('\n',' ').replace('\r',' ').replace('\t',' ')
        attachments.append((index,name,part.get_content_type(),content))
    raw_id='raw-'+hashlib.sha256(message['id'].encode()).hexdigest()
    db.put('blob',raw_id,{'base64':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest()})
    captured=[]
    for index,name,ctype,content in attachments:
        key=hashlib.sha256(f"{message['id']}:{index}".encode()).hexdigest()
        digest=hashlib.sha256(content).hexdigest()
        db.put('blob',key,{'base64':base64.b64encode(content).decode(),'sha256':digest})
        artifact={'id':key,'message_id':message['id'],'case_id':message['case_id'],
            'filename':name,'content_type':ctype,'bytes':len(content),'sha256':digest,
            'captured_at':time.time(),'source':'Proton Bridge IMAP; original MIME attachment bytes',
            'received_date_header':message.get('date',''),'email_message_id':message['message_id'],
            'uid':message['uid'],'uid_validity':message['uid_validity'],'folder':message['folder'],
            'raw_message_sha256':hashlib.sha256(raw).hexdigest(),'quarantined':True,'executed':False}
        db.put('artifact',key,artifact);captured.append(artifact)
    message.update(raw_blob_id=raw_id,raw_sha256=hashlib.sha256(raw).hexdigest(),captured=True,artifact_ids=[a['id'] for a in captured])
    db.put('mail',message['id'],message)
    return captured
