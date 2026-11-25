import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from measured_io import CopyMetrics, InjectedInterruption, copy_measured


def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")


with tempfile.TemporaryDirectory(prefix="measured-copy-") as temporary:
    folder = Path(temporary)
    source = folder / "source.bin"
    source.write_bytes(bytes(range(100)))

    for threshold in (0, 35, 100):
        destination = folder / f"partial-{threshold}.bin"
        metrics = CopyMetrics()
        interrupted = False

        try:
            copy_measured(
                source,
                destination,
                metrics,
                fail_after_bytes=threshold,
                chunk_size=16,
            )
        except InjectedInterruption:
            interrupted = True

        require(interrupted, f"no interruption at {threshold}")
        require(metrics.bytes_read == threshold, "incorrect read count")
        require(metrics.bytes_written == threshold, "incorrect write count")
        require(
            destination.read_bytes() == source.read_bytes()[:threshold],
            "partial output does not match the expected source prefix",
        )
        print(f"PASS: interruption at {threshold} bytes counted correctly.")

    destination = folder / "complete.bin"
    metrics = CopyMetrics()
    copy_measured(source, destination, metrics, chunk_size=16)

    require(destination.read_bytes() == source.read_bytes(), "copy differs")
    require(metrics.bytes_read == 100, "incorrect complete read count")
    require(metrics.bytes_written == 100, "incorrect complete write count")

print("PASS: complete copy verified; read=100 bytes, written=100 bytes.")
