"""Verify a synthetic dataset round trip through Azure Hot storage."""
import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command, env, capture=False):
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    ).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--azure-config-dir",
        type=Path,
        default=Path.home() / ".azure-genomic-restore-study",
    )
    args = parser.parse_args()

    env = os.environ.copy()
    env["AZURE_CONFIG_DIR"] = str(args.azure_config_dir.expanduser())

    run_id = uuid.uuid4().hex[:12]
    prefix = f"smoke/{run_id}"
    destination = ROOT / "data" / "cloud-smoke" / run_id
    report_folder = ROOT / "results" / f"cloud-smoke-{run_id}"
    report_folder.mkdir(parents=True, exist_ok=False)

    report = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "experiment": "hot-tier-round-trip",
        "prefix": prefix,
        "status": "failed",
    }
    status = 1

    try:
        report["git_commit"] = run(
            ["git", "rev-parse", "HEAD"], env, capture=True
        ).strip()
        report["git_status"] = run(
            ["git", "status", "--porcelain"], env, capture=True
        )

        source = ROOT / "data" / "synthetic"
        run(
            [sys.executable, "src/validate_dataset.py", str(source)],
            env,
        )
        original_manifest = (source / "manifest.json").read_bytes()

        storage = json.loads(run(
            [
                "terraform", "-chdir=infra/environments/research",
                "output", "-json", "research_storage",
            ],
            env,
            capture=True,
        ))
        subscription = storage["storage_account_id"].split("/")[2]
        report["storage"] = storage
        report["subscription_id"] = subscription

        run(
            ["az", "account", "set", "--subscription", subscription],
            env,
        )

        common = [
            "--account-name", storage["storage_account_name"],
            "--auth-mode", "login",
            "--output", "json",
        ]

        print(f"Uploading to {prefix}", flush=True)
        run(
            [
                "az", "storage", "blob", "upload-batch",
                "--destination", storage["container_name"],
                "--destination-path", prefix,
                "--source", str(source),
                "--overwrite", "false",
                *common,
            ],
            env,
        )

        destination.mkdir(parents=True, exist_ok=False)
        run(
            [
                "az", "storage", "blob", "download-batch",
                "--source", storage["container_name"],
                "--pattern", f"{prefix}/*",
                "--destination", str(destination),
                *common,
            ],
            env,
        )

        restored = destination / prefix
        if (restored / "manifest.json").read_bytes() != original_manifest:
            raise ValueError("Downloaded manifest differs from original")

        run(
            [sys.executable, "src/validate_dataset.py", str(restored)],
            env,
        )

        manifest = json.loads(original_manifest)
        report["verified_files"] = len(manifest["files"])
        report["verified_payload_bytes"] = sum(
            entry["size_bytes"] for entry in manifest["files"]
        )
        report["status"] = "passed"
        status = 0
        print("PASS: Azure round trip and dataset integrity verified.")

    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        report["error"] = str(error)
        print(f"FAIL: {error}", file=sys.stderr)

    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        path = report_folder / "report.json"
        path.write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Report: {path}")

    return status


if __name__ == "__main__":
    sys.exit(main())
