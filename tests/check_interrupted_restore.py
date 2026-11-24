import contextlib
import io
import runpy
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

real_copy = shutil.copyfile
copied_files = 0


def interrupted_copy(source, destination, *args, **kwargs):
    global copied_files
    copied_files += 1

    if copied_files == 3:
        source = Path(source)
        destination = Path(destination)
        content = source.read_bytes()
        destination.write_bytes(content[:len(content) // 2])
        raise OSError("Injected interruption during third file")

    return real_copy(source, destination, *args, **kwargs)


with tempfile.TemporaryDirectory(prefix="restore-interruption-") as temporary:
    destination = Path(temporary) / "restored"
    destination.mkdir()
    output = io.StringIO()
    exit_code = None

    with (
        patch("tempfile.mkdtemp", return_value=str(destination)),
        patch("shutil.copyfile", side_effect=interrupted_copy),
        contextlib.redirect_stdout(output),
    ):
        try:
            runpy.run_path(
                str(ROOT / "src" / "restore_local.py"),
                run_name="__main__",
            )
        except SystemExit as error:
            exit_code = error.code

    text = output.getvalue()
    print(text)

    if exit_code != 1:
        raise SystemExit(f"Unexpected exit code: {exit_code}")

    if any(line.startswith("READY:") for line in text.splitlines()):
        raise SystemExit("ERROR: incomplete restoration reported READY")

    if "Injected interruption" not in text:
        raise SystemExit("ERROR: expected interruption was not observed")

    partial = destination / "sample_002_R1.fastq"
    original = ROOT / "data" / "synthetic" / partial.name

    if not (0 < partial.stat().st_size < original.stat().st_size):
        raise SystemExit("ERROR: partial-file condition was not created")

print("PASS: interrupted restoration exited with failure and never reported READY.")
