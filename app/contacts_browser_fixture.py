"""Ephemeral HTTP fixture for contact research; forbids every external action."""
from datetime import timedelta
from pathlib import Path
import json
import tempfile

from service import Service, safe_dispatch
from storage import Database
from secure_store import Store
from test_contacts import Protector
import contacts
import server


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='relay-contacts-browser-') as temporary:
        root=Path(temporary)
        service=Service(Database(root/'desk',Protector()),mail_store=Store(root/'mail',Protector()))
        service.dispatch('desk_save_workspace',{'revision':0,'starter_pack':'civicresultmaps'})
        for cid,days in [('county:26001',0),('county:26003',120)]:
            day=(contacts.today()-timedelta(days=days)).isoformat()
            value={'outcome':'verified','checked_on':day,'note':'Synthetic source evidence only.',
                   'contacts':[{'department':'Synthetic FOIA office','email':'records@example.test','route_type':'designated_custodian','source_url':'https://example.gov/foia'}],
                   'sources':[{'url':'https://example.gov/foia','title':'Synthetic official page','publisher':'Synthetic County','checked_on':day,'official':True,'evidence':'Synthetic published role and address.'}]}
            service.dispatch('desk_save_contact',{'county_id':cid,'role':'public_records','revision':0,'operation_key':'fixture-'+cid,'result':value})
        allowed=set(contacts.ARGUMENTS)|{'desk_get_state_guide','desk_list_cases','desk_get_case','desk_get_deadlines','desk_get_workflow'}
        def invoke(name,args):
            if name not in allowed:
                return {'ok':False,'error':'Synthetic fixture forbids mail, send, publication, fees and settings changes.'}
            return safe_dispatch(name,args,service)
        server.invoke=invoke
        httpd=server.Server(('127.0.0.1',0),server.Handler)
        server.PORT=httpd.server_address[1];server.ORIGIN=f'http://127.0.0.1:{server.PORT}'
        print(json.dumps({'port':server.PORT,'synthetic':True}),flush=True)
        httpd.serve_forever()
