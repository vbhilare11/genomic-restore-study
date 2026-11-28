import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from event_store import EventStore
from inventory_worker import InventoryWorker

prep = {
    "manifest_sha256": "a" * 64,
    "prefix": "archive/test",
    "storage": {
        "storage_account_name": "account",
        "container_name": "container",
    },
    "manifest": {"files": [{"path": "R1.fastq", "size_bytes": 100}]},
}
observation = {
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
            "properties": {"blobTier": "Hot", "contentLength": 100},
        },
    ],
}


def require(value, message):
    if not value:
        raise SystemExit("FAIL: " + message)


def crash():
    raise RuntimeError("Injected interruption")


with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / "state.sqlite3"
    store = EventStore(path)
    store.register_job("job", "a" * 64)
    store.record("job", "storage", "event-1", {"hint": "changed"})
    worker = InventoryWorker(store)

    try:
        worker.process_one("job", prep, crash)
    except RuntimeError:
        pass
    require(
        store.db.execute(
            "SELECT COUNT(*) FROM inspection_errors"
        ).fetchone()[0] == 1,
        "failed observation not recorded",
    )
    require(
        store.db.execute(
            "SELECT COUNT(*) FROM inspections"
        ).fetchone()[0] == 0,
        "failed observation marked processed",
    )
    print("PASS: failed observation recorded; work retained.")

    try:
        worker.process_one(
            "job", prep, lambda: observation, before_commit=crash
        )
    except RuntimeError:
        pass

    store.close()
    store = EventStore(path)
    worker = InventoryWorker(store)
    require(
        store.db.execute(
            "SELECT COUNT(*) FROM inspections"
        ).fetchone()[0] == 0,
        "uncommitted inspection survived",
    )
    result = worker.process_one("job", prep, lambda: observation)
    require(
        result["availability"] == "ONLINE_UNVERIFIED",
        "incorrect availability",
    )
    require(
        store.state("job") == "WAITING",
        "inspection advanced dataset readiness",
    )
    print("PASS: pre-commit interruption rolled back; retry succeeded.")

    store.record("job", "storage", "event-2", {"hint": "changed"})
    try:
        worker.process_one(
            "job", prep, lambda: observation, after_commit=crash
        )
    except RuntimeError:
        pass

    store.close()
    store = EventStore(path)
    worker = InventoryWorker(store)
    require(
        worker.process_one("job", prep, crash) is None,
        "committed work inspected twice",
    )
    require(
        store.db.execute(
            "SELECT COUNT(*) FROM inspections"
        ).fetchone()[0] == 2,
        "committed result lost",
    )
    print("PASS: post-commit receipt retained; restart skipped completed work.")
    store.close()

print("PASS: inventory worker recovery checks completed.")
