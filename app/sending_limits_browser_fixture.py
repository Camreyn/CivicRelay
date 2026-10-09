"""Real HTTP/service with fictional send history; all mail transports forbidden."""
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
import runtime
import connector
import server
class FixtureUpdates:
    def status(self):
        return {'installed_version':'0.9.0','automatic_checks':False,'last_checked_at':None,
            'latest':None,'approved':None,'update_available':False}
    def operation(self, action, args):
        if action != 'status' or args: raise AssertionError('Synthetic fixture forbids update actions.')
        return self.status()
server.UPDATES = FixtureUpdates()  # Never read real preferences or public releases.
from service import Service, safe_dispatch
from storage import Database
from secure_store import Store
from test_records_desk import TestProtector


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='relay-limits-browser-') as temporary:
        root = Path(temporary)
        mail = Store(root / 'mail', TestProtector())
        mail.save_settings({'version':2, 'email':'relay@example.org', 'display_name':'Synthetic Relay',
            'profile_id':'00000000-0000-4000-8000-000000000001', 'password':'synthetic-only',
            'imap_port':1143, 'smtp_port':1025, 'imap_pin':'1'*64, 'smtp_pin':'2'*64,
            'project_mailbox_confirmed':True, 'sending_enabled':False})
        now = time.time()
        for index in range(10):
            draft = connector.dispatch('proton_prepare_draft', {'to':['records@example.gov'],
                'subject':'Fictional attempt', 'body':f'Synthetic local-only draft {index}'}, mail)['draft']
            mail.claim_send(draft['draft_id'], draft['digest'], now - 1000 + index * 60)
            mail.finish_send(draft['draft_id'], 'uncertain', {'synthetic':True})
        service = Service(Database(root / 'desk', TestProtector()), mail_store=mail)
        allowed = {'desk_list_cases', 'desk_get_case', 'desk_get_state_guide', 'desk_get_deadlines',
            'desk_get_workflow', 'desk_get_workspace', 'desk_list_templates', 'desk_list_campaigns',
            'desk_list_destinations', 'desk_get_sources', 'desk_get_mail_scope', 'desk_status',
            'desk_get_send_limits', 'desk_save_send_limits'}
        server.invoke = lambda name, args: safe_dispatch(name, args, service) if name in allowed else {
            'ok':False, 'error':'Synthetic fixture forbids this action.'}
        with patch('bridge.imap_connection', side_effect=AssertionError('IMAP forbidden')), patch('bridge.smtp_connection', side_effect=AssertionError('SMTP forbidden')):
            httpd = server.Server(('127.0.0.1', 0), server.Handler)
            server.PORT = httpd.server_address[1]
            server.ORIGIN = f'http://127.0.0.1:{server.PORT}'
            print(json.dumps({'port':server.PORT, 'synthetic':True}), flush=True)
            httpd.serve_forever()
