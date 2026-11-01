"""Exercise deployment checks against a real HTTP server with CSRF enabled."""
from contextlib import contextmanager
import os
import subprocess
import sys
from threading import Thread
from urllib.error import HTTPError

import pytest
from werkzeug.serving import make_server

from app import app
import smoke_test


@contextmanager
def live_app(monkeypatch):
    monkeypatch.setitem(app.config, "SECRET_KEY", "test-only-secret")
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", True)
    monkeypatch.setitem(app.config, "SESSION_COOKIE_SECURE", False)
    monkeypatch.setenv("APP_REVISION", "test-revision")
    server = make_server("127.0.0.1", 0, app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_live_smoke_and_wrong_revision(monkeypatch, capsys):
    with live_app(monkeypatch) as url:
        smoke_test.verify(url, "test-revision")
        assert "PASS:" in capsys.readouterr().out
        with pytest.raises(ValueError, match="expected revision"):
            smoke_test.verify(url, "wrong-revision")


def test_staging_requires_secret_and_secure_cookies():
    env = {**os.environ, "APP_ENV": "staging"}
    env.pop("SECRET_KEY", None)
    result = subprocess.run([sys.executable, "-c", "import app"],
                            env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "Staging requires SECRET_KEY" in result.stderr
    env["SECRET_KEY"] = "test-only-secret"
    result = subprocess.run(
        [sys.executable, "-c", "from app import app; "
         "assert app.config['SESSION_COOKIE_SECURE']; "
         "assert app.config['SESSION_COOKIE_HTTPONLY']; "
         "assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'"],
        env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_smoke_cli_success(monkeypatch):
    with live_app(monkeypatch) as url:
        monkeypatch.setattr(
            sys, "argv", ["smoke_test.py", url, "test-revision",
                          "--attempts", "1"])
        smoke_test.main()


def test_smoke_cli_retries_then_fails(monkeypatch, capsys):
    def fail(*args):
        raise ValueError("wrong revision")

    monkeypatch.setattr(smoke_test, "verify", fail)
    monkeypatch.setattr(smoke_test.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        sys, "argv", ["smoke_test.py", "http://localhost", "revision",
                      "--attempts", "2"])
    with pytest.raises(SystemExit, match="Smoke tests failed"):
        smoke_test.main()
    assert "Attempt 2/2" in capsys.readouterr().out


def test_smoke_rejects_missing_token(monkeypatch):
    monkeypatch.setitem(app.view_functions, "home", lambda: "no form")
    with live_app(monkeypatch) as url:
        with pytest.raises(ValueError, match="CSRF token"):
            smoke_test.verify(url, "test-revision")


def test_smoke_rejects_wrong_calculation(monkeypatch):
    monkeypatch.setitem(app.view_functions, "calculate", lambda: "Result: 9")
    with live_app(monkeypatch) as url:
        with pytest.raises(ValueError, match="incorrect result"):
            smoke_test.verify(url, "test-revision")


def test_smoke_rejects_invalid_input_acceptance(monkeypatch):
    original = app.view_functions["calculate"]
    from flask import request

    def bad_calculator():
        if request.form.get("a") == "abc":
            return "incorrectly accepted"
        return original()

    monkeypatch.setitem(app.view_functions, "calculate", bad_calculator)
    with live_app(monkeypatch) as url:
        with pytest.raises(ValueError, match="was accepted"):
            smoke_test.verify(url, "test-revision")


def test_smoke_rejects_server_error(monkeypatch):
    original = app.view_functions["calculate"]
    from flask import request

    def bad_calculator():
        if request.form.get("a") == "abc":
            return "failure", 500
        return original()

    monkeypatch.setitem(app.view_functions, "calculate", bad_calculator)
    with live_app(monkeypatch) as url:
        with pytest.raises(HTTPError) as error:
            smoke_test.verify(url, "test-revision")
        assert error.value.code == 500
