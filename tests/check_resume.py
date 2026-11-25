import contextlib
import io
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import restore_resumable as restore

real_copy = restore.shutil.copyfile
copy_calls = 0


def interrupt_third_copy(source, destination, *args, **kwargs):
    global copy_calls
    copy_calls += 1

    if copy_calls == 3:
        content = Path(source).read_bytes()
        Path(destination).write_bytes(content[:len(content) // 2])
        raise OSError("Injected interruption during third file")

    return real_copy(source, destination, *args, **kwargs)


with tempfile.TemporaryDirectory(prefix="resume-check-") as temporary:
    destination = Path(temporary) / "restored"

    with patch.object(restore, "DESTINATION", destination):
        first_output = io.StringIO()
        interrupted = False

        with contextlib.redirect_stdout(first_output):
            try:
                with patch.object(
                    restore.shutil,
                    "copyfile",
                    side_effect=interrupt_third_copy,
                ):
                    restore.main()
            except OSError as error:
                if str(error) != "Injected interruption during third file":
                    raise
                interrupted = True

        if not interrupted:
            raise SystemExit("FAIL: expected interruption did not occur")

        if any(
            line.startswith("READY:")
            for line in first_output.getvalue().splitlines()
        ):
            raise SystemExit("FAIL: interrupted run reported READY")

        partial = destination / "sample_002_R1.fastq.part"
        original = restore.SOURCE / "sample_002_R1.fastq"

        if not partial.is_file():
            raise SystemExit("FAIL: partial file was not retained")
        if not (0 < partial.stat().st_size < original.stat().st_size):
            raise SystemExit("FAIL: partial file has unexpected size")

        print("PASS: interruption left a partial file without reporting READY.")

        second_output = io.StringIO()
        with contextlib.redirect_stdout(second_output):
            status = restore.main()

        text = second_output.getvalue()
        print("\nRecovery run:")
        print(text)

        if status != 0:
            raise SystemExit("FAIL: recovery run failed")
        if "Summary: copied=4, skipped=2, file_bytes_copied=91200" not in text:
            raise SystemExit("FAIL: unexpected recovery counters")
        if partial.exists():
            raise SystemExit("FAIL: partial file remains after recovery")

print("PASS: recovery reused 2 verified files and copied the remaining 4.")
