"""End-to-end route tests using the Flask test client."""
import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Translation Alignment" in resp.data


def test_index_has_cta_to_mark_1_1(client):
    resp = client.get("/")
    assert b"/mark/1/1" in resp.data
