"""Verify a running deployment using only the Python standard library."""
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
        with opener.open(base_url + path, timeout=30) as response:
            return response.read().decode()

    health = json.loads(get("/health"))
    if health != {"status": "ok", "revision": revision}:
        raise ValueError("Health response does not match expected revision")
    parser = TokenParser()
    parser.feed(get("/"))
    if not parser.token:
        raise ValueError("Calculator form is missing its CSRF token")

    def post(data):
        request = Request(base_url + "/calculate",
                          data=urlencode(data).encode(),
                          headers={"Referer": base_url + "/"})
        return opener.open(request, timeout=30)

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
    print(f"PASS: revision={revision}; health, 5+3=8, invalid input, CSRF")


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
            print(f"Attempt {attempt}/{args.attempts}: {type(error).__name__}")
            if attempt == args.attempts:
                raise SystemExit("Smoke tests failed") from error
            time.sleep(15)


if __name__ == "__main__":
    main()
