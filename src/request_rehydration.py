"""Request Standard-priority rehydration for a prepared small experiment."""
import argparse
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from azure_smoke import ROOT, run


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preparation", type=Path, required=True)
    args = parser.parse_args()

    preparation = json.loads(args.preparation.read_text())
    if preparation["status"] != "archive_requests_succeeded":
        raise ValueError("Preparation did not complete successfully")

    storage = preparation["storage"]
    prefix = preparation["prefix"]
    manifest = preparation["manifest"]
    source_manifest = ROOT / "data/synthetic/manifest.json"
    if hashlib.sha256(source_manifest.read_bytes()).hexdigest() != preparation["manifest_sha256"]:
        raise ValueError("Local manifest differs from the preparation record")

    env = os.environ.copy()
    env["AZURE_CONFIG_DIR"] = str(
        Path.home() / ".azure-genomic-restore-study"
    )
    subscription = storage["storage_account_id"].split("/")[2]
    run(["az", "account", "set", "--subscription", subscription], env)

    common = [
        "--account-name", storage["storage_account_name"],
        "--auth-mode", "login",
        "--output", "json",
    ]
    blobs = json.loads(run(
        [
            "az", "storage", "blob", "list",
            "--container-name", storage["container_name"],
            "--prefix", prefix + "/",
            *common,
        ],
        env, capture=True,
    ))
    inventory = {blob["name"]: blob for blob in blobs}
    expected = {f"{prefix}/{entry['path']}" for entry in manifest["files"]}
    if set(inventory) != expected | {f"{prefix}/manifest.json"}:
        raise ValueError("Remote inventory differs from the prepared dataset")

    manifest_properties = inventory[f"{prefix}/manifest.json"]["properties"]
    if (
        manifest_properties.get("blobTier") != "Hot"
        or manifest_properties.get("archiveStatus")
    ):
        raise ValueError("Remote manifest must remain Hot with no pending operation")

    actions = []
    for entry in manifest["files"]:
        name = f"{prefix}/{entry['path']}"
        properties = inventory[name]["properties"]
        if properties.get("contentLength") != entry["size_bytes"]:
            raise ValueError(f"Remote size differs: {name}")
        tier = properties.get("blobTier")
        pending = properties.get("archiveStatus")
        if tier == "Hot" and not pending:
            action = "already_hot"
        elif tier == "Archive" and pending == "rehydrate-pending-to-hot":
            action = "already_pending"
        elif tier == "Archive" and not pending:
            action = "request_rehydration"
        else:
            raise ValueError(f"Unexpected state: {name}: {tier}, {pending}")
        actions.append({"blob": name, "action": action})

    folder = ROOT / "results" / (
        f"rehydration-request-{preparation['experiment_id']}-"
        + uuid.uuid4().hex[:8]
    )
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / "report.json"
    report = {
        "prefix": prefix,
        "started_at": now(),
        "git_commit": run(
            ["git", "rev-parse", "HEAD"], env, capture=True
        ).strip(),
        "priority": "Standard",
        "target_tier": "Hot",
        "status": "in_progress",
        "actions": actions,
    }

    def save():
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(path)

    save()
    try:
        for item in actions:
            if item["action"] == "request_rehydration":
                item["requested_at"] = now()
                item["result"] = "request_started"
                save()
                run(
                    [
                        "az", "storage", "blob", "set-tier",
                        "--container-name", storage["container_name"],
                        "--name", item["blob"],
                        "--tier", "Hot",
                        "--rehydrate-priority", "Standard",
                        *common,
                    ],
                    env,
                )
                item["result"] = "request_succeeded"
                item["response_received_at"] = now()
                save()
            print(f"{item['action']}: {item['blob']}", flush=True)
        report["status"] = "requests_processed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        report["finished_at"] = now()
        save()
        print(f"Report: {path}", flush=True)

    print("Requests processed. Dataset readiness has NOT been verified.")


if __name__ == "__main__":
    main()
