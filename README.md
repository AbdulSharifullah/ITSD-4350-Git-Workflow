# CI Calculator — Midterm

[![CI Pipeline](https://github.com/AbdulSharifullah/ITSD-4350-Git-Workflow/actions/workflows/ci.yml/badge.svg)](https://github.com/AbdulSharifullah/ITSD-4350-Git-Workflow/actions/workflows/ci.yml)

Repository: https://github.com/AbdulSharifullah/ITSD-4350-Git-Workflow

This continues Mini Projects 1.1–1.4: the original Python addition function,
unit test, feature-branch workflow, and local hooks now support a calculator web
application and a repeatable CI package build. No runtime dependencies are needed.

## Run and validate

Requires Python 3.14 and Git. On Windows, substitute `py` for `python` if needed.

```sh
python -m pip install -r requirements-dev.txt
git config core.hooksPath hooks
python webapp.py
```

Open http://127.0.0.1:8000. Enter two numbers and select **Add numbers**.
Stop the server with Ctrl+C.

```sh
python -m flake8 calculator.py webapp.py test_calculator.py test_webapp.py scripts
python -m pytest
python scripts/build.py
python dist/calculator-web.zip
```

The ZIP is runnable with Python and contains the application sources and entry point.
Tests cover addition, the home page, the API, invalid/nonfinite inputs, and HTTP 404.

## Commit stage and CI

Install development dependencies and enable hooks in every clone. The pre-commit
hook blocks commits on lint, test, or compilation/package failures. The commit-msg
hook enforces Conventional Commits, e.g. `feat: add calculator web interface`.
Hooks are local safeguards and can be bypassed; CI repeats checks on GitHub.

`.github/workflows/ci.yml` runs on every branch push and on pull requests into
`main`. It installs pinned development dependencies, lints, tests with coverage,
compiles the application, packages it, and uploads `calculator-web` as an artifact.
The PR-only `standards` job validates branch names, PR titles, and new non-merge
commit subjects. Existing historical commits remain intact.

## Branches and review

Use short-lived `feature/`, `fix/`, `docs/`, or `ci/` branches from `main`, such as
`feature/midterm-ci-foundation`. Open a PR with a Conventional Commit title and
complete the review template. Require passing `build-and-test` and `standards`
checks and one independent approval before merging. See WORKFLOW.md for details.
A green CI run is automated validation; it does not constitute peer approval.

## Structure

- `calculator.py`, `test_calculator.py`: original calculation and test.
- `webapp.py`, `test_webapp.py`: browser interface and HTTP integration tests.
- `hooks/`: local commit checks; `scripts/`: package and naming validation.
- `.github/`: CI and PR template; `requirements-dev.txt`: pinned tooling.
- `sonar-project.properties`: preserved configuration from the earlier project.

The required build is independent of SonarCloud credentials. The previous CI scan
was replaced by the self-contained commit-stage pipeline; the Sonar configuration
is retained for a future optional scan.
