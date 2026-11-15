"""Local-only Blue/Green controller. Run commands from the repository root."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_test import verify  # noqa: E402

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / 'runtime'
STATE = RUNTIME / 'state.json'
PORTS = {'blue': 18081, 'green': 18082}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def compose(*args):
    return subprocess.check_output(
        ['docker', 'compose', '-f', str(ROOT / 'compose.yml'), *args],
        text=True).strip()


def load():
    return json.loads(STATE.read_text())


def save(state):
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2))
    temporary.replace(STATE)


def config(color):
    version = 'Version 1' if color == 'blue' else 'Version 2'
    return (ROOT / 'nginx.conf.template').read_text().replace(
        '@COLOR@', color).replace('@VERSION@', version)


def validate(color, revision, attempts=20):
    for attempt in range(attempts):
        try:
            verify(f'http://127.0.0.1:{PORTS[color]}', revision)
            return
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(1)


def endpoint(revision):
    for attempt in range(30):
        try:
            verify('http://127.0.0.1:18080', revision)
            return
        except Exception:
            if attempt == 29:
                raise
            time.sleep(.2)


def switch(color, revision):
    validate(color, revision, attempts=1)
    route = RUNTIME / 'nginx' / 'default.conf'
    old = route.read_text()
    route.write_text(config(color))
    try:
        print(compose('exec', '-T', 'router', 'nginx', '-t'), flush=True)
        compose('exec', '-T', 'router', 'nginx', '-s', 'reload')
        endpoint(revision)
    except Exception:
        route.write_text(old)
        compose('exec', '-T', 'router', 'nginx', '-t')
        compose('exec', '-T', 'router', 'nginx', '-s', 'reload')
        raise


def initialize(blue_revision):
    if STATE.exists():
        raise RuntimeError('Existing state: clean up this simulation first')
    (RUNTIME / 'nginx').mkdir(parents=True, exist_ok=True)
    key = RUNTIME / 'app.env'
    key.write_text('APP_ENV=production-simulation\nSECRET_KEY=' +
                   secrets.token_hex(32) + '\n')
    os.chmod(key, 0o600)
    (RUNTIME / 'nginx' / 'default.conf').write_text(config('blue'))
    compose('up', '-d', '--no-deps', 'blue')
    validate('blue', blue_revision)
    compose('up', '-d', '--no-deps', 'router')
    endpoint(blue_revision)
    save({'active': 'blue', 'previous': None,
          'revisions': {'blue': blue_revision}, 'candidate': None})


def deploy(revision):
    state = load()
    color = 'green' if state['active'] == 'blue' else 'blue'
    if state['previous'] == color:
        raise RuntimeError('Inactive slot is retained for rollback; do not overwrite')
    compose('up', '-d', '--no-deps', '--force-recreate', color)
    validate(color, revision)
    state['revisions'][color] = revision
    state['candidate'] = color
    save(state)
    return color


def promote(expected_revision, approved):
    if not approved:
        raise RuntimeError('Explicit human approval is required')
    state = load()
    target = state['candidate']
    if not target or state['revisions'][target] != expected_revision:
        raise RuntimeError('Candidate does not match the approved revision')
    # Repeat validation immediately before any route file changes.
    validate(target, expected_revision, attempts=1)
    previous = state['active']
    switch(target, expected_revision)
    state.update(active=target, previous=previous, candidate=None)
    save(state)
    print(f'{stamp()} PROMOTED {target} revision={expected_revision}', flush=True)


def rollback():
    state = load()
    target = state['previous']
    if not target:
        raise RuntimeError('No previous environment is recorded')
    started = time.perf_counter()
    switch(target, state['revisions'][target])
    previous = state['active']
    state.update(active=target, previous=previous, candidate=None)
    save(state)
    elapsed = time.perf_counter() - started
    print(f'{stamp()} ROLLBACK restored={target} seconds={elapsed:.3f}', flush=True)
    return elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=[
        'init', 'deploy', 'validate', 'promote', 'rollback', 'status'])
    parser.add_argument('--revision')
    parser.add_argument('--color', choices=list(PORTS))
    parser.add_argument('--approve', action='store_true')
    args = parser.parse_args()
    if args.command in {'init', 'deploy', 'validate', 'promote'} and not args.revision:
        parser.error('--revision is required')
    if args.command == 'init':
        initialize(args.revision)
    elif args.command == 'deploy':
        deploy(args.revision)
    elif args.command == 'validate':
        if not args.color:
            parser.error('--color is required')
        validate(args.color, args.revision, attempts=1)
    elif args.command == 'promote':
        promote(args.revision, args.approve)
    elif args.command == 'rollback':
        rollback()
    else:
        print(json.dumps(load(), indent=2))


if __name__ == '__main__':
    main()
