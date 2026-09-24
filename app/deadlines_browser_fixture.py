"""Short-lived synthetic deadline HTTP fixture. No real mail settings or external actions."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import secrets
import tempfile
from service import Service, safe_dispatch
from storage import Database
from secure_store import Store, ConnectorError
from test_equipment import Protector
import deadlines
import server


class FixtureMail(Store):
    def __init__(self,root):
        super().__init__(root,Protector());self.drafts={}
    def get_draft(self,key):
        if key not in self.drafts: raise ConnectorError('Synthetic draft missing.')
        return self.drafts[key]


if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='relay-deadlines-browser-') as temporary:
        root=Path(temporary);mail=FixtureMail(root/'mail')
        service=Service(Database(root/'desk',Protector()),mail_store=mail)
        now=datetime(2026,9,20,18,tzinfo=timezone.utc)
        deadlines.utcnow=lambda:now
        ids={}
        for state in ('MI','PA','WI','TX','CA','SD'):
            c=service.dispatch('desk_create_equipment_request',{'state':state,'jurisdiction':'Synthetic records office','jurisdiction_level':'state'})['case']
            c=service.case(c['id']);c.update(subject='Synthetic request',body='Synthetic test only. No email will be sent.',routing_verified=True,routing_evidence='https://example.gov/records',recipient='records@example.test')
            if state!='SD':
                key='synthetic-'+state;mid=f'<synthetic-{state}@example.test>'
                mail.drafts[key]={'draft_id':key,'state':'accepted','message_id':mid,'receipt':{'message_id':mid,'accepted_at':'2026-09-09T21:50:00+00:00' if state=='MI' else '2026-09-14T00:33:00+00:00'},'in_reply_to':None,'to':['records@example.test'],'from':'synthetic@example.test','subject':'Synthetic request','body':'Synthetic test only.','digest':'a'*64}
                c.update(drafts=[key],stage='waiting')
            service.save(c);ids[state]=c['id']
        mid='INBOX:1:1'
        service.db.put('mail',mid,{'id':mid,'uid_validity':1,'uid':1,'folder':'INBOX','case_id':ids['TX'],'synced_at':now.timestamp(),'read_in_desk':False,'body_loaded':False,'subject':'Synthetic availability notice','from':'records@example.test','date':'Synthetic date','message_id':'<notice@example.test>'})
        service.db.put('sync','INBOX',{'id':'INBOX','folder':'INBOX','at':now.timestamp()-90000})
        allowed={'desk_get_state_guide','desk_list_cases','desk_get_case','desk_get_deadlines','desk_save_deadline_tracking','desk_get_equipment_campaign','desk_get_workflow'}
        def invoke(name,args):
            if name not in allowed:return {'ok':False,'error':'Synthetic fixture forbids mail sync, sends, fees and external operations.'}
            return safe_dispatch(name,args,service)
        server.invoke=invoke
        token=secrets.token_urlsafe(24);original_post=server.Handler.do_POST
        def fixture_post(handler):
            global now
            if handler.path!='/__fixture__/advance':return original_post(handler)
            if not handler.allowed(True) or handler.headers.get('X-Relay-Fixture-Token')!=token:
                return handler.json({'ok':False,'error':'Synthetic token required.'},403)
            now+=timedelta(days=2)
            return handler.json({'ok':True,'date':now.isoformat()})
        server.Handler.do_POST=fixture_post
        httpd=server.Server(('127.0.0.1',0),server.Handler);server.PORT=httpd.server_address[1];server.ORIGIN=f'http://127.0.0.1:{server.PORT}'
        print(json.dumps({'port':server.PORT,'synthetic':True,'ids':ids,'token':token}),flush=True)
        httpd.serve_forever()
