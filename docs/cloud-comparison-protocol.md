# Cloud restoration comparison protocol

Status: draft for implementation and pilot evaluation.

## Research question

How do availability-checking strategies affect detection delay, request
volume, and verified dataset delivery under delayed availability and
temporary observation failures?

## Existing evidence

One small synthetic dataset was archived and successfully restored.
An earlier observation blocked downloading while payloads were pending.
A later observation allowed downloading and checksum validation.

This demonstrates functional behavior.
It does not establish exact rehydration duration, comparative performance,
cost savings, or scientific novelty.

## Strategies

1. Fixed polling: check availability every 60 seconds.
2. Adaptive polling: check immediately, then wait 15, 30, 60, 120, 240,
   and at most 300 seconds between subsequent checks.

Intervals are implementation-pilot choices, not established optimal values.
Both strategies perform an immediate first check.

Both use identical:
- Expected file manifests.
- Availability and completeness rules.
- Download implementation.
- Manifest and payload checksum validation.
- Rehydration priority and target tier.

A failed status request must never imply dataset readiness.

## Phase 1: deterministic observation replay

Implement a controlled observation source before additional cloud trials.

Scenarios:
- All files become available together.
- Files become available at different times.
- One expected file remains unavailable.
- A status request fails temporarily.
- A response omits an expected file.
- A downloaded payload fails checksum validation.

Use a virtual clock so replay does not require real waiting.
Supply the same underlying availability timeline to both strategies.
Each strategy observes that timeline only at its own scheduled check times.

Replay results describe the controlled model, not Azure performance.

## Measurements

- Availability-check attempts and failures.
- Time of each observation.
- First observation satisfying the online availability gate.
- Download attempts and verification outcome.
- Any premature READY report.
- Timeout or unresolved outcome.

For replay, also measure detection delay relative to the known time when
all expected payloads became available.

Count logical observations separately from HTTP requests.
An Azure CLI invocation is not necessarily one billable storage request.
Do not convert request counts into dollar savings without billing evidence.

## Phase 2: limited live-cloud pilot

Proceed after replay checks pass.

Record Azure CLI and Python versions, Git commit and working-tree status,
dataset manifest hash, region, configuration, and observation timestamps.

Do not treat repeated observations of one restoration as independent
rehydration trials.

Live polling generally establishes an interval containing completion.
Do not report the first successful poll as the exact service completion time.

Set trial count, timeout, dataset sizes, and budget before execution.
Keep failures and timeouts in the results and document exclusions.

## Contribution decision

Before expanding into a main study:
- Review existing tools and published approaches.
- Identify whether the comparison answers a useful unresolved question.
- Assess whether the workloads represent relevant restoration behavior.
- Revise or stop if findings merely reproduce established behavior.

Event-driven monitoring and download-recovery comparisons require separate
implementation and protocol extensions.

## Publication boundaries

Synthetic fixtures are not biological simulations or patient datasets.
The project is an independent research prototype.
Publication venue and acceptance are not established by this protocol.
