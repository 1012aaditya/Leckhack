from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_which_database_is_in_use():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "live_database" in body and "source" in body


def test_audit_endpoint_returns_a_report():
    response = client.post(
        "/audit", json={"text": "Bush v. Gore, 531 U.S. 98 (2000). Id. at 99."}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["citations"][0]["verdict"] == "green"


def test_blank_text_rejected():
    assert client.post("/audit", json={"text": "   "}).status_code == 422
    assert client.post("/audit", json={"text": ""}).status_code == 422
