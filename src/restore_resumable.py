import hashlib
import json
import shutil
import sys
from pathlib import Path

from validate_dataset import validate

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "synthetic"
DESTINATION = ROOT / "data" / "restored" / "resume-pilot"


def matches(path, entry):
    if not path.is_file():
        return False
    if path.stat().st_size != entry["size_bytes"]:
        return False

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest() == entry["sha256"]


def main():
    manifest_path = SOURCE / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)

    if validate(SOURCE) != 0:
        print("STOPPED: source dataset failed validation.")
        return 1

    DESTINATION.mkdir(parents=True, exist_ok=True)
    saved_manifest = DESTINATION / "manifest.json"

    if saved_manifest.exists():
        if saved_manifest.read_bytes() != manifest_bytes:
            print("NOT READY: destination belongs to a different manifest.")
            return 1

    copied = 0
    skipped = 0
    bytes_copied = 0

    for entry in manifest["files"]:
        relative = Path(entry["path"])
        target = DESTINATION / relative
        target.parent.mkdir(parents=True, exist_ok=True)

        if matches(target, entry):
            skipped += 1
            print(f"SKIP verified: {relative}")
            continue

        partial = target.with_name(target.name + ".part")
        shutil.copyfile(SOURCE / relative, partial)

        if not matches(partial, entry):
            raise ValueError(f"Copied file failed verification: {relative}")

        partial.replace(target)
        copied += 1
        bytes_copied += entry["size_bytes"]
        print(f"COPIED verified: {relative}")

    manifest_partial = DESTINATION / "manifest.json.part"
    manifest_partial.write_bytes(manifest_bytes)
    manifest_partial.replace(saved_manifest)

    if validate(DESTINATION) != 0:
        print("NOT READY: destination failed validation.")
        return 1

    print(
        f"Summary: copied={copied}, skipped={skipped}, "
        f"file_bytes_copied={bytes_copied}"
    )
    print("READY: restored files match the source manifest.")
    return 0


if __name__ == "__main__":
    try:
        status = main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"NOT READY: restoration stopped: {error}")
        status = 1
    sys.exit(status)
