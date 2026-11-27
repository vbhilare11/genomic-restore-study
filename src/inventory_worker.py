"""Recoverable inventory inspection for a single local worker."""
import json
from archive_gate import evaluate


class InventoryWorker:
    def __init__(self, store):
        self.store = store
        store.db.executescript("""
            CREATE TABLE IF NOT EXISTS inspections (
                job_id TEXT NOT NULL,
                source TEXT NOT NULL,
                event_id TEXT NOT NULL,
                result TEXT NOT NULL,
                PRIMARY KEY (job_id, source, event_id),
                FOREIGN KEY (job_id, source, event_id)
                    REFERENCES inbox(job_id, source, event_id)
            );
            CREATE TABLE IF NOT EXISTS inspection_errors (
                attempt_id INTEGER PRIMARY KEY,
                job_id TEXT NOT NULL,
                source TEXT NOT NULL,
                event_id TEXT NOT NULL,
                error TEXT NOT NULL
            );
        """)

    def process_one(self, job_id, preparation, inspect, before_commit=None,
                    after_commit=None):
        row = self.store.db.execute(
            "SELECT manifest_sha256 FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None or row[0] != preparation["manifest_sha256"]:
            raise ValueError("Job manifest identity mismatch")

        pending = self.store.db.execute("""
            SELECT i.source, i.event_id FROM inbox AS i
            LEFT JOIN inspections AS p
            ON p.job_id = i.job_id AND p.source = i.source
                AND p.event_id = i.event_id
            WHERE i.job_id = ? AND p.event_id IS NULL
            ORDER BY i.source, i.event_id LIMIT 1
        """, (job_id,)).fetchone()
        if pending is None:
            return None
        source, event_id = pending

        try:
            observation = inspect()
            blockers = evaluate(preparation, observation)
            result = {
                "availability": "WAITING" if blockers else "ONLINE_UNVERIFIED",
                "observation": observation,
                "blockers": blockers,
            }
            encoded = json.dumps(result, sort_keys=True, allow_nan=False)
        except Exception as error:
            with self.store.db:
                self.store.db.execute(
                    "INSERT INTO inspection_errors(job_id, source, event_id, error) VALUES (?, ?, ?, ?)",
                    (job_id, source, event_id, str(error)),
                )
            raise

        with self.store.db:
            self.store.db.execute(
                "INSERT INTO inspections(job_id, source, event_id, result) VALUES (?, ?, ?, ?)",
                (job_id, source, event_id, encoded),
            )
            if before_commit is not None:
                before_commit()
        if after_commit is not None:
            after_commit()
        return result
