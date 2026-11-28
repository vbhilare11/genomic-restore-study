import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from event_store import EventStore, receive
from inventory_worker import InventoryWorker


def require(value, message):
    if not value:
        raise SystemExit("FAIL: " + message)


prep = {
    "manifest_sha256": "a" * 64,
    "prefix": "archive/test",
    "storage": {
        "storage_account_name": "account",
        "container_name": "container",
    },
    "manifest": {"files": [{"path": "R1.fastq", "size_bytes": 100}]},
}
current = {
    "prefix": "archive/test",
    "storage_account": "account",
    "container": "container",
    "blobs": [
        {
            "name": "archive/test/manifest.json",
            "properties": {"blobTier": "Hot"},
        },
        {
            "name": "archive/test/R1.fastq",
            "properties": {
                "blobTier": "Archive",
                "contentLength": 100,
                "rehydrationStatus": "rehydrate-pending-to-hot",
            },
        },
    ],
}

with tempfile.TemporaryDirectory() as temporary:
    store = EventStore(Path(temporary) / "state.sqlite3")
    store.register_job("job", "a" * 64)
    worker = InventoryWorker(store)
    acknowledgements, inspections = [], []

    def acknowledge():
        acknowledgements.append("ack")

    def inspect():
        inspections.append("inspect")
        return copy.deepcopy(current)

    hint = {"claimed_tier": "Hot", "created_at_virtual_seconds": 20}
    receive(store, "job", "storage", "event-1", hint, acknowledge)
    receive(store, "job", "storage", "event-1", hint, acknowledge)
    result = worker.process_one("job", prep, inspect)
    require(
        result["availability"] == "WAITING",
        "notification bypassed inventory gate",
    )
    require(
        worker.process_one("job", prep, inspect) is None,
        "duplicate generated work",
    )
    require(len(inspections) == 1, "duplicate caused another inspection")
    print("PASS: duplicate acknowledged; Hot hint cannot override pending inventory.")

    properties = current["blobs"][1]["properties"]
    properties["blobTier"] = "Hot"
    properties["rehydrationStatus"] = None
    receive(
        store, "job", "storage", "event-2",
        {"claimed_tier": "Hot", "created_at_virtual_seconds": 30},
        acknowledge,
    )
    require(
        worker.process_one("job", prep, inspect)["availability"]
        == "ONLINE_UNVERIFIED",
        "online inventory not recognized",
    )

    receive(
        store, "job", "storage", "event-old",
        {"claimed_tier": "Archive", "created_at_virtual_seconds": 10},
        acknowledge,
    )
    require(
        worker.process_one("job", prep, inspect)["availability"]
        == "ONLINE_UNVERIFIED",
        "stale hint overrode fresh inventory",
    )
    print("PASS: delayed older notification uses fresh inventory.")

    receive(store, "job", "storage", "event-1", hint, acknowledge)
    require(
        worker.process_one("job", prep, inspect) is None,
        "processed redelivery generated work",
    )
    require(len(acknowledgements) == 5, "incorrect acknowledgement count")
    require(len(inspections) == 3, "incorrect inspection count")
    rows = store.db.execute("SELECT result FROM inspections").fetchall()
    require(len(rows) == 3, "incorrect receipt count")
    require(
        all(json.loads(row[0])["availability"] != "READY" for row in rows),
        "inspection claimed verified readiness",
    )
    require(store.state("job") == "WAITING", "inspection changed job state")
    print("PASS: five deliveries, three inspections, no READY transition.")
    store.close()

print("PASS: inbox-to-inventory integration checks completed.")
