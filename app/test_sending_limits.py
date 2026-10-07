"""Service-level policy contracts; no live settings or network."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import runtime
from secure_store import Store, ConnectorError
from storage import Database
from service import Service, READ_ONLY, safe_dispatch
from test_records_desk import TestProtector


class SendingLimitServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='relay-limit-service-')
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'mail', TestProtector())
        self.service = Service(Database(self.root / 'desk', TestProtector()), mail_store=self.store)

    def tearDown(self):
        self.temp.cleanup()

    def enroll(self):
        self.store.save_settings({'version':2, 'email':'relay@example.org', 'display_name':'Synthetic Relay',
            'profile_id':'00000000-0000-4000-8000-000000000001', 'password':'synthetic-credential-only',
            'imap_port':1143, 'smtp_port':1025, 'imap_pin':'1'*64, 'smtp_pin':'2'*64,
            'project_mailbox_confirmed':True, 'sending_enabled':False})

    def test_getter_is_read_only_without_enrollment_or_network(self):
        with patch('bridge.imap_connection', side_effect=AssertionError('No IMAP')), patch('bridge.smtp_connection', side_effect=AssertionError('No SMTP')):
            result = self.service.dispatch('desk_get_send_limits', {})
        self.assertIn('desk_get_send_limits', READ_ONLY)
        self.assertNotIn('desk_save_send_limits', READ_ONLY)
        self.assertFalse(result['configured'])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_save_needs_enrollment_and_strict_arguments_without_send_enablement(self):
        args = {'revision':0, 'max_attempts_per_24h':25, 'minimum_interval_seconds':30}
        with self.assertRaises(ConnectorError):
            self.service.dispatch('desk_save_send_limits', args)
        self.enroll()
        for bad in [{**args,'sending_enabled':True}, {**args,'revision':False},
                    {**args,'max_attempts_per_24h':'25'}, {'revision':0}, {**args,'window_seconds':1}]:
            self.assertFalse(safe_dispatch('desk_save_send_limits', bad, self.service)['ok'])
        with patch('bridge.imap_connection', side_effect=AssertionError('No IMAP')), patch('bridge.smtp_connection', side_effect=AssertionError('No SMTP')):
            result = self.service.dispatch('desk_save_send_limits', args)
            status = self.service.dispatch('desk_status', {})
            workflow = self.service.dispatch('desk_get_workflow', {})
        self.assertEqual(result['revision'], 1)
        self.assertFalse(status['connector']['sending_enabled'])
        self.assertFalse(status['automatic_polling'])
        self.assertEqual(status['connector']['send_window']['max_attempts'], 25)
        self.assertEqual(workflow['limits']['send_attempts_per_day'], 25)
        self.assertNotIn('synthetic-credential', json.dumps(result))
        self.assertIsNone(self.store.mail_scope())
        self.assertFalse(safe_dispatch('desk_save_send_limits', args, self.service)['ok'])


if __name__ == '__main__':
    unittest.main()
