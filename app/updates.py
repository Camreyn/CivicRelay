"""Dashboard-only release checks and approved packages. Never opens private stores."""
from __future__ import annotations
from pathlib import Path, PurePosixPath
from contextlib import contextmanager
import hashlib
import io
import json
import os
import re
import secrets
import stat
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPOSITORY = "Camreyn/CivicRelay"
API = f"https://api.github.com/repos/{REPOSITORY}"
MAX_PACKAGE = 32_000_000
MAX_EXPANDED = 64_000_000
MANIFEST = "civicrelay-release.json"
CHECK_INTERVAL = 24 * 60 * 60
VERSION = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SHA = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
ROOT_FILES = {'README.md', 'AGENTS.md', 'LICENSE', 'NOTICE', 'SECURITY.md',
    '.gitignore', '.gitattributes', 'package.json', 'package-lock.json', 'runtime-config.mjs',
    'Open CivicRelay.cmd', 'Open Records Desk.cmd', 'Open Proton Setup.cmd',
    'Install CivicRelay.cmd', 'Check CivicRelay.cmd', 'Update CivicRelay.cmd',
    'Open-Records-Desk.ps1', 'Open-Proton-Setup.ps1'}
REQUIRED = {'package.json', 'package-lock.json', 'app/server.py', 'connector/desktop.py',
    'scripts/check-install.mjs', 'scripts/start.mjs', 'Open CivicRelay.cmd'}


class UpdateError(Exception):
    """A deliberately public diagnostic, never a raw network/filesystem exception."""


def version(value):
    if not isinstance(value, str) or not VERSION.fullmatch(value) or len(value) > 40:
        raise UpdateError('The release version is invalid or not a stable release.')
    return tuple(int(part) for part in value.lstrip('v').split('.'))


def public_path(name):
    if not isinstance(name, str) or len(name) > 180 or '\\' in name:
        raise UpdateError('The update contains an unsafe file path.')
    parts = PurePosixPath(name).parts
    if not parts or str(PurePosixPath(name)) != name or name.startswith('/'):
        raise UpdateError('The update contains an unsafe file path.')
    for part in parts:
        if part in ('.', '..') or part.endswith(('.', ' ')) or ':' in part or re.search(r'[\x00-\x1f]', part):
            raise UpdateError('The update contains an unsafe file path.')
        if part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *{f'COM{i}' for i in range(1, 10)}, *{f'LPT{i}' for i in range(1, 10)}}:
            raise UpdateError('The update contains a reserved Windows path.')
    if len(parts) > 1 and any(part.startswith('.') or part.lower() in {'node_modules', '__pycache__', 'exports', 'attachments', 'collections', 'quarantine'} for part in parts):
        if name != '.github/workflows/ci.yml':
            raise UpdateError('The update contains a private or unexpected path.')
    if name in ROOT_FILES or name == '.github/workflows/ci.yml':
        return name
    if re.fullmatch(r'(app|connector|scripts)/[\w./-]+\.(py|mjs|js|html|css|json|ps1)', name, re.ASCII):
        if any(part.startswith('.') or part.lower() in {'node_modules', '__pycache__', 'exports', 'attachments', 'collections', 'quarantine'} for part in parts):
            raise UpdateError('The update contains a private or unexpected path.')
        return name
    if re.fullmatch(r'docs/[\w./-]+\.(md|toml)', name, re.ASCII) or name in {
        'docs/images/demo-national-overview.jpg', 'docs/images/demo-county-progress.jpg', 'docs/images/demo-request-template.jpg',
        'data/catalog.json', 'data/snapshot-provenance.json', 'data/records-response.yml'}:
        return name
    raise UpdateError('The update contains a private or unexpected path.')


def safe_path(path):
    """Reject redirected parents, links and hard-linked files, including on Windows."""
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400 or (item.is_file() and info.st_nlink != 1):
                raise UpdateError('A linked update location was refused. No installation was changed.')
    return path


def read_json(path, limit=1_000_000):
    path = safe_path(path)
    if path.stat().st_size > limit:
        raise UpdateError('Local update metadata is oversized. No installation was changed.')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeError, ValueError):
        raise UpdateError('Local update metadata is invalid. No installation was changed.') from None


def atomic_json(path, value):
    encoded = json.dumps(value, ensure_ascii=True).encode('utf-8')
    if len(encoded) > 2_000_000:
        raise UpdateError('The local updater receipt capacity was reached. Use a reviewed manual upgrade; existing receipts were retained.')
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = safe_path(path.parent / ('update-' + secrets.token_hex(12) + '.partial'))
    try:
        with temporary.open('xb') as stream:
            stream.write(encoded)
        safe_path(path)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def get_bytes(url, limit, *, asset=False):
    """Fixed public HTTPS requests: no proxies, cookies, credentials or local identifiers."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    started = time.monotonic()
    for attempt in range(3):
        parsed = urllib.parse.urlsplit(url)
        hosts = {'github.com', 'release-assets.githubusercontent.com'} if asset else {'api.github.com'}
        if parsed.scheme != 'https' or parsed.hostname not in hosts or parsed.port not in (None, 443) or parsed.username or parsed.password or parsed.fragment:
            raise UpdateError('The release download location was refused.')
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'CivicRelay-updates', 'Accept': 'application/octet-stream' if asset else 'application/vnd.github+json'})
            with opener.open(request, timeout=12) as response:
                if response.status != 200:
                    raise UpdateError('GitHub did not return a complete release response.')
                if response.headers.get('Content-Length') and int(response.headers['Content-Length']) > limit:
                    raise UpdateError('The release response is too large.')
                chunks, size = [], 0
                while True:
                    if time.monotonic() - started > 60:
                        raise UpdateError('The release request timed out. No installation was changed.')
                    chunk = response.read(min(65536, limit + 1 - size))
                    if not chunk:
                        return b''.join(chunks)
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > limit:
                        raise UpdateError('The release response is too large.')
        except urllib.error.HTTPError as error:
            if asset and attempt < 2 and error.code in (301, 302, 303, 307, 308):
                location = error.headers.get('Location', '')
                # Only GitHub's asset service may receive its temporary download URL.
                if urllib.parse.urlsplit(location).hostname != 'release-assets.githubusercontent.com':
                    raise UpdateError('The release redirect was refused.') from None
                url = location
                continue
            raise UpdateError('GitHub could not provide the release. Check your connection or try again later; no installation was changed.') from None
        except UpdateError:
            raise
        except Exception:
            raise UpdateError('The release request failed. Check your connection; no installation was changed.') from None
    raise UpdateError('The release download was interrupted. No installation was changed.')


def get_json(url):
    try:
        result = json.loads(get_bytes(url, 1_000_000))
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (ValueError, UnicodeError):
        raise UpdateError('GitHub returned invalid release metadata.') from None


def latest_release():
    release = get_json(API + '/releases/latest')
    tag = release.get('tag_name')
    version(tag)
    if not tag.startswith('v') or release.get('draft') is not False or release.get('prerelease') is not False:
        raise UpdateError('Only published stable CivicRelay releases can be installed.')
    reference = get_json(API + '/git/ref/tags/' + tag).get('object', {})
    if not isinstance(reference, dict):
        raise UpdateError('The release tag metadata is invalid.')
    if reference.get('type') == 'tag' and COMMIT.fullmatch(str(reference.get('sha', ''))):
        reference = get_json(API + '/git/tags/' + reference['sha']).get('object', {})
    if not isinstance(reference, dict):
        raise UpdateError('The release tag metadata is invalid.')
    commit = reference.get('sha', '')
    if reference.get('type') != 'commit' or not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise UpdateError('The release tag could not be bound to a source commit.')
    name = f'civicrelay-{tag}.zip'
    assets = release.get('assets', [])
    if not isinstance(assets, list) or len(assets) > 100:
        raise UpdateError('The release assets are invalid.')
    matches = [item for item in assets if isinstance(item, dict) and item.get('name') == name]
    package = None
    if len(matches) > 1:
        raise UpdateError('The release has ambiguous update packages.')
    if matches:
        item = matches[0]
        digest = item.get('digest', '')
        size = item.get('size')
        expected_url = f'https://github.com/{REPOSITORY}/releases/download/{tag}/{name}'
        if item.get('state') != 'uploaded' or type(size) is not int or not 1 <= size <= MAX_PACKAGE or not isinstance(digest, str) or not digest.startswith('sha256:') or not SHA.fullmatch(digest[7:]) or item.get('browser_download_url') != expected_url:
            raise UpdateError('The release package lacks valid GitHub integrity metadata.')
        package = {'url': expected_url, 'sha256': digest[7:], 'size': size}
    body = release.get('body', '')
    return {'version': tag[1:], 'tag': tag, 'commit': commit,
        'release_url': f'https://github.com/{REPOSITORY}/releases/tag/{tag}',
        'notes': body[:12000] if isinstance(body, str) else '', 'package': package}


def verify_package(raw, release):
    package = release.get('package') or {}
    if len(raw) != package.get('size') or hashlib.sha256(raw).hexdigest() != package.get('sha256'):
        raise UpdateError('The downloaded package failed its GitHub SHA-256 check. Nothing was installed.')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if not 1 <= len(entries) <= 1024 or sum(item.file_size for item in entries) > MAX_EXPANDED:
                raise UpdateError('The update archive exceeds the safe extraction limits.')
            names = [item.filename for item in entries]
            if len(set(name.casefold() for name in names)) != len(names) or MANIFEST not in names:
                raise UpdateError('The update archive contains duplicate paths or lacks its manifest.')
            for item in entries:
                mode = item.external_attr >> 16
                if item.is_dir() or item.flag_bits & 1 or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)) or item.file_size > 2_000_000:
                    raise UpdateError('The update archive contains a linked, encrypted or oversized file.')
                if item.filename != MANIFEST:
                    public_path(item.filename)
            manifest = json.loads(archive.read(MANIFEST))
            if not isinstance(manifest, dict) or set(manifest) != {'schema_version', 'version', 'commit', 'files'} or type(manifest['schema_version']) is not int or manifest['schema_version'] != 1 or manifest['version'] != release['version'] or manifest['commit'] != release['commit']:
                raise UpdateError('The package does not match the reviewed release version and commit.')
            files = manifest['files']
            if not isinstance(files, dict) or set(files) != set(names) - {MANIFEST} or not REQUIRED <= set(files):
                raise UpdateError('The package manifest is incomplete or contains unexpected files.')
            for name, digest in files.items():
                if not isinstance(digest, str) or not SHA.fullmatch(digest) or hashlib.sha256(archive.read(name)).hexdigest() != digest:
                    raise UpdateError('A release file failed its manifest integrity check.')
            for name in ('package.json', 'package-lock.json'):
                metadata = json.loads(archive.read(name))
                if not isinstance(metadata, dict) or metadata.get('name') != 'civic-relay' or metadata.get('version') != release['version']:
                    raise UpdateError('The release package has inconsistent application versions.')
            return manifest
    except (zipfile.BadZipFile, ValueError, UnicodeError, KeyError, RuntimeError, NotImplementedError):
        raise UpdateError('The release package could not be safely verified. Nothing was installed.') from None


class Updates:
    def __init__(self, root):
        self.root = safe_path(root)
        self.directory = self.root / '.local' / 'updates'
        self.lock = threading.Lock()
        self.current_version = read_json(self.root / 'package.json')['version']
        version(self.current_version)

    def state(self):
        file = safe_path(self.directory / 'status.json')
        if not file.exists():
            return {'schema_version': 1, 'automatic_checks': False, 'last_checked_at': None, 'latest': None, 'last_error': None, 'approved': None}
        result = read_json(file, 2_000_000)  # Bounded retained release receipts, including literal notes.
        if not isinstance(result, dict) or result.get('schema_version') != 1 or type(result.get('automatic_checks')) is not bool:
            raise UpdateError('Saved update preferences are invalid. No installation was changed.')
        return result

    def status(self):
        result = self.state()
        latest = result.get('latest')
        return {**result, 'installed_version': self.current_version,
            'update_available': bool(latest and version(latest['version']) > version(self.current_version)),
            'check_interval_seconds': CHECK_INTERVAL}

    def save(self, state):
        atomic_json(self.directory / 'status.json', state)

    @contextmanager
    def exclusive(self):
        if not self.lock.acquire(blocking=False):
            raise UpdateError('Another update action is in progress. Wait for its result.')
        try:
            import msvcrt  # Supported runtime is Windows; never touch a mailbox lease.
            file = safe_path(self.directory / 'operation.lock')
            file.parent.mkdir(parents=True, exist_ok=True)
            with file.open('a+b') as stream:
                if stream.tell() == 0:
                    stream.write(b'0'); stream.flush()
                stream.seek(0)
                try: msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError: raise UpdateError('Another updater process is active. Wait for its result.') from None
                try: yield
                finally:
                    stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.lock.release()

    def operation(self, action, args):
        if not isinstance(args, dict):
            raise UpdateError('Invalid update arguments.')
        keys = {'status': set(), 'preferences': {'automatic_checks'}, 'check': {'automatic'}, 'approve': {'version', 'sha256'}, 'cancel': set()}
        if action not in keys or set(args) != keys[action]:
            raise UpdateError('Unknown update action or arguments.')
        if action == 'status':
            return self.status()  # Atomic snapshot read; no directories/files created.
        with self.exclusive():
            state = self.state()
            if action == 'preferences':
                if type(args['automatic_checks']) is not bool:
                    raise UpdateError('Automatic checks must be enabled or disabled explicitly.')
                state['automatic_checks'] = args['automatic_checks']
                self.save(state)
            elif action == 'cancel':
                if not state.get('approved') or state['approved']['stage'] != 'ready':
                    raise UpdateError('Only a not-yet-installed approved package can be cancelled.')
                state['approved']['stage'] = 'cancelled'
                self.save(state)  # Keep its archive and receipt; never silently delete files.
            elif action == 'check':
                if type(args['automatic']) is not bool:
                    raise UpdateError('Invalid automatic-check flag.')
                if args['automatic'] and (not state['automatic_checks'] or time.time() - (state.get('last_checked_at') or 0) < CHECK_INTERVAL):
                    return self.status()
                state['last_checked_at'] = time.time()
                self.save(state)  # Persist the attempt before I/O, even if a response/receipt fails.
                try:
                    state['latest'] = latest_release()
                    state['last_error'] = None
                except Exception as error:
                    state['last_error'] = str(error) if isinstance(error, UpdateError) else 'The release check failed safely. Try a manual check later; no installation was changed.'
                self.save(state)
            elif action == 'approve':
                previous = state.get('approved')
                if previous and previous.get('stage') in ('ready', 'extracted'):
                    raise UpdateError('An approved installation is already pending. Inspect its outcome or cancel the ready package first.')
                latest = state.get('latest')
                if not latest or not latest.get('package') or args['version'] != latest['version'] or args['sha256'] != latest['package']['sha256'] or version(latest['version']) <= version(self.current_version):
                    raise UpdateError('Check the available release and approve its exact package first.')
                if previous and previous.get('stage') == 'installed' and previous.get('release', {}).get('version') == latest['version']:
                    raise UpdateError('This release was already installed. Switch to its new folder; do not install it again from the old app.')
                history = state.get('history', [])
                if not isinstance(history, list) or len(history) >= 100:
                    raise UpdateError('The local updater receipt capacity was reached. Use a reviewed manual upgrade; old receipts were retained.')
                # Recheck the release immediately before download; never substitute changed bytes.
                current = latest_release()
                if current['tag'] != latest['tag'] or current['commit'] != latest['commit'] or current['package'] != latest['package']:
                    raise UpdateError('The release changed since review. Check for updates and review it again.')
                raw = get_bytes(latest['package']['url'], MAX_PACKAGE, asset=True)
                verify_package(raw, latest)
                identifier = secrets.token_hex(16)
                target = safe_path(self.directory / (identifier + '.zip'))
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(raw)
                if previous:
                    state['history'] = [*history, previous]
                state['approved'] = {'id': identifier, 'release': latest, 'approved_at': time.time(), 'stage': 'ready', 'destination': str(self.root.parent / ('CivicRelay-v' + latest['version'] + '-' + identifier[:8]))}
                self.save(state)
            return self.status()

    def approved(self):
        approval = self.state().get('approved')
        if not isinstance(approval, dict) or not re.fullmatch(r'[0-9a-f]{32}', str(approval.get('id', ''))):
            raise UpdateError('No approved update is ready. Use Settings > Updates first.')
        release = approval.get('release', {})
        version(release.get('version'))
        expected = self.root.parent / ('CivicRelay-v' + release['version'] + '-' + approval['id'][:8])
        if approval.get('destination') != str(expected):
            raise UpdateError('The approved update destination changed. Nothing was installed.')
        if approval.get('stage') not in ('ready', 'extracted', 'failed', 'installed', 'cancelled'):
            raise UpdateError('The update installation state is invalid.')
        return approval, safe_path(expected)

    def extract(self):
        approval, destination = self.approved()
        if approval['stage'] != 'ready' or destination.exists():
            if approval['stage'] == 'ready':
                self.finish('failed')
            raise UpdateError('This update was already attempted or its destination exists. Nothing was overwritten; approve a new download to retry.')
        file = safe_path(self.directory / (approval['id'] + '.zip'))
        if file.stat().st_size > MAX_PACKAGE:
            raise UpdateError('The approved archive is oversized.')
        raw = file.read_bytes()
        try: manifest = verify_package(raw, approval['release'])
        except UpdateError:
            self.finish('failed')
            raise
        if len(str(destination)) > 150:
            raise UpdateError('The installation path is too long. Use the manual upgrade guide; nothing was installed.')
        destination.mkdir()
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                for name in [*manifest['files'], MANIFEST]:
                    target = safe_path(destination / name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open('xb') as stream:
                        stream.write(archive.read(name))
            self.finish('extracted')
            return str(destination)
        except Exception:
            self.finish('failed')
            raise UpdateError('Extraction did not complete. The old installation is untouched; the incomplete new folder was retained for review.') from None

    def finish(self, stage):
        approval, _ = self.approved()
        transitions = {'extracted': {'ready'}, 'installed': {'extracted'}, 'failed': {'ready', 'extracted'}}
        if stage not in transitions or approval['stage'] not in transitions[stage]:
            raise UpdateError('The update completion state was refused.')
        state = self.state()
        state['approved']['stage'] = stage
        self.save(state)
