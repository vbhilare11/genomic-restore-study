# Initial Azure storage smoke test

## Purpose

Verify that the personal Azure research environment supports authenticated
upload, download, and dataset integrity validation.

## Infrastructure

Terraform created four resources:

- Dedicated research resource group.
- Standard LRS StorageV2 account in East US 2.
- Private blob container.
- Storage Blob Data Contributor assignment for the research operator.

Shared Key authentication and anonymous blob access were disabled.
The storage public network endpoint remained enabled.

## Execution

The operator ran the test from a local macOS environment using Azure CLI
with Microsoft Entra login authentication.

1. Validated the original synthetic dataset.
2. Uploaded six FASTQ fixtures and their manifest to a unique smoke prefix.
3. Downloaded the seven blobs into a separate local directory.
4. Compared the downloaded manifest byte-for-byte with the original.
5. Validated downloaded file sizes, SHA-256 checksums, and sample pairs.

## Observed result

Run prefix: `smoke/bdadcd604fa3`

Both source and downloaded datasets passed validation:
six files across three complete pairs.

The manifest comparison succeeded.

## Interpretation

This was a successful Hot-tier connectivity and integrity smoke test.
It did not exercise archive rehydration, failure recovery, performance
comparisons, or cloud cost measurement.

The result was reported from an operator-run terminal session.
It was not an independently reviewed experiment.

## CI scope

GitHub Actions checks Terraform formatting and configuration validity.
It does not authenticate to Azure, run a deployment plan, or apply resources.
Cloud deployment remains a separate operator action.
