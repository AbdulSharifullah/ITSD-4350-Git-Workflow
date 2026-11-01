# Mini Project 2.1: Automated staging deployment

Repository: https://github.com/AbdulSharifullah/ITSD-4350-Git-Workflow

Status: implementation under review; hosted deployment and final submission evidence pending.
Staging URL: not configured yet. This document is not proof of a successful deployment.

## Application and platform

The existing Flask calculator adds two numbers. This extension keeps the original
application, tests, Flake8 check, and SonarCloud integration and adds delivery to
staging. GitHub Actions is the CD platform because it already runs the CI checks.
Render hosts the container as an image-backed Free web service.

The original build only compiled the Python files. It did not publish a reusable
application artifact. The new build packages the validated application and its
installed dependencies into a Linux container image.

## Pipeline

Push or pull request -> Flake8 -> pytest and coverage -> Python compilation ->
SonarCloud scan -> build and upload container artifact. On `main`, the scan also
waits for the quality gate before the build and delivery stages can proceed.

Only a successful push to `main` continues to delivery:

Download artifact -> verify SHA-256 -> load the image -> publish to GHCR ->
deploy the immutable registry digest to Render -> wait for live status ->
smoke-test the deployed commit -> preserve deployment evidence.

CI is configured in `.github/workflows/ci.yml`; delivery is configured separately
in `.github/workflows/cd.yml`. The existing `build-and-test` job name is retained.
Feature branches and PRs run CI and build an artifact. Delivery is triggered only
by a completed main CI run, and proceeds only when that run succeeded and came
from a push to main in this repository. It downloads the artifact by that exact
CI run ID and uses that run's commit SHA. PRs have no delivery jobs to skip.
Review and protected-branch checks remain in place; an approved merge is manual.
The scanner explicitly waits for the configured SonarCloud quality gate on
`main`. Branch and PR scans retain the existing scan behavior: this SonarCloud
organization rejects synchronous gate-status queries for non-main branches.
No gate or required check is removed or relaxed.

The container uses `requirements-staging.lock`, which pins every resolved runtime
dependency and its wheel SHA-256 hash for Linux amd64 / Python 3.14. Installation
uses `--only-binary=:all:` and `--require-hashes`, so source setup scripts cannot
execute and modified or unlisted packages are rejected. Refresh the lock when
intentionally updating runtime dependencies, then verify CI and the image again.

`staging-application-<commit>` contains `application.tar`, its SHA-256 checksum,
and the smoke-test script from the same commit. Upload/download use GitHub's
artifact service. The publish job loads that image instead of rebuilding it.
Render receives `ghcr.io/abdulsharifullah/itsd-4350-git-workflow-staging@sha256:...`.
Render pulls that image; it does not rebuild the repository. Keep registry images
available because Render needs them when restarting or rolling back.

## Development and staging

Local development continues to use `app.py`. The container uses Gunicorn,
listens on Render's `PORT` (default 10000), and runs as a non-root user.
`APP_REVISION` is embedded at build time and reported by `/health` so the smoke
test cannot accidentally approve an older deployment.

Render has its own runtime environment. Set `APP_ENV=staging` and a strong
random `SECRET_KEY`. The application refuses staging startup without the key.
Staging session cookies use Secure, HttpOnly, and SameSite=Lax. CSRF remains
enabled. No development secret is included in the image.

## Manual setup checkpoints

Do not paste credentials into chat or source files. Do not weaken existing
repository or environment protections. These setup actions belong to the owner.

1. Review the feature PR. Have the second GitHub account approve it, then merge
   it using the normal protected-branch process. Do not bypass checks.
2. In repository Settings -> Environments, create/select `staging`. Preserve
   existing protection settings. Configure deployment branches to permit `main`
   only if setting up this new environment; approval rules are the owner's choice.
3. The first `main` CI run builds the artifact; the subsequent Staging Deployment
   workflow publishes the package. Deployment will fail
   clearly until hosting configuration is provided. Open the GitHub profile's
   Packages page, select `itsd-4350-git-workflow-staging`, and make that package
   Public so Render can pull it without a private-registry token. This is an
   owner action; only application code and dependencies are in the image.
4. Sign in to https://dashboard.render.com and choose New -> Web Service ->
   Existing Image. Use the image URL/tag reported by the publish job summary.
   Do not connect the Git repository as a source. Choose Free compute and a
   free workspace plan. If payment or a paid plan is required, stop for review.
5. Name the service `itsd-4350-calculator-staging`; choose a region. Add runtime
   environment variables `APP_ENV=staging` and `SECRET_KEY` with a newly generated
   random value. Set health check path `/health`. Keep the image's default command.
   Create the service. This initial setup deployment is not the required automated
   deployment demonstration.
6. Copy the service ID (`srv-...`) and its public HTTPS URL from Render. In
   GitHub Settings -> Environments -> staging, add environment variables
   `RENDER_SERVICE_ID` and `STAGING_URL` (no trailing slash).
7. Create a Render API key in Render Account Settings -> API Keys. Store it as
   GitHub environment secret `RENDER_API_KEY` under `staging`. Keep the existing
   `SONAR_TOKEN` unchanged. Never include either token in evidence or ZIP files.
8. Re-run the failed job in the Staging Deployment workflow associated with the
   successful `main` CI run.
   Approve the GitHub environment deployment if existing rules require it.
   The job must deploy and smoke-test successfully before submission is complete.

If the first run already passed deployment because configuration existed,
verify its image digest and revision rather than triggering an unnecessary run.

## Smoke tests and failures

`python smoke_test.py https://YOUR-STAGING-URL COMMIT_SHA` checks `/health`, the
exact commit revision, and the calculator form. It carries the session cookie
and real CSRF token through the POST and confirms 5 + 3 = 8. Invalid numeric
input and missing CSRF must both return HTTP 400. Network/cold-start failures
retry within a bounded window. Persistent failure exits nonzero.

Tests and lint block the CI job. A failed SonarCloud gate on `main` blocks the
artifact job and deployment. Every downstream job uses `needs`; no failure is
converted into success.
The publishing job only runs on `main`. The deployment job serializes staging
updates, validates configuration, checks HTTP API errors, waits for the Render
deployment ID to reach `live`, and fails on terminal errors or timeout.
Smoke tests then require that exact revision, not just an HTTP 200 homepage.

Inspect GitHub job logs and the `deployment-evidence-<commit>-<attempt>` artifact
when deployment fails. The Staging Deployment workflow is separate from the CI
workflow; inspect both. Render's service Events and Logs explain startup failures.
A post-deploy smoke failure marks the workflow failed but does not automatically
roll back; the owner can redeploy a previously verified digest after diagnosis.
Do not remove checks, change gates, or expose secrets to obtain a passing run.

## Local validation

Use Python 3.14 in an isolated environment:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest==8.4.2 pytest-cov==7.0.0 flake8==7.3.0
.\.venv\Scripts\python.exe -m pytest --cov=. --cov-report=xml
.\.venv\Scripts\python.exe -m flake8 calculator.py test_calculator.py app.py test_app.py smoke_test.py test_deployment.py
.\.venv\Scripts\python.exe -m py_compile app.py calculator.py smoke_test.py test_deployment.py
```

The added tests exercise real HTTP requests, CSRF, revision mismatches, invalid
input, incorrect results, server failures, retry exhaustion, and staging startup
requirements. Docker/Gunicorn run on Linux in GitHub Actions and Render; neither
is claimed to have been tested natively on this Windows host.

## Evidence and demo

Final evidence must include the successful main CI/build/publish/deploy job URLs,
artifact metadata, Render deployment ID and immutable digest, staging URL,
successful health and calculator smoke output, and genuine failure logs showing
deployment was blocked or failed. Never use prior midterm CI evidence as proof
of this assignment's staging deployment.

Demo: open the successful main run, show the uploaded application artifact and
the dependent deployment job, open staging and add 5 and 3, visit `/health`, and
compare its revision with the run's commit SHA. Show the smoke-test log and a
genuine failed gate/job with its downstream job states.

Submission ZIP: pending successful hosted deployment and evidence collection.
Exclude `.git`, `.venv`, caches, credentials, and the previous midterm submission.

## Hosting references (checked November 1, 2026)

- https://render.com/docs/deploying-an-image (image deployment and digests)
- https://api-docs.render.com/reference/create-deploy (API imageUrl parameter)
- https://render.com/docs/free (Free service limits)

Free services sleep after 15 minutes idle and have 750 shared instance hours per
workspace per month. Cold starts take about a minute. Usage limits still apply;
with a payment method, excess bandwidth can be billed. Do not authorize paid
resources or add billing information for this assignment without approval.
