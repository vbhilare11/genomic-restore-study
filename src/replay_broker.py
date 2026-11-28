"""In-memory virtual-time delivery model, not an Azure broker emulator."""
import copy
import heapq
import itertools


class ReplayBroker:
    def __init__(self, retry_delays=(10, 20)):
        if any(delay <= 0 for delay in retry_delays):
            raise ValueError("Retry delays must be positive")
        self.retry_delays = tuple(retry_delays)
        self.queue = []
        self.sequence = itertools.count()
        self.history = []
        self.dead_letters = []
        self.last_time = None

    def enqueue(self, at, event):
        if at < 0 or (self.last_time is not None and at < self.last_time):
            raise ValueError("Cannot enqueue in the past")
        self._schedule(at, copy.deepcopy(event), 1)

    def _schedule(self, at, event, attempt):
        heapq.heappush(
            self.queue, (at, next(self.sequence), event, attempt)
        )

    def deliver_due(self, now, handle):
        if self.last_time is not None and now < self.last_time:
            raise ValueError("Virtual clock cannot move backward")
        self.last_time = now

        while self.queue and self.queue[0][0] <= now:
            scheduled_at, _, event, attempt = heapq.heappop(self.queue)
            record = {
                "scheduled_at": scheduled_at,
                "delivered_at": now,
                "event": copy.deepcopy(event),
                "attempt": attempt,
            }
            try:
                handle(copy.deepcopy(event))
            except Exception as error:
                record["error"] = str(error)
                if attempt <= len(self.retry_delays):
                    retry_at = now + self.retry_delays[attempt - 1]
                    record["outcome"] = "retry_scheduled"
                    record["retry_at"] = retry_at
                    self._schedule(retry_at, event, attempt + 1)
                else:
                    record["outcome"] = "dead_lettered"
                    self.dead_letters.append(copy.deepcopy(record))
            else:
                record["outcome"] = "acknowledged"
            self.history.append(record)
