import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_home_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Simple Web Calculator" in response.data


def test_add_numbers(client):
    response = client.post(
        "/calculate",
        data={"a": "5", "b": "3"}
    )
    assert response.status_code == 200
    assert b"Result: 8.0" in response.data


def test_invalid_input(client):
    response = client.post(
        "/calculate",
        data={"a": "abc", "b": "3"}
    )
    assert response.status_code == 400


def test_missing_input(client):
    response = client.post(
        "/calculate",
        data={"a": "5"}
    )
    assert response.status_code == 400
