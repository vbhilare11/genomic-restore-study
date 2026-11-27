# Restoration benchmark design

Status: implementation draft; experimental settings are not frozen.

## Scope

Compare restoration coordination strategies under controlled faults.
Do not claim a new storage service, transfer protocol, or checksum algorithm.

Initial implementations use deterministic local replay.
Azure integration follows only after the shared correctness checks pass.

## Shared job identity

Each job records:
- Unique restoration job ID.
- Manifest SHA-256 digest.
- Storage account, container, and dataset prefix.
- Expected object paths, sizes, and checksums.
- Strategy and experiment configuration.

State from different jobs must never be combined.
The manifest is fixed for a job.
Notifications are hints to inspect authoritative storage state;
they are not proof of dataset completeness or integrity.

## Shared state model

- WAITING: one or more expected objects are not confirmed online.
- ONLINE_UNVERIFIED: all expected objects passed the availability gate.
- VERIFYING: transfer and integrity checks are in progress.
- READY: downloaded manifest and every required payload passed verification.
- FAILED: a terminal error prevented successful delivery.
- TIMED_OUT: the configured observation deadline expired.

Transient errors are recorded without automatically terminating the job.

READY refers to a specific verified local artifact.
It does not guarantee that source objects remain unchanged afterward.

## Persistence and acknowledgement

Persist job state and processed notification identities transactionally.

Acknowledge a notification only after the corresponding state transaction
has committed. A crash before acknowledgement may cause redelivery.

Duplicate or reordered notifications must not inflate completed-file counts.
Recover state after process restart.

Partial files must not be published as verified artifacts.
Persist enough information to retry an interrupted verification attempt.
Transfer retries and output publication rules must be identical across
all monitoring strategies.

## Compared implementations

### Polling

Inspect authoritative inventory at a configured interval.
Recover after temporary observation failures and process restarts.

### Durable events

Use persistent notification processing, bounded retries, and failed-event
records. Define how failed records are replayed.
Perform an initial inventory inspection when attaching to a job.
Use notifications to trigger subsequent authoritative inspections.

### Events plus reconciliation

Use the same durable-event implementation and initial inspection.
Additionally inspect authoritative inventory periodically.

## Initial fault scenarios

| ID | Injected condition | Required behavior |
|---|---|---|
| F0 | No injected fault | Deliver the complete verified dataset |
| F1 | Duplicate notification | No inflated completion counts |
| F2 | Reordered notifications | No regression based on stale event order |
| F3 | Consumer downtime within retry window | Recover through redelivery |
| F4 | Crash after state commit, before acknowledgement | Safely process redelivery |
| F5 | Notification retries exhausted | Preserve failure evidence; follow defined recovery policy |
| F6 | Temporary inventory request failure | Do not infer readiness |
| F7 | One expected object remains unavailable | Never report READY |
| F8 | Transfer interrupted after partial output | Never publish partial output as verified |
| F9 | Same-size payload corruption | Reject checksum mismatch |

F5 is an injected benchmark condition, not an assertion that Azure lost
an event. Failed-event replay policy must be explicit in every comparison.

## Fairness controls

Use identical underlying object timelines and fault schedules.
Separate broker delivery, consumer processing, and storage observation.
Do not expose future availability times to a strategy.

Use identical manifests, transfer implementations, checksum validation,
timeouts, and retry policies wherever applicable.
Record differences that are inherent to the monitoring strategy.

## Measurements

- Final job outcome and verification evidence.
- Premature READY reports.
- Observation attempts and failures.
- Notification deliveries, duplicates, retries, and acknowledgements.
- Persistent-state commits and consumer restarts.
- Transfer attempts and application-level bytes transferred.
- Detection delay when ground truth is known in replay.
- Verified-delivery time under the stated clock model.
- Recovery after each injected fault.

Logical operations are not automatically HTTP requests or billable units.
Report modeled time separately from real execution time.

## Decision before live trials

Freeze configurations, workloads, fault schedules, repetition counts,
timeouts, and budget in a protocol revision.

Keep unresolved outcomes and explain exclusions.
Demonstrate a representative genomic workflow dependency before making
genomics-specific performance or usefulness claims.
