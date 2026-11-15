"""Execute and record the complete simulation on one Docker host."""
import json
import os
from pathlib import Path
import threading
import time
from urllib.request import urlopen

import manage as bg

EVIDENCE = Path(__file__).resolve().parent / 'evidence'
URL = 'http://127.0.0.1:18080'


def health():
    with urlopen(URL + '/health', timeout=2) as response:
        return {'body': json.load(response),
                'color': response.headers['X-Deployment-Color'],
                'version': response.headers['X-Deployment-Version']}


def screenshot(name):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': 1100, 'height': 700})
        page.goto(URL)
        observed = health()
        page.evaluate('''data => {
            const pre = document.createElement('pre');
            pre.textContent = JSON.stringify(data, null, 2);
            document.body.prepend(pre);
        }''', {'observed_at_utc': bg.stamp(), 'endpoint': URL, **observed})
        page.screenshot(path=str(EVIDENCE / (name + '.png')), full_page=True)
        browser.close()
    record(name, observed)


def record(event, values):
    data = {'utc': bg.stamp(), 'event': event, **values}
    print(json.dumps(data), flush=True)
    with (EVIDENCE / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps(data) + '\n')


def monitor(stop, samples, phase):
    with (EVIDENCE / 'requests.jsonl').open('w') as stream:
        while not stop.is_set():
            start = time.perf_counter()
            sample = {'utc': bg.stamp(), 'phase': phase[0]}
            try:
                sample.update(health())
                sample['ok'] = sample['body']['status'] == 'ok'
            except Exception as error:
                sample.update(ok=False, error=str(error))
            sample['duration_seconds'] = time.perf_counter() - start
            samples.append(sample)
            stream.write(json.dumps(sample) + '\n')
            stream.flush()
            stop.wait(.05)


def main():
    EVIDENCE.mkdir(exist_ok=True)
    blue, green = os.environ['BLUE_REVISION'], os.environ['GREEN_REVISION']
    if os.environ.get('PROMOTION_APPROVED') != 'true':
        raise RuntimeError('Workflow dispatch must include human approval')
    record('human-approval', {
        'actor': os.environ['GITHUB_ACTOR'], 'approved_revision': green,
        'mechanism': 'required workflow_dispatch boolean input',
        'run': os.environ['RUN_URL']})
    bg.initialize(blue)
    screenshot('01-blue-version-1')
    samples, phase, stop = [], ['before-promotion'], threading.Event()
    thread = threading.Thread(target=monitor, args=(stop, samples, phase))
    thread.start()
    try:
        identity = bg.compose('ps', '-q', 'blue')
        started = bg.subprocess.check_output(
            ['docker', 'inspect', '-f', '{{.State.StartedAt}}', identity],
            text=True).strip()
        bg.deploy(green)
        assert bg.load()['active'] == 'blue'
        bg.endpoint(blue)
        record('green-validated-blue-still-active', {
            'green_revision': green, 'production': health()})
        screenshot('02-green-ready-blue-active')
        # An actual mismatched revision must fail inside promotion, before routing.
        route = (bg.RUNTIME / 'nginx' / 'default.conf').read_text()
        try:
            # Make the candidate metadata claim a bad revision. The live verifier
            # must catch it rather than relying only on candidate metadata.
            state = bg.load()
            state['revisions']['green'] = 'deliberately-wrong-revision'
            bg.save(state)
            try:
                bg.promote('deliberately-wrong-revision', True)
            except ValueError as error:
                record('unsafe-promotion-blocked', {'error': str(error)})
            else:
                raise AssertionError('Unsafe promotion was accepted')
        finally:
            state = bg.load()
            state['revisions']['green'] = green
            bg.save(state)
        assert route == (bg.RUNTIME / 'nginx' / 'default.conf').read_text()
        assert bg.load()['active'] == 'blue'
        bg.endpoint(blue)
        time.sleep(2)
        phase[0] = 'promotion'
        record('approval-checkpoint', {'approved': True, 'revision': green})
        switch_start = time.perf_counter()
        bg.promote(green, True)
        promotion_seconds = time.perf_counter() - switch_start
        phase[0] = 'after-promotion'
        screenshot('03-green-version-2')
        assert identity == bg.compose('ps', '-q', 'blue')
        assert started == bg.subprocess.check_output(
            ['docker', 'inspect', '-f', '{{.State.StartedAt}}', identity],
            text=True).strip()
        record('blue-kept-running', {'container': identity, 'started_at': started})
        time.sleep(3)
        phase[0] = 'failure-and-rollback'
        failure_start = time.perf_counter()
        bg.compose('stop', '-t', '1', 'green')
        # Require a real failed endpoint check before recovery.
        try:
            health()
        except Exception as error:
            record('post-promotion-failure-detected', {'error': str(error)})
        else:
            raise AssertionError('Simulated failure was not observable')
        rollback_seconds = bg.rollback()
        recovery_seconds = time.perf_counter() - failure_start
        phase[0] = 'after-rollback'
        screenshot('04-blue-restored')
        bg.endpoint(blue)
        time.sleep(3)
    finally:
        stop.set()
        thread.join()
    groups = {}
    for item in samples:
        group = groups.setdefault(item['phase'], {'requests': 0, 'failed': 0})
        group['requests'] += 1
        group['failed'] += int(not item['ok'])
    assert all(groups.get(name, {}).get('requests', 0) > 0 for name in
               ['before-promotion', 'promotion', 'after-promotion',
                'failure-and-rollback', 'after-rollback'])
    record('completed', {'requests_by_phase': groups,
                         'promotion_seconds': promotion_seconds,
                         'rollback_seconds': rollback_seconds,
                         'failure_to_recovery_seconds': recovery_seconds,
                         'sampling_interval_seconds': .05,
                         'request_timeout_seconds': 2,
                         'final': health()})
    (EVIDENCE / 'results.json').write_text(json.dumps({
        'result': 'PASS', 'utc': bg.stamp(), 'run': os.environ['RUN_URL'],
        'blue_revision': blue, 'green_revision': green,
        'requests_by_phase': groups, 'promotion_seconds': promotion_seconds,
        'rollback_seconds': rollback_seconds,
        'failure_to_recovery_seconds': recovery_seconds,
        'limitation': 'Sampled localhost HTTP checks; not proof of universal zero downtime.'
    }, indent=2))


if __name__ == '__main__':
    main()
