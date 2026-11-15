"""Test evidence accounting and failure handling; these are not Docker evidence."""
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
SPEC = importlib.util.spec_from_file_location(
    'bluegreen_demonstrate', Path(__file__).with_name('demonstrate.py'))
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


def test_monitor_records_real_exceptions_and_stops(monkeypatch, tmp_path):
    monkeypatch.setattr(demo, 'EVIDENCE', tmp_path)
    stop = threading.Event()

    def unavailable():
        stop.set()
        raise OSError('connection refused')
    monkeypatch.setattr(demo, 'health', unavailable)
    samples = []
    demo.monitor(stop, samples, ['failure'])
    saved = json.loads((tmp_path / 'requests.jsonl').read_text())
    assert saved == samples[0]
    assert saved['ok'] is False
    assert saved['phase'] == 'failure'
    assert saved['error'] == 'connection refused'
    assert saved['duration_seconds'] >= 0


def test_demo_requires_approval_before_start(monkeypatch, tmp_path):
    monkeypatch.setattr(demo, 'EVIDENCE', tmp_path)
    monkeypatch.setenv('BLUE_REVISION', 'old')
    monkeypatch.setenv('GREEN_REVISION', 'new')
    monkeypatch.delenv('PROMOTION_APPROVED', raising=False)
    with pytest.raises(RuntimeError, match='human approval'):
        demo.main()
    assert not (tmp_path / 'results.json').exists()


def test_evidence_lifecycle_accounting_with_simulated_docker(monkeypatch, tmp_path):
    # This unit test checks orchestration with fake Docker responses. Only the
    # manually approved hosted run can supply real deployment evidence.
    bg = demo.bg
    runtime = tmp_path / 'runtime'
    evidence = tmp_path / 'evidence'
    monkeypatch.setattr(bg, 'RUNTIME', runtime)
    monkeypatch.setattr(bg, 'STATE', runtime / 'state.json')
    monkeypatch.setattr(demo, 'EVIDENCE', evidence)
    for key, value in {'BLUE_REVISION': 'old', 'GREEN_REVISION': 'new',
                       'PROMOTION_APPROVED': 'true', 'GITHUB_ACTOR': 'unit-test',
                       'RUN_URL': 'unit-test-only'}.items():
        monkeypatch.setenv(key, value)
    stopped = [False]

    def color():
        route = (runtime / 'nginx/default.conf').read_text()
        return 'green' if 'green:10000' in route else 'blue'

    def verify(url, revision):
        current = ('green' if ':18082' in url else 'blue')
        if ':18080' in url:
            current = color()
        actual = 'new' if current == 'green' else 'old'
        if revision != actual or (current == 'green' and stopped[0]):
            raise ValueError('Health response does not match expected revision')

    def compose(*args):
        if args[0] == 'stop':
            stopped[0] = True
            original_sleep(.1)
        return 'same-blue-container' if args[:2] == ('ps', '-q') else ''

    def health():
        current = color()
        if current == 'green' and stopped[0]:
            raise OSError('injected outage')
        return {'body': {'status': 'ok', 'revision': 'new' if current == 'green' else 'old'},
                'color': current, 'version': current}

    original_sleep = time.sleep
    original_promote = bg.promote

    def promote(*args):
        original_sleep(.1)
        return original_promote(*args)

    monkeypatch.setattr(bg, 'verify', verify)
    monkeypatch.setattr(bg, 'compose', compose)
    monkeypatch.setattr(bg, 'promote', promote)
    monkeypatch.setattr(bg.subprocess, 'check_output', lambda *args, **kwargs: 'start-time')
    monkeypatch.setattr(demo, 'health', health)
    monkeypatch.setattr(demo, 'screenshot', lambda name: demo.record(name, health()))
    monkeypatch.setattr(demo.time, 'sleep', lambda seconds: original_sleep(.12))
    demo.main()
    results = json.loads((evidence / 'results.json').read_text())
    samples = [json.loads(line) for line in (evidence / 'requests.jsonl').read_text().splitlines()]
    assert results['result'] == 'PASS'
    assert sum(group['requests'] for group in results['requests_by_phase'].values()) == len(samples)
    assert results['requests_by_phase']['failure-and-rollback']['failed'] > 0
    assert results['requests_by_phase']['after-rollback']['failed'] == 0
    events = [json.loads(line) for line in (evidence / 'events.jsonl').read_text().splitlines()]
    assert any(item['event'] == 'unsafe-promotion-blocked' for item in events)
    assert events[-1]['final']['body']['revision'] == 'old'
