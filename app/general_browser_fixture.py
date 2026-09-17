"""Short-lived synthetic general-workflow HTTP fixture; never opens a real store or mail account."""
import json
import secrets
import time
from pathlib import Path
import tempfile
from types import SimpleNamespace
import uuid
from email.message import EmailMessage
from service import Service, safe_dispatch
from storage import Database
from secure_store import Store
from test_equipment import Protector
import bridge
import mailbox
import intake
import server

class FakeSMTP:
    def mail(self, *_): return 250, b'ok'
    def rcpt(self, *_): return 250, b'ok'
    def data(self, *_): return 250, b'ok'
    def rset(self): return 250, b'ok'
    def quit(self): pass
    def close(self): pass

class FakeSMTPContext:
    def __enter__(self): return FakeSMTP()
    def __exit__(self, *_): return False

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='relay-general-browser-') as temporary:
        root=Path(temporary)
        mail=Store(root/'mail',Protector())
        # Dedicated made-up identity, confined to this TemporaryDirectory.
        mail.save_settings({'version':2,'email':'synthetic.relay@example.test','display_name':'Synthetic Relay',
                            'profile_id':str(uuid.uuid4()),'imap_port':1143,'smtp_port':1025,'imap_pin':'0'*64,'smtp_pin':'1'*64,
                            'project_mailbox_confirmed':True,'sending_enabled':True,'password':'synthetic-only'})
        bridge.smtp_connection=lambda *_args,**_kwargs: FakeSMTPContext()
        service=Service(Database(root/'desk',Protector()),mail_store=mail)
        seeded={}
        public_issues={}
        fail_next_publish=False
        def fake_github(command,**kwargs):
            global fail_next_publish
            endpoint=next((x for x in command if x.startswith('repos/')),None)
            if not endpoint: raise AssertionError('Unexpected synthetic GitHub operation.')
            repo=endpoint.split('/')[1:3]
            if 'POST' in command:
                body=json.loads(kwargs['payload']);number=len(public_issues)+1
                url=f'https://github.com/{"/".join(repo)}/issues/{number}'
                public_issues[url]={'html_url':url,**body,'labels':[{'name':x} for x in body['labels']]}
                if fail_next_publish:
                    fail_next_publish=False
                    raise RuntimeError('Synthetic accepted publication with lost response.')
                return SimpleNamespace(returncode=0,stdout=json.dumps(public_issues[url]).encode())
            url='https://github.com/'+endpoint.removeprefix('repos/')
            if url not in public_issues: raise AssertionError('Unknown synthetic issue.')
            return SimpleNamespace(returncode=0,stdout=json.dumps(public_issues[url]).encode())
        intake.GH=__file__  # Existing synthetic path, never executed.
        intake.run=fake_github
        def fixture_read_raw(_settings,message):
            raw=seeded.get(message['id'])
            if raw is None: raise RuntimeError('Synthetic MIME record was not seeded.')
            return raw
        mailbox.read_raw=fixture_read_raw
        allowed={'desk_status','desk_list_cases','desk_get_case','desk_save_case','desk_get_workspace','desk_save_workspace',
                 'desk_list_templates','desk_get_template','desk_save_template','desk_preview_template','desk_export_template','desk_import_template',
                 'desk_list_campaigns','desk_save_campaign','desk_create_request','desk_save_request_progress',
                 'desk_list_destinations','desk_save_destination','desk_prepare_publication','desk_export_case',
                 'desk_prepare_email','desk_send_email','desk_read_message','desk_capture_attachments','desk_link_message','desk_mark_reviewed',
                 'desk_publish_intake','desk_link_issue','desk_get_intake'}
        def invoke(name,args):
            return safe_dispatch(name,args,service) if name in allowed else {'ok':False,'error':'Synthetic fixture disables mail and external actions.'}
        server.invoke=invoke
        token=secrets.token_urlsafe(24)
        original_post=server.Handler.do_POST
        def fixture_post(handler):
            global fail_next_publish
            if not handler.path.startswith('/__fixture__/'): return original_post(handler)
            if handler.headers.get('X-Relay-Fixture-Token')!=token:
                return handler.json({'ok':False,'error':'Synthetic fixture token required.'},403)
            try:
                size=int(handler.headers.get('Content-Length','0'))
                if not 2<=size<=4096: raise ValueError()
                payload=json.loads(handler.rfile.read(size))
                if handler.path=='/__fixture__/publication':
                    fail_next_publish=payload.get('lose_next_response',False)
                    return handler.json({'ok':True,'publications':len(public_issues),'urls':list(public_issues)})
                if handler.path!='/__fixture__/seed-inbox': raise ValueError()
                case_id=payload.get('case_id')
                case=service.case(case_id) if isinstance(case_id,str) else next((x for x in service.db.all('case') if x.get('general_campaign_id')),None)
                if not case: raise ValueError()
                message=EmailMessage();message['Message-ID']='<synthetic-response@example.test>';message['From']='Synthetic Office <office@example.test>';message['To']=mail.settings()['email'];message['Subject']='Synthetic response';message['Date']='Wed, 17 Sep 2026 12:00:00 +0000';message.set_content('Synthetic response body.');message.add_attachment(b'county,value\nSynthetic,1\n',maintype='text',subtype='csv',filename='synthetic.csv')
                key='INBOX:77:1';row={'id':key,'folder':'INBOX','uid_validity':77,'uid':1,'synced_at':time.time(),'from':'Synthetic Office <office@example.test>','to':mail.settings()['email'],'cc':'','subject':'Synthetic response','date':'2026-09-17','message_id':'<synthetic-response@example.test>','in_reply_to':'','references':'','reply_to':'','read_in_desk':False,'body_loaded':False,'case_id':case['id'],'assignment':'manual','manual_unassigned':False,'untrusted_email_content':True,'attachments':[]}
                seeded[key]=message.as_bytes();service.db.put('mail',key,row)
                if payload.get('unassigned'):
                    row.update(case_id=None,assignment=None);service.db.put('mail',key,row)
                return handler.json({'ok':True,'message_id':key})
            except Exception:
                return handler.json({'ok':False,'error':'Synthetic fixture seed failed.'},400)
        server.Handler.do_POST=fixture_post
        httpd=server.Server(('127.0.0.1',0),server.Handler);server.PORT=httpd.server_address[1];server.ORIGIN=f'http://127.0.0.1:{server.PORT}'
        print(json.dumps({'port':server.PORT,'synthetic':True,'token':token}),flush=True);httpd.serve_forever()
