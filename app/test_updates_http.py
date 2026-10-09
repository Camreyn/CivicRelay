"""Synthetic HTTP boundary tests; no actual update state or network requests."""
import http.client
import json
import threading
import unittest
from unittest.mock import Mock, patch
import server


class UpdateHTTPTests(unittest.TestCase):
    def test_only_same_origin_dashboard_can_request_fixed_update_actions(self):
        updater = Mock()
        updater.operation.return_value = {'installed_version': '0.9.0', 'automatic_checks': False}
        with patch('server.UPDATES', updater), server.Server(('127.0.0.1', 0), server.Handler) as httpd:
            port = httpd.server_address[1]
            origin = f'http://127.0.0.1:{port}'
            with patch('server.PORT', port), patch('server.ORIGIN', origin):
                thread = threading.Thread(target=httpd.serve_forever)
                thread.start()
                try:
                    def request(headers):
                        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                        connection.request('POST', '/api/updates', json.dumps({'action': 'status', 'arguments': {}}), headers)
                        response = connection.getresponse()
                        result = response.status, json.loads(response.read())
                        connection.close()
                        return result
                    headers = {'Content-Type': 'application/json', 'Host': f'127.0.0.1:{port}', 'X-Records-Desk': '1', 'Origin': origin, 'Cookie': f'records_session={server.COOKIE}'}
                    for key in ('X-Records-Desk', 'Origin', 'Cookie'):
                        wrong = dict(headers); wrong.pop(key)
                        self.assertEqual(request(wrong)[0], 403)
                    wrong = dict(headers); wrong['Origin'] = 'https://untrusted.example.test'
                    self.assertEqual(request(wrong)[0], 403)
                    updater.operation.assert_not_called()
                    code, result = request(headers)
                    self.assertEqual(code, 200)
                    self.assertTrue(result['ok'])
                    updater.operation.assert_called_once_with('status', {})
                    updater.operation.side_effect = OSError('synthetic secret diagnostic must not escape')
                    code, result = request(headers)
                    self.assertEqual(code, 400)
                    self.assertNotIn('synthetic secret', json.dumps(result))
                finally:
                    httpd.shutdown(); thread.join(timeout=5)
