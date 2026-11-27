"""Inspect blob tiers without changing remote data."""
import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

from azure_smoke import ROOT, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prefix", required=True,
        help="Exact dataset prefix, for example smoke/5978062d14ed",
    )
    args = parser.parse_args()
    prefix = args.prefix.strip("/")
    if not prefix:
        parser.error("A nonempty dataset prefix is required")

    env = os.environ.copy()
    env["AZURE_CONFIG_DIR"] = str(
        ROOT.home() / ".azure-genomic-restore-study"
    )

    storage = json.loads(run(
        [
            "terraform", "-chdir=infra/environments/research",
            "output", "-json", "research_storage",
        ],
        env, capture=True,
    ))
    subscription = storage["storage_account_id"].split("/")[2]
    run(["az", "account", "set", "--subscription", subscription], env)

    blobs = json.loads(run(
        [
            "az", "storage", "blob", "list",
            "--account-name", storage["storage_account_name"],
            "--container-name", storage["container_name"],
            "--prefix", prefix + "/",
            "--auth-mode", "login",
            "--output", "json",
        ],
        env, capture=True,
    ))

    report = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": run(
            ["git", "rev-parse", "HEAD"], env, capture=True
        ).strip(),
        "prefix": prefix,
        "storage_account": storage["storage_account_name"],
        "container": storage["container_name"],
        "blob_count": len(blobs),
        "blobs": blobs,
        "interpretation": (
            "Inventory observation only; not dataset readiness validation."
        ),
    }

    folder = ROOT / "results" / (
        "archive-status-" + uuid.uuid4().hex[:12]
    )
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    for blob in blobs:
        properties = blob.get("properties") or {}
        tier = properties.get("blobTier") or "unknown"
        pending = properties.get("rehydrationStatus") or "none reported"
        print(f"{blob['name']} | tier={tier} | archive_status={pending}")

    print(f"\nObserved {len(blobs)} blobs.")
    print(f"Report: {path}")
    if not blobs:
        print("FAIL: no blobs found for the supplied prefix.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
