import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from verified_delivery import deliver_verified

SOURCE = ROOT / 'data/synthetic'
manifest_bytes = (SOURCE / 'manifest.json').read_bytes()
digest = hashlib.sha256(manifest_bytes).hexdigest()
first_payload = json.loads(manifest_bytes)['files'][0]['path']


def require(condition, message):
    if not condition:
        raise SystemExit('FAIL: ' + message)


with tempfile.TemporaryDirectory() as temporary:
    for case in ('intact', 'interrupted', 'missing_payload', 'corrupt_payload',
                 'changed_manifest', 'extra_file', 'symlink'):
        root = Path(temporary) / case

        def transfer(staging):
            if case == 'interrupted':
                (staging / first_payload).write_bytes(b'partial')
                raise OSError('Injected transfer interruption')
            shutil.copytree(SOURCE, staging, dirs_exist_ok=True)
            payload = staging / first_payload
            if case == 'missing_payload':
                payload.unlink()
            elif case == 'corrupt_payload':
                content = bytearray(payload.read_bytes())
                content[0] ^= 1
                payload.write_bytes(content)
            elif case == 'changed_manifest':
                path = staging / 'manifest.json'
                path.write_bytes(path.read_bytes() + b'\n')
            elif case == 'extra_file':
                (staging / 'unexpected.txt').write_text('extra')
            elif case == 'symlink':
                payload.unlink()
                payload.symlink_to(SOURCE / first_payload)

        result = deliver_verified(root, digest, transfer)
        if case == 'intact':
            require(result['status'] == 'READY', 'intact delivery failed')
            artifact = Path(result['artifact_directory'])
            require(artifact.is_dir(), 'published artifact missing')
            require(not Path(result['staging_directory']).exists(), 'staging was not promoted')
            require((artifact / 'manifest.json').read_bytes() == manifest_bytes, 'published manifest differs')
            require(result['verified_files'] == 6, 'wrong verified file count')
        else:
            require(result['status'] == 'FAILED', case + ': failure was accepted')
            require('artifact_directory' not in result, case + ': artifact published')
            require(not list(root.glob('verified-*')), case + ': published directory exists')
            require(Path(result['staging_directory']).is_dir(), case + ': staging evidence lost')
        print('PASS: ' + case)

require((SOURCE / 'manifest.json').read_bytes() == manifest_bytes, 'source manifest changed')
print('PASS: verified publication and six failure cases checked.')
