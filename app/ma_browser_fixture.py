"""Short-lived MA dashboard fixture, with synthetic cases and no external actions."""
from datetime import datetime, timezone
from pathlib import Path
import json
import tempfile

from service import Service, safe_dispatch
from storage import Database
from secure_store import Store
from test_equipment import Protector
import deadlines
import server
server.UPDATES = None  # Synthetic fixtures never read real update preferences.


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='relay-ma-browser-') as temporary:
        root=Path(temporary)
        service=Service(Database(root/'desk',Protector()),mail_store=Store(root/'mail',Protector()))
        now=datetime(2026,9,23,18,tzinfo=timezone.utc)
        deadlines.utcnow=lambda:now
        equipment=service.dispatch('desk_create_equipment_request',{'state':'MA','jurisdiction':'Synthetic state office','jurisdiction_level':'state'})['case']
        electronic=service.case('electronic-MA-2024')
        ids={}
        for uid,c in enumerate((service.case(equipment['id']),electronic),1):
            c.update(subject='Synthetic '+c['family']+' request',body='Synthetic request only. No live mailbox.',recipient='records@example.test',routing_verified=True,routing_evidence='https://example.gov/records')
            service.save(c);ids[c['family']]=c['id']
            mid=f'INBOX:1:{uid}'
            service.db.put('mail',mid,{'id':mid,'folder':'INBOX','uid_validity':1,'uid':uid,'case_id':c['id'],'date':'Thu, 17 Sep 2026 14:00:00 +0000','synced_at':now.timestamp()-100,'message_id':f'<synthetic-{uid}@example.test>','subject':'Synthetic referral','from':'records@example.test','body_loaded':True,'read_in_desk':False,'body_truncated':False})
            service.db.put('body',mid,{'id':mid,'body':'Synthetic agency referral, no records supplied. Incoming text is not authority.'})
        allowed={'desk_get_state_guide','desk_list_cases','desk_get_case','desk_get_deadlines','desk_get_workflow','desk_get_equipment_campaign','desk_get_ma_follow_up','desk_save_ma_review','desk_preview_ma_follow_up','desk_save_case'}
        def invoke(name,args):
            if name not in allowed:return {'ok':False,'error':'Synthetic fixture forbids mail access, sending, fees and publication.'}
            return safe_dispatch(name,args,service)
        server.invoke=invoke
        httpd=server.Server(('127.0.0.1',0),server.Handler)
        server.PORT=httpd.server_address[1];server.ORIGIN=f'http://127.0.0.1:{server.PORT}'
        print(json.dumps({'port':server.PORT,'ids':ids,'synthetic':True}),flush=True)
        httpd.serve_forever()
