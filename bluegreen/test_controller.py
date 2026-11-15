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


def test_stateful_lifecycle_preserves_previous_slot(monkeypatch, tmp_path):
    monkeypatch.setattr(bg, 'RUNTIME', tmp_path)
    monkeypatch.setattr(bg, 'STATE', tmp_path / 'state.json')
    commands, validations = [], []
    monkeypatch.setattr(bg, 'compose', lambda *args: commands.append(args) or '')
    monkeypatch.setattr(bg, 'validate', lambda *args, **kwargs: validations.append(args))
    monkeypatch.setattr(bg, 'endpoint', lambda revision: validations.append(('endpoint', revision)))
    bg.initialize('old')
    assert bg.load()['active'] == 'blue'
    assert 'SECRET_KEY=' in (tmp_path / 'app.env').read_text()
    with pytest.raises(RuntimeError, match='Existing state'):
        bg.initialize('old')
    assert bg.deploy('new') == 'green'
    assert bg.load()['active'] == 'blue'
    with pytest.raises(RuntimeError, match='approved revision'):
        bg.promote('wrong', True)
    bg.promote('new', True)
    assert bg.load()['active'] == 'green'
    assert bg.load()['previous'] == 'blue'
    assert 'green:10000' in (tmp_path / 'nginx/default.conf').read_text()
    with pytest.raises(RuntimeError, match='retained for rollback'):
        bg.deploy('third')
    assert bg.rollback() >= 0
    assert bg.load()['active'] == 'blue'
    assert 'blue:10000' in (tmp_path / 'nginx/default.conf').read_text()
    assert commands.count(('up', '-d', '--no-deps', 'blue')) == 1
    assert ('up', '-d', '--no-deps', '--force-recreate', 'green') in commands
    assert ('endpoint', 'old') in validations and ('endpoint', 'new') in validations


def test_rollback_without_previous_slot(monkeypatch):
    monkeypatch.setattr(bg, 'load', lambda: {'previous': None})
    with pytest.raises(RuntimeError, match='No previous'):
        bg.rollback()


def test_validation_retries_and_exhaustion(monkeypatch):
    calls = []

    def flaky(url, revision):
        calls.append((url, revision))
        if len(calls) < 2:
            raise ValueError('Not ready')
    monkeypatch.setattr(bg, 'verify', flaky)
    monkeypatch.setattr(bg.time, 'sleep', lambda seconds: None)
    bg.validate('green', 'new', attempts=2)
    assert len(calls) == 2
    calls.clear()
    with pytest.raises(ValueError, match='Not ready'):
        bg.validate('green', 'new', attempts=1)
    calls.clear()
    bg.endpoint('new')
    assert calls[-1] == ('http://127.0.0.1:18080', 'new')


@pytest.mark.parametrize('command,arguments,function', [
    ('init', ['--revision', 'old'], 'initialize'),
    ('deploy', ['--revision', 'new'], 'deploy'),
    ('validate', ['--revision', 'new', '--color', 'green'], 'validate'),
    ('promote', ['--revision', 'new', '--approve'], 'promote'),
    ('rollback', [], 'rollback'),
])
def test_cli_dispatch(monkeypatch, command, arguments, function):
    calls = []
    monkeypatch.setattr(bg, function, lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(bg.sys, 'argv', ['manage.py', command, *arguments])
    bg.main()
    assert len(calls) == 1


@pytest.mark.parametrize('arguments', [['deploy'], ['validate', '--revision', 'new']])
def test_cli_missing_arguments(monkeypatch, arguments):
    monkeypatch.setattr(bg.sys, 'argv', ['manage.py', *arguments])
    with pytest.raises(SystemExit) as result:
        bg.main()
    assert result.value.code == 2
