"""Check that failure paths cannot silently promote an unsafe candidate."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    'bluegreen_manage', Path(__file__).with_name('manage.py'))
bg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bg)


def test_approval_required_before_state_or_docker(monkeypatch):
    def unexpected():
        pytest.fail('State must not be read without approval')
    monkeypatch.setattr(bg, 'load', unexpected)
    with pytest.raises(RuntimeError, match='approval'):
        bg.promote('new', False)


def test_failed_live_validation_cannot_switch(monkeypatch):
    monkeypatch.setattr(bg, 'load', lambda: {
        'candidate': 'green', 'active': 'blue', 'revisions': {'green': 'new'}})

    def fail(*args, **kwargs):
        raise ValueError('Wrong live revision')

    def unsafe(*args):
        pytest.fail('Switch must not run after failed validation')
    monkeypatch.setattr(bg, 'validate', fail)
    monkeypatch.setattr(bg, 'switch', unsafe)
    with pytest.raises(ValueError, match='Wrong live revision'):
        bg.promote('new', True)


def test_nginx_failure_restores_old_config(monkeypatch, tmp_path):
    directory = tmp_path / 'nginx'
    directory.mkdir()
    route = directory / 'default.conf'
    route.write_text('old working config')
    monkeypatch.setattr(bg, 'RUNTIME', tmp_path)
    monkeypatch.setattr(bg, 'validate', lambda *args, **kwargs: None)
    calls = []

    def command(*args):
        calls.append(args)
        if len(calls) == 1:
            raise RuntimeError('Nginx candidate rejected')
        return ''
    monkeypatch.setattr(bg, 'compose', command)
    with pytest.raises(RuntimeError, match='candidate rejected'):
        bg.switch('green', 'new')
    assert route.read_text() == 'old working config'
    assert calls[-1][-2:] == ('-s', 'reload')


def test_rollback_validates_before_state_commit(monkeypatch):
    monkeypatch.setattr(bg, 'load', lambda: {
        'active': 'green', 'previous': 'blue', 'revisions': {'blue': 'old'}})

    def unhealthy(*args):
        raise ValueError('Previous slot unhealthy')

    def unsafe(*args):
        pytest.fail('Must not commit rollback state after failed switch')
    monkeypatch.setattr(bg, 'switch', unhealthy)
    monkeypatch.setattr(bg, 'save', unsafe)
    with pytest.raises(ValueError, match='unhealthy'):
        bg.rollback()
