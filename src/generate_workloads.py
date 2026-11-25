import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "workloads-v1"

PROFILES = {
    "many-small": [512] * 64,
    "few-large": [8192] * 4,
    "mixed": [1024, 3072, 8192, 20480],
}

TRANSLATION = bytes(
    b"ACGT"[value % 4] for value in range(256)
)


def generate_profile(name, counts):
    output = BASE / name

    # Avoid overwriting an existing generated workload.
    output.mkdir(parents=True, exist_ok=False)
    files = []

    for sample_number, read_count in enumerate(counts, start=1):
        sample = f"sample_{sample_number:04d}"

        for mate in (1, 2):
            rng = random.Random(42 + sample_number * 2 + mate)
            filename = f"{sample}_R{mate}.fastq"
            digest = hashlib.sha256()
            size = 0

            with (output / filename).open("wb") as handle:
                for read_number in range(1, read_count + 1):
                    sequence = rng.randbytes(100).translate(TRANSLATION)
                    header = (
                        f"@{sample}_read_{read_number:08d}/{mate}\n"
                    ).encode("ascii")
                    record = (
                        header + sequence + b"\n+\n"
                        + b"I" * 100 + b"\n"
                    )
                    handle.write(record)
                    digest.update(record)
                    size += len(record)

            files.append({
                "sample_id": sample,
                "mate": mate,
                "path": filename,
                "size_bytes": size,
                "sha256": digest.hexdigest(),
            })

    manifest = {
        "schema_version": 1,
        "dataset_id": f"synthetic-{name}-v1",
        "seed_rule": "42 + sample_number * 2 + mate",
        "read_length": 100,
        "reads_per_mate_by_sample": counts,
        "purpose": "Synthetic restoration fixtures; not biological simulation",
        "files": files,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    total = sum(entry["size_bytes"] for entry in files)
    print(
        f"{name}: {len(files)} files, "
        f"{len(counts)} pairs, {total:,} payload bytes"
    )
    return total


def main():
    if BASE.exists():
        raise SystemExit(
            f"STOP: {BASE} already exists. "
            "Do not delete it; share this message so we can inspect it."
        )

    if len({sum(counts) for counts in PROFILES.values()}) != 1:
        raise SystemExit("Profile read totals differ")

    totals = [
        generate_profile(name, counts)
        for name, counts in PROFILES.items()
    ]

    if len(set(totals)) != 1:
        raise SystemExit("FAIL: workload payload sizes differ")

    print("\nPASS: all 3 workloads have identical total payload sizes.")
    print(f"Location: {BASE}")


if __name__ == "__main__":
    main()
