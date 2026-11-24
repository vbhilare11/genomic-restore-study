import hashlib
import json
import sys
from pathlib import Path

def validate(folder):
    manifest = json.loads(
        (folder / "manifest.json").read_text(encoding="utf-8")
    )
    errors = []
    samples = {}
    seen_paths = set()

    if not manifest.get("files"):
        errors.append("Manifest contains no files.")

    for entry in manifest["files"]:
        name = entry["path"]
        relative = Path(name)

        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"Unsafe path: {name}")
            continue

        if name in seen_paths:
            errors.append(f"Duplicate file entry: {name}")
        seen_paths.add(name)

        sample = entry["sample_id"]
        mate = entry["mate"]
        mates = samples.setdefault(sample, [])

        if mate not in (1, 2):
            errors.append(f"Invalid mate for {name}: {mate}")
        mates.append(mate)

        path = folder / relative
        if not path.is_file():
            errors.append(f"Missing file: {name}")
            continue

        if path.stat().st_size != entry["size_bytes"]:
            errors.append(f"Size mismatch: {name}")

        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)

        if digest.hexdigest() != entry["sha256"]:
            errors.append(f"Checksum mismatch: {name}")

    for sample, mates in samples.items():
        if sorted(mates) != [1, 2]:
            errors.append(f"Incomplete or duplicate pair: {sample}")

    if errors:
        print("FAIL: dataset is not ready.")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        f"PASS: {len(seen_paths)} files verified "
        f"across {len(samples)} complete pairs."
    )
    return 0

if __name__ == "__main__":
    folder = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).resolve().parents[1] / "data" / "synthetic"
    )
    try:
        status = validate(folder)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"FAIL: could not validate dataset: {error}")
        status = 1
    sys.exit(status)
