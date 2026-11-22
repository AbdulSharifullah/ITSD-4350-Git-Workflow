import pytest

import app as app_module
from app import app


@pytest.fixture
def client():
    with app_module._metrics_lock:
        app_module._request_counts.clear()
        app_module._request_durations.clear()
        app_module._request_duration_sum.clear()
        app_module._request_duration_count.clear()
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as test_client:
        yield test_client


def test_home_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Simple Web Calculator" in response.data


def test_add_numbers(client):
    response = client.post("/calculate", data={"a": "5", "b": "3"})
    assert response.status_code == 200
    assert b"Result: 8.0" in response.data


@pytest.mark.parametrize("data", [{"a": "abc", "b": "3"}, {"a": "5"}])
def test_invalid_or_missing_input(client, data):
    response = client.post("/calculate", data=data)
    assert response.status_code == 400


def test_liveness_and_readiness(client):
    assert client.get("/health/live").status_code == 200
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.get_json()["status"] == "ready"


def test_readiness_failure_is_reported_in_metrics(client, monkeypatch):
    monkeypatch.setattr(app_module, "_readiness_ok", False)
    assert client.get("/health/ready").status_code == 503
    metrics = client.get("/metrics").get_data(as_text=True)
    assert "app_readiness_status 0" in metrics


def test_metrics_count_status_and_latency_without_self_counting(client):
    client.get("/health/live")
    client.get("/missing-route")
    metrics = client.get("/metrics").get_data(as_text=True)
    assert 'http_requests_total{method="GET",status="200"}' in metrics
    assert 'http_requests_total{method="GET",status="404"}' in metrics
    assert "http_request_duration_seconds_bucket" in metrics
    assert "app_build_info" in metrics
    assert 'http_requests_total{method="GET",status="200"} 1' in metrics
