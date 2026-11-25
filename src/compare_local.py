import json
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from measured_io import (
    CopyMetrics,
    VerificationMetrics,
    InjectedInterruption,
    copy_measured,
    sha256_measured,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "synthetic"


def matches(path, entry, metrics):
    if not path.is_file():
        return False
    if path.stat().st_size != entry["size_bytes"]:
        return False
    return sha256_measured(path, metrics) == entry["sha256"]


def attempt(source, destination, entries, strategy, fail_after=None):
    copy_metrics = CopyMetrics()
    source_checks = VerificationMetrics()
    destination_checks = VerificationMetrics()

    result = {
        "strategy": strategy,
        "ready": False,
        "interrupted": False,
        "error": None,
        "copied_files": 0,
        "skipped_files": 0,
    }
    started = time.perf_counter()

    try:
        # Validate every source file on every attempt for both strategies.
        for entry in entries:
            if not matches(source / entry["path"], entry, source_checks):
                raise ValueError(f"Invalid source file: {entry['path']}")

        destination.mkdir(parents=True, exist_ok=True)

        for entry in entries:
            target = destination / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)

            if strategy == "resume":
                if matches(target, entry, destination_checks):
                    result["skipped_files"] += 1
                    continue

            partial = target.with_name(target.name + ".part")
            remaining = (
                None if fail_after is None
                else fail_after - copy_metrics.bytes_written
            )

            copy_measured(
                source / entry["path"],
                partial,
                copy_metrics,
                fail_after_bytes=remaining,
            )

            if not matches(partial, entry, destination_checks):
                raise ValueError(f"Invalid copied file: {entry['path']}")

            partial.replace(target)
            result["copied_files"] += 1

        # Both strategies must pass the same final file checks.
        for entry in entries:
            if not matches(destination / entry["path"], entry, destination_checks):
                raise ValueError(f"Final verification failed: {entry['path']}")

        result["ready"] = True

    except InjectedInterruption as error:
        result["interrupted"] = True
        result["error"] = str(error)
    except (OSError, ValueError) as error:
        result["error"] = str(error)
    finally:
        result["elapsed_seconds"] = time.perf_counter() - started
        result["copy"] = asdict(copy_metrics)
        result["source_verification"] = asdict(source_checks)
        result["destination_verification"] = asdict(destination_checks)

    return result


def main():
    manifest = json.loads(
        (SOURCE / "manifest.json").read_text(encoding="utf-8")
    )
    entries = manifest["files"]

    # This pilot accepts only our flat, generated fixture manifest.
    if not entries:
        raise ValueError("Empty manifest")
    paths = [entry["path"] for entry in entries]
    if len(set(paths)) != len(paths):
        raise ValueError("Duplicate manifest paths")
    for name in paths:
        if (
            not isinstance(name, str)
            or name in ("", ".", "..")
            or Path(name).name != name
        ):
            raise ValueError(f"Unsupported fixture path: {name}")

    pairs = {}
    for entry in entries:
        pairs.setdefault(entry["sample_id"], []).append(entry["mate"])
    if any(sorted(mates) != [1, 2] for mates in pairs.values()):
        raise ValueError("Manifest must contain one R1/R2 pair per sample")

    total_bytes = sum(entry["size_bytes"] for entry in entries)
    threshold = total_bytes // 4
    if threshold <= 0:
        raise ValueError("Dataset is too small for this interruption")

    report = {
        "experiment": "local-pilot-25-percent-interruption",
        "dataset_bytes": total_bytes,
        "interruption_after_bytes": threshold,
        "trials": [],
    }

    with tempfile.TemporaryDirectory(prefix="restore-comparison-") as temporary:
        for strategy in ("restart", "resume"):
            destination = Path(temporary) / strategy
            first = attempt(
                SOURCE, destination, entries, strategy,
                fail_after=threshold,
            )
            recovery = attempt(SOURCE, destination, entries, strategy)

            report["trials"].append({
                "strategy": strategy,
                "initial": first,
                "recovery": recovery,
                "total_bytes_written": (
                    first["copy"]["bytes_written"]
                    + recovery["copy"]["bytes_written"]
                ),
            })

    print(json.dumps(report, indent=2))

    for trial in report["trials"]:
        if (
            not trial["initial"]["interrupted"]
            or trial["initial"]["ready"]
            or not trial["recovery"]["ready"]
        ):
            raise SystemExit("FAIL: unexpected trial outcome")

    print("\nPASS: both strategies recovered and verified the dataset.")


if __name__ == "__main__":
    main()
