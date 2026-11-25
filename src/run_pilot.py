import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from compare_local import SOURCE, attempt

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads(
        (SOURCE / "manifest.json").read_text(encoding="utf-8")
    )
    entries = manifest["files"]
    sizes = [entry["size_bytes"] for entry in entries]
    total = sum(sizes)

    if not entries or any(size <= 0 for size in sizes):
        raise ValueError("Expected nonempty files in the fixture")

    paths = [entry["path"] for entry in entries]
    if len(set(paths)) != len(paths):
        raise ValueError("Duplicate paths")
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
        raise ValueError("Expected one R1/R2 pair per sample")

    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    run_folder = Path(tempfile.mkdtemp(prefix="pilot-", dir=results))

    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()

    report = {
        "purpose": "Local accounting checks, not performance conclusions",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "git_commit": revision,
        "git_status_at_start": dirty,
        "manifest": manifest,
        "trials": [],
    }

    all_passed = True

    with tempfile.TemporaryDirectory(prefix="pilot-work-") as work:
        for index, percent in enumerate((25, 50, 75)):
            threshold = total * percent // 100
            if threshold <= 0:
                raise ValueError("Fixture too small")

            # A file is promoted only if copying returns successfully.
            # Reaching the failure threshold exactly still interrupts it.
            completed_bytes = 0
            completed_count = 0
            cumulative = 0
            for size in sizes:
                cumulative += size
                if cumulative < threshold:
                    completed_bytes += size
                    completed_count += 1
                else:
                    break

            order = (
                ("restart", "resume")
                if index % 2 == 0
                else ("resume", "restart")
            )

            for strategy in order:
                destination = Path(work) / f"{percent}-{strategy}"
                first = attempt(
                    SOURCE, destination, entries, strategy,
                    fail_after=threshold,
                )
                recovery = attempt(
                    SOURCE, destination, entries, strategy,
                )

                expected_skipped = (
                    completed_count if strategy == "resume" else 0
                )
                expected_recovery_bytes = total - (
                    completed_bytes if strategy == "resume" else 0
                )

                checks = {
                    "initial_interrupted": first["interrupted"],
                    "initial_not_ready": not first["ready"],
                    "initial_bytes": (
                        first["copy"]["bytes_written"] == threshold
                    ),
                    "initial_completed_files": (
                        first["copied_files"] == completed_count
                    ),
                    "recovery_ready": recovery["ready"],
                    "recovery_no_error": recovery["error"] is None,
                    "recovery_bytes": (
                        recovery["copy"]["bytes_written"]
                        == expected_recovery_bytes
                    ),
                    "recovery_skipped_files": (
                        recovery["skipped_files"] == expected_skipped
                    ),
                    "recovery_copied_files": (
                        recovery["copied_files"]
                        == len(entries) - expected_skipped
                    ),
                }

                passed = all(checks.values())
                all_passed = all_passed and passed
                written = (
                    first["copy"]["bytes_written"]
                    + recovery["copy"]["bytes_written"]
                )

                report["trials"].append({
                    "interruption_percent": percent,
                    "strategy": strategy,
                    "initial": first,
                    "recovery": recovery,
                    "total_bytes_written": written,
                    "checks": checks,
                    "passed": passed,
                })

                label = "PASS" if passed else "FAIL"
                print(
                    f"{label}: {percent}% {strategy}; "
                    f"total written={written:,}; "
                    f"recovery skipped={recovery['skipped_files']}"
                )

    report["all_passed"] = all_passed
    report_path = run_folder / "report.json"
    report_path.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8",
    )
    print(f"\nReport saved: {report_path}")

    if not all_passed:
        raise SystemExit("FAIL: inspect checks in the saved report")
    print("PASS: all 6 accounting checks completed.")


if __name__ == "__main__":
    main()
