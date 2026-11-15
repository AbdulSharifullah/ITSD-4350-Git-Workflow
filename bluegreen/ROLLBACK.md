# Emergency rollback

Use rollback when the promoted calculator is failing and the previous
environment is still running on the same Docker host. Rollback changes only
Nginx routing; it does not rebuild, redeploy or restart the previous application.
The demonstration automatically calls this same operation after detecting the
deliberately stopped Green container.

## Prerequisites

- Access to the same runner/host and checkout with `bluegreen/runtime/state.json`.
- Docker and Compose, Python 3 and the original `BLUE_IMAGE`/`GREEN_IMAGE` values.
- Previous healthy environment retained, with its correct image and revision.
- Run from the repository root; do not run deployment commands concurrently.

## Commands

```bash
python bluegreen/manage.py status
docker compose -f bluegreen/compose.yml ps -a
python bluegreen/manage.py rollback
curl --fail --include http://127.0.0.1:18080/health
python smoke_test.py http://127.0.0.1:18080 <previous-revision> --attempts 1
```

The controller checks the recorded previous slot directly: correct revision,
healthy response, correct calculator result, invalid-input rejection and CSRF
rejection. If those checks fail, routing stays unchanged. If they pass, it
writes the previous route, executes `nginx -t`, gracefully reloads Nginx and
verifies the restored revision through port 18080. It commits deployment state
only after endpoint validation succeeds. It prints a UTC timestamp and elapsed
rollback seconds. A configuration/reload/endpoint failure restores the prior
route file and attempts to reload it, then raises an error for investigation.

Expected result for this drill: `X-Deployment-Color: blue`,
`X-Deployment-Version: Version 1`, health revision `988612607ef85e7accea16aad881f8f7bd6d519e`,
and `PASS` for the calculator smoke tests. Green remains stopped after the
injected failure; Blue is the already-running original container.

If rollback fails, inspect `demonstration.log`, `container-logs.txt` and Nginx
errors. Do not rebuild the previous slot or overwrite state as a shortcut.
The retained slot is protected against accidental deployment overwrite.

GitHub-hosted runners disappear after the job. These commands cannot restore
containers from an earlier completed run; start a new complete simulation
instead. The workflow saves evidence before termination and removes only its
own Compose resources. Nothing here rolls back the separate Render service.
