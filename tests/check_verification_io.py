import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from measured_io import VerificationMetrics, sha256_measured

with tempfile.TemporaryDirectory(prefix="verification-check-") as temporary:
    path = Path(temporary) / "fixture.bin"

    for content in (b"", bytes(range(100))):
        path.write_bytes(content)
        metrics = VerificationMetrics()
        expected = hashlib.sha256(content).hexdigest()

        for attempt in range(1, 3):
            actual = sha256_measured(path, metrics, chunk_size=16)

            if actual != expected:
                raise SystemExit("FAIL: incorrect checksum")
            if metrics.bytes_read != len(content) * attempt:
                raise SystemExit("FAIL: incorrect cumulative byte count")

        print(
            f"PASS: {len(content)}-byte file verified twice; "
            f"counted {metrics.bytes_read} bytes."
        )
