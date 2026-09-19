from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_describes_every_component():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    components = body["components"]
    for key in (
        "database",
        "database_authoritative",
        "judge",
        "judge_is_model_based",
        "embeddings",
    ):
        assert key in components


def test_audit_returns_a_report():
    response = client.post(
        "/audit", json={"text": "Bush v. Gore, 531 U.S. 98 (2000). Id. at 99."}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["citations"][0]["verdict"] == "green"


def test_audit_reports_stage_two_when_opinion_text_is_held():
    response = client.post(
        "/audit",
        json={
            "text": "A landlord may not resort to self-help eviction, "
                    "Whitfield v. Cedar Ridge Apartments, 58 F.3d 900 (1995)."
        },
    )
    item = response.json()["citations"][0]
    assert item["support"] is not None
    assert item["support"]["stance"] == "supports"
    # Anything displayed as a quote must have passed the verbatim guard.
    assert item["support"]["quote_verified"] is True


def test_synthetic_opinion_text_is_labelled_as_such():
    """Invented demo text must never be presented as a real court record."""
    response = client.post(
        "/audit",
        json={"text": "A tenant cannot waive habitability, Alvarez v. Northgate, "
                      "42 F.3d 100 (1994)."},
    )
    notes = " ".join(response.json()["citations"][0]["notes"])
    assert "synthetic" in notes.lower()


def test_blank_text_rejected():
    assert client.post("/audit", json={"text": "   "}).status_code == 422
    assert client.post("/audit", json={"text": ""}).status_code == 422


def test_non_pdf_upload_rejected():
    response = client.post(
        "/audit/pdf", files={"file": ("notes.txt", b"hello", "text/plain")}
    )
    assert response.status_code == 422


def test_frontend_is_served():
    assert client.get("/").status_code == 200
