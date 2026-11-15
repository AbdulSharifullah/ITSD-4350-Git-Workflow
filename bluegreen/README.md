# Mini Project 2.3: Blue/Green production promotion

This assignment runs the calculator in two Docker Compose services behind Nginx.
Blue starts with Version 1 (baseline commit `9886126`). Green runs Version 2,
the exact CI image already used by a successful Render staging deployment.
Versions identify Git revisions; the calculator's arithmetic stays the same.
The production simulation is temporary and reachable only inside the runner.
Render staging and the Mini Project 2.2 Terraform configuration are unchanged.

## Run the demonstration

1. Review and merge the feature PR through the existing protected branch process.
2. Wait for the normal **CI Pipeline** and **Staging Deployment** runs for that
   exact main commit to succeed. Copy the Staging Deployment run ID from its URL.
3. Open **Actions → Production Blue Green Simulation → Run workflow** on `main`.
4. Enter that staging run ID. Check the explicit promotion approval box only
   after reviewing the revision and this procedure. Click **Run workflow**.
   This is advance human approval for promotion after successful validation and
   for deliberately stopping Green during the rollback drill. It is not a
   separate mid-run review or a claim that approval was supplied by automation.
5. Inspect both jobs. Download `bluegreen-demonstration-<run>-<attempt>` within
   30 days. A validation-only run does not demonstrate deployment.

The validation job checks code and Compose syntax; it creates no application
containers. The **demonstrate** job performs the entire deployment lifecycle on
one Ubuntu runner. No container or deployment state is transferred between jobs.
The run verifies staging success for the exact revision, downloads that run's
deployment summary, and pulls the exact registry digest recorded as deployed
and tested there. It checks the embedded revision and runs that image without
rebuilding Version 2. This preserves the image originally built by CI and
published by the existing staging workflow. Blue is built from the pinned
earlier source commit. Image identity and staging run are recorded in evidence.

The controller initializes Blue, deploys and tests Green while Blue stays active,
and proves a wrong live revision blocks promotion without changing routing.
It repeats validation at the approval checkpoint, checks Nginx configuration,
gracefully reloads Nginx, and verifies Version 2 through the stable endpoint.
It checks Blue's container ID and start timestamp to confirm Blue was not
recreated or restarted. It then stops Green, observes a real endpoint failure,
automatically restores Blue, and repeats the calculator tests.

## Deliverable map

| Required deliverable | Files |
|---|---|
| Architecture diagram | `evidence/architecture.png`; maintained `architecture.svg` |
| Deployment automation | `compose.yml`, `nginx.conf.template`, `manage.py`, `demonstrate.py`, workflow in `.github/workflows/production-bluegreen.yml` |
| Traffic-switch demonstration | Four browser PNGs, `demonstration.log`, `events.jsonl`, `requests.jsonl`, `results.json`, image/staging provenance and container diagnostics in `evidence/` |
| Emergency rollback documentation | `ROLLBACK.md` |

The browser screenshots show the actual calculator page and a read-only panel
of the observed endpoint health response, deployment headers and UTC timestamp.
They are captured by Chromium while the containers are running, not generated
representations of successful results. Events and raw request samples provide
the corresponding machine-readable evidence.

## Measurements and limits

The HTTP monitor runs before, during and after promotion and rollback. Every
sample records its UTC timestamp, phase, revision, deployment headers, request
duration and success/failure. It targets `/health` about every 50 milliseconds
after the preceding request completes, with a 2-second timeout. Functionality
tests separately verify `5 + 3 = 8`, invalid input rejection and CSRF protection.
`results.json` reports actual per-phase request and failed-request counts,
promotion duration, rollback execution duration and failure-to-recovery duration.
The latter includes the stop command and failure detection; it is not an exact
timestamp for when a real user's first request would have failed.

Zero observed failed promotion samples means only that this measured localhost
sample found none. It does not prove universal zero downtime. The deliberately
injected outage is recorded separately from promotion. This lab uses loopback
HTTP and a stateless calculator; public HTTPS, shared session storage, database
migrations, real load and persistent production hosting are outside its scope.
The prior version remains running until the simulation's final cleanup.

## Reproduce on an existing Linux Docker host

Prerequisites: Docker Engine with Compose v2, Python 3, the two locally loaded
images and their embedded revisions. For browser evidence, install Playwright
1.56.0 and its Chromium browser. No local installation was performed on the
Windows workstation for this assignment.

```bash
export BLUE_IMAGE=calculator:blue GREEN_IMAGE=calculator:<approved-commit>
python bluegreen/manage.py init --revision <baseline-commit>
python bluegreen/manage.py deploy --revision <approved-commit>
python bluegreen/manage.py validate --color green --revision <approved-commit>
# A human must approve before using --approve.
python bluegreen/manage.py promote --revision <approved-commit> --approve
python bluegreen/manage.py rollback
docker compose -f bluegreen/compose.yml down --remove-orphans
```

Run commands from the repository root, sequentially, with one operator. Runtime
state, generated session secrets and evidence are ignored by Git. Never upload
`runtime/`, full Docker inspection output, tokens or credentials. The workflow
uploads only selected evidence and cleans up this named Compose project. Its
always-run upload still preserves diagnostics if the demonstration fails.

## References

- [Compose up](https://docs.docker.com/reference/cli/docker/compose/up/)
- [Nginx configuration testing and graceful reload](https://nginx.org/en/docs/switches.html)
- [Manual workflow inputs](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)
