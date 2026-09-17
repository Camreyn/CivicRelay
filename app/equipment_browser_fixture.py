"""Owned, short-lived synthetic HTTP fixture. No real store or external operation."""
import json
from pathlib import Path
import tempfile
from service import Service, safe_dispatch
from storage import Database
from secure_store import Store
from test_equipment import Protector
import server


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='relay-equipment-browser-') as temporary:
        root = Path(temporary)
        service = Service(Database(root / 'desk', Protector()), mail_store=Store(root / 'mail', Protector()))
        service.dispatch('desk_save_workspace', {'revision':0,'starter_pack':'civicresultmaps'})
        for state in ['AZ','GA','MA','MI','NC','NV','PA','TX','WI']:
            service.dispatch('desk_create_equipment_request', {'state':state,'jurisdiction':'Synthetic state agency','jurisdiction_level':'state'})
        def invoke(name, args):
            if name not in {'desk_list_cases','desk_get_case','desk_get_workflow','desk_get_equipment_campaign',
                            'desk_save_case','desk_save_equipment_state','desk_save_equipment_progress'}:
                return {'ok':False,'error':'External/mail operations are disabled in this synthetic fixture.'}
            return safe_dispatch(name, args, service)
        server.invoke = invoke
        httpd = server.Server(('127.0.0.1',0),server.Handler)
        server.PORT = httpd.server_address[1]
        server.ORIGIN = f'http://127.0.0.1:{server.PORT}'
        print(json.dumps({'port':server.PORT,'synthetic':True}),flush=True)
        httpd.serve_forever()
