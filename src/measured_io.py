from dataclasses import dataclass
from pathlib import Path


class InjectedInterruption(OSError):
    """A deliberately injected copy failure."""


@dataclass
class CopyMetrics:
    bytes_read: int = 0
    bytes_written: int = 0


def copy_measured(
    source: Path,
    destination: Path,
    metrics: CopyMetrics,
    *,
    fail_after_bytes: int | None = None,
    chunk_size: int = 1024 * 1024,
):
    """Copy a file, optionally failing after an exact number of bytes.

    The failure threshold is per call. Reaching the threshold raises an
    interruption, even when it coincides with the end of the source.
    Counters describe application-level I/O, not physical disk activity.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if fail_after_bytes is not None and fail_after_bytes < 0:
        raise ValueError("fail_after_bytes must be nonnegative")

    copied_this_call = 0

    with source.open("rb") as reader, destination.open("wb") as writer:
        while True:
            amount = chunk_size

            if fail_after_bytes is not None:
                remaining = fail_after_bytes - copied_this_call
                if remaining == 0:
                    raise InjectedInterruption(
                        f"Interrupted after {copied_this_call} bytes"
                    )
                amount = min(amount, remaining)

            content = reader.read(amount)
            metrics.bytes_read += len(content)

            if not content:
                return

            view = memoryview(content)
            while view:
                written = writer.write(view)
                if written is None or written <= 0:
                    raise OSError("Copy made no write progress")
                metrics.bytes_written += written
                copied_this_call += written
                view = view[written:]
