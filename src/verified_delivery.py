"""Stage, verify, and publish a local dataset using a pinned manifest digest."""
import contextlib
import hashlib
import io
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from validate_dataset import validate


def now():
    return datetime.now(timezone.utc).isoformat()


def deliver_verified(output_root, manifest_sha256, transfer):
    """transfer(staging) writes into a fresh directory; failures retain staging.

    A READY result applies only to the published local artifact. This function
    does not implement transfer retries, resume, or durable job-state updates.
    """
    if not isinstance(manifest_sha256, str) or not re.fullmatch(
        r'[a-f0-9]{64}', manifest_sha256
    ):
        raise ValueError('Expected a lowercase SHA-256 manifest digest')
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.partial-', dir=output_root))
    published = output_root / ('verified-' + staging.name.removeprefix('.partial-'))
    result = {'status': 'FAILED', 'started_at': now(),
              'manifest_sha256': manifest_sha256, 'staging_directory': str(staging)}
    try:
        transfer(staging)
        result['transfer_completed_at'] = now()
        # Reject symlinks before opening the downloaded manifest or payloads.
        if any(path.is_symlink() for path in staging.rglob('*')):
            raise ValueError('Symlinks are not allowed in the staged dataset')
        manifest_bytes = (staging / 'manifest.json').read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != manifest_sha256:
            raise ValueError('Manifest digest differs from the pinned reference')
        manifest = json.loads(manifest_bytes)
        paths = [entry['path'] for entry in manifest['files']]
        if not paths or len(paths) != len(set(paths)):
            raise ValueError('Manifest must contain nonempty, unique payload paths')
        for name in paths:
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Unsafe payload path')
        expected = set(paths) | {'manifest.json'}
        actual = {str(path.relative_to(staging))
                  for path in staging.rglob('*') if path.is_file()}
        if actual != expected:
            raise ValueError('Staged file inventory differs from manifest')
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            status = validate(staging)
        result['validation_output'] = captured.getvalue()
        if status != 0:
            raise ValueError('Payload completeness or checksum validation failed')
        result['verified_files'] = len(paths)
        result['verified_at'] = now()
        staging.rename(published)
        result['artifact_directory'] = str(published)
        result['status'] = 'READY'
    except Exception as error:
        result['error'] = str(error)
    result['finished_at'] = now()
    return result
