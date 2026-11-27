"""Check current Azure availability, then download and verify the dataset."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from archive_gate import evaluate
from azure_smoke import ROOT, run


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preparation", type=Path, required=True)
    args = parser.parse_args()

    preparation = json.loads(args.preparation.read_text())
    prefix = preparation["prefix"]
    if not re.fullmatch(r"archive/[a-f0-9]{12}", prefix):
        raise ValueError("Unexpected experiment prefix")
    if preparation["status"] != "archive_requests_succeeded":
        raise ValueError("Preparation did not complete successfully")

    storage = preparation["storage"]
    env = os.environ.copy()
    env["AZURE_CONFIG_DIR"] = str(
        Path.home() / ".azure-genomic-restore-study"
    )

    attempt_id = uuid.uuid4().hex[:12]
    folder = ROOT / "results" / f"archive-restore-{attempt_id}"
    folder.mkdir(parents=True, exist_ok=False)
    report_path = folder / "report.json"
    report = {
        "started_at": now(),
        "prefix": prefix,
        "status": "in_progress",
        "storage": storage,
        "manifest_sha256": preparation["manifest_sha256"],
    }

    def save():
        temporary = report_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(report_path)

    save()
    try:
        report["git_commit"] = run(
            ["git", "rev-parse", "HEAD"], env, capture=True
        ).strip()
        report["git_status"] = run(
            ["git", "status", "--porcelain"], env, capture=True
        )

        subscription = storage["storage_account_id"].split("/")[2]
        run(["az", "account", "set", "--subscription", subscription], env)
        common = [
            "--account-name", storage["storage_account_name"],
            "--auth-mode", "login",
            "--output", "json",
        ]

        observation = {
            "prefix": prefix,
            "storage_account": storage["storage_account_name"],
            "container": storage["container_name"],
            "observation_started_at": now(),
        }
        observation["blobs"] = json.loads(run(
            [
                "az", "storage", "blob", "list",
                "--container-name", storage["container_name"],
                "--prefix", prefix + "/",
                *common,
            ],
            env, capture=True,
        ))
        observation["observed_at"] = now()
        report["observation"] = observation
        report["blockers"] = evaluate(preparation, observation)
        save()

        if report["blockers"]:
            report["status"] = "blocked"
            print("BLOCKED: no download attempted.")
            for problem in report["blockers"]:
                print(f"  - {problem}")
            return 2

        destination = ROOT / "data/archive-restored" / attempt_id
        destination.mkdir(parents=True, exist_ok=False)
        report["download_started_at"] = now()
        save()

        run(
            [
                "az", "storage", "blob", "download-batch",
                "--source", storage["container_name"],
                "--pattern", prefix + "/*",
                "--destination", str(destination),
                *common,
            ],
            env,
        )
        report["download_completed_at"] = now()
        restored = destination / prefix
        manifest_bytes = (restored / "manifest.json").read_bytes()

        if hashlib.sha256(manifest_bytes).hexdigest() != preparation["manifest_sha256"]:
            raise ValueError("Downloaded manifest differs from preparation")
        if json.loads(manifest_bytes) != preparation["manifest"]:
            raise ValueError("Downloaded manifest contents differ")

        run(
            [sys.executable, "src/validate_dataset.py", str(restored)],
            env,
        )
        report["status"] = "verified"
        report["verified_at"] = now()
        report["verified_files"] = len(preparation["manifest"]["files"])
        report["restored_directory"] = str(restored.relative_to(ROOT))
        return 0

    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        report["status"] = "failed"
        report["error"] = str(error)
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    finally:
        report["finished_at"] = now()
        save()
        print(f"Report: {report_path}")
        if report["status"] == "verified":
            print("READY: downloaded dataset matches the prepared manifest.")


if __name__ == "__main__":
    sys.exit(main())
