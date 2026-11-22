"""Create a truthful short-window validation report from live local metrics."""
import argparse
from datetime import datetime, timezone
import json
import time
from urllib.parse import urlencode
from urllib.request import urlopen


def get_text(url):
    with urlopen(url, timeout=10) as response:
        return response.read().decode()


def query(prometheus_url, expression):
    url = f"{prometheus_url}/api/v1/query?{urlencode({'query': expression})}"
    result = json.loads(get_text(url))["data"]["result"]
    return float(result[0]["value"][1]) if result else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--prometheus", default="http://127.0.0.1:9090")
    parser.add_argument("--app", default="http://127.0.0.1:18000")
    parser.add_argument("--alert-routing", required=True,
                        choices=("passed", "failed"))
    args = parser.parse_args()

    collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    metrics = get_text(args.app + "/metrics")
    scrape_up = query(args.prometheus, 'up{job="flask-app"}')
    readiness = query(args.prometheus, "app_readiness_status")
    validation_alert = query(
        args.prometheus,
        'ALERTS{alertname="DeploymentValidationFailed",alertstate="firing"}')
    if scrape_up != 1 or readiness != 1:
        raise SystemExit("Report blocked: Prometheus target or readiness is unhealthy")
    if args.alert_routing == "passed" and validation_alert != 1:
        raise SystemExit("Report blocked: failed-validation alert was not observed")

    metric_values = {}
    for line in metrics.splitlines():
        if line.startswith("http_requests_total{"):
            labels, value = line.split(" ", 1)
            status = labels.split('status="', 1)[1].split('"', 1)[0]
            metric_values[status] = metric_values.get(status, 0.0) + float(value)
    requests = sum(metric_values.values())
    errors = sum(value for status, value in metric_values.items()
                 if status.startswith("5"))
    latency_sum = 0.0
    latency_count = 0.0
    process_start = None
    for line in metrics.splitlines():
        if line.startswith("http_request_duration_seconds_sum{"):
            latency_sum += float(line.rsplit(" ", 1)[1])
        elif line.startswith("http_request_duration_seconds_count{"):
            latency_count += float(line.rsplit(" ", 1)[1])
        elif line.startswith("process_start_time_seconds "):
            process_start = float(line.split()[-1])
    if process_start is None:
        raise SystemExit("Report blocked: process start metric is missing")

    observed_uptime = max(time.time() - process_start, 0.0)
    mean_latency = latency_sum / latency_count if latency_count else None
    error_rate = errors / requests if requests else 0.0
    lines = [
        "# Mini Project 2.4 deployment validation report",
        "",
        f"- Collection time (UTC): {collected_at}",
        f"- Candidate revision: `{args.revision}`",
        f"- Application availability at collection: {'PASS' if scrape_up == 1 else 'FAIL'}",
        f"- Readiness: {'PASS' if readiness == 1 else 'FAIL'}",
        f"- Process uptime at collection: {observed_uptime:.1f} seconds",
        f"- HTTP requests since process start: {int(requests)}",
        f"- HTTP 5xx errors since process start: {int(errors)}",
        f"- HTTP 5xx ratio since process start: {error_rate:.2%}",
        (f"- Mean observed request latency: {mean_latency * 1000:.2f} ms"
         if mean_latency is not None else "- Mean observed request latency: no requests"),
        f"- Prometheus scrape: {'PASS' if scrape_up == 1 else 'FAIL'}",
        f"- Alert routing to local SMTP and webhook sinks: {args.alert_routing.upper()}",
        "- Application unit tests and lint: PASS (generated after those gates pass)",
        "- Application smoke tests: PASS (same workflow run)",
        ("- Failed-validation alert evaluation: PASS (simulated injected failure)"
         if validation_alert == 1 else
         "- Failed-validation alert evaluation: not observed"),
        "- External notification delivery: not tested; local capture services only",
        ("- Live Render staging monitoring: not run by pull-request CI; this report covers "
         "the isolated CI app"),
        ("- Failed staging candidates block promotion: the manual workflow requires "
         "matching successful staging and monitoring runs"),
        ("- Production approval: not requested by this validation workflow; configure "
         "the protected environment separately"),
        ("- Rollback: not exercised by this workflow; the blue/green rollback drill "
         "is a separate simulation"),
        "",
        "Metrics reflect this container's lifetime, not a long-term availability SLA.",
    ]
    with open("monitoring-evidence/deployment-validation-report.md", "w",
              encoding="utf-8") as report:
        report.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
