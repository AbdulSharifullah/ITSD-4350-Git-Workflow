"""Verify a running calculator using the Python standard library."""
import argparse
from http.cookiejar import CookieJar
from html.parser import HTMLParser
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


class TokenParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.token = None

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "input" and fields.get("name") == "csrf_token":
            self.token = fields.get("value")


def verify(base_url, revision):
    base_url = base_url.rstrip("/")
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def get(path):
        with opener.open(base_url + path, timeout=10) as response:
            return response.read().decode()

    health = json.loads(get("/health"))
    if health != {"status": "ok", "revision": revision}:
        raise ValueError("Health response does not match expected revision")
    if json.loads(get("/health/live")).get("status") != "alive":
        raise ValueError("Liveness check failed")
    readiness = json.loads(get("/health/ready"))
    if (readiness.get("status") != "ready"
            or readiness.get("revision") != revision):
        raise ValueError("Readiness check failed or revision is incorrect")

    parser = TokenParser()
    parser.feed(get("/"))
    if not parser.token:
        raise ValueError("Calculator form is missing its CSRF token")

    def post(data):
        request = Request(
            base_url + "/calculate", data=urlencode(data).encode(),
            headers={"Referer": base_url + "/"})
        return opener.open(request, timeout=10)

    with post({"a": "5", "b": "3", "csrf_token": parser.token}) as response:
        if "Result: 8.0" not in response.read().decode():
            raise ValueError("Calculator returned an incorrect result")
    for data in ({"a": "abc", "b": "3", "csrf_token": parser.token},
                 {"a": "5", "b": "3"}):
        try:
            with post(data):
                raise ValueError("Invalid input or missing CSRF was accepted")
        except HTTPError as error:
            if error.code != 400:
                raise

    metrics = get("/metrics")
    expected_metrics = (
        "http_requests_total", "http_request_duration_seconds_bucket",
        "app_readiness_status", "process_start_time_seconds", "app_build_info")
    for metric in expected_metrics:
        if metric not in metrics:
            raise ValueError(f"Monitoring endpoint is missing metric {metric}")
    if f'revision="{revision}"' not in metrics:
        raise ValueError("Monitoring revision does not match expected release")
    print(f"PASS: {revision}; health, calculator, CSRF, and metrics")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("revision")
    parser.add_argument("--attempts", type=int, default=20)
    args = parser.parse_args()
    for attempt in range(1, args.attempts + 1):
        try:
            verify(args.base_url, args.revision)
            return
        except (HTTPError, URLError, ValueError, TimeoutError) as error:
            print(
                f"Attempt {attempt}/{args.attempts}: "
                f"{type(error).__name__}: {error}")
            if attempt == args.attempts:
                raise SystemExit("Smoke tests failed") from error
            time.sleep(15)


if __name__ == "__main__":
    main()
