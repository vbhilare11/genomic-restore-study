import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from event_store import EventStore, receive


def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")


with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / "events.sqlite3"
    store = EventStore(path)
    store.register_job("job-a", "a" * 64)
    store.register_job("job-b", "b" * 64)
    acknowledgements = []
    payload = {"blob": "sample_R1.fastq", "type": "tier_changed"}

    def acknowledge():
        acknowledgements.append("ack")

    require(
        receive(store, "job-a", "storage", "event-1", payload, acknowledge),
        "new event not inserted",
    )
    require(
        not receive(store, "job-a", "storage", "event-1", payload, acknowledge),
        "duplicate inserted",
    )
    require(len(store.pending("job-a")) == 1, "duplicate changed inbox count")
    require(len(acknowledgements) == 2, "redelivery was not acknowledged")
    print("PASS: duplicate retained once and acknowledged twice.")

    def crash_before_ack():
        raise RuntimeError("Injected failure after commit, before acknowledgement")

    try:
        receive(store, "job-a", "storage", "event-2", payload, crash_before_ack)
    except RuntimeError:
        pass
    else:
        raise SystemExit("FAIL: injected acknowledgement failure missing")

    store.close()
    store = EventStore(path)
    require(len(store.pending("job-a")) == 2, "committed work lost")
    require(
        not receive(store, "job-a", "storage", "event-2", payload, acknowledge),
        "redelivery after restart duplicated work",
    )
    print("PASS: committed work survived restart and redelivery.")

    require(
        receive(store, "job-b", "storage", "event-1", payload, acknowledge),
        "different jobs incorrectly deduplicated",
    )
    require(len(store.pending("job-b")) == 1, "job isolation failed")
    print("PASS: event identities isolated by job.")

    before = len(acknowledgements)
    try:
        receive(
            store, "job-a", "storage", "event-1",
            {"blob": "different"}, acknowledge,
        )
    except ValueError:
        pass
    else:
        raise SystemExit("FAIL: conflicting identity accepted")
    require(len(acknowledgements) == before, "conflicting event acknowledged")
    print("PASS: conflicting payload rejected without acknowledgement.")

    try:
        receive(store, "unknown-job", "storage", "event-3", payload, acknowledge)
    except sqlite3.IntegrityError:
        pass
    else:
        raise SystemExit("FAIL: unknown job accepted")
    require(len(acknowledgements) == before, "uncommitted event acknowledged")
    print("PASS: failed persistence prevented acknowledgement.")

    try:
        store.register_job("job-a", "c" * 64)
    except ValueError:
        pass
    else:
        raise SystemExit("FAIL: job manifest identity changed")

    require(
        store.state("job-a") == store.state("job-b") == "WAITING",
        "notification receipt advanced readiness",
    )
    print("PASS: manifest identity fixed; receipt never implies READY.")
    store.close()

print("PASS: durable inbox checks completed.")
