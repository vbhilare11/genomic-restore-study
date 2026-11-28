"""Virtual availability comparison; no Azure calls, downloads, or READY claims."""
import hashlib
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from event_store import EventStore, receive
from inventory_worker import InventoryWorker
from replay_broker import ReplayBroker

ROOT = Path(__file__).resolve().parents[1]
STRATEGIES = ('polling', 'events', 'events_reconcile')
SCENARIOS = [
    {'name': 'never_available', 'available_at': None, 'event_at': None},
    {'name': 'normal', 'available_at': 125, 'event_at': 125},
    {'name': 'duplicate', 'available_at': 125, 'event_at': 125, 'duplicate': True},
    {'name': 'delayed_notification', 'available_at': 125, 'event_at': 200},
    {'name': 'notification_receiver_outage', 'available_at': 125,
     'event_at': 125, 'receiver_down': [100, 200]},
    {'name': 'inventory_failure', 'available_at': 125, 'event_at': 125,
     'inventory_down': [120, 170]},
]


def inside(t, window):
    return window is not None and window[0] <= t < window[1]


def run_case(strategy, scenario, manifest):
    if strategy not in STRATEGIES:
        raise ValueError('Unknown strategy')
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    preparation = {
        'manifest_sha256': digest, 'prefix': 'replay/dataset',
        'storage': {'storage_account_name': 'account', 'container_name': 'container'},
        'manifest': manifest,
    }
    trial = {
        'strategy': strategy, 'scenario': scenario['name'],
        'status': 'timed_out', 'first_online_at': None,
        'detection_delay': None, 'observations': [],
        'inventory_attempts': 0, 'inventory_failures': 0,
        'duplicate_receipts': 0, 'dead_letter_replays': 0,
    }
    clock = [0]
    broker = ReplayBroker(retry_delays=(10, 20))
    if strategy != 'polling' and scenario['event_at'] is not None:
        for index, entry in enumerate(manifest['files']):
            event = {'source': 'storage', 'id': f'event-{index}',
                     'payload': {'blob': entry['path'], 'hint': 'changed'}}
            broker.enqueue(scenario['event_at'], event)
            if scenario.get('duplicate'):
                broker.enqueue(scenario['event_at'], event)

    with tempfile.TemporaryDirectory() as temporary:
        store = EventStore(Path(temporary) / 'state.sqlite3')
        store.register_job('job', digest)
        worker = InventoryWorker(store)
        store.record('job', 'scheduler', 'initial', {'reason': 'initial_inventory'})
        replayed = set()
        next_worker_attempt = 0

        def inspect():
            t = clock[0]
            trial['inventory_attempts'] += 1
            if inside(t, scenario.get('inventory_down')):
                trial['inventory_failures'] += 1
                raise RuntimeError('Injected inventory failure')
            online = scenario['available_at'] is not None and t >= scenario['available_at']
            blobs = [{
                'name': 'replay/dataset/manifest.json',
                'properties': {'blobTier': 'Hot'},
            }]
            for entry in manifest['files']:
                blobs.append({
                    'name': 'replay/dataset/' + entry['path'],
                    'properties': {
                        'contentLength': entry['size_bytes'],
                        'blobTier': 'Hot' if online else 'Archive',
                        'rehydrationStatus': None if online else 'rehydrate-pending-to-hot',
                    },
                })
            return {
                'prefix': 'replay/dataset', 'storage_account': 'account',
                'container': 'container', 'observed_at_virtual_seconds': t,
                'blobs': blobs,
            }

        def handle(message):
            if inside(clock[0], scenario.get('receiver_down')):
                raise RuntimeError('Injected notification receiver outage')
            inserted = receive(store, 'job', message['source'], message['id'],
                               message['payload'], lambda: None)
            if not inserted:
                trial['duplicate_receipts'] += 1

        try:
            for t in range(301):
                clock[0] = t
                if strategy != 'polling':
                    # Explicit failed-event sweep every 120 virtual seconds.
                    if t > 0 and t % 120 == 0:
                        for index, failure in enumerate(broker.dead_letters):
                            if index not in replayed:
                                broker.enqueue(t, failure['event'])
                                replayed.add(index)
                                trial['dead_letter_replays'] += 1
                    broker.deliver_due(t, handle)

                if t > 0 and t % 60 == 0 and strategy in ('polling', 'events_reconcile'):
                    store.record('job', 'scheduler', f'inspect-{t}', {'reason': 'periodic_inventory'})

                if t < next_worker_attempt:
                    continue
                while True:
                    try:
                        result = worker.process_one('job', preparation, inspect)
                    except RuntimeError:
                        next_worker_attempt = t + 10
                        break
                    if result is None:
                        break
                    trial['observations'].append({
                        'virtual_seconds': t, 'availability': result['availability'],
                    })
                    if result['availability'] == 'ONLINE_UNVERIFIED':
                        trial['status'] = 'online_unverified'
                        trial['first_online_at'] = t
                        trial['detection_delay'] = t - scenario['available_at']
                        break
                if trial['status'] == 'online_unverified':
                    break
            trial['delivery_history'] = broker.history
            trial['dead_letters'] = broker.dead_letters
            trial['job_state'] = store.state('job')
            trial['recorded_notifications'] = store.db.execute(
                "SELECT COUNT(*) FROM inbox WHERE source = 'storage'"
            ).fetchone()[0]
            trial['processing_receipts'] = store.db.execute(
                'SELECT COUNT(*) FROM inspections'
            ).fetchone()[0]
        finally:
            store.close()
    return trial


def main():
    manifest = json.loads((ROOT / 'data/synthetic/manifest.json').read_text())
    if not manifest.get('files'):
        raise SystemExit('Expected a nonempty synthetic manifest')
    trials = []
    for scenario in SCENARIOS:
        for strategy in STRATEGIES:
            trial = run_case(strategy, scenario, manifest)
            trials.append(trial)
            print(f"{scenario['name']} / {strategy}: {trial['status']}; "
                  f"online_at={trial['first_online_at']}; "
                  f"checks={trial['inventory_attempts']}; "
                  f"failures={trial['inventory_failures']}")
    folder = ROOT / 'results' / ('event-comparison-' + uuid.uuid4().hex[:12])
    folder.mkdir(parents=True, exist_ok=False)
    report = {
        'scope': 'Virtual availability only; no Azure calls, transfers, or checksum verification.',
        'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'git_status': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
        'python': sys.version, 'manifest': manifest, 'scenarios': SCENARIOS,
        'policy': {'timeout': 300, 'poll_interval': 60, 'reconcile_interval': 60,
                   'broker_retry_delays': [10, 20], 'dead_letter_sweep_interval': 120,
                   'worker_retry_delay': 10, 'stop': 'first_online_unverified'},
        'trials': trials,
    }
    path = folder / 'report.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Report: {path}')


if __name__ == '__main__':
    main()
