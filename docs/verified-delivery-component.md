# Shared verified-delivery component

`deliver_verified(output_root, manifest_sha256, transfer)` creates a fresh
staging directory and calls `transfer(staging)` to populate it.

The component then rejects symlinks, checks the downloaded manifest against
the pinned SHA-256 digest, requires the exact payload-file inventory, and
calls the existing completeness and checksum validator.

Only a successful validation followed by directory promotion returns READY.
READY identifies the specific published local artifact, not cloud availability,
biological validity, source authenticity, or future immutability.

A failed operation returns FAILED and retains its staging directory. No
verified artifact path is returned. Callers must inspect the returned status;
a normal Python function return does not imply success.

The callback must write only inside staging. It is trusted application code,
not sandboxed. Staging and publication share a parent filesystem directory.
This component targets the existing single-worker local prototype. It does
not implement concurrent writers, transfer retry/resume, durable coordinator
state, or a transaction spanning directory publication and job-state storage.
Directory promotion is not a claim of power-loss durability.

Tests use real local fixture copies and SHA-256 verification. Failures are
controlled interruption, missing payload, same-size corruption, changed
manifest bytes, unexpected extra file, and a symlink payload. They are not
live network-failure or machine-crash tests. Failed staging data is retained
by the function; the test harness removes its temporary directories afterward.

All three monitoring strategies will use this same component. Availability
replay and local verification clocks must remain separate unless an explicit
transfer-duration model is introduced.
