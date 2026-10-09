"""Create a deterministic, source-only release asset from reviewed Git blobs."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'app'))
from updates import COMMIT, MANIFEST, public_path, safe_path, verify_package, version


def build(commit, files):
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit) or not isinstance(files, list) or len(files) != len(set(files)):
        raise ValueError('Invalid packaging inputs.')
    blobs = {}
    for name in sorted(files):
        public_path(name)
        blobs[name] = subprocess.check_output(['git', 'show', f'{commit}:{name}'], cwd=ROOT, timeout=20)
    release_version = json.loads(blobs['package.json'])['version']
    version(release_version)
    manifest = {'schema_version': 1, 'version': release_version, 'commit': commit,
        'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in blobs.items()}}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in {**blobs, MANIFEST: json.dumps(manifest, sort_keys=True).encode()}.items():
            item = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            item.create_system = 3
            item.external_attr = 0o100644 << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, raw)
    raw = buffer.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    release = {'version': release_version, 'commit': commit, 'package': {'size': len(raw), 'sha256': digest}}
    verify_package(raw, release)
    output = safe_path(ROOT / '.local' / 'release' / f'civicrelay-v{release_version}.zip')
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        if output.read_bytes() != raw:
            raise ValueError('An existing release asset has different bytes. Nothing was overwritten.')
    else:
        with output.open('xb') as stream:
            stream.write(raw)
    return {'version': release_version, 'commit': commit, 'asset': str(output), 'sha256': digest,
        'files': len(blobs), 'bytes': len(raw), 'private_data_included': False,
        'note': 'SHA-256 integrity is checked against the fixed official GitHub release; this is not a publisher-key signature.'}


if __name__ == '__main__':
    try:
        payload = json.load(sys.stdin)
        print(json.dumps(build(payload['commit'], payload['files'])))
    except Exception:
        print('Packaging stopped. Use a clean reviewed source commit and inspect the public file policy.', file=sys.stderr)
        sys.exit(1)
