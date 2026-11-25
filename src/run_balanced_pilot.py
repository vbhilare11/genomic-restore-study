import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from compare_local import SOURCE, attempt
from validate_dataset import validate

ROOT = Path(__file__).resolve().parents[1]


def git_output(*arguments):
    return subprocess.run(
        ["git", *arguments],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()


def main():
    manifest_path = SOURCE / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    entries = manifest["files"]

    # Preflight outside measured attempts; both strategies then perform
    # their own measured source verification inside attempt().
    if validate(SOURCE) != 0:
        raise SystemExit("Source validation failed")

    paths = [entry["path"] for entry in entries]
    if not entries or len(set(paths)) != len(paths):
        raise ValueError("Empty manifest or duplicate paths")

    pairs = {}
    for entry in entries:
        name = entry["path"]
        if (
            not isinstance(name, str)
            or name in ("", ".", "..")
            or Path(name).name != name
            or entry["size_bytes"] <= 0
        ):
            raise ValueError("Unsupported fixture entry")
        pairs.setdefault(entry["sample_id"], []).append(entry["mate"])

    if any(sorted(mates) != [1, 2] for mates in pairs.values()):
        raise ValueError("Expected one R1/R2 pair per sample")

    total = sum(entry["size_bytes"] for entry in entries)
    hashes = {}
    for name in ("measured_io.py", "compare_local.py",
                 "validate_dataset.py", "run_balanced_pilot.py"):
        hashes[name] = hashlib.sha256(
            (ROOT / "src" / name).read_bytes()
        ).hexdigest()

    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    run_folder = Path(tempfile.mkdtemp(prefix="balanced-", dir=results))

    report = {
        "purpose": "Balanced local accounting pilot",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "git_commit": git_output("rev-parse", "HEAD"),
        "git_status_at_start": git_output("status", "--porcelain"),
        "source_code_sha256": hashes,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "manifest": manifest,
        "preflight_outside_measurements": True,
        "cache_control": "None",
        "trials": [],
    }

    with tempfile.TemporaryDirectory(prefix="balanced-work-") as work:
        for percent in (0, 25, 50, 75):
            threshold = None if percent == 0 else total * percent // 100
            completed_count = 0
            completed_bytes = 0
            cumulative = 0

            if threshold is not None:
                for entry in entries:
                    cumulative += entry["size_bytes"]
                    if cumulative >= threshold:
                        break
                    completed_count += 1
                    completed_bytes += entry["size_bytes"]

            for block, order in enumerate(
                (("restart", "resume"), ("resume", "restart")), start=1
            ):
                for position, strategy in enumerate(order, start=1):
                    destination = (
                        Path(work) / f"p{percent}-b{block}-{strategy}"
                    )
                    initial = attempt(
                        SOURCE, destination, entries, strategy,
                        fail_after=threshold,
                    )
                    recovery = None

                    if threshold is None:
                        checks = {
                            "ready": initial["ready"],
                            "no_error": initial["error"] is None,
                            "not_interrupted": not initial["interrupted"],
                            "copied_all": initial["copied_files"] == len(entries),
                            "skipped_none": initial["skipped_files"] == 0,
                            "written_bytes": (
                                initial["copy"]["bytes_written"] == total
                            ),
                        }
                    else:
                        recovery = attempt(
                            SOURCE, destination, entries, strategy,
                        )
                        skipped = (
                            completed_count if strategy == "resume" else 0
                        )
                        recovery_bytes = total - (
                            completed_bytes if strategy == "resume" else 0
                        )
                        checks = {
                            "interrupted": initial["interrupted"],
                            "not_ready_initially": not initial["ready"],
                            "initial_bytes": (
                                initial["copy"]["bytes_written"] == threshold
                            ),
                            "initial_completed": (
                                initial["copied_files"] == completed_count
                            ),
                            "recovered": recovery["ready"],
                            "no_recovery_error": recovery["error"] is None,
                            "recovery_bytes": (
                                recovery["copy"]["bytes_written"]
                                == recovery_bytes
                            ),
                            "skipped_files": recovery["skipped_files"] == skipped,
                            "copied_files": (
                                recovery["copied_files"] == len(entries) - skipped
                            ),
                        }

                    attempts = [initial]
                    if recovery is not None:
                        attempts.append(recovery)

                    trial = {
                        "interruption_percent": percent,
                        "order_block": block,
                        "position_in_block": position,
                        "strategy": strategy,
                        "initial": initial,
                        "recovery": recovery,
                        "total_bytes_written": sum(
                            item["copy"]["bytes_written"] for item in attempts
                        ),
                        "checks": checks,
                        "passed": all(checks.values()),
                    }
                    report["trials"].append(trial)
                    label = "PASS" if trial["passed"] else "FAIL"
                    print(
                        f"{label}: {percent}% block={block} "
                        f"position={position} {strategy}; "
                        f"written={trial['total_bytes_written']:,}"
                    )

    report["all_passed"] = all(
        trial["passed"] for trial in report["trials"]
    )
    path = run_folder / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nReport saved: {path}")

    if not report["all_passed"]:
        raise SystemExit("FAIL: inspect saved trial checks")
    print("PASS: all 16 balanced pilot trials passed.")


if __name__ == "__main__":
    main()
