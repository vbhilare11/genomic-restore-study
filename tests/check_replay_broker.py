import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from event_store import EventStore, receive
from replay_broker import ReplayBroker


def require(condition, message):
    if not condition:
        raise SystemExit("FAIL: " + message)


event = {"source": "storage", "id": "event-1", "payload": {"hint": "changed"}}

# Consumer unavailable until virtual second 25.
broker = ReplayBroker()
broker.enqueue(0, event)
clock = [0]
received = []

def recovering_consumer(message):
    if clock[0] < 25:
        raise RuntimeError("Injected consumer downtime")
    received.append(message)

for t in (0, 10, 30):
    clock[0] = t
    broker.deliver_due(t, recovering_consumer)

require(
    [entry["delivered_at"] for entry in broker.history] == [0, 10, 30],
    "incorrect retry schedule",
)
require(len(received) == 1 and not broker.dead_letters, "recovery failed")
print("PASS: downtime recovered at virtual second 30.")

# Persistent failure exhausts the same three-attempt policy.
broker = ReplayBroker()
broker.enqueue(0, event)

def unavailable(message):
    raise RuntimeError("Injected persistent failure")

for t in (0, 10, 30):
    broker.deliver_due(t, unavailable)

require(len(broker.history) == 3, "incorrect attempt count")
require(len(broker.dead_letters) == 1, "failed event not retained")
require(not broker.queue, "exhausted event still queued")
print("PASS: exhausted retries retained one dead-letter record.")

# Failure after inbox commit causes redelivery, not duplicate inbox work.
with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / "events.sqlite3"
    store = EventStore(path)
    store.register_job("job", "a" * 64)
    broker = ReplayBroker()
    broker.enqueue(0, event)
    acknowledgements = []

    def acknowledge():
        acknowledgements.append("attempt")
        if len(acknowledgements) == 1:
            raise RuntimeError("Injected failure after inbox commit")

    def consumer(message):
        receive(
            store, "job", message["source"], message["id"],
            message["payload"], acknowledge,
        )

    broker.deliver_due(0, consumer)
    store.close()
    store = EventStore(path)
    broker.deliver_due(10, consumer)

    require(len(store.pending("job")) == 1, "redelivery duplicated inbox work")
    require(len(acknowledgements) == 2, "acknowledgement was not retried")
    require(
        [entry["outcome"] for entry in broker.history]
        == ["retry_scheduled", "acknowledged"],
        "incorrect redelivery outcomes",
    )
    require(store.state("job") == "WAITING", "delivery implied readiness")
    store.close()

print("PASS: post-commit redelivery preserved one durable inbox entry.")

# Equal-time deliveries preserve insertion order deterministically.
broker = ReplayBroker()
broker.enqueue(5, {"id": "first"})
broker.enqueue(5, {"id": "second"})
order = []
broker.deliver_due(5, lambda message: order.append(message["id"]))
require(order == ["first", "second"], "unstable equal-time ordering")
print("PASS: equal-time delivery order is deterministic.")

print("PASS: virtual broker and durable inbox integration checks completed.")
