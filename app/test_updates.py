"""Synthetic regression tests for the dashboard-only release updater."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import unittest
import uuid
from unittest.mock import patch
import zipfile

import updates


class UpdateTests(unittest.TestCase):
    """All release inputs are synthetic; no network, stores or tools are used."""

    def setUp(self):
        # Keep disposable roots under the checkout because some Windows runners
        # deny the account's global TEMP directory even though the workspace is writable.
        # The updater deliberately rejects installation paths over 150 chars;
        # keep this disposable fixture short enough for that production guard.
        self.base = Path.cwd() / ('.u' + uuid.uuid4().hex[:6])
        self.base.mkdir()
        self.root = self.make_root('current')
        self.updater = updates.Updates(self.root)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def make_root(self, name):
        root = self.base / name
        root.mkdir(parents=True, exist_ok=True)
        (root / 'package.json').write_text(json.dumps({'name': 'civic-relay', 'version': '0.8.0'}), encoding='utf-8')
        return root

    @staticmethod
    def regular_info(name):
        info = zipfile.ZipInfo(name)
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        return info

    def archive(self, *, version='0.9.0', commit='a' * 40, extra=None, omit=(), attrs=None):
        files = {
            'package.json': json.dumps({'name': 'civic-relay', 'version': version}).encode(),
            'package-lock.json': json.dumps({'name': 'civic-relay', 'version': version, 'lockfileVersion': 3}).encode(),
            'app/server.py': b'# synthetic server\n',
            'connector/desktop.py': b'# synthetic connector\n',
            'scripts/check-install.mjs': b'// synthetic check\n',
            'scripts/start.mjs': b'// synthetic start\n',
            'Open CivicRelay.cmd': b'@rem synthetic launcher\n',
        }
        if extra:
            files.update(extra)
        for name in omit:
            files.pop(name, None)
        attrs = attrs or {}
        manifest = {
            'schema_version': 1,
            'version': version,
            'commit': commit,
            'files': {name: hashlib.sha256(value).hexdigest() for name, value in files.items()},
        }
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_STORED) as archive:
            for name, value in files.items():
                info = attrs.get(name, self.regular_info(name))
                archive.writestr(info, value)
            archive.writestr(self.regular_info(updates.MANIFEST), json.dumps(manifest).encode())
        return out.getvalue(), manifest

    @staticmethod
    def release(raw, *, version='0.9.0', commit='a' * 40):
        return {
            'version': version,
            'tag': 'v' + version,
            'commit': commit,
            'release_url': 'https://github.com/Camreyn/CivicRelay/releases/tag/v' + version,
            'notes': 'Synthetic release',
            'package': {
                'url': 'https://github.com/Camreyn/CivicRelay/releases/download/v' + version + '/civicrelay-v' + version + '.zip',
                'sha256': hashlib.sha256(raw).hexdigest(),
                'size': len(raw),
            },
        }

    def save_latest(self, release):
        state = self.updater.state()
        state['latest'] = release
        self.updater.save(state)

    def preserve_sentinels(self):
        private = self.root / '.private'
        codex = self.root / '.codex'
        local = self.root / '.local'
        private.mkdir(exist_ok=True); codex.mkdir(exist_ok=True); local.mkdir(exist_ok=True)
        (private / 'sentinel.txt').write_text('private synthetic data', encoding='utf-8')
        (codex / 'config.toml').write_text('existing host choices', encoding='utf-8')
        (local / 'sentinel.txt').write_text('runtime state', encoding='utf-8')
        appdata = self.base / 'fake-AppData'
        appdata.mkdir()
        (appdata / 'records.sqlite3').write_bytes(b'fake private database')
        return private, codex, local, appdata

    def test_automatic_checks_are_opt_in_and_throttled(self):
        raw, _ = self.archive()
        release = self.release(raw)
        with patch.object(updates, 'latest_release', return_value=release) as check:
            result = self.updater.operation('check', {'automatic': True})
            check.assert_not_called()
            self.assertFalse(result['automatic_checks'])

            self.updater.operation('preferences', {'automatic_checks': True})
            self.updater.operation('check', {'automatic': True})
            self.assertEqual(check.call_count, 1)

            check.reset_mock()
            throttled = self.updater.operation('check', {'automatic': True})
            check.assert_not_called()
            self.assertEqual(throttled['latest']['commit'], release['commit'])

    def test_check_failure_preserves_prior_release_and_private_files(self):
        raw, _ = self.archive()
        prior = self.release(raw)
        self.save_latest(prior)
        private, codex, local, appdata = self.preserve_sentinels()
        before = {path: path.read_bytes() for path in (
            private / 'sentinel.txt', codex / 'config.toml', local / 'sentinel.txt', appdata / 'records.sqlite3')}

        with patch.object(updates, 'latest_release', side_effect=updates.UpdateError('synthetic offline')):
            result = self.updater.operation('check', {'automatic': False})

        self.assertEqual(result['latest'], prior)
        self.assertEqual(result['last_error'], 'synthetic offline')
        self.assertIsNone(result['approved'])
        self.assertFalse(any(self.base.glob('CivicRelay-v*')))
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_oversized_receipt_refuses_before_temp_write(self):
        state_path = self.root / '.local' / 'updates' / 'status.json'
        prior = self.updater.state()
        self.updater.save(prior)
        before = state_path.read_bytes()
        oversized = dict(prior, latest={'notes': '\u2603' * 400_000})

        with self.assertRaisesRegex(updates.UpdateError, 'receipt capacity'):
            self.updater.save(oversized)

        self.assertEqual(state_path.read_bytes(), before)
        self.assertEqual(self.updater.state(), prior)
        self.assertEqual(list(state_path.parent.glob('*.partial')), [])

    def test_approval_requires_exact_review_and_rechecks_release(self):
        raw, _ = self.archive()
        release = self.release(raw)
        self.save_latest(release)

        with patch.object(updates, 'latest_release') as check, patch.object(updates, 'get_bytes', return_value=raw) as fetch:
            with self.assertRaisesRegex(updates.UpdateError, 'exact package'):
                self.updater.operation('approve', {'version': '0.9.1', 'sha256': release['package']['sha256']})
            check.assert_not_called(); fetch.assert_not_called()

        changed_releases = {
            'version': dict(release, version='0.9.1', tag='v0.9.1'),
            'commit': dict(release, commit='b' * 40),
            'digest': dict(release, package={**release['package'], 'sha256': 'b' * 64}),
        }
        for kind, changed in changed_releases.items():
            with self.subTest(kind=kind), patch.object(updates, 'latest_release', return_value=changed) as check, patch.object(updates, 'get_bytes') as fetch:
                with self.assertRaisesRegex(updates.UpdateError, 'changed since review'):
                    self.updater.operation('approve', {'version': release['version'], 'sha256': release['package']['sha256']})
                check.assert_called_once_with()
                fetch.assert_not_called()
        self.assertIsNone(self.updater.state()['approved'])

    def test_tampered_archive_is_rejected_without_downloaded_package(self):
        raw, _ = self.archive()
        release = self.release(raw)
        self.save_latest(release)
        tampered = raw[:-1] + bytes([raw[-1] ^ 1])
        with patch.object(updates, 'latest_release', side_effect=[release, release]), patch.object(updates, 'get_bytes', return_value=tampered):
            with self.assertRaisesRegex(updates.UpdateError, 'SHA-256 check'):
                self.updater.operation('approve', {'version': release['version'], 'sha256': release['package']['sha256']})
        self.assertIsNone(self.updater.state()['approved'])
        self.assertEqual(list((self.root / '.local' / 'updates').glob('*.zip')), [])

    def test_malformed_package_metadata_is_an_explicit_update_error(self):
        for name in ('package.json', 'package-lock.json'):
            with self.subTest(name=name):
                raw, _ = self.archive(extra={name: b'[]'})
                with self.assertRaisesRegex(updates.UpdateError, 'inconsistent application versions'):
                    updates.verify_package(raw, self.release(raw))

    def assert_bad_archive(self, raw, message):
        release = self.release(raw)
        with self.assertRaisesRegex(updates.UpdateError, message):
            updates.verify_package(raw, release)

    def test_archive_rejects_traversal_case_collision_links_reserved_private_and_missing_files(self):
        traversal, _ = self.archive(extra={'../escape.py': b'bad'})
        self.assert_bad_archive(traversal, 'unsafe file path')

        attrs = {'app/server.py': self.regular_info('app/server.py')}
        collision, _ = self.archive(extra={'APP/server.py': b'collision'})
        self.assert_bad_archive(collision, 'duplicate paths')

        linked_info = zipfile.ZipInfo('app/server.py')
        linked_info.external_attr = (stat.S_IFLNK | 0o777) << 16
        linked, _ = self.archive(attrs={'app/server.py': linked_info})
        self.assert_bad_archive(linked, 'linked, encrypted or oversized')

        reserved, _ = self.archive(extra={'app/CON.py': b'reserved'})
        self.assert_bad_archive(reserved, 'reserved Windows path')

        private, _ = self.archive(extra={'app/.private.py': b'private'})
        self.assert_bad_archive(private, 'private or unexpected path')

        missing, _ = self.archive(omit={'connector/desktop.py'})
        self.assert_bad_archive(missing, 'manifest is incomplete')

    def test_side_by_side_extract_preserves_old_private_config_runtime_and_appdata(self):
        raw, _ = self.archive()
        release = self.release(raw)
        self.save_latest(release)
        private, codex, local, appdata = self.preserve_sentinels()
        before = {path: path.read_bytes() for path in (
            private / 'sentinel.txt', codex / 'config.toml', local / 'sentinel.txt', appdata / 'records.sqlite3')}

        with patch.object(updates, 'latest_release', side_effect=[release, release]), patch.object(updates, 'get_bytes', return_value=raw):
            self.updater.operation('approve', {'version': release['version'], 'sha256': release['package']['sha256']})
        destination = Path(self.updater.state()['approved']['destination'])
        self.assertEqual(self.updater.extract(), str(destination))
        self.assertTrue((destination / 'package.json').is_file())
        self.assertFalse((destination / '.private').exists())
        self.assertEqual(self.updater.state()['approved']['stage'], 'extracted')
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def approve_synthetic(self, release, raw):
        self.save_latest(release)
        with patch.object(updates, 'latest_release', return_value=release), patch.object(updates, 'get_bytes', return_value=raw):
            self.updater.operation('approve', {'version': release['version'], 'sha256': release['package']['sha256']})

    def test_duplicate_approval_is_blocked_while_ready_or_extracted(self):
        raw, _ = self.archive()
        release = self.release(raw)
        self.approve_synthetic(release, raw)
        with patch.object(updates, 'latest_release') as check, patch.object(updates, 'get_bytes') as fetch:
            with self.assertRaisesRegex(updates.UpdateError, 'already pending'):
                self.updater.operation('approve', {'version': release['version'], 'sha256': release['package']['sha256']})
            check.assert_not_called(); fetch.assert_not_called()

        self.updater.extract()
        with self.assertRaisesRegex(updates.UpdateError, 'already pending'):
            self.updater.operation('approve', {'version': release['version'], 'sha256': release['package']['sha256']})
        with self.assertRaisesRegex(updates.UpdateError, 'Only a not-yet-installed'):
            self.updater.operation('cancel', {})

    def test_cancelled_approval_can_be_replaced_and_history_is_retained(self):
        raw, _ = self.archive()
        release = self.release(raw)
        self.approve_synthetic(release, raw)
        first = self.updater.state()['approved']
        cancelled = self.updater.operation('cancel', {})
        self.assertEqual(cancelled['approved']['stage'], 'cancelled')
        self.assertTrue((self.root / '.local' / 'updates' / (first['id'] + '.zip')).is_file())

        self.approve_synthetic(release, raw)
        state = self.updater.state()
        self.assertNotEqual(state['approved']['id'], first['id'])
        self.assertEqual(len(state['history']), 1)
        self.assertEqual(state['history'][0]['id'], first['id'])
        self.assertEqual(state['history'][0]['stage'], 'cancelled')
        self.assertEqual(self.updater.operation('cancel', {})['approved']['stage'], 'cancelled')

    def test_installed_same_version_cannot_be_approved_again(self):
        raw, _ = self.archive()
        release = self.release(raw)
        self.approve_synthetic(release, raw)
        self.updater.extract()
        self.updater.finish('installed')
        with patch.object(updates, 'latest_release') as check, patch.object(updates, 'get_bytes') as fetch:
            with self.assertRaisesRegex(updates.UpdateError, 'already installed'):
                self.updater.operation('approve', {'version': release['version'], 'sha256': release['package']['sha256']})
            check.assert_not_called(); fetch.assert_not_called()

    def test_cross_instance_updater_lock_refuses_concurrent_action(self):
        other = updates.Updates(self.root)
        with self.updater.exclusive():
            with self.assertRaisesRegex(updates.UpdateError, 'Another updater process is active'):
                with other.exclusive():
                    pass

    def test_existing_destination_refuses_overwrite(self):
        raw, _ = self.archive()
        release = self.release(raw)
        self.save_latest(release)
        with patch.object(updates, 'latest_release', side_effect=[release, release]), patch.object(updates, 'get_bytes', return_value=raw):
            self.updater.operation('approve', {'version': release['version'], 'sha256': release['package']['sha256']})
        destination = Path(self.updater.state()['approved']['destination'])
        destination.mkdir()
        (destination / 'sentinel.txt').write_text('do not overwrite', encoding='utf-8')
        with self.assertRaisesRegex(updates.UpdateError, 'already attempted or its destination exists'):
            self.updater.extract()
        self.assertEqual((destination / 'sentinel.txt').read_text(encoding='utf-8'), 'do not overwrite')
        self.assertEqual(self.updater.state()['approved']['stage'], 'failed')

    def test_failed_extraction_retains_old_install_and_records_failed_stage(self):
        raw, manifest = self.archive()
        release = self.release(raw)
        self.save_latest(release)
        private, codex, local, appdata = self.preserve_sentinels()
        before = {path: path.read_bytes() for path in (
            private / 'sentinel.txt', codex / 'config.toml', local / 'sentinel.txt', appdata / 'records.sqlite3')}
        with patch.object(updates, 'latest_release', side_effect=[release, release]), patch.object(updates, 'get_bytes', return_value=raw):
            self.updater.operation('approve', {'version': release['version'], 'sha256': release['package']['sha256']})

        real_zip = zipfile.ZipFile

        class FailingZip:
            def __init__(self, *args, **kwargs): self.inner = real_zip(*args, **kwargs)
            def __enter__(self): self.inner.__enter__(); return self
            def __exit__(self, *args): return self.inner.__exit__(*args)
            def read(self, name): raise OSError('synthetic extraction failure')

        with patch.object(updates, 'verify_package', return_value=manifest), patch.object(updates.zipfile, 'ZipFile', FailingZip):
            with self.assertRaisesRegex(updates.UpdateError, 'Extraction did not complete'):
                self.updater.extract()
        self.assertEqual(self.updater.state()['approved']['stage'], 'failed')
        destination = Path(self.updater.state()['approved']['destination'])
        self.assertTrue(destination.exists())
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def hardlink_or_skip(self, link, target):
        try:
            os.link(target, link)
        except (OSError, NotImplementedError) as error:
            self.skipTest('synthetic hard links are unavailable: ' + str(error))

    def test_linked_state_and_target_are_rejected(self):
        state_root = self.make_root('linked-state')
        state_updates = updates.Updates(state_root)
        state_file = state_root / '.local' / 'updates' / 'status.json'
        state_file.parent.mkdir(parents=True)
        external_state = self.base / 'external-status.json'
        external_state.write_text(json.dumps(state_updates.state()), encoding='utf-8')
        self.hardlink_or_skip(state_file, external_state)
        with self.assertRaisesRegex(updates.UpdateError, 'linked update location'):
            state_updates.state()

        target_root = self.make_root('linked-target')
        target_updates = updates.Updates(target_root)
        raw, _ = self.archive()
        release = self.release(raw)
        target_updates.save({**target_updates.state(), 'latest': release, 'approved': {
            'id': 'c' * 32, 'release': release, 'approved_at': 1, 'stage': 'ready',
            'destination': str(target_root.parent / ('CivicRelay-v' + release['version'] + '-' + 'c' * 8)),
        }})
        target = target_root.parent / ('CivicRelay-v' + release['version'] + '-' + 'c' * 8)
        external_target = self.base / 'external-target'
        external_target.write_text('not a destination', encoding='utf-8')
        self.hardlink_or_skip(target, external_target)
        with self.assertRaisesRegex(updates.UpdateError, 'linked update location'):
            target_updates.approved()


if __name__ == '__main__':
    unittest.main(verbosity=2)
