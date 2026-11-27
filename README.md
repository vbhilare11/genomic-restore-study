# Genomic Restore Study

Experimental tooling for studying reliable restoration of datasets used in genomic workflows.

## Research question

How do restoration strategies affect the time and resources required to deliver a complete, checksum-verified dataset when failures occur?

## Current status

The local pilot is implemented. Cloud archive restoration experiments are planned.

Implemented features:

- Deterministic synthetic paired-file fixtures and SHA-256 manifests.
- Dataset completeness and integrity validation.
- Restart-from-scratch and file-level recovery strategies.
- Injected copy interruptions and corruption-repair checks.
- Application-level copy and checksum-read measurements.
- A 48-trial local pilot across three equal-size workload profiles.

The pilot checks correctness and measurement accounting. It does not establish cloud cost savings, scientific novelty, or production readiness.

## Running checks

The initial pilot used Python 3.14. No third-party Python dependencies are required.

Generate the small fixture with `python src/generate_dataset.py`.

Run the six check scripts in `tests/` individually using Python.

To run the full pilot, generate the workloads once with `python src/generate_workloads.py`, then run `python src/run_full_pilot.py`.

The workload generator refuses to overwrite an existing workload directory. Results are saved under a new directory in `results/`.

## Repository structure

- `src/`: generation, validation, restoration, and experiment runners.
- `tests/`: correctness and measurement-accounting checks.
- `docs/`: experimental protocol.
- `results/`: recorded reports and logs.
- `data/`: locally generated fixtures, excluded from Git.

See [the pilot protocol](docs/pilot_protocol.md).

## Limitations

Synthetic fixtures are not patient data or a biological simulation.
Checksums establish agreement with the supplied manifest.
Recovery operates at file boundaries.
Injected copy interruptions do not demonstrate recovery from machine crashes.
Application byte counters are not physical disk I/O or cloud charges.

## Planned work

- Terraform infrastructure for a personal Azure research environment.
- Automated checks through GitHub Actions.
- Cloud archive restoration and dataset readiness tracking.
- Controlled experiments with reproducible configurations.
- Related-work assessment and analysis of experimental findings.

## Ownership and development

Maintained by Vipul Bhilare as an independent research project.
This repository does not represent an official SOPHiA GENETICS product.

AI assistance has been used to draft code, documentation, and experimental ideas.
The maintainer runs checks and reviews changes; AI assistance does not constitute independent scientific validation.
