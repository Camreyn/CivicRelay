"""Real HTTP/service/storage with synthetic empty-label IMAP; no live accounts."""
import json
import secrets
import tempfile
from pathlib import Path
from unittest.mock import patch

import runtime
import bridge
import server
server.UPDATES = None  # Synthetic fixtures never read real update preferences.
from service import Service, safe_dispatch
from storage import Database
from secure_store import Store
from test_mail_privacy import FakeIMAP
from test_records_desk import TestProtector


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='relay-mail-sync-browser-') as temporary:
        root = Path(temporary)
        mail = Store(root / 'mail', TestProtector())
        mail.save_settings({'version': 2, 'email': 'relay@example.org', 'display_name': 'Synthetic Relay',
                            'profile_id': '00000000-0000-4000-8000-000000000001', 'password': 'synthetic-only',
                            'imap_port': 1143, 'smtp_port': 1025, 'imap_pin': '1' * 64, 'smtp_pin': '2' * 64,
                            'project_mailbox_confirmed': True, 'sending_enabled': False})
        service = Service(Database(root / 'desk', TestProtector()), mail_store=mail)
        imap = FakeIMAP()
        imap.boxes['Folders/CivicRelay'].clear()
        imap.boxes['Labels/CivicRelay Sent'].clear()
        original_uid = imap.uid
        fail_search = False

        def synthetic_uid(command, *args):
            if command == 'search' and fail_search:
                return 'NO', [b'synthetic search failure']
            return original_uid(command, *args)

        imap.uid = synthetic_uid
        allowed = {'desk_list_cases', 'desk_get_case', 'desk_get_state_guide', 'desk_get_deadlines',
                   'desk_get_workflow', 'desk_get_workspace', 'desk_list_templates', 'desk_list_campaigns', 'desk_list_destinations',
                   'desk_get_sources', 'desk_get_mail_scope', 'desk_preview_mail_scope',
                   'desk_apply_mail_scope', 'desk_sync_mail', 'desk_list_messages'}
        server.invoke = lambda name, args: safe_dispatch(name, args, service) if name in allowed else {
            'ok': False, 'error': 'Synthetic fixture forbids this action.'}
        token = secrets.token_urlsafe(24)
        original_post = server.Handler.do_POST

        def fixture_post(handler):
            global fail_search
            if handler.path != '/__fixture__/mail':
                return original_post(handler)
            if handler.headers.get('X-Relay-Fixture-Token') != token:
                return handler.json({'ok': False}, 403)
            size = int(handler.headers.get('Content-Length', '0'))
            if not 2 <= size <= 1000:
                return handler.json({'ok': False}, 400)
            action = json.loads(handler.rfile.read(size)).get('action')
            if action == 'arrival':
                imap.boxes['Folders/CivicRelay'][1] = imap.raw('first-scoped-reply')
            elif action == 'fail':
                imap.boxes['Folders/CivicRelay'][2] = imap.raw('second-scoped-reply')
                fail_search = True
            elif action == 'recover':
                fail_search = False
            elif action != 'inspect':
                return handler.json({'ok': False}, 400)
            return handler.json({'ok': True, 'searches': imap.searches, 'fetches': imap.fetches,
                                 'saved_headers': len(service.db.all('mail'))})

        server.Handler.do_POST = fixture_post
        with patch('bridge.imap_connection', return_value=imap), patch('bridge.smtp_connection', side_effect=AssertionError('SMTP forbidden')):
            httpd = server.Server(('127.0.0.1', 0), server.Handler)
            server.PORT = httpd.server_address[1]
            server.ORIGIN = f'http://127.0.0.1:{server.PORT}'
            print(json.dumps({'port': server.PORT, 'synthetic': True, 'token': token}), flush=True)
            httpd.serve_forever()
