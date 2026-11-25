import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import restore_resumable as restore

manifest = json.loads(
    (restore.SOURCE / "manifest.json").read_text(encoding="utf-8")
)
entry = manifest["files"][0]

with tempfile.TemporaryDirectory(prefix="corruption-check-") as temporary:
    destination = Path(temporary) / "restored"

    with patch.object(restore, "DESTINATION", destination):
        with contextlib.redirect_stdout(io.StringIO()):
            status = restore.main()

        if status != 0:
            raise SystemExit("FAIL: initial restoration failed")

        target = destination / entry["path"]
        content = bytearray(target.read_bytes())
        position = content.index(b"\n") + 1
        content[position] = (
            ord("T") if content[position] != ord("T") else ord("A")
        )
        target.write_bytes(content)

        if target.stat().st_size != entry["size_bytes"]:
            raise SystemExit("FAIL: test unexpectedly changed file size")
        if restore.matches(target, entry):
            raise SystemExit("FAIL: corruption was not detected")

        print("PASS: same-size corruption detected by checksum.")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = restore.main()

        text = output.getvalue()
        print("\nRepair run:")
        print(text)

        expected = (
            f"Summary: copied=1, skipped={len(manifest['files']) - 1}, "
            f"file_bytes_copied={entry['size_bytes']}"
        )
        if status != 0 or expected not in text:
            raise SystemExit("FAIL: unexpected repair result")
        if not restore.matches(target, entry):
            raise SystemExit("FAIL: repaired file still fails verification")

print("PASS: corrupted file repaired; the other 5 files were verified and skipped.")
