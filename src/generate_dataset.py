import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "synthetic"
OUTPUT.mkdir(parents=True, exist_ok=True)

rng = random.Random(42)
files = []

for sample_number in range(1, 4):
    sample = f"sample_{sample_number:03d}"
    reads = {1: [], 2: []}

    for read_number in range(1, 101):
        for mate in (1, 2):
            sequence = "".join(rng.choice("ACGT") for _ in range(100))
            reads[mate].append(
                f"@{sample}_read_{read_number:04d}/{mate}\n"
                f"{sequence}\n+\n{'I' * 100}\n"
            )

    for mate in (1, 2):
        name = f"{sample}_R{mate}.fastq"
        content = "".join(reads[mate]).encode("ascii")
        (OUTPUT / name).write_bytes(content)

        files.append({
            "sample_id": sample,
            "mate": mate,
            "path": name,
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })

manifest = {
    "schema_version": 1,
    "dataset_id": "synthetic-paired-fastq-v1",
    "seed": 42,
    "reads_per_file": 100,
    "read_length": 100,
    "files": files,
}

manifest_path = OUTPUT / "manifest.json"
manifest_path.write_text(
    json.dumps(manifest, indent=2) + "\n",
    encoding="utf-8",
)

print(f"Created {len(files)} FASTQ files for 3 samples.")
print("Each file contains 100 synthetic reads.")
print(f"Manifest: {manifest_path}")
print(f"Total FASTQ bytes: {sum(f['size_bytes'] for f in files):,}")
