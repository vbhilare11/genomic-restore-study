"""Controlled polling replay with real local fixture integrity checks."""
import contextlib
import copy
import io
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from archive_gate import evaluate
from validate_dataset import validate

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/synthetic"
TIMEOUT = 900

SCENARIOS = [
    {
        "name": "simultaneous",
        "available_at": [120] * 6,
        "expected": "verified",
    },
    {
        "name": "staggered",
        "available_at": [30, 60, 90, 120, 150, 180],
        "expected": "verified",
    },
    {
        "name": "one_unavailable",
        "available_at": [120] * 5 + [None],
        "expected": "timeout",
    },
    {
        "name": "temporary_observation_failure",
        "available_at": [120] * 6,
        "failure_window": [110, 190],
        "expected": "verified",
    },
    {
        "name": "temporarily_omitted_file",
        "available_at": [120] * 6,
        "omission_window": [110, 190],
        "expected": "verified",
    },
    {
        "name": "corrupt_payload",
        "available_at": [120] * 6,
        "corrupt": True,
        "expected": "verification_failed",
    },
]


def in_window(t, window):
    return window is not None and window[0] <= t < window[1]


def simulate(strategy, scenario, manifest):
    prefix = "replay/dataset"
    storage = {
        "storage_account_name": "replayaccount",
        "container_name": "replaycontainer",
    }
    preparation = {
        "prefix": prefix,
        "storage": storage,
        "manifest": manifest,
    }
    times = scenario["available_at"]
    all_available = None if None in times else max(times)
    trial = {
        "strategy": strategy,
        "scenario": scenario["name"],
        "status": "timeout",
        "logical_observation_attempts": 0,
        "failed_observations": 0,
        "observations": [],
        "all_available_at_virtual_seconds": all_available,
        "first_online_at_virtual_seconds": None,
        "detection_delay_virtual_seconds": None,
        "local_fixture_copy_attempts": 0,
        "premature_verified": False,
    }

    t = 0
    interval = 15
    with tempfile.TemporaryDirectory(prefix="polling-replay-") as temporary:
        while t <= TIMEOUT:
            trial["logical_observation_attempts"] += 1
            event = {"virtual_seconds": t}

            if in_window(t, scenario.get("failure_window")):
                trial["failed_observations"] += 1
                event["result"] = "observation_failed"
            else:
                blobs = [{
                    "name": f"{prefix}/manifest.json",
                    "properties": {
                        "blobTier": "Hot",
                        "rehydrationStatus": None,
                    },
                }]
                for entry, available_at in zip(manifest["files"], times):
                    online = available_at is not None and t >= available_at
                    blobs.append({
                        "name": f"{prefix}/{entry['path']}",
                        "properties": {
                            "blobTier": "Hot" if online else "Archive",
                            "rehydrationStatus": (
                                None if online else "rehydrate-pending-to-hot"
                            ),
                            "contentLength": entry["size_bytes"],
                        },
                    })

                if in_window(t, scenario.get("omission_window")):
                    blobs.pop()

                observation = {
                    "prefix": prefix,
                    "storage_account": storage["storage_account_name"],
                    "container": storage["container_name"],
                    "blobs": blobs,
                }
                blockers = evaluate(preparation, observation)
                event["result"] = "blocked" if blockers else "online_unverified"
                event["blockers"] = blockers

                if not blockers:
                    trial["first_online_at_virtual_seconds"] = t
                    if all_available is not None:
                        trial["detection_delay_virtual_seconds"] = t - all_available

                    trial["local_fixture_copy_attempts"] += 1
                    destination = Path(temporary) / "download"
                    shutil.copytree(SOURCE, destination)

                    if scenario.get("corrupt"):
                        target = destination / manifest["files"][0]["path"]
                        content = bytearray(target.read_bytes())
                        content[0] ^= 1
                        target.write_bytes(content)

                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        status = validate(destination)
                    trial["validation_output"] = output.getvalue()
                    trial["status"] = (
                        "verified" if status == 0 else "verification_failed"
                    )
                    trial["premature_verified"] = (
                        status == 0
                        and (all_available is None or t < all_available)
                    )
                    trial["observations"].append(event)
                    break

            trial["observations"].append(event)
            if strategy == "fixed":
                t += 60
            else:
                t += interval
                interval = min(interval * 2, 300)

    trial["timeout_virtual_seconds"] = TIMEOUT
    trial["passed"] = (
        trial["status"] == scenario["expected"]
        and not trial["premature_verified"]
    )
    return trial


def main():
    if validate(SOURCE) != 0:
        raise SystemExit("Source fixture validation failed")

    manifest = json.loads((SOURCE / "manifest.json").read_text())
    if (
        len(manifest["files"]) != 6
        or sum(e["size_bytes"] for e in manifest["files"]) != 136800
    ):
        raise SystemExit("Expected the original six-file synthetic fixture")

    trials = []
    for scenario in SCENARIOS:
        for strategy in ("fixed", "adaptive"):
            trial = simulate(strategy, copy.deepcopy(scenario), manifest)
            trials.append(trial)
            print(
                f"{'PASS' if trial['passed'] else 'FAIL'}: "
                f"{trial['scenario']} / {strategy}; "
                f"outcome={trial['status']}; "
                f"checks={trial['logical_observation_attempts']}; "
                f"delay={trial['detection_delay_virtual_seconds']}"
            )

    folder = ROOT / "results" / f"polling-replay-{uuid.uuid4().hex[:12]}"
    folder.mkdir(parents=True, exist_ok=False)
    report = {
        "experiment": "controlled-polling-replay",
        "scope": (
            "Virtual availability timelines; real local fixture copying and "
            "validation. No Azure requests or cloud performance measurements."
        ),
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "git_status": subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True
        ),
        "python": sys.version,
        "platform": platform.platform(),
        "scenarios": SCENARIOS,
        "timeout_virtual_seconds": TIMEOUT,
        "fixed_interval_seconds": 60,
        "adaptive_intervals_seconds": [15, 30, 60, 120, 240, 300],
        "interval_rule": "Intervals continue after failed observations.",
        "trials": trials,
        "all_passed": all(t["passed"] for t in trials),
    }
    path = folder / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nReport: {path}")
    if not report["all_passed"]:
        raise SystemExit("FAIL: inspect the saved report")
    print("PASS: all 12 controlled replay outcomes matched expectations.")


if __name__ == "__main__":
    main()
