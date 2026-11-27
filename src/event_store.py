"""Local durable notification inbox; receipt is not dataset readiness."""
import json
import sqlite3


class EventStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA synchronous = FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                manifest_sha256 TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'WAITING'
                    CHECK (state = 'WAITING')
            );
            CREATE TABLE IF NOT EXISTS inbox (
                job_id TEXT NOT NULL REFERENCES jobs(job_id),
                source TEXT NOT NULL,
                event_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY (job_id, source, event_id)
            );
        """)

    def register_job(self, job_id, manifest_sha256):
        if not job_id or not isinstance(manifest_sha256, str):
            raise ValueError("Job ID and manifest digest are required")
        if len(manifest_sha256) != 64 or any(
            c not in "0123456789abcdef" for c in manifest_sha256
        ):
            raise ValueError("Expected a lowercase SHA-256 digest")
        with self.db:
            row = self.db.execute(
                "SELECT manifest_sha256 FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row is not None and row[0] != manifest_sha256:
                raise ValueError("Job already belongs to a different manifest")
            self.db.execute(
                "INSERT OR IGNORE INTO jobs(job_id, manifest_sha256) VALUES (?, ?)",
                (job_id, manifest_sha256),
            )

    def record(self, job_id, source, event_id, payload):
        if not source or not event_id:
            raise ValueError("Notification source and ID are required")
        encoded = json.dumps(payload, sort_keys=True, allow_nan=False)
        with self.db:
            row = self.db.execute(
                "SELECT payload FROM inbox WHERE job_id = ? AND source = ? AND event_id = ?",
                (job_id, source, event_id),
            ).fetchone()
            if row is not None:
                if row[0] != encoded:
                    raise ValueError("Notification identity reused with different payload")
                return False
            self.db.execute(
                "INSERT INTO inbox(job_id, source, event_id, payload) VALUES (?, ?, ?, ?)",
                (job_id, source, event_id, encoded),
            )
        return True

    def pending(self, job_id):
        rows = self.db.execute(
            "SELECT source, event_id, payload FROM inbox WHERE job_id = ? ORDER BY source, event_id",
            (job_id,),
        ).fetchall()
        return [
            (source, event_id, json.loads(payload))
            for source, event_id, payload in rows
        ]

    def state(self, job_id):
        row = self.db.execute(
            "SELECT state FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return row[0]

    def close(self):
        self.db.close()


def receive(store, job_id, source, event_id, payload, acknowledge):
    inserted = store.record(job_id, source, event_id, payload)
    # Commit completed; pending inspection remains in the durable inbox.
    acknowledge()
    return inserted
