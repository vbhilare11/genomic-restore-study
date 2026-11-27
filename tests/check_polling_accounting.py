import contextlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from compare_polling import SCENARIOS, SOURCE, simulate

manifest = json.loads((SOURCE / "manifest.json").read_text())

# Explicit expectations, independent of the runner's scheduling loop.
expected = {
    ("simultaneous", "fixed"): ([0, 60, 120], 0, 0, "verified"),
    ("simultaneous", "adaptive"): ([0, 15, 45, 105, 225], 105, 0, "verified"),
    ("staggered", "fixed"): ([0, 60, 120, 180], 0, 0, "verified"),
    ("staggered", "adaptive"): ([0, 15, 45, 105, 225], 45, 0, "verified"),
    ("one_unavailable", "fixed"): (list(range(0, 901, 60)), None, 0, "timeout"),
    ("one_unavailable", "adaptive"): (
        [0, 15, 45, 105, 225, 465, 765], None, 0, "timeout"
    ),
    ("temporary_observation_failure", "fixed"): (
        [0, 60, 120, 180, 240], 120, 2, "verified"
    ),
    ("temporary_observation_failure", "adaptive"): (
        [0, 15, 45, 105, 225], 105, 0, "verified"
    ),
    ("temporarily_omitted_file", "fixed"): (
        [0, 60, 120, 180, 240], 120, 0, "verified"
    ),
    ("temporarily_omitted_file", "adaptive"): (
        [0, 15, 45, 105, 225], 105, 0, "verified"
    ),
    ("corrupt_payload", "fixed"): (
        [0, 60, 120], 0, 0, "verification_failed"
    ),
    ("corrupt_payload", "adaptive"): (
        [0, 15, 45, 105, 225], 105, 0, "verification_failed"
    ),
}

def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")

for scenario in SCENARIOS:
    for strategy in ("fixed", "adaptive"):
        key = (scenario["name"], strategy)
        times, delay, failures, outcome = expected[key]

        with contextlib.redirect_stdout(io.StringIO()):
            trial = simulate(strategy, scenario, manifest)

        actual_times = [
            observation["virtual_seconds"]
            for observation in trial["observations"]
        ]
        require(actual_times == times, f"{key}: incorrect schedule")
        require(
            trial["logical_observation_attempts"] == len(times),
            f"{key}: incorrect observation count",
        )
        require(
            trial["failed_observations"] == failures,
            f"{key}: incorrect failure count",
        )
        require(
            trial["detection_delay_virtual_seconds"] == delay,
            f"{key}: incorrect delay",
        )
        require(trial["status"] == outcome, f"{key}: incorrect outcome")
        require(
            trial["first_online_at_virtual_seconds"]
            == (None if outcome == "timeout" else times[-1]),
            f"{key}: incorrect first-online time",
        )
        require(
            trial["local_fixture_copy_attempts"]
            == (0 if outcome == "timeout" else 1),
            f"{key}: incorrect copy count",
        )
        require(not trial["premature_verified"], f"{key}: premature verification")

        if outcome == "verification_failed":
            require(
                "Checksum mismatch:" in trial["validation_output"],
                f"{key}: expected checksum rejection missing",
            )

        print(f"PASS: {scenario['name']} / {strategy}")

print("PASS: all 12 schedules and accounting results verified.")
