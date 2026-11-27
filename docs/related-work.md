# Initial related-work assessment

Reviewed: 2026-11-27.
Scope: targeted initial review, not an exhaustive literature survey.

## Established capabilities

### AWS genomics archival workflow

Describes event-driven restoration, tracking restoration jobs, and delaying
workflow execution until all required objects have been restored.

https://aws.amazon.com/blogs/architecture/genomics-workflows-part-4-processing-archival-data/

### Azure archive rehydration

Documents rehydration status inspection and completion events.

https://learn.microsoft.com/en-us/azure/storage/blobs/archive-rehydrate-overview

### BDBag and reproducible genomic workflows

BDBag supports dataset completeness and checksum validation.
Published work applies BDBags and Globus to reproducible scientific workflows.

https://github.com/fair-research/bdbag/blob/master/doc/cli.md
https://doi.org/10.1371/journal.pone.0213013

### AzCopy transfer recovery

Provides transfer job plans and resumption of incomplete transfers.

https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azcopy-configure

### Event delivery behavior

Event Grid documents retry behavior, possible duplicates, and unordered
delivery. Experiments must distinguish injected failures from observed
service behavior.

https://learn.microsoft.com/en-us/azure/event-grid/delivery-and-retry

## Implications

Do not claim novelty for manifests, checksum verification, transfer resume,
completion events, or waiting until all expected objects are available.

The current fixed-versus-adaptive polling replay validates implementation
and accounting. It does not establish a sufficient publication contribution.

## Candidate contribution

A reproducible fault-testing benchmark for verified dataset restoration,
comparing polling, event-driven monitoring, and event-driven monitoring
with periodic reconciliation.

This is a candidate empirical contribution, not a confirmed research gap.
Reconciliation itself is not claimed as a new technique.

## Requirements before a main experiment

- Extend the literature and software review.
- Use credible baselines with documented retry and recovery behavior.
- Avoid comparing a robust implementation only against a deliberately weak one.
- Define duplicate events, reordered events, handler downtime, temporary
  observation failures, interrupted transfers, and corruption precisely.
- Distinguish dataset availability from verified delivery.
- Use representative file distributions and reproducible fault schedules.
- Report unresolved trials and measurement limitations.
- Demonstrate genomic workflow relevance beyond FASTQ-shaped filenames.

## Decision

Retain existing code and results as prototype evidence.
Do not expand cloud trials until the candidate contribution and baseline
design have been evaluated further.

## Extended review and baseline decision

### AWS automated archive restore guidance

Documents manifest-based restoration, persistent state, event-driven copy,
failure records, dead-letter handling, and retries.

https://docs.aws.amazon.com/solutions/automated-restore-and-copy-for-amazon-s3-glacier-objects/

Implication: an event baseline without durable recovery would be inadequate.

### Globus transfer API

Documents checksum-based synchronization, external checksum inputs,
and retransmission after checksum verification failures.

https://docs.globus.org/api/transfer/task_submit/

Implication: integrity verification and transfer recovery are established
capabilities, not standalone novelty claims.

### Distributed storage fault testing

Ganesan et al., FAST 2017, studies distributed storage reactions to
file-system errors and corruption.

https://www.usenix.org/conference/fast17/technical-sessions/presentation/ganesan

This provides methodological context for fault testing. Its storage-layer
scope differs from application-level archive restoration coordination.
It does not establish that our proposed benchmark fills a research gap.

## Exploratory benchmark decision

Continue with a bounded benchmark design, not a novelty claim.

Compare:
1. Polling with recovery after temporary observation failures.
2. Durable event-driven monitoring with retries and failed-event recovery.
3. The same event-driven implementation plus inventory reconciliation.

Use identical download and checksum-verification components.

Define the exact location and duration of each injected fault.
Distinguish broker delivery failures, consumer failures, and application
state persistence failures.

Duplicate notifications must not count as additional completed files.
Restarted consumers must recover their recorded state.
Timeouts must remain visible in results.

Do not expand cloud trials until the implementations pass deterministic
fault scenarios and the benchmark scope is frozen.

Genomic relevance still requires representative dataset structure and a
demonstrated downstream workflow dependency. FASTQ-shaped filenames alone
are insufficient.

The targeted review has not established an exhaustive literature gap.
