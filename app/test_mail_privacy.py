"""Populated personal-mailbox regression fixtures. No live IMAP, secrets or sends."""
from email.message import EmailMessage
from pathlib import Path
import copy
import tempfile
import time
import unittest
from unittest.mock import patch

import runtime
import bridge
import connector
import mail_scope
import mailbox
from mail_privacy import protected_ids
from secure_store import Store, ConnectorError
from service import Service
from storage import Database
from test_records_desk import TestProtector, mail


class FakeIMAP:
    def __init__(self):
        self.boxes = {'INBOX': {1: self.raw('personal-one'), 2: self.raw('personal-two')},
                      'Sent': {1: self.raw('private-outgoing')},
                      'Folders/CivicRelay': {1: self.raw('old-records')},
                      'Labels/CivicRelay Sent': {1: self.raw('old-records-sent')}}
        self.epochs = {key: 42 for key in self.boxes}
        self.selected = None
        self.fetches = []
        self.selections = []
        self.missing_next = False
    @staticmethod
    def raw(label, reply=None):
        m = EmailMessage(); m['From'] = 'records@example.gov'; m['To'] = 'relay@example.org'
        m['Message-ID'] = f'<{label}@example.gov>'; m['Subject'] = label
        if reply: m['In-Reply-To'] = reply
        m.set_content('Synthetic body only.')
        return m.as_bytes()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def select(self, folder, readonly):
        assert readonly is True
        self.selected = folder.strip('"'); self.selections.append(self.selected)
        return ('OK', [b'1']) if self.selected in self.boxes else ('NO', [])
    def response(self, key):
        if key == 'UIDVALIDITY': value = self.epochs[self.selected]
        elif key == 'UIDNEXT':
            if self.missing_next: return ('UIDNEXT', [None])
            value = max(self.boxes[self.selected], default=0) + 1
        elif key == 'EXISTS': value = len(self.boxes[self.selected])
        else: raise AssertionError(key)
        return key, [str(value).encode()]
    def uid(self, command, *args):
        if command == 'search':
            assert args[1] == 'UID', args
            lo, hi = args[2].split(':'); hi = max(self.boxes[self.selected], default=0) if hi == '*' else int(hi)
            # Real IMAP ranges can return the last UID for N:* even when N is
            # above it. The caller must enforce the lower bound independently.
            lo, hi = sorted((int(lo), hi))
            return 'OK', [b' '.join(str(x).encode() for x in self.boxes[self.selected] if lo <= x <= hi)]
        assert command == 'fetch', command
        uid = int(args[0]); self.fetches.append((self.selected, uid, args[1])); raw = self.boxes[self.selected][uid]
        if args[1] == '(UID RFC822.SIZE)': return 'OK', [f'1 (UID {uid} RFC822.SIZE {len(raw)})'.encode()]
        return 'OK', [(f'1 (UID {uid} BODY[] {{{len(raw)}}})'.encode(), raw)]


class MailPrivacyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog = runtime.load_catalog()
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='civicrelay-privacy-synthetic-')
        root = Path(self.temp.name)
        self.db = Database(root / 'desk', TestProtector()); self.store = Store(root / 'mail', TestProtector())
        self.settings = {'version': 2, 'email': 'relay@example.org', 'display_name': 'Synthetic Relay',
            'profile_id': '00000000-0000-4000-8000-000000000001', 'password': 'synthetic-only',
            'imap_port': 1143, 'smtp_port': 1025, 'imap_pin': '1' * 64, 'smtp_pin': '2' * 64,
            'project_mailbox_confirmed': True, 'sending_enabled': False}
        self.store.save_settings(self.settings)
        self.service = Service(self.db, copy.deepcopy(self.catalog), self.store)
        self.imap = FakeIMAP()
        self.patch = patch('bridge.imap_connection', return_value=self.imap); self.patch.start()
        self.smtp = patch('bridge.smtp_connection', side_effect=AssertionError('SMTP forbidden')); self.smtp.start()
    def tearDown(self):
        self.patch.stop(); self.smtp.stop(); self.temp.cleanup()
    def call(self, name, **args): return self.service.dispatch(name, args)
    def configure(self, mode='folders', history=False, **kwargs):
        args = {'mode': mode, 'import_history': history}
        if mode == 'folders': args['incoming_folder'] = 'Folders/CivicRelay'
        args.update(kwargs)
        p = self.call('desk_preview_mail_scope', **args)
        return self.call('desk_apply_mail_scope', preview_id=p['preview_id'], expected_digest=p['digest'])
    def test_missing_scope_blocks_both_connectors_without_connection_or_write(self):
        for name, args in [('desk_sync_mail', {}), ('proton_list_messages', {}), ('proton_read_message', {'uid': 1, 'uid_validity': 42})]:
            with self.assertRaisesRegex(ConnectorError, 'scope'):
                if name.startswith('desk_'): self.call(name, **args)
                else: connector.dispatch(name, args, self.store)
        self.assertEqual(self.imap.selections, []); self.assertEqual(self.db.all('mail'), [])
    def test_new_only_skips_history_including_imap_reversed_star_range(self):
        self.configure('dedicated')
        self.assertEqual(self.imap.fetches, [])
        self.assertEqual(self.call('desk_sync_mail')['new_headers'], 0)
        self.assertEqual(connector.dispatch('proton_list_messages', {}, self.store)['messages'], [])
        with self.assertRaisesRegex(ConnectorError, 'predates'):
            connector.dispatch('proton_read_message', {'uid': 1, 'uid_validity': 42, 'mail_scope_id':mail_scope.read(self.store)['id']}, self.store)
        self.assertEqual(self.imap.fetches, [])
        self.imap.boxes['INBOX'][3] = self.imap.raw('new-records')
        self.assertEqual(self.call('desk_sync_mail')['new_headers'], 1)
        self.assertEqual([m['subject'] for m in self.call('desk_list_messages')['messages']], ['new-records'])
        self.assertEqual(self.call('desk_sync_mail')['new_headers'], 0)
    def test_arrival_between_preview_and_apply_is_not_lost(self):
        p = self.call('desk_preview_mail_scope', mode='folders', incoming_folder='Folders/CivicRelay')
        self.imap.boxes['Folders/CivicRelay'][2] = self.imap.raw('during-preview')
        self.call('desk_apply_mail_scope', preview_id=p['preview_id'], expected_digest=p['digest'])
        self.assertEqual(self.call('desk_sync_mail')['new_headers'], 1)
    def test_selected_folder_only_and_low_level_cannot_bypass(self):
        self.configure(history=True)
        self.assertEqual(self.call('desk_sync_mail')['new_headers'], 1)
        self.assertEqual({x[0] for x in self.imap.fetches}, {'Folders/CivicRelay'})
        self.assertEqual(connector.dispatch('proton_list_messages', {}, self.store)['messages'][0]['subject'], 'old-records')
        with self.assertRaisesRegex(ConnectorError, 'outside'):
            connector.dispatch('proton_read_message', {'folder': 'Sent', 'uid': 1, 'uid_validity': 42, 'mail_scope_id':mail_scope.read(self.store)['id']}, self.store)
        self.assertEqual(connector.dispatch('proton_read_message', {'uid': 1, 'uid_validity': 42, 'mail_scope_id':mail_scope.read(self.store)['id']}, self.store)['subject'], 'old-records')
        m = self.db.all('mail')[0]
        self.assertIn('Synthetic body', self.call('desk_read_message', message_id=m['id'])['message']['body'])
    def test_separate_custom_sent_and_colliding_uids_are_bound_to_remote_folder(self):
        self.configure(history=True, sent_folder='Labels/CivicRelay Sent')
        self.assertEqual(self.call('desk_sync_mail')['new_headers'], 2)
        self.assertEqual({m['remote_folder'] for m in self.db.all('mail')}, {'Folders/CivicRelay', 'Labels/CivicRelay Sent'})
        self.assertNotEqual(mail_scope.message_key('INBOX', 42, 1, 'Folders/CivicRelay'), 'INBOX:42:1')
        self.assertEqual(connector.dispatch('proton_list_messages', {'folder': 'Sent'}, self.store)['messages'][0]['subject'], 'old-records-sent')
    def test_epoch_change_blocks_before_fetch_without_cursor_rewind(self):
        self.configure(history=True); self.call('desk_sync_mail')
        before = self.db.all('sync'); self.imap.fetches.clear(); self.imap.epochs['Folders/CivicRelay'] = 43
        with self.assertRaisesRegex(ConnectorError, 'identity changed'): self.call('desk_sync_mail')
        with self.assertRaisesRegex(ConnectorError, 'identity changed'): connector.dispatch('proton_list_messages', {}, self.store)
        self.assertEqual(self.imap.fetches, []); self.assertEqual(self.db.all('sync'), before)
    def test_unsafe_folders_and_missing_boundary_fail_closed(self):
        for folder in ['INBOX', 'Sent', 'All Mail', '*', 'Folders/a\r\n', '"INBOX"', 'Folders/a\\b']:
            with self.assertRaises(ConnectorError): self.call('desk_preview_mail_scope', mode='folders', incoming_folder=folder)
        self.imap.missing_next = True
        with self.assertRaisesRegex(ConnectorError, 'UIDNEXT'): self.configure()
        self.assertFalse(self.call('desk_get_mail_scope')['scope']['configured'])
        self.imap.missing_next = False
        for epoch in (0, 4294967296):
            self.imap.epochs['Folders/CivicRelay'] = epoch
            with self.assertRaisesRegex(ConnectorError, 'invalid mailbox identity'): self.configure()
        self.assertFalse(self.call('desk_get_mail_scope')['scope']['configured'])
        self.assertEqual(self.imap.fetches, [])
    def test_scope_requires_digest_expiry_revision_and_preserves_credentials(self):
        original = (self.store.root / 'settings.dpapi').read_bytes()
        p = self.call('desk_preview_mail_scope', mode='dedicated')
        with self.assertRaises(ConnectorError): self.call('desk_apply_mail_scope', preview_id=p['preview_id'], expected_digest='0' * 64)
        self.configure()
        with self.assertRaisesRegex(ConnectorError, 'changed'): self.call('desk_apply_mail_scope', preview_id=p['preview_id'], expected_digest=p['digest'])
        p = self.call('desk_preview_mail_scope', mode='dedicated')
        with patch('mail_privacy.time.time', return_value=time.time() + 1000), self.assertRaisesRegex(ConnectorError, 'expired'):
            self.call('desk_apply_mail_scope', preview_id=p['preview_id'], expected_digest=p['digest'])
        self.assertEqual((self.store.root / 'settings.dpapi').read_bytes(), original)

    def test_scope_is_persistent_encrypted_and_bound_to_identity(self):
        self.configure()
        reopened=Store(self.store.root,TestProtector())
        scope=mail_scope.read(reopened)
        self.assertEqual(scope['folders']['INBOX']['remote_folder'],'Folders/CivicRelay')
        self.assertNotIn(b'Folders/CivicRelay',(self.store.root/'mail-scope.dpapi').read_bytes())
        with patch.object(reopened,'settings',return_value={**self.settings,'email':'another@example.org'}):
            with self.assertRaisesRegex(ConnectorError,'different'):mail_scope.read(reopened)

    def test_low_level_read_rejects_stale_scope_even_with_same_role_uid_and_epoch(self):
        self.configure(history=True)
        old=connector.dispatch('proton_list_messages',{},self.store)['mail_scope_id']
        self.configure('dedicated',history=True)
        self.imap.fetches.clear()
        with self.assertRaisesRegex(ConnectorError,'scope changed'):
            connector.dispatch('proton_read_message',{'uid':1,'uid_validity':42,'mail_scope_id':old},self.store)
        self.assertEqual(self.imap.fetches,[])
    def test_upgrade_hides_old_unassigned_but_preserves_case_evidence(self):
        old = mail(); self.db.put('mail', old['id'], old)
        linked = mail('INBOX:1:2', case='source-IN-2024', assignment='manual'); self.db.put('mail', linked['id'], linked)
        self.assertEqual(self.call('desk_get_mail_scope')['hidden_imports'], 1)
        self.assertEqual([m['id'] for m in self.call('desk_list_messages')['messages']], [linked['id']])
        with self.assertRaisesRegex(ConnectorError, 'hidden'): self.call('desk_read_message', message_id=old['id'])
        self.configure()
        self.assertIsNotNone(self.db.get('mail', old['id']))
    def test_cleanup_removes_only_local_unprotected_imports_and_cached_body(self):
        old = mail(); old['body_loaded'] = True; self.db.put('mail', old['id'], old)
        self.db.put('body', old['id'], {'id': old['id'], 'body': 'synthetic personal text'})
        linked = mail('INBOX:1:2', mid='<protected@example.gov>', case='source-IN-2024'); self.db.put('mail', linked['id'], linked)
        p = self.call('desk_preview_mail_cleanup'); self.assertEqual(p['count'], 1)
        before_boxes = copy.deepcopy(self.imap.boxes)
        result = self.call('desk_apply_mail_cleanup', preview_id=p['preview_id'], expected_digest=p['digest'])
        self.assertEqual(result['removed_local_messages'], 1)
        self.assertIsNone(self.db.get('mail', old['id'])); self.assertIsNone(self.db.get('body', old['id']))
        self.assertIsNotNone(self.db.get('mail', linked['id'])); self.assertEqual(before_boxes, self.imap.boxes)
        self.assertEqual(self.call('desk_apply_mail_cleanup', preview_id=p['preview_id'], expected_digest=p['digest']), result)
        self.assertEqual(self.imap.fetches, [])
    def test_cleanup_stale_or_newly_protected_is_atomic(self):
        old = mail(); other = mail('INBOX:1:2', mid='<other@example.gov>')
        for m in (old, other): self.db.put('mail', m['id'], m)
        p = self.call('desk_preview_mail_cleanup')
        other['subject'] = 'changed'; self.db.put('mail', other['id'], other)
        with self.assertRaisesRegex(ConnectorError, 'changed'): self.call('desk_apply_mail_cleanup', preview_id=p['preview_id'], expected_digest=p['digest'])
        self.assertEqual(len(self.db.all('mail')), 2); self.assertEqual(self.db.all('mail_exclusion'), [])
        p = self.call('desk_preview_mail_cleanup'); old['case_id'] = 'source-IN-2024'; self.db.put('mail', old['id'], old)
        with self.assertRaisesRegex(ConnectorError, 'protected'): self.call('desk_apply_mail_cleanup', preview_id=p['preview_id'], expected_digest=p['digest'])
        self.assertEqual(len(self.db.all('mail')), 2)
    def test_draft_refs_artifacts_and_audit_refs_protect_even_unassigned(self):
        rows = [mail(f'INBOX:1:{i}', mid=f'<m{i}@example.gov>') for i in range(1, 5)]
        for m in rows: self.db.put('mail', m['id'], m)
        connector.dispatch('proton_prepare_draft', {'to': ['records@example.gov'], 'subject': 'Synthetic', 'body': 'Synthetic', 'in_reply_to': rows[0]['message_id']}, self.store)
        self.db.put('artifact', 'a', {'id': 'a', 'message_id': rows[1]['id'], 'case_id': None})
        self.db.event('source-IN-2024', 'review', {'message_id': rows[2]['id']})
        rows[3]['in_reply_to'] = rows[0]['message_id']; self.db.put('mail', rows[3]['id'], rows[3])
        self.assertEqual(protected_ids(self.service, self.db.all('mail')), {m['id'] for m in rows})
        self.assertEqual(self.call('desk_preview_mail_cleanup')['count'], 0)
    def test_cleanup_exclusion_survives_explicit_history_reimport(self):
        self.configure(history=True); self.call('desk_sync_mail'); m = self.db.all('mail')[0]
        p = self.call('desk_preview_mail_cleanup', message_ids=[m['id']])
        self.call('desk_apply_mail_cleanup', preview_id=p['preview_id'], expected_digest=p['digest'])
        self.configure(history=True)
        self.assertEqual(self.call('desk_sync_mail')['new_headers'], 0); self.assertEqual(self.db.all('mail'), [])
    def test_out_of_scope_case_body_cannot_fetch_original_but_saved_body_remains(self):
        old = mail('INBOX:42:1', case='source-IN-2024'); self.db.put('mail', old['id'], old)
        self.configure(history=True)
        with self.assertRaisesRegex(ConnectorError, 'outside'): self.call('desk_read_message', message_id=old['id'])
        old['body_loaded'] = True; self.db.put('mail', old['id'], old)
        self.db.put('body', old['id'], {'id': old['id'], 'body': 'already saved evidence'})
        self.assertEqual(self.call('desk_read_message', message_id=old['id'])['message']['body'], 'already saved evidence')
        self.assertEqual(self.imap.fetches, [])


if __name__ == '__main__': unittest.main()
