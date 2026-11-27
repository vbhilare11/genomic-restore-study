"""Upload a fresh synthetic dataset and request archival of its payload."""
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from azure_smoke import ROOT, run


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    env = os.environ.copy()
    env["AZURE_CONFIG_DIR"] = str(
        Path.home() / ".azure-genomic-restore-study"
    )
    source = ROOT / "data" / "synthetic"
    run([sys.executable, "src/validate_dataset.py", str(source)], env)

    manifest_bytes = (source / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    entries = manifest["files"]

    # Restrict this initial experiment to the known six-file fixture.
    expected = {
        f"sample_{sample:03d}_R{mate}.fastq"
        for sample in range(1, 4)
        for mate in (1, 2)
    }
    if (
        len(entries) != 6
        or {entry["path"] for entry in entries} != expected
        or sum(entry["size_bytes"] for entry in entries) != 136800
    ):
        raise ValueError("This experiment requires the original small fixture")

    storage = json.loads(run(
        [
            "terraform", "-chdir=infra/environments/research",
            "output", "-json", "research_storage",
        ],
        env, capture=True,
    ))
    subscription = storage["storage_account_id"].split("/")[2]
    run(["az", "account", "set", "--subscription", subscription], env)

    experiment_id = uuid.uuid4().hex[:12]
    prefix = f"archive/{experiment_id}"
    folder = ROOT / "results" / f"archive-prepare-{experiment_id}"
    folder.mkdir(parents=True, exist_ok=False)
    report_path = folder / "report.json"

    report = {
        "experiment_id": experiment_id,
        "started_at": now(),
        "git_commit": run(
            ["git", "rev-parse", "HEAD"], env, capture=True
        ).strip(),
        "prefix": prefix,
        "storage": storage,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "manifest": manifest,
        "status": "in_progress",
        "archive_requests": [],
    }

    common = [
        "--account-name", storage["storage_account_name"],
        "--auth-mode", "login",
        "--output", "json",
    ]

    def save():
        report_path.write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )

    save()
    try:
        run(
            [
                "az", "storage", "blob", "upload-batch",
                "--destination", storage["container_name"],
                "--destination-path", prefix,
                "--source", str(source),
                "--overwrite", "false",
                "--tier", "Hot",
                *common,
            ],
            env,
        )
        report["upload_completed_at"] = now()
        save()

        for entry in entries:
            name = f"{prefix}/{entry['path']}"
            request = {
                "blob": name,
                "requested_at": now(),
                "status": "request_started",
            }
            report["archive_requests"].append(request)
            save()

            run(
                [
                    "az", "storage", "blob", "set-tier",
                    "--container-name", storage["container_name"],
                    "--name", name,
                    "--tier", "Archive",
                    *common,
                ],
                env,
            )
            request["status"] = "request_succeeded"
            request["response_received_at"] = now()
            save()
            print(f"Archive request succeeded: {name}", flush=True)

        report["status"] = "archive_requests_succeeded"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        report["finished_at"] = now()
        save()
        print(f"Report: {report_path}", flush=True)

    print(f"\nInspect with: python src/archive_status.py --prefix {prefix}")
    print("Manifest retained in Hot. Confirm payload tiers before rehydration.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
