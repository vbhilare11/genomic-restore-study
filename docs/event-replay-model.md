# Three-strategy virtual availability model

This is a deterministic implementation check, not a cloud experiment or a
complete restoration benchmark. No Azure calls, downloads, or payload checksum
verification occur. The terminal success condition is ONLINE_UNVERIFIED;
the durable job remains WAITING for a later verified-delivery coordinator.

## Policies

- All strategies perform one initial inventory inspection.
- Polling inspects every 60 virtual seconds.
- Events persist received notifications and trigger inventory inspections.
- Events plus reconciliation adds a 60-second inventory schedule.
- Failed inventory inspections are retried after 10 seconds for all strategies.
- Broker retries occur 10 and then 20 seconds after failed delivery attempts.
- Failed deliveries are retained; event strategies sweep dead letters every
  120 seconds and re-enqueue each newly dead-lettered record once per sweep.
- Each delivered hint describes one expected file. Duplicate scenarios deliver
  each hint twice. No event payload can establish availability.
- The simulation stops at the first successful online availability gate or at
  virtual second 300, inclusive.

All payloads become available together at second 125 except in the never-
available scenario. Notification delay and notification receiver outages
are separate from storage availability. Receiver downtime affects the
notification receiver only, not polling or the inventory worker. Inventory
request failures affect all strategies.

The driver advances in one-second virtual increments. Delivery occurs before
periodic scheduling, followed by worker processing. Future event schedules
belong to the driver; the inspection callback exposes only current state.

## Interpretation limits

Broker policy is an experimental model, not Azure's retry policy.
The broker is in memory and is not claimed to survive process restart.
SQLite inbox and worker behavior are exercised through the existing modules.
The model does not yet implement staggered file availability, live network
latency, real process crashes, transfer interruption, or verified output release.

The exact accounting test covers 18 combinations of three strategies and six
scenarios. Expected outcomes are correctness checks, not statistical findings.
Changing model parameters requires updating the protocol and reviewing the
expected outcomes; do not tune parameters to make one strategy win.
