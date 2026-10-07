"""Connector policy tests with disposable stores only; no SMTP or real credentials."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import copy
import tempfile
import unittest
from unittest.mock import patch

import connector
from secure_store import ConnectorError, Store
from test_connector import TestOnlyProtector, profile_settings, settings


class SendingLimitsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='relay-limits-test-')
        self.store = Store(Path(self.temp.name) / 'mail', TestOnlyProtector())
        self.store.save_settings(profile_settings())

    def tearDown(self):
        self.temp.cleanup()

    def draft(self, suffix):
        return connector.dispatch('proton_prepare_draft', {'to':['records@example.gov'],
            'subject':'Synthetic limits test', 'body':f'Fictional request {suffix}'}, self.store)['draft']

    def attempt(self, suffix, at):
        draft = self.draft(suffix)
        self.store.claim_send(draft['draft_id'], draft['digest'], at)
        return draft

    def test_unconfigured_default_read_creates_nothing_and_never_connects(self):
        empty = Store(Path(self.temp.name) / 'empty', TestOnlyProtector())
        with patch('bridge.imap_connection', side_effect=AssertionError('No IMAP')), patch('bridge.smtp_connection', side_effect=AssertionError('No SMTP')):
            value = empty.get_send_limits(1000)
        self.assertEqual(value['revision'], 0)
        self.assertEqual(value['max_attempts_per_24h'], 10)
        self.assertEqual(value['minimum_interval_seconds'], 60)
        self.assertEqual(value['send_window']['attempts_used'], 0)
        self.assertFalse(empty.root.exists())

    def test_existing_database_reads_default_without_migration_and_save_preserves_drafts(self):
        self.attempt('old-history', 1000)
        path = self.store.root / 'drafts.sqlite3'
        before = path.read_bytes()
        self.assertEqual(self.store.get_send_limits(1100)['revision'], 0)
        self.assertEqual(before, path.read_bytes())
        with self.store.database(readonly=True) as db:
            payload = db.execute('SELECT payload FROM drafts').fetchone()[0]
        credentials = (self.store.root / 'settings.dpapi').read_bytes()
        value = self.store.save_send_limits(0, 25, 30, 1100)
        self.assertEqual(value['send_window']['attempts_remaining'], 24)
        self.assertEqual((self.store.root / 'settings.dpapi').read_bytes(), credentials)
        with self.store.database(readonly=True) as db:
            self.assertEqual(db.execute('SELECT payload FROM drafts').fetchone()[0], payload)
        reopened = Store(self.store.root, TestOnlyProtector())
        self.assertEqual(reopened.get_send_limits(1100), value)
        self.assertNotIn('identity', value)
        self.assertNotIn(b'relay@example.org', path.read_bytes())

    def test_higher_limit_is_used_for_final_claims_and_status(self):
        self.store.save_send_limits(0, 12, 5, 900)
        for i in range(12):
            self.attempt(i, 1000 + i * 5)
        extra = self.draft('extra')
        window = self.store.send_window(1060)
        self.assertEqual(window['attempts_used'], 12)
        self.assertEqual(window['max_attempts'], 12)
        self.assertEqual(window['reason'], 'daily_limit')
        with self.assertRaisesRegex(ConnectorError, '12 attempts.*5 seconds'):
            self.store.claim_send(extra['draft_id'], extra['digest'], 1060)
        with patch('connector.time.time', return_value=1060):
            self.assertEqual(connector.dispatch('proton_status', {}, self.store)['send_window'], window)
        self.assertTrue(self.store.send_window(87400)['ready'])

    def test_lower_limit_expires_enough_attempts_without_erasing_uncertain_history(self):
        first = self.attempt('uncertain', 1000)
        self.store.finish_send(first['draft_id'], 'uncertain', {'synthetic':True})
        second = self.attempt('failed', 1060)
        self.store.finish_send(second['draft_id'], 'failed_before_data', {'synthetic':True})
        self.attempt('accepted', 1120)
        value = self.store.save_send_limits(0, 2, 90, 2000)
        self.assertEqual(value['send_window']['attempts_used'], 3)
        self.assertEqual(value['send_window']['attempts_remaining'], 0)
        self.assertEqual(value['send_window']['next_attempt_at'], 87460)
        self.assertFalse(self.store.send_window(87459.999)['ready'])
        self.assertTrue(self.store.send_window(87460)['ready'])
        self.assertEqual(self.store.get_draft(first['draft_id'])['state'], 'uncertain')
        self.store.save_send_limits(1, 10, 60, 2001)
        self.assertEqual(self.store.send_window(2001)['attempts_used'], 3)
        with self.assertRaises(ConnectorError):
            self.store.claim_send(first['draft_id'], first['digest'], 2001)

    def test_current_policy_is_rechecked_after_preflight_and_spacing_change(self):
        self.attempt('prior', 1000)
        draft = self.draft('next')
        self.assertTrue(self.store.send_window(1060)['ready'])
        # Another UI/MCP worker saves a stricter policy after the original preflight.
        other = Store(self.store.root, TestOnlyProtector())
        other.save_send_limits(0, 1, 120, 1059)
        with self.assertRaises(ConnectorError):
            self.store.claim_send(draft['draft_id'], draft['digest'], 1060)
        other.save_send_limits(1, 20, 120, 1061)
        self.assertEqual(self.store.send_window(1119.1)['retry_after_seconds'], 1)
        self.assertTrue(self.store.send_window(1120)['ready'])
        self.assertEqual(self.store.get_draft(draft['draft_id'])['state'], 'draft')

    def test_invalid_values_and_stale_revisions_cannot_change_policy(self):
        for revision, maximum, interval in [(True,10,60),(-1,10,60),(0,True,60),(0,1.5,60),(0,0,60),
                (0,1001,60),(0,10,0),(0,10,3601),(0,10,'60'),(0,10,None)]:
            with self.subTest(values=(revision,maximum,interval)), self.assertRaises(ConnectorError):
                self.store.save_send_limits(revision, maximum, interval, 1000)
        self.assertFalse((self.store.root / 'drafts.sqlite3').exists())
        self.store.save_send_limits(0, 1, 1, 1000)
        with self.assertRaisesRegex(ConnectorError, 'changed'):
            self.store.save_send_limits(0, 20, 60, 1001)
        self.store.save_send_limits(1, 1000, 3600, 1002)
        self.assertEqual(self.store.get_send_limits(1003)['revision'], 2)

    def test_concurrent_edits_have_one_winner(self):
        def save(maximum):
            other = Store(self.store.root, TestOnlyProtector())
            try:
                other.save_send_limits(0, maximum, 60, 1000)
                return True
            except ConnectorError:
                return False
        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertEqual(sorted(workers.map(save, [20,30])), [False,True])
        self.assertEqual(self.store.get_send_limits(1001)['revision'], 1)

    def test_corrupt_saved_policy_fails_closed_for_reads_claims_and_writes(self):
        draft = self.draft('blocked')
        self.store.save_send_limits(0, 20, 60, 1000)
        with self.store.database() as db:
            original = self.store.protector.unprotect(db.execute('SELECT payload FROM send_limits').fetchone()[0])
        for key, replacement in [('version',True), ('revision',5), ('max_attempts_per_24h',0),
                ('minimum_interval_seconds',True), ('identity',['someone@example.org','Other',None]), ('changed_at','bad')]:
            bad = {**copy.deepcopy(original), key:replacement}
            with self.store.database() as db:
                db.execute('UPDATE send_limits SET payload=?', (self.store.protector.protect(bad),))
            with self.subTest(key=key):
                for action in [lambda:self.store.get_send_limits(1100),
                               lambda:self.store.claim_send(draft['draft_id'],draft['digest'],1100),
                               lambda:self.store.save_send_limits(1,30,60,1100)]:
                    with self.assertRaisesRegex(ConnectorError, 'could not be verified'):
                        action()
        with self.store.database() as db:
            db.execute('DELETE FROM send_limits')
        with self.assertRaises(ConnectorError):
            self.store.send_window(1100)
        self.assertEqual(self.store.get_draft(draft['draft_id'])['state'], 'draft')

    def test_credential_refresh_and_reviewed_legacy_upgrade_preserve_limits(self):
        legacy = Store(Path(self.temp.name) / 'legacy', TestOnlyProtector())
        legacy.save_settings(settings())
        legacy.save_send_limits(0, 25, 30, 1000)
        updated = settings(); updated['password'] = 'another-synthetic-credential'
        legacy.save_settings(updated)
        self.assertEqual(legacy.get_send_limits(1000)['revision'], 1)
        legacy.save_settings(profile_settings(email=connector.PROJECT_EMAIL, name='CivicResultMaps'))
        self.assertEqual(legacy.get_send_limits(1000)['max_attempts_per_24h'], 25)
        legacy.save_send_limits(1, 20, 15, 1001)
        self.assertEqual(legacy.get_send_limits(1002)['revision'], 2)


if __name__ == '__main__':
    unittest.main()
