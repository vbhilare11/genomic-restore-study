# Local restoration pilot protocol — version 1

## Research question
What are the recovery-time and I/O trade-offs between restarting
restoration from scratch and reusing verified completed files?

## Scope
Local filesystem experiment using synthetic paired FASTQ fixtures.
This does not simulate cloud archive latency, event delivery, or billing.
Synthetic mates are file-pair fixtures, not biologically realistic reads.

## Strategies
1. Restart: copy every expected file on each attempt.
2. Resume: verify existing files; skip matching files and recopy others.

Both strategies use the same source manifest and final validator.
Neither may report READY before all expected files pass validation.

## Scenarios
- No interruption.
- Interruption approximately 25%, 50%, and 75% through file payload copying.
- Same-size corruption of one completed destination file before recovery.
- One expected destination file missing before recovery.

Interruption boundaries will be defined consistently in the harness.
Each strategy receives the same dataset and failure schedule.

## Measurements
- Successful completion and final dataset validation.
- Any premature READY report.
- Initial-attempt and recovery elapsed time, recorded separately.
- Total elapsed time, excluding any deliberately imposed restart delay.
- Bytes copied, including partial failed copies.
- Bytes read for checksum verification, including source validation.
- Completed, skipped, and recopied file counts.
- Failure reason and recovery outcome.

Application-level byte counters are not physical disk I/O measurements.
Local copied bytes are not cloud charges.

## Execution controls
Use fresh destinations for independent trials.
Retain the same destination only within an interruption/recovery trial.
Use reproducible dataset seeds and record file sizes and counts.
Balance strategy execution order to reduce order effects.
Record Python version, OS, hardware, Git commit, and run configuration.
Do not claim filesystem caches have been cleared unless verified.

Start with small fixtures to validate the harness.
Choose larger workloads and repetition counts after examining pilot
variability; freeze those choices before the main experiment.
Report all trial outcomes and explain exclusions.

## Interpretation
Current correctness checks are not evidence of novelty or superiority.
Do not assume either strategy will outperform the other.
A checksum match establishes agreement with the supplied manifest,
not biological validity or authenticity of the manifest.

## Decision gate
Proceed beyond the pilot only if:
- Measurements are reliable and reproducible.
- Trade-offs are meaningful beyond trivial fixture behavior.
- Related-work review supports a useful contribution.
- Genomic-workflow relevance can be demonstrated rather than asserted.

## Deferred work
Cloud archive experiments, event-driven strategies, and actual cost
measurement require a separate protocol extension.
