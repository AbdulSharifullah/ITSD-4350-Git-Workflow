"""Flask calculator with low-cardinality Prometheus exposition metrics."""
import os
import threading
import time
from collections import Counter

from flask import Flask, Response, request
from flask_wtf.csrf import CSRFProtect, generate_csrf

from calculator import add

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "local-development-only")
csrf = CSRFProtect(app)

if os.environ.get("APP_ENV") == "staging":
    if not os.environ.get("SECRET_KEY"):
        raise RuntimeError("Staging requires SECRET_KEY")
    app.config.update(SESSION_COOKIE_SECURE=True,
                      SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE="Lax")

_metrics_lock = threading.Lock()
_request_counts = Counter()
_request_durations = Counter()
_request_duration_sum = Counter()
_request_duration_count = Counter()
_duration_buckets = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
_process_started = time.time()
_readiness_ok = True


@app.before_request
def start_request_timer():
    request._metrics_started = time.perf_counter()


@app.after_request
def record_request_metrics(response):
    if request.endpoint != "metrics":
        method = request.method
        status = str(response.status_code)
        started = getattr(request, "_metrics_started", time.perf_counter())
        elapsed = max(time.perf_counter() - started, 0.0)
        key = (method, status)
        with _metrics_lock:
            _request_counts[key] += 1
            _request_duration_count[method] += 1
            _request_duration_sum[method] += elapsed
            for bucket in _duration_buckets:
                if elapsed <= bucket:
                    _request_durations[(method, bucket)] += 1
    return response


@app.get("/health")
def health():
    """Keep the response used by earlier deployment tooling."""
    return {"status": "ok",
            "revision": os.environ.get("APP_REVISION", "local")}


@app.get("/health/live")
def live():
    return {"status": "alive"}, 200


@app.get("/health/ready")
def ready():
    if not _readiness_ok:
        return {"status": "not_ready"}, 503
    return {"status": "ready",
            "revision": os.environ.get("APP_REVISION", "local")}, 200


@app.get("/metrics")
def metrics():
    """Expose request counters, latency histograms, and process health."""
    lines = [
        "# HELP http_requests_total Total HTTP requests, excluding /metrics.",
        "# TYPE http_requests_total counter",
    ]
    with _metrics_lock:
        for (method, status), value in sorted(_request_counts.items()):
            lines.append(
                f'http_requests_total{{method="{method}",status="{status}"}} '
                f"{value}")
        lines.extend([
            "# HELP http_request_duration_seconds Request latency in seconds.",
            "# TYPE http_request_duration_seconds histogram",
        ])
        methods = sorted(_request_duration_count)
        for method in methods:
            for bucket in _duration_buckets:
                value = _request_durations[(method, bucket)]
                lines.append(
                    f'http_request_duration_seconds_bucket{{method="{method}",'
                    f'le="{bucket:g}"}} {value}')
            count = _request_duration_count[method]
            total = _request_duration_sum[method]
            lines.append(
                f'http_request_duration_seconds_bucket{{method="{method}",'
                f'le="+Inf"}} {count}')
            lines.append(
                f'http_request_duration_seconds_sum{{method="{method}"}} '
                f"{total:.9f}")
            lines.append(
                f'http_request_duration_seconds_count{{method="{method}"}} '
                f"{count}")
    revision = os.environ.get("APP_REVISION", "local")
    lines.extend([
        "# HELP app_readiness_status Readiness state (1=ready, 0=not ready).",
        "# TYPE app_readiness_status gauge",
        f"app_readiness_status {1 if _readiness_ok else 0}",
        "# HELP process_start_time_seconds Process start Unix timestamp.",
        "# TYPE process_start_time_seconds gauge",
        f"process_start_time_seconds {_process_started:.3f}",
        "# HELP app_build_info Build revision information.",
        "# TYPE app_build_info gauge",
        f'app_build_info{{revision="{revision}"}} 1',
        "",
    ])
    return Response(
        "\n".join(lines),
        content_type="text/plain; version=0.0.4; charset=utf-8")


@app.route("/", methods=["GET"])
def home():
    token = generate_csrf()
    return f"""
    <h1>Simple Web Calculator</h1>
    <form method="POST" action="/calculate">
        <input type="hidden" name="csrf_token" value="{token}">
        <input type="number" name="a" step="any" required>
        <input type="number" name="b" step="any" required>
        <button type="submit">Add</button>
    </form>
    """


@app.route("/calculate", methods=["POST"])
def calculate():
    try:
        a = float(request.form["a"])
        b = float(request.form["b"])
    except (KeyError, ValueError):
        return "Invalid input", 400

    result = add(a, b)
    return f"<h1>Result: {result}</h1><a href='/'>Back</a>"


if __name__ == "__main__":
    app.run(debug=False)
