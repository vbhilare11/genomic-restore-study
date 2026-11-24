import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "synthetic"
VALIDATOR = ROOT / "src" / "validate_dataset.py"

cases = [
    ("intact", 0, "PASS:"),
    ("missing_file", 1, "Missing file:"),
    ("modified_file", 1, "Checksum mismatch:"),
]

with tempfile.TemporaryDirectory(prefix="restore-check-") as temporary:
    for name, expected_code, expected_message in cases:
        folder = Path(temporary) / name
        shutil.copytree(SOURCE, folder)
        target = folder / "sample_001_R1.fastq"

        if name == "missing_file":
            target.unlink()
        elif name == "modified_file":
            content = bytearray(target.read_bytes())
            position = content.index(b"\n") + 1
            content[position] = (
                ord("T") if content[position] != ord("T") else ord("A")
            )
            target.write_bytes(content)

        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(folder)],
            capture_output=True,
            text=True,
        )

        print(f"\n{name}:")
        print(result.stdout.strip())

        if (
            result.returncode != expected_code
            or expected_message not in result.stdout
        ):
            print(result.stderr)
            raise SystemExit(f"Unexpected result for {name}")

print("\nAll 3 checks passed. Original dataset unchanged.")
