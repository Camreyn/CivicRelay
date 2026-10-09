"""Public release transport tests. All sockets and GitHub responses are synthetic."""
import io
import urllib.error
import unittest
from unittest.mock import patch
import updates


class ReleaseMetadataTests(unittest.TestCase):
    def release(self):
        return {'tag_name': 'v0.10.0', 'draft': False, 'prerelease': False, 'body': '<script>untrusted</script>',
            'assets': [{'name': 'civicrelay-v0.10.0.zip', 'state': 'uploaded', 'size': 1024,
                'digest': 'sha256:' + 'a' * 64,
                'browser_download_url': 'https://github.com/Camreyn/CivicRelay/releases/download/v0.10.0/civicrelay-v0.10.0.zip'}]}

    def test_metadata_binds_annotated_tag_and_fixed_official_asset(self):
        with patch.object(updates, 'get_json', side_effect=[self.release(), {'object': {'type': 'tag', 'sha': 'b' * 40}}, {'object': {'type': 'commit', 'sha': 'c' * 40}}]) as fetch:
            result = updates.latest_release()
        self.assertEqual(result['commit'], 'c' * 40)
        self.assertEqual(result['notes'], '<script>untrusted</script>')
        self.assertEqual([call.args[0] for call in fetch.call_args_list], [updates.API + '/releases/latest', updates.API + '/git/ref/tags/v0.10.0', updates.API + '/git/tags/' + 'b' * 40])

    def test_rejects_nonstable_or_unsafe_assets_and_malformed_tag(self):
        cases = []
        for key, value in [('draft', True), ('prerelease', True), ('tag_name', 'v0.10.0-beta'), ('tag_name', '../bad')]:
            cases.append({**self.release(), key: value})
        for key, value in [('digest', None), ('digest', 'sha256:bad'), ('size', True), ('size', updates.MAX_PACKAGE + 1), ('state', 'new'), ('browser_download_url', 'https://untrusted.example.test/package.zip')]:
            release = self.release(); release['assets'][0][key] = value; cases.append(release)
        for release in cases:
            with self.subTest(release=release), patch.object(updates, 'get_json', side_effect=[release, {'object': {'type': 'commit', 'sha': 'c' * 40}}]):
                with self.assertRaises(updates.UpdateError): updates.latest_release()
        with patch.object(updates, 'get_json', side_effect=[self.release(), {'object': []}]):
            with self.assertRaises(updates.UpdateError): updates.latest_release()
        release = self.release(); release['assets'] *= 2
        with patch.object(updates, 'get_json', side_effect=[release, {'object': {'type': 'commit', 'sha': 'c' * 40}}]):
            with self.assertRaisesRegex(updates.UpdateError, 'ambiguous'): updates.latest_release()

    def test_no_asset_is_metadata_only_and_never_substitutes_source_zip(self):
        release = self.release(); release['assets'] = []
        with patch.object(updates, 'get_json', side_effect=[release, {'object': {'type': 'commit', 'sha': 'c' * 40}}]):
            self.assertIsNone(updates.latest_release()['package'])


class TransportTests(unittest.TestCase):
    class Response(io.BytesIO):
        status = 200
        headers = {}

    def test_fixed_https_no_credentials_proxy_cookies_or_identifiers(self):
        class Opener:
            def open(self, request, timeout):
                self.request, self.timeout = request, timeout
                return TransportTests.Response(b'synthetic')
        opener = Opener()
        with patch.object(updates.urllib.request, 'build_opener', return_value=opener) as builder:
            self.assertEqual(updates.get_bytes(updates.API + '/releases/latest', 100), b'synthetic')
        self.assertEqual(builder.call_args.args[0].proxies, {})
        self.assertEqual(opener.timeout, 12)
        self.assertEqual(dict(opener.request.header_items()), {'User-agent': 'CivicRelay-updates', 'Accept': 'application/vnd.github+json'})
        for url in ['http://api.github.com/x', 'https://untrusted.example.test/x', 'https://credential@api.github.com/x', 'https://api.github.com:444/x']:
            with self.subTest(url=url), patch.object(updates.urllib.request, 'build_opener', return_value=opener):
                with self.assertRaises(updates.UpdateError): updates.get_bytes(url, 100)

    def test_redirect_whitelist_and_size_limits(self):
        public = 'https://github.com/Camreyn/CivicRelay/releases/download/v0.10.0/civicrelay-v0.10.0.zip'
        class Redirect:
            def open(self, request, timeout):
                raise urllib.error.HTTPError(request.full_url, 302, 'redirect', {'Location': 'https://untrusted.example.test/package.zip'}, None)
        with patch.object(updates.urllib.request, 'build_opener', return_value=Redirect()):
            with self.assertRaisesRegex(updates.UpdateError, 'redirect was refused'): updates.get_bytes(public, 100, asset=True)
        class Oversized:
            def open(self, request, timeout): return TransportTests.Response(b'x' * 101)
        with patch.object(updates.urllib.request, 'build_opener', return_value=Oversized()):
            with self.assertRaisesRegex(updates.UpdateError, 'too large'): updates.get_bytes(public, 100, asset=True)
        class AllowedRedirect:
            def __init__(self): self.calls = []
            def open(self, request, timeout):
                self.calls.append(request.full_url)
                if len(self.calls) == 1:
                    raise urllib.error.HTTPError(request.full_url, 302, 'redirect', {'Location': 'https://release-assets.githubusercontent.com/synthetic.zip?temporary=synthetic'}, None)
                return TransportTests.Response(b'safe')
        opener = AllowedRedirect()
        with patch.object(updates.urllib.request, 'build_opener', return_value=opener):
            self.assertEqual(updates.get_bytes(public, 100, asset=True), b'safe')
        self.assertEqual(len(opener.calls), 2)

    def test_network_failures_never_expose_raw_diagnostics(self):
        class Broken:
            def open(self, request, timeout): raise OSError('synthetic sensitive exception details')
        with patch.object(updates.urllib.request, 'build_opener', return_value=Broken()):
            with self.assertRaises(updates.UpdateError) as error: updates.get_bytes(updates.API + '/releases/latest', 100)
        self.assertNotIn('sensitive', str(error.exception))
