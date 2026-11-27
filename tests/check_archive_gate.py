import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from archive_gate import evaluate

preparation = {
    "prefix": "archive/test",
    "storage": {
        "storage_account_name": "testaccount",
        "container_name": "restore-lab",
    },
    "manifest": {
        "files": [{"path": "sample_R1.fastq", "size_bytes": 100}]
    },
}
intact = {
    "prefix": "archive/test",
    "storage_account": "testaccount",
    "container": "restore-lab",
    "blobs": [
        {
            "name": "archive/test/sample_R1.fastq",
            "properties": {
                "blobTier": "Hot",
                "contentLength": 100,
                "rehydrationStatus": None,
            },
        },
        {
            "name": "archive/test/manifest.json",
            "properties": {"blobTier": "Hot", "rehydrationStatus": None},
        },
    ],
}

def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")

require(not evaluate(preparation, intact), "intact inventory blocked")

for case in ("missing_payload", "missing_manifest", "pending", "wrong_size",
             "unknown_tier", "unexpected_blob"):
    observation = copy.deepcopy(intact)
    if case == "missing_payload":
        observation["blobs"].pop(0)
    elif case == "missing_manifest":
        observation["blobs"].pop()
    elif case == "pending":
        observation["blobs"][0]["properties"]["rehydrationStatus"] = (
            "rehydrate-pending-to-hot"
        )
    elif case == "wrong_size":
        observation["blobs"][0]["properties"]["contentLength"] = 99
    elif case == "unknown_tier":
        observation["blobs"][0]["properties"].pop("blobTier")
    else:
        observation["blobs"].append({
            "name": "archive/test/unexpected",
            "properties": {"blobTier": "Hot"},
        })
    require(evaluate(preparation, observation), f"{case} was accepted")
    print(f"PASS: {case} blocked")

print("PASS: intact inventory accepted as online; six unsafe cases blocked.")
