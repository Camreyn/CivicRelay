"""The public screenshot fixture uses invented data and read-only operations."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from screenshots_fixture import ALLOWED, invoke_demo, seed_demo
from service import ARGUMENTS, Service
from storage import Database
from secure_store import Store
from test_equipment import Protector


class ScreenshotFixtureTests(unittest.TestCase):
    def test_seed_is_isolated_readable_and_has_no_enrolled_account(self):
        with tempfile.TemporaryDirectory(prefix='relay-screenshot-test-') as temporary:
            root = Path(temporary)
            service = Service(Database(root / 'desk', Protector()), mail_store=Store(root / 'mail', Protector()))
            with patch('connector.dispatch', side_effect=AssertionError('No mail operations')):
                ids = seed_demo(service)
                cases = invoke_demo(service, 'desk_list_cases', {})
                self.assertTrue(cases['ok'])
                self.assertEqual(cases['result']['workspace']['organization'], 'DEMO / FICTIONAL DATA')
                self.assertEqual(cases['result']['email'], '')
                self.assertFalse((root / 'mail').exists())
                self.assertEqual(cases['result']['equipment_campaign']['counts']['states_started'], 15)
                self.assertGreater(len(cases['result']['catalog']['cases']), 14)
                counties = invoke_demo(service, 'desk_list_counties', {'state': 'MI', 'include_requests': True})
                self.assertTrue(counties['ok'])
                self.assertEqual(len(counties['result']['request_progress']['counties']), 83)
                template = invoke_demo(service, 'desk_get_template', {'template_id': ids['template_id']})
                self.assertTrue(template['ok'])
                self.assertEqual(template['result']['template']['versions'][-1]['definition']['title'],
                                 'Park maintenance contracts')
                for case in service.db.all('case'):
                    self.assertIn(case.get('recipient', ''), ('', 'records@example.test'))
                for message in service.db.all('mail'):
                    self.assertIn('@example.test', message['from'])
                    self.assertIn('@example.test', message['to'])

    def test_every_non_allowlisted_operation_is_rejected_without_dispatch(self):
        with patch('screenshots_fixture.safe_dispatch', side_effect=AssertionError('Must not dispatch')):
            for operation in (set(ARGUMENTS) - ALLOWED) | {'unknown_operation'}:
                result = invoke_demo(None, operation, {})
                self.assertFalse(result['ok'], operation)
                self.assertIn('disabled', result['error'])


if __name__ == '__main__':
    unittest.main()
