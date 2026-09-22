"""Disposable local HTTP county status fixture; cannot send or sync mail."""
import json
from pathlib import Path
import tempfile

from service import Service, safe_dispatch
from storage import Database
from secure_store import Store
from test_contacts import Protector
from test_county_progress import seed_browser
import server

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='relay-county-map-') as temp:
        root=Path(temp);s=Service(Database(root/'desk',Protector()),mail_store=Store(root/'mail',Protector()))
        ids=seed_browser(s)
        allowed={'desk_list_counties','desk_list_cases','desk_get_case','desk_get_deadlines','desk_get_workflow','desk_mark_reviewed','desk_status'}
        def invoke(name,args):
            if name not in allowed:return {'ok':False,'error':'Synthetic fixture forbids mail, sends and all other external actions.'}
            return safe_dispatch(name,args,s)
        server.invoke=invoke
        httpd=server.Server(('127.0.0.1',0),server.Handler);server.PORT=httpd.server_address[1];server.ORIGIN=f'http://127.0.0.1:{server.PORT}'
        print(json.dumps({'port':server.PORT,'synthetic':True,'cases':ids}),flush=True)
        httpd.serve_forever()
