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
