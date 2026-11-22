# Mini Project 2.4 monitoring

This local stack runs the existing Flask calculator, Prometheus, Alertmanager,
Mailpit (SMTP capture), and a small webhook receiver. Mailpit and the webhook
receiver are test sinks: they demonstrate both notification routes without
sending email or webhooks to external recipients. No credentials are included.

## Start and verify

From the repository root:

```bash
docker compose -f docker-compose.monitoring.yml up -d --build --wait
docker compose -f docker-compose.monitoring.yml exec -T prometheus \
  promtool check config /etc/prometheus/prometheus.yml
docker compose -f docker-compose.monitoring.yml exec -T alertmanager \
  amtool check-config /etc/alertmanager/alertmanager.yml
docker compose -f docker-compose.monitoring.yml exec -T prometheus \
  promtool test rules /etc/prometheus/alert-rules.test.yml
python smoke_test.py http://127.0.0.1:18000 local
```

Prometheus is available at http://127.0.0.1:9090, Alertmanager at
http://127.0.0.1:9093, the Mailpit inbox at http://127.0.0.1:8025, and the
webhook receiver health endpoint at http://127.0.0.1:8081/health. All host
listeners bind to loopback. Stop with `docker compose -f
docker-compose.monitoring.yml down`.

## Metrics and alert thresholds

The app emits request totals by method and status code, latency histogram
buckets, readiness, process start time, and build revision. `/metrics` is
scraped every five seconds. Application paths are not used as metric labels,
keeping cardinality bounded. The small staging container uses one Gunicorn
worker with four threads so its in-memory counters include every request.
`/health` remains compatible with the earlier
deployment pipeline; `/health/live` and `/health/ready` provide separate
liveness and readiness checks.

| Alert | Condition | Hold time |
|---|---|---:|
| ApplicationUnavailable | Prometheus target is down | 1 minute |
| ReadinessCheckFailed | readiness gauge is zero | 30 seconds |
| ElevatedHttp5xxRate | 5xx exceeds 5% with meaningful traffic | 2 minutes |
| ExcessiveRequestLatency | 5 minute p95 exceeds 500 ms | 2 minutes |
| DeploymentValidationFailed | validation status gauge is zero | immediate |

The validation status is scraped from the local Pushgateway. The CI integration
test pushes a simulated failed validation and confirms that the Prometheus
alert fires and reaches both local notification sinks. `promtool test rules`
also exercises all five alert expressions using fixture time series. This
simulated failure verifies the alert path; it is not evidence that a real
staging deployment failed. The other application rules use metrics emitted by
the Flask app.

For real notifications, replace the test SMTP and webhook endpoints with
organization-managed endpoints, store credentials in the deployment secret
manager, and verify delivery from the target environment. The local test sink
does not establish production notification delivery.
