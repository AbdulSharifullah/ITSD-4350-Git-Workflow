# Mini Project 2.4: monitoring, validation, and release governance

This change instruments the existing Flask calculator, adds distinct liveness
and readiness endpoints, and supplies a Docker Compose stack for Prometheus,
Alertmanager, SMTP capture, and webhook capture. The existing `/health` route
and staging deployment interface remain compatible.

## Run locally

```bash
docker compose -f docker-compose.monitoring.yml up -d --build --wait
python smoke_test.py http://127.0.0.1:18000 local
docker compose -f docker-compose.monitoring.yml exec -T prometheus \
  promtool check config /etc/prometheus/prometheus.yml
docker compose -f docker-compose.monitoring.yml exec -T alertmanager \
  amtool check-config /etc/alertmanager/alertmanager.yml
```

Open Prometheus at http://127.0.0.1:9090, Alertmanager at
http://127.0.0.1:9093, and Mailpit at http://127.0.0.1:8025. The webhook test
receiver health is at http://127.0.0.1:8081/health. These are local test tools;
no notification is sent externally. See [`monitoring/README.md`](monitoring/README.md)
and [`RELEASE-GOVERNANCE.md`](RELEASE-GOVERNANCE.md).

## CI evidence

The `MP2.4 Monitoring Validation` GitHub Actions workflow runs unit tests,
configuration checks, an application smoke test, verifies a successful
Prometheus scrape, tests email and webhook routing against local capture
services, and uploads genuine short-window evidence. CI evidence is not a
claim of long-term uptime or external notification delivery.

On `main`, the staging workflow also runs Prometheus against the actual Render
staging URL for a short observation window after deployment. It records uptime,
request counts, latency, error rate, readiness, and critical alerts in the
deployment evidence artifact. A failed target, readiness check, revision match,
or critical alert fails the staging workflow.

The monitoring validation run also produces a source-only submission ZIP as a
separate GitHub Actions artifact. It excludes generated evidence, local runtime
state, caches, and credentials.

