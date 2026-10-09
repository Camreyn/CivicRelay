"""Actual dashboard/update endpoint with fictional stores and mocked public releases."""
import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch
import server
import updates
from service import Service, safe_dispatch
from storage import Database
from secure_store import Store
from test_records_desk import TestProtector


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='civicrelay-updates-browser-') as temporary:
        root = Path(temporary)
        code = root / 'old'; code.mkdir()
        (code / 'package.json').write_text(json.dumps({'name':'civic-relay','version':'0.9.0'}))
        server.UPDATES = updates.Updates(code)
        files = {name:b'fictional public source' for name in updates.REQUIRED}
        for name in ('package.json','package-lock.json'):
            files[name] = json.dumps({'name':'civic-relay','version':'0.10.0'}).encode()
        manifest = {'schema_version':1,'version':'0.10.0','commit':'c'*40,
            'files':{name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()}}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:
            for name,content in {**files,updates.MANIFEST:json.dumps(manifest).encode()}.items():
                item=zipfile.ZipInfo(name);item.create_system=3;item.external_attr=0o100644<<16
                archive.writestr(item,content)
        raw = buffer.getvalue()
        release = {'version':'0.10.0','tag':'v0.10.0','commit':'c'*40,
            'release_url':'https://github.com/Camreyn/CivicRelay/releases/tag/v0.10.0',
            'notes':'Fictional release notes <img src=x onerror=window.injected=true>',
            'package':{'url':'https://github.com/Camreyn/CivicRelay/releases/download/v0.10.0/civicrelay-v0.10.0.zip','size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}}
        service = Service(Database(root/'records',TestProtector()),mail_store=Store(root/'mail',TestProtector()))
        allowed = {'desk_list_cases','desk_get_workspace','desk_list_templates','desk_list_campaigns',
            'desk_list_destinations','desk_get_sources','desk_get_state_guide','desk_get_deadlines','desk_get_mail_scope'}
        server.invoke = lambda name,args: safe_dispatch(name,args,service) if name in allowed else {'ok':False,'error':'Synthetic fixture forbids this operation.'}
        with patch.object(updates,'latest_release',return_value=release), patch.object(updates,'get_bytes',return_value=raw), patch('bridge.imap_connection',side_effect=AssertionError('IMAP forbidden')), patch('bridge.smtp_connection',side_effect=AssertionError('SMTP forbidden')):
            with server.Server(('127.0.0.1',0),server.Handler) as httpd:
                server.PORT=httpd.server_address[1];server.ORIGIN=f'http://127.0.0.1:{server.PORT}'
                print(json.dumps({'port':server.PORT,'synthetic':True}),flush=True)
                httpd.serve_forever()
