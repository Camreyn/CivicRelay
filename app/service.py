"""Shared operations used by HTTP, CLI, and MCP. External writes always require desktop review."""
from __future__ import annotations
from datetime import datetime,timezone
from email.utils import parseaddr
import hashlib
import re
import time
import uuid
from runtime import load_catalog
from storage import Database
from secure_store import ConnectorError, SendPreflightError, Store, canonical
import bridge
import connector
import intake
import mailbox

ARGUMENTS={
 'desk_status':set(),'desk_list_cases':set(),'desk_get_case':{'case_id','before_message_id','artifact_offset'},
 'desk_get_workflow':set(),'desk_get_intake':{'issue_id'},
 'desk_list_messages':{'case_id','folder','before_message_id','limit','unreviewed_only'},
 'desk_save_case':{'case_id','revision','recipient','subject','body','routing_verified','routing_evidence','note','stage'},
 'desk_clone_case':{'case_id','label'},'desk_sync_mail':set(),
 'desk_read_message':{'message_id'},'desk_link_message':{'message_id','case_id'},
 'desk_mark_reviewed':{'message_id'},'desk_capture_attachments':{'message_id'},
 'desk_prepare_email':{'case_id','reply_message_id'},
 'desk_send_email':{'case_id','draft_id','expected_digest','confirmation'},
 'desk_prepare_intake':{'case_id','fields','artifact_ids'},
 'desk_publish_intake':{'issue_id','expected_digest','confirmation'},
 'desk_export_package':{'issue_id'},'desk_link_issue':{'issue_id','url'},
 'desk_record_portal':{'case_id','tracking_reference','submitted_date','note'},
}
READ_ONLY={'desk_status','desk_list_cases','desk_get_case','desk_get_workflow','desk_list_messages','desk_get_intake'}

STATUS_LABELS={'none':'No prepared request','routing':'Routing needed','draft':'Draft',
 'waiting':'Awaiting reply','new':'New reply','attention':'Action needed',
 'ready':'Ready for review','submitted':'Submitted','closed':'Closed'}

def require(value,maximum=1000,blank=False):
    if blank and value=='':return ''
    return connector.clean_text(value,maximum,multiline=True)

class Service:
    def __init__(self,db=None,catalog=None,mail_store=None):
        self.db=db or Database();self.catalog=catalog or load_catalog();self.mail_store=mail_store or Store()
    def settings(self):return connector.validate_settings(self.mail_store.settings())
    def case(self,key):
        if not isinstance(key,str):raise ConnectorError('Choose a request from the catalog.')
        stored=self.db.get('case',key)
        if stored:return stored
        base=next((x for x in self.catalog['cases'] if x['id']==key),None)
        if not base:raise ConnectorError('Request not found.')
        return {**base,'base':base,'catalog_sha256':self.catalog['sha256'],'revision':0,
                'routing_verified':False,'routing_evidence':'','stage':'draft','note':'','drafts':[], 'issues':[],
                'status':'routing','created_at':time.time()}
    def save(self,c):
        c['revision']+=1;c['updated_at']=time.time();self.db.put('case',c['id'],c)
    def mails(self,case_id=None):
        return sorted([m for m in self.db.all('mail') if case_id is None or m.get('case_id')==case_id],key=lambda m:(m['synced_at'],m['id']),reverse=True)
    def view_case(self,c,allmail=None):
        mails=[m for m in (allmail if allmail is not None else self.mails()) if m.get('case_id')==c['id']]
        unread=[m for m in mails if m['folder']=='INBOX' and not m.get('read_in_desk')]
        status='new' if unread else ('routing' if c['stage']=='draft' and not c['routing_verified'] else c['stage'])
        current={k:v for k,v in c.items() if k!='base'}
        base=next((x for x in self.catalog['cases'] if x['id']==c['base']['id']),None)
        current.update(status=status,unread_count=len(unread),mail_count=len(mails),catalog_drift=not base or base!=c['base'])
        return current
    def listing(self):
        stored=self.db.all('case');ids={x['id'] for x in stored}
        cases=stored+[self.case(x['id']) for x in self.catalog['cases'] if x['id'] not in ids]
        messages=self.mails()
        summaries=[{k:v for k,v in self.view_case(c,messages).items() if k not in ('body','requests')} for c in sorted(cases,key=lambda c:(c['state'],c['id']))]
        return {'catalog':{**self.catalog,'cases':summaries},
                'unassigned':[{k:v for k,v in m.items() if k not in ('body','attachments','raw_blob_id')} for m in messages if not m.get('case_id')][:200],
                'unassigned_total':sum(not m.get('case_id') for m in messages),'sync':self.db.all('sync'),
                'private_storage':str(self.db.root),'email':connector.PROJECT_EMAIL}
    def detail(self,key,before_message_id=None,artifact_offset=0):
        c=self.case(key)
        drafts=[]
        for draft_id in c['drafts'][-30:]:
            try:drafts.append(self.mail_store.get_draft(draft_id))
            except ConnectorError:drafts.append({'draft_id':draft_id,'state':'unavailable','warning':'Reconcile connector storage before sending.'})
        messages=self.mails(key)
        if before_message_id:
            index=next((i for i,m in enumerate(messages) if m['id']==before_message_id),None)
            if index is None:raise ConnectorError('Message cursor does not belong to this request.')
            messages=messages[index+1:]
        page=messages[:30]
        connector.integer(artifact_offset,0,20000)
        artifacts=[a for a in self.db.all('artifact') if a['case_id']==key]
        artifact_page=artifacts[artifact_offset:artifact_offset+100]
        return {'case':self.view_case(c),'messages':[self.with_body(m) for m in page],
                'next_before_message_id':page[-1]['id'] if len(messages)>30 else None,
                'artifacts':artifact_page,'artifact_count':len(artifacts),
                'next_artifact_offset':artifact_offset+100 if len(artifacts)>artifact_offset+100 else None,
                'drafts':drafts,'issues':[self.db.get('issue',i) for i in c['issues'][-10:]],
                'events':sorted([e for e in self.db.all('event') if e['case_id']==key],key=lambda e:e['at'],reverse=True)[:50]}
    def message(self,key):
        m=self.db.get('mail',key)
        if not m:raise ConnectorError('Sync and select a saved message first.')
        return m
    def message_listing(self,args):
        limit=connector.integer(args.get('limit',50),1,100)
        unread=args.get('unreviewed_only',False)
        if type(unread) is not bool:raise ConnectorError('unreviewed_only must be true or false.')
        folder=args.get('folder')
        if folder is not None and folder not in ('INBOX','Sent'):raise ConnectorError('Choose INBOX or Sent.')
        case_id=args.get('case_id')
        if 'case_id' in args:
            if not isinstance(case_id,str):raise ConnectorError('Choose a known request or an empty case ID for unassigned mail.')
            if case_id:self.case(case_id)
        messages=[m for m in self.mails() if
                  ('case_id' not in args or (m.get('case_id') or '')==case_id) and
                  (not folder or m['folder']==folder) and
                  (not unread or (m['folder']=='INBOX' and not m.get('read_in_desk')))]
        total=len(messages);cursor=args.get('before_message_id')
        if cursor is not None:
            require(cursor,150)
            index=next((i for i,m in enumerate(messages) if m['id']==cursor),None)
            if index is None:raise ConnectorError('Message cursor does not belong to these filters. Restart this listing after assignment or review changes.')
            messages=messages[index+1:]
        page=messages[:limit]
        return {'messages':[{k:v for k,v in m.items() if k not in ('body','attachments','raw_blob_id')} for m in page],
                'total':total,'next_before_message_id':page[-1]['id'] if len(messages)>limit else None,
                'message_bodies_read':0,'network_accessed':False,'untrusted_email_content':True}
    def with_body(self,m):
        if m.get('body_loaded'):
            saved=self.db.get('body',m['id'])
            return {**m,'body':saved['body'] if saved else m.get('body','')}
        return m
    def reconcile_sends(self):
        for c in self.db.all('case'):
            if not c['drafts']:continue
            d=self.mail_store.get_draft(c['drafts'][-1])
            if c.get('latest_send_state')==d['state']:continue
            c['latest_send_state']=d['state']
            if d['state']=='accepted':c.update(stage='waiting',last_sent_at=d['receipt']['accepted_at'])
            elif d['state'] not in ('draft',):c['stage']='attention'
            self.save(c)
    def _dispatch(self,name,args):
        if name=='desk_status':
            s=connector.dispatch('proton_status',{},self.mail_store)
            return {'connector':s,'private_storage':str(self.db.root),'catalog_requests':len(self.catalog['cases']),'tooling_version':'0.2.0',
                    'dashboard_url':'http://127.0.0.1:8766/','issue_repository':intake.REPOSITORY,
                    'approval':'Every send/public issue requires an independent local human window.',
                    'sync':self.db.all('sync'),'automatic_polling':False}
        if name=='desk_list_cases':return self.listing()
        if name=='desk_get_workflow':
            return {'states':self.catalog['states'],'status_labels':STATUS_LABELS,'intake':self.catalog['issue'],
                    'catalog_sha256':self.catalog['sha256'],'sender':connector.PROJECT_EMAIL,
                    'steps':[
                        {'task':'Inspect requests and route using current official sources','tools':['desk_list_cases','desk_get_case','desk_save_case','desk_clone_case']},
                        {'task':'Prepare exact correspondence; optional message ID preserves reply/follow-up chain','tools':['desk_prepare_email'],'sends':False},
                        {'task':'Send one explicitly reviewed email with desktop human approval','tools':['desk_send_email']},
                        {'task':'Check headers, review/assign mail and capture returned originals privately','tools':['desk_sync_mail','desk_list_messages','desk_read_message','desk_link_message','desk_mark_reviewed','desk_capture_attachments']},
                        {'task':'Prepare reviewed/redacted public intake; read back exact preview','tools':['desk_prepare_intake','desk_get_intake'],'publishes':False},
                        {'task':'Publish one reviewed issue or verify/link a manually submitted issue','tools':['desk_publish_intake','desk_link_issue']},
                        {'task':'Export originals for separate file review; no automatic upload','tools':['desk_export_package']},
                        {'task':'Record an existing agency portal receipt; does not submit a portal','tools':['desk_record_portal']}],
                    'limits':{'header_sync_per_folder':80,'send_attempts_per_day':10,'minimum_send_interval_seconds':60,
                              'body_preview_characters':20000,'automatic_polling':False},
                    'human_only':['Independent approval windows for send, public issue and unredacted export',
                                  'Agency-portal submission and reviewed private-attachment upload are not implemented by this connector'],
                    'production_import':False,'network_accessed':False}
        if name=='desk_list_messages':return self.message_listing(args)
        if name=='desk_get_intake':
            key=require(args.get('issue_id'),150);issue=self.db.get('issue',key)
            if not issue:raise ConnectorError('Saved intake preview not found.')
            self.case(issue['case_id'])
            return {'issue':issue,'network_accessed':False,'untrusted_content':True}
        if name=='desk_get_case':return self.detail(args.get('case_id'),args.get('before_message_id'),args.get('artifact_offset',0))
        if name=='desk_save_case':
            c=self.case(args.get('case_id'))
            if args.get('revision')!=c['revision']:raise ConnectorError('This request changed in another window. Reload it before saving.')
            recipient=require(args.get('recipient',''),254,True)
            if recipient:connector.address(recipient)
            c.update(recipient=recipient,subject=connector.clean_text(args.get('subject'),250),
                     body=require(args.get('body'),50000),routing_evidence=require(args.get('routing_evidence',''),1500,True),
                     note=require(args.get('note',''),4000,True))
            if type(args.get('routing_verified')) is not bool:raise ConnectorError('Confirm routing explicitly.')
            c['routing_verified']=args['routing_verified']
            if c['routing_verified'] and (not c['recipient'] or not c['routing_evidence']):raise ConnectorError('Verified routing needs an email address and an official contact source or verification note.')
            c['verified_catalog_sha256']=self.catalog['sha256'] if c['routing_verified'] else None
            c['routing_verified_at']=time.time() if c['routing_verified'] else None
            stage=args.get('stage',c['stage'])
            if stage not in ('draft','waiting','attention','ready','submitted','closed'):raise ConnectorError('Invalid case stage.')
            if stage in ('waiting','submitted') and stage!=c['stage']:raise ConnectorError('Waiting/submitted require a send, portal receipt, or verified GitHub issue.')
            c['stage']=stage;self.save(c);self.db.event(c['id'],'request_saved',{'revision':c['revision']})
            return {'case':self.view_case(c),'messages_sent':0}
        if name=='desk_clone_case':
            source=self.case(args.get('case_id'))
            base=next((x for x in self.catalog['cases'] if x['id']==source['base']['id']),None)
            if not base:raise ConnectorError('The source template is no longer in the current catalog.')
            label=connector.clean_text(args.get('label'),120)
            c={**base,'base':base,'catalog_sha256':self.catalog['sha256'],'id':base['id']+'-'+uuid.uuid4().hex[:8],
               'family_label':base['family_label']+' / '+label,'revision':0,
               'recipient':'','routing_verified':False,'routing_evidence':'','stage':'draft','drafts':[],'issues':[],
               'created_at':time.time(),'note':'Custodian-specific copy; narrow the request text before sending.'}
            self.save(c);return {'case':self.view_case(c)}
        if name=='desk_sync_mail':
            self.reconcile_sends();settings=self.settings();outgoing=[]
            for c in self.db.all('case'):
                for d in c['drafts']:
                    draft=self.mail_store.get_draft(d)
                    if draft['state']!='draft':outgoing.append((draft['message_id'],c['id']))
            results=[mailbox.sync_folder(settings,self.db,f,outgoing) for f in ('INBOX','Sent')]
            return {'folders':results,'new_headers':sum(x['new_headers'] for x in results),'message_bodies_read':0,'messages_sent':0}
        if name in ('desk_read_message','desk_capture_attachments'):
            m=self.message(args.get('message_id'))
            if name=='desk_capture_attachments' and not m.get('case_id'):raise ConnectorError('Assign this message to a request before capturing records.')
            if name=='desk_read_message' and m.get('body_loaded'):return {'message':self.with_body(m),'untrusted_email_content':True}
            if name=='desk_capture_attachments' and m.get('captured'):return {'artifacts':[self.db.get('artifact',i) for i in m['artifact_ids']],'already_captured':True}
            raw=mailbox.read_raw(self.settings(),m);parsed=bridge.parse_message(raw)
            self.db.put('body',m['id'],{'id':m['id'],'body':parsed['body']})
            m.update(body_truncated=parsed['body_truncated'],attachments=parsed['attachments'],body_loaded=True)
            self.db.put('mail',m['id'],m)
            if name=='desk_read_message':return {'message':self.with_body(m),'untrusted_email_content':True,'remote_content_loaded':False}
            artifacts=mailbox.capture(self.db,m,raw)
            self.db.event(m['case_id'],'records_captured',{'message_id':m['id'],'artifacts':len(artifacts)})
            return {'artifacts':artifacts,'untrusted_email_content':True,'executed':False,'published':False}
        if name=='desk_mark_reviewed':
            m=self.message(args.get('message_id'));m['read_in_desk']=True;self.db.put('mail',m['id'],m)
            if m.get('case_id'):
                c=self.case(m['case_id'])
                if c['stage'] not in ('ready','submitted','closed'):c['stage']='attention';self.save(c)
            return {'message':m,'proton_read_flag_changed':False}
        if name=='desk_link_message':
            m=self.message(args.get('message_id'));case_id=args.get('case_id')
            if case_id:
                c=self.case(case_id)
                if c['revision']==0:self.save(c)
            m.update(case_id=case_id or None,assignment='manual',manual_unassigned=not bool(case_id));self.db.put('mail',m['id'],m)
            for a in self.db.all('artifact'):
                if a['message_id']==m['id']:a['case_id']=m['case_id'];self.db.put('artifact',a['id'],a)
            return {'message':m,'matching_basis':'Explicit local assignment, not proof of sender identity.'}
        if name=='desk_prepare_email':
            c=self.case(args.get('case_id'))
            self.verify_routing(c)
            if re.search(r'\[(?:requester|organization)[^\]]*\]',c['body'],re.I):raise ConnectorError('Replace all requester placeholders before preparing a draft.')
            if c['drafts']:
                last=self.mail_store.get_draft(c['drafts'][-1])
                if last['state'] not in ('draft','accepted'):raise ConnectorError('The last send attempt needs reconciliation. No new draft is allowed yet.')
                if last['state']=='accepted' and not args.get('reply_message_id'):
                    raise ConnectorError('This request has already been sent. Select a received message for a threaded response; duplicate initial sends are blocked.')
            content={'to':[c['recipient']],'subject':c['subject'],'body':c['body']}
            reply=args.get('reply_message_id')
            if reply:
                m=self.message(reply)
                if m.get('case_id')!=c['id'] or m['folder'] not in ('INBOX','Sent'):raise ConnectorError('Reply target must be an incoming or Sent message assigned to this request.')
                connector.message_id(m['message_id'])
                refs=mailbox.identities(m.get('references',''))+[m['message_id']]
                content.update(in_reply_to=m['message_id'],references=list(dict.fromkeys(refs))[-20:])
            draft=connector.dispatch('proton_prepare_draft',content,self.mail_store)['draft']
            # Same content is deduplicated by Proton; a draft cannot belong to two cases.
            for other in self.db.all('case'):
                if other['id']!=c['id'] and draft['draft_id'] in other['drafts']:raise ConnectorError('This exact draft already belongs to another tracked request.')
            if draft['draft_id'] not in c['drafts']:c['drafts'].append(draft['draft_id'])
            if c['revision']==0 or c.get('last_prepared')!=draft['draft_id']:
                c['last_prepared']=draft['draft_id'];self.save(c)
            return {'draft':draft,'messages_sent':0,'case_id':c['id']}
        if name=='desk_send_email':
            try:
                if args.get('confirmation')!='SEND_REVIEWED_EMAIL':raise ConnectorError('Explicit send confirmation is required.')
                c=self.case(args.get('case_id'));draft_id=args.get('draft_id')
                if draft_id not in c['drafts'] or draft_id!=c['drafts'][-1]:raise ConnectorError('Select the latest reviewed draft for this request.')
                d=self.mail_store.get_draft(draft_id)
                self.verify_routing(c)
                if d['body']!=c['body'] or d['subject']!=c['subject'] or d['to']!=[c['recipient']] or not c['routing_verified']:
                    raise ConnectorError('Request content/routing changed after preparation. Prepare and review a fresh immutable draft.')
            except ConnectorError as exc:
                # Only these read-only validations are known to precede approval.
                # Never attach this marker to a transport or receipt failure.
                raise SendPreflightError(str(exc)) from exc
            result=connector.dispatch('proton_send_draft',{'draft_id':draft_id,'expected_digest':args.get('expected_digest'),'confirmation':'SEND_PROTON_DRAFT'},self.mail_store)
            self.reconcile_sends();self.db.event(c['id'],'send_result',{'draft_id':draft_id,'state':result.get('state')})
            return result
        if name=='desk_record_portal':
            c=self.case(args.get('case_id'));reference=require(args.get('tracking_reference'),500)
            date=require(args.get('submitted_date'),10)
            try:datetime.strptime(date,'%Y-%m-%d')
            except ValueError:raise ConnectorError('Use YYYY-MM-DD for the submission date.') from None
            receipt={'reference':reference,'date':date,'note':require(args.get('note',''),2000,True),'user_attested':True}
            if c.get('portal_receipt')==receipt:return {'case':self.view_case(c),'portal_submitted_by_tool':False,'already_recorded':True}
            if c.get('portal_receipt') or c['stage'] in ('submitted','closed'):raise ConnectorError('An existing portal receipt/completed case cannot be overwritten here. Record corrections in private notes or create a new custodian case.')
            c.update(stage='waiting',portal_receipt=receipt)
            self.save(c);self.db.event(c['id'],'portal_submission_recorded',c['portal_receipt']);return {'case':self.view_case(c),'portal_submitted_by_tool':False}
        if name=='desk_prepare_intake':
            c=self.case(args.get('case_id'));issue=intake.prepare(self.db,self.catalog,c,args.get('fields'),args.get('artifact_ids',[]))
            if issue['id'] not in c['issues']:c['issues'].append(issue['id'])
            c['stage']='submitted' if issue['state']=='published' else 'ready';self.save(c)
            return {'issue':issue,'published':issue['state']=='published'}
        if name=='desk_publish_intake':
            if args.get('confirmation')!='PUBLISH_REVIEWED_RECORDS_ISSUE':raise ConnectorError('Explicit public issue confirmation is required.')
            result=intake.publish(self.db,self.catalog,args.get('issue_id'),args.get('expected_digest'))
            c=self.case(result['issue']['case_id'])
            if result['issue']['id'] not in c['issues']:c['issues'].append(result['issue']['id']);self.save(c)
            if result['state']=='published':c['stage']='submitted';self.save(c)
            elif result['state']=='uncertain':c['stage']='attention';self.save(c)
            self.db.event(c['id'],'issue_result',{'issue_id':result['issue']['id'],'state':result['state']})
            return result
        if name=='desk_link_issue':
            issue=intake.reconcile(self.db,args.get('issue_id'),args.get('url'));c=self.case(issue['case_id']);c['stage']='submitted'
            if issue['id'] not in c['issues']:c['issues'].append(issue['id'])
            self.save(c)
            return {'issue':issue}
        if name=='desk_export_package':
            issue=self.db.get('issue',args.get('issue_id'))
            if not issue:raise ConnectorError('Prepare an intake preview first.')
            return intake.export_package(self.db,issue)
        raise ConnectorError('Unknown records operation.')
    def dispatch(self,name,args):
        if name not in ARGUMENTS or not isinstance(args,dict) or set(args)-ARGUMENTS[name]:raise ConnectorError('Unknown operation or unexpected arguments.')
        if name in READ_ONLY:return self._dispatch(name,args)
        with self.db.operation():return self._dispatch(name,args)
    def verify_routing(self,c):
        if not c['routing_verified']:raise ConnectorError('Verify the custodian and recipient before preparing or sending.')
        if c.get('verified_catalog_sha256')!=self.catalog['sha256'] or time.time()-c.get('routing_verified_at',0)>7*86400:
            raise ConnectorError('Routing review is stale or the public catalog changed. Review current official routing and save verification again.')
        if c['base']!=next((x for x in self.catalog['cases'] if x['id']==c['base']['id']),None):
            raise ConnectorError('This tracked template changed in the public catalog. Review its current text and recreate a custodian copy before sending; existing correspondence is preserved.')

def safe_dispatch(name,args,service=None):
    try:return {'ok':True,'result':(service or Service()).dispatch(name,args)}
    except SendPreflightError as exc:return {'ok':False,'error':str(exc),'send_not_started':True}
    except ConnectorError as exc:return {'ok':False,'error':str(exc)}
    except Exception:return {'ok':False,'error':'The local operation could not complete. Check Proton Bridge and the desktop session. Private exception details were not logged; do not retry external writes without inspecting their receipt.'}
