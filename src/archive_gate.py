"""Evaluate a saved inventory observation; does not verify file checksums."""
import argparse
import json
from pathlib import Path


def evaluate(preparation, observation):
    if observation["prefix"] != preparation["prefix"]:
        raise ValueError("Inventory prefix differs from preparation")

    storage = preparation["storage"]
    if (
        observation["storage_account"] != storage["storage_account_name"]
        or observation["container"] != storage["container_name"]
    ):
        raise ValueError("Inventory storage differs from preparation")

    prefix = preparation["prefix"]
    expected = {
        f"{prefix}/{entry['path']}": entry["size_bytes"]
        for entry in preparation["manifest"]["files"]
    }
    expected[f"{prefix}/manifest.json"] = None

    blobs = observation["blobs"]
    inventory = {blob["name"]: blob for blob in blobs}
    if len(inventory) != len(blobs):
        raise ValueError("Duplicate blob names in inventory")

    problems = []
    for name in sorted(set(expected) - set(inventory)):
        problems.append(f"Missing: {name}")
    for name in sorted(set(inventory) - set(expected)):
        problems.append(f"Unexpected: {name}")

    for name, size in expected.items():
        if name not in inventory:
            continue
        properties = inventory[name].get("properties") or {}
        if size is not None and properties.get("contentLength") != size:
            problems.append(f"Size mismatch: {name}")
        if properties.get("blobTier") != "Hot":
            problems.append(f"Not Hot: {name}")
        if properties.get("rehydrationStatus"):
            problems.append(f"Rehydration pending: {name}")

    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()

    preparation = json.loads(args.preparation.read_text())
    observation = json.loads(args.inventory.read_text())
    problems = evaluate(preparation, observation)

    print(f"Observation time: {observation['observed_at']}")
    if problems:
        print("BLOCKED: dataset must not be released.")
        for problem in problems:
            print(f"  - {problem}")
        return 2

    print("ONLINE_UNVERIFIED: all expected blobs were Hot at observation time.")
    print("Download and checksum validation are still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
