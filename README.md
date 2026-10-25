# ITSD-4350 Midterm Project – Git Workflow and CI

[![CI Pipeline](https://github.com/AbdulSharifullah/ITSD-4350-Git-Workflow/actions/workflows/ci.yml/badge.svg)](https://github.com/AbdulSharifullah/ITSD-4350-Git-Workflow/actions/workflows/ci.yml)

## About this project

For this midterm, I built on my earlier mini projects to set up a basic Git workflow and an automated CI pipeline. I used a simple web calculator made with Python and Flask. You enter two numbers, and it adds them together.

My goal was to make sure changes are checked automatically before they are merged into the main branch.

## How I organized the work

I kept `main` as the main branch and made changes in a separate feature branch called `feature/web-calculator`. When the feature was ready, I opened a pull request to merge it into `main`.

I used commit messages such as `feat:`, `fix:`, and `test:` to make it easier to tell what each change was for. The pull request also needed approval from another reviewer before it could be merged.

## How the CI pipeline works

I used GitHub Actions for the CI pipeline. It runs automatically whenever code is pushed and when a pull request is opened or updated.

The pipeline:
- Installs the Python packages the project needs.
- Checks the code with Flake8.
- Runs the tests with pytest.
- Checks that the Python application files can compile.
- Runs a SonarCloud code quality check.

If a required check fails, the pull request cannot be merged until the problem is fixed. I had to fix a few warnings before all the checks passed.

## What I tested

I added tests for the calculator and web application, including adding two numbers and handling invalid or missing inputs. I also checked that the home page loads.

The final pull request passed the CI checks and was approved before being merged.

## Files to look at

- `app.py` – the web calculator.
- `calculator.py` – the addition function.
- `test_app.py` and `test_calculator.py` – automated tests.
- `requirements.txt` – Python packages.
- `.github/workflows/ci.yml` – GitHub Actions pipeline.
- `WORKFLOW.md` – more details about the branching and commit rules.

## Repository

https://github.com/AbdulSharifullah/ITSD-4350-Git-Workflow
