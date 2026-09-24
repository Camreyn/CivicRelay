"""Disposable sources/guide HTTP fixture: synthetic contacts, zero external IO."""
from pathlib import Path
import json
import tempfile
import runtime
from service import Service, safe_dispatch
from storage import Database
from secure_store import Store
from test_equipment import Protector
from test_public_sources import sample
import public_sources
import server

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='relay-sources-browser-') as temporary:
        root=Path(temporary)
        s=Service(Database(root/'desk',Protector()),mail_store=Store(root/'mail',Protector()))
        s.dispatch('desk_save_workspace',{'revision':0,'starter_pack':'civicresultmaps'})
        s.dispatch('desk_import_source',{'source_id':public_sources.SOURCE_ID,'checked_on':'2026-09-23','text':sample()})
        def blocked():raise public_sources.SourceError('source_blocked','Synthetic official-source blocking page. Previous contacts were preserved.',['No real network request occurred.'])
        public_sources.fetch_directory=blocked
        allowed=set(public_sources.ARGUMENTS)|{'desk_get_state_guide','desk_list_cases','desk_get_case','desk_get_deadlines','desk_get_workflow'}
        def invoke(name,args):
            if name not in allowed:return {'ok':False,'error':'Synthetic fixture forbids mailbox and external actions.'}
            return safe_dispatch(name,args,s)
        server.invoke=invoke
        httpd=server.Server(('127.0.0.1',0),server.Handler)
        server.PORT=httpd.server_address[1];server.ORIGIN=f'http://127.0.0.1:{server.PORT}'
        print(json.dumps({'port':server.PORT,'synthetic':True}),flush=True)
        httpd.serve_forever()
