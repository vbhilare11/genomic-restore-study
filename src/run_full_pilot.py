import csv
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    batch = Path(tempfile.mkdtemp(prefix="full-pilot-", dir=results))
    logs = batch / "logs"
    logs.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=ROOT,
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Local correctness and accounting pilot",
        "python": sys.version,
        "platform": platform.platform(),
        "git_commit": git("rev-parse", "HEAD"),
        "git_status_at_start": git("status", "--porcelain"),
        "cache_control": "None",
        "file_order": "Manifest order; not randomized",
        "source_hashes": {
            str(path.relative_to(ROOT)): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for directory in ("src", "tests")
            for path in sorted((ROOT / directory).glob("*.py"))
        },
        "all_passed": False,
    }
    rows = []
    checks_passed = 0

    def run_step(label, command):
        process = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True,
        )
        log_path = logs / f"{label}.log"
        log_path.write_text(
            "STDOUT\n" + process.stdout
            + "\nSTDERR\n" + process.stderr,
            encoding="utf-8",
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"{label} exited with {process.returncode}; log: {log_path}"
            )
        return process.stdout

    try:
        checks = (
            "check_validation.py",
            "check_interrupted_restore.py",
            "check_resume.py",
            "check_corruption_repair.py",
            "check_measured_io.py",
            "check_verification_io.py",
        )

        for filename in checks:
            run_step(
                Path(filename).stem,
                [sys.executable, str(ROOT / "tests" / filename)],
            )
            checks_passed += 1

        print(f"PASS: {checks_passed} existing check scripts.", flush=True)

        payload_sizes = []
        for name in ("many-small", "few-large", "mixed"):
            source = ROOT / "data" / "workloads-v1" / name

            # Run the existing balanced runner in a fresh process.
            # Only its input dataset changes; both strategies share it.
            command = [
                sys.executable, "-c",
                (
                    "import sys; from pathlib import Path; "
                    "sys.path.insert(0, 'src'); "
                    "import run_balanced_pilot as runner; "
                    "runner.SOURCE = Path(sys.argv[1]); "
                    "runner.main()"
                ),
                str(source),
            ]
            output = run_step(f"workload-{name}", command)

            report_lines = [
                line.removeprefix("Report saved: ")
                for line in output.splitlines()
                if line.startswith("Report saved: ")
            ]
            if len(report_lines) != 1:
                raise RuntimeError(f"{name}: report path not found")

            original_path = Path(report_lines[0])
            report = json.loads(original_path.read_text(encoding="utf-8"))

            # Retain a copy inside this batch for convenient sharing.
            (batch / f"{name}.json").write_text(
                json.dumps(report, indent=2) + "\n",
                encoding="utf-8",
            )

            trials = report["trials"]
            if len(trials) != 16 or not report["all_passed"]:
                raise RuntimeError(f"{name}: expected 16 passing trials")
            if not all(
                trial["passed"] and all(trial["checks"].values())
                for trial in trials
            ):
                raise RuntimeError(f"{name}: a saved trial check failed")

            payload_sizes.append(sum(
                entry["size_bytes"]
                for entry in report["manifest"]["files"]
            ))

            for trial in trials:
                attempts = [trial["initial"]]
                if trial["recovery"] is not None:
                    attempts.append(trial["recovery"])

                rows.append({
                    "workload": name,
                    "interruption_percent": trial["interruption_percent"],
                    "order_block": trial["order_block"],
                    "position_in_block": trial["position_in_block"],
                    "strategy": trial["strategy"],
                    "passed": trial["passed"],
                    "total_bytes_written": sum(
                        item["copy"]["bytes_written"] for item in attempts
                    ),
                    "copy_bytes_read": sum(
                        item["copy"]["bytes_read"] for item in attempts
                    ),
                    "source_checksum_bytes_read": sum(
                        item["source_verification"]["bytes_read"]
                        for item in attempts
                    ),
                    "destination_checksum_bytes_read": sum(
                        item["destination_verification"]["bytes_read"]
                        for item in attempts
                    ),
                    "initial_seconds": trial["initial"]["elapsed_seconds"],
                    "recovery_seconds": (
                        trial["recovery"]["elapsed_seconds"]
                        if trial["recovery"] is not None else ""
                    ),
                    "recovery_skipped_files": (
                        trial["recovery"]["skipped_files"]
                        if trial["recovery"] is not None else ""
                    ),
                })

            print(f"PASS: {name} — 16/16 trials.", flush=True)

        if len(set(payload_sizes)) != 1:
            raise RuntimeError("Workload payload totals differ")
        if len(rows) != 48:
            raise RuntimeError(f"Expected 48 trials, found {len(rows)}")

        metadata["all_passed"] = True
        metadata["payload_bytes_per_workload"] = payload_sizes[0]

    except Exception as error:
        metadata["error"] = str(error)

    finally:
        metadata["check_scripts_passed"] = checks_passed
        metadata["trials_collected"] = len(rows)

        if rows:
            with (batch / "summary.csv").open(
                "w", newline="", encoding="utf-8",
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)

        (batch / "batch.json").write_text(
            json.dumps(metadata, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"\nResults folder: {batch}")
    if not metadata["all_passed"]:
        print(f"FAIL: {metadata.get('error', 'Unknown failure')}")
        raise SystemExit(1)

    print("PASS: all 48 pilot trials completed.")
    print("Saved: summary.csv, batch.json, 3 workload reports, and logs.")
    print("These are local accounting checks, not cloud cost findings.")


if __name__ == "__main__":
    main()
