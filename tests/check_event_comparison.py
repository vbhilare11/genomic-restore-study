import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from compare_event_strategies import SCENARIOS, STRATEGIES, run_case


def require(value, message):
    if not value:
        raise SystemExit('FAIL: ' + message)


manifest = {'files': [
    {'path': f'sample_{sample:03d}_R{mate}.fastq', 'size_bytes': 22800}
    for sample in range(1, 4) for mate in (1, 2)
]}
# Each tuple: detection time, inventory attempts, inventory failures,
# broker delivery attempts, dead-letter replays, duplicate receipts.
expected = {
    'never_available': [(None, 6, 0, 0, 0, 0), (None, 1, 0, 0, 0, 0), (None, 6, 0, 0, 0, 0)],
    'normal': [(180, 4, 0, 0, 0, 0), (125, 2, 0, 6, 0, 0), (125, 4, 0, 6, 0, 0)],
    'duplicate': [(180, 4, 0, 0, 0, 0), (125, 2, 0, 12, 0, 6), (125, 4, 0, 12, 0, 6)],
    'delayed_notification': [(180, 4, 0, 0, 0, 0), (200, 2, 0, 6, 0, 0), (180, 4, 0, 0, 0, 0)],
    'notification_receiver_outage': [(180, 4, 0, 0, 0, 0), (240, 2, 0, 24, 6, 0), (180, 4, 0, 18, 0, 0)],
    'inventory_failure': [(170, 8, 5, 0, 0, 0), (175, 7, 5, 6, 0, 0), (170, 8, 5, 6, 0, 0)],
}

for scenario in SCENARIOS:
    for index, strategy in enumerate(STRATEGIES):
        trial = run_case(strategy, scenario, manifest)
        actual = (
            trial['first_online_at'], trial['inventory_attempts'],
            trial['inventory_failures'], len(trial['delivery_history']),
            trial['dead_letter_replays'], trial['duplicate_receipts'],
        )
        label = scenario['name'] + ' / ' + strategy
        require(actual == expected[scenario['name']][index], label + ': accounting differs')
        online = actual[0]
        require(trial['status'] == ('timed_out' if online is None else 'online_unverified'), label + ': incorrect outcome')
        require(trial['job_state'] == 'WAITING', label + ': availability became verified readiness')
        expected_delay = None if online is None else online - scenario['available_at']
        require(trial['detection_delay'] == expected_delay, label + ': incorrect detection delay')
        require(expected_delay is None or expected_delay >= 0, label + ': premature availability')
        if scenario['name'] == 'duplicate' and strategy != 'polling':
            require(trial['recorded_notifications'] == 6, label + ': duplicate rows retained')
        print('PASS: ' + label)

print('PASS: all 18 virtual outcomes and accounting results verified.')
