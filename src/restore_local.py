import json
import shutil
import sys
import tempfile
from pathlib import Path

from validate_dataset import validate

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "synthetic"
DESTINATION_PARENT = ROOT / "data" / "restored"


def main():
    manifest_path = SOURCE / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Check the source before starting the copy.
    if validate(SOURCE) != 0:
        print("STOPPED: source dataset failed validation.")
        return 1

    DESTINATION_PARENT.mkdir(parents=True, exist_ok=True)
    destination = Path(tempfile.mkdtemp(
        prefix="run-",
        dir=DESTINATION_PARENT,
    ))

    print(f"\nDestination: {destination}")

    for entry in manifest["files"]:
        relative = Path(entry["path"])
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / relative, target)
        print(f"Copied: {relative}")

    shutil.copyfile(manifest_path, destination / "manifest.json")

    print("\nValidating restored dataset...")
    if validate(destination) != 0:
        print("NOT READY: restored dataset failed validation.")
        return 1

    print("READY: restored files match the source manifest.")
    return 0


if __name__ == "__main__":
    try:
        status = main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"NOT READY: restoration stopped: {error}")
        status = 1
    sys.exit(status)
