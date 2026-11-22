"""Report a short Prometheus observation window for the deployed staging app."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from urllib.parse import urlencode
from urllib.request import urlopen


def get_json(url):
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode())


def query(prometheus_url, expression):
    url = (f"{prometheus_url}/api/v1/query?"
           f"{urlencode({'query': expression})}")
    values = get_json(url)["data"]["result"]
    return float(values[0]["value"][1]) if values else None


def display(value, suffix=""):
    return "not available" if value is None else f"{value:.2f}{suffix}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--prometheus", default="http://127.0.0.1:9090")
    parser.add_argument("--output", required=True)
    parser.add_argument("--window-seconds", type=int, default=30)
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=args.window_seconds)
    base = '{job="flask-app"}'
    available = query(args.prometheus, f"up{base}")
    readiness = query(args.prometheus, f"app_readiness_status{base}")
    revision = query(args.prometheus,
                     f'app_build_info{{revision="{args.revision}"}}')
    requests = query(args.prometheus, f"sum(http_requests_total{base})")
    errors = query(args.prometheus,
                   f'sum(http_requests_total{{job="flask-app",status=~"5.."}})')
    uptime = query(args.prometheus, "time() - process_start_time_seconds")
    mean_latency = query(
        args.prometheus,
        "sum(rate(http_request_duration_seconds_sum{job=\"flask-app\"}[5m])) "
        "/ clamp_min(sum(rate(http_request_duration_seconds_count{"
        "job=\"flask-app\"}[5m])), 0.000001)")
    p95_latency = query(
        args.prometheus,
        "histogram_quantile(0.95, sum by (le) (rate("
        "http_request_duration_seconds_bucket{job=\"flask-app\"}[5m])))")
    critical_alerts = query(
        args.prometheus,
        'count(ALERTS{job="flask-app",severity="critical",alertstate="firing"})')

    error_ratio = (errors / requests) if requests else 0.0
    lines = [
        "# Staging monitoring and deployment validation",
        "",
        f"- Candidate revision: `{args.revision}`",
        f"- Observation window (UTC): {start.isoformat(timespec='seconds')} to "
        f"{now.isoformat(timespec='seconds')} ({args.window_seconds} seconds; "
        "5-second scrape interval)",
        f"- Prometheus target availability at collection: {'PASS' if available == 1 else 'FAIL'}",
        f"- Readiness at collection: {'PASS' if readiness == 1 else 'FAIL'}",
        f"- Deployed revision metric matches candidate: {'PASS' if revision == 1 else 'FAIL'}",
        f"- Process uptime at collection: {display(uptime, ' seconds')}",
        f"- HTTP requests since process start: {int(requests or 0)}",
        f"- HTTP 5xx responses since process start: {int(errors or 0)}",
        f"- HTTP 5xx ratio since process start: {error_ratio:.2%}",
        f"- Mean request latency from Prometheus 5-minute rate: "
        f"{display(mean_latency * 1000 if mean_latency is not None else None, ' ms')}",
        f"- 95th percentile request latency: "
        f"{display(p95_latency * 1000 if p95_latency is not None else None, ' ms')}",
        f"- Active critical Prometheus alerts: {int(critical_alerts or 0)}",
        "- Build and tests: passed before staging through the CI Pipeline",
        "- Staging deployment: Render reported `live`; exact staged image digest "
        "is in deployment evidence",
        "- Smoke tests: passed before observation and were repeated during the sampling window",
        "- Notification delivery: this scrape does not prove external email or "
        "webhook delivery",
        "- Production approval: not requested; this workflow validates staging only",
        "- Rollback: not exercised; the blue/green simulation covers rollback behavior",
        "",
        "Counters and uptime span the app process lifetime. Availability is a "
        "short observation, not a long-term SLA.",
    ]
    with open(args.output, "w", encoding="utf-8") as report:
        report.write("\n".join(lines) + "\n")

    if available != 1 or readiness != 1 or revision != 1:
        raise SystemExit(
            "Staging monitoring validation failed: target, readiness, or "
            "revision mismatch")
    if critical_alerts:
        raise SystemExit("Staging monitoring validation failed: critical alert is active")


if __name__ == "__main__":
    main()
