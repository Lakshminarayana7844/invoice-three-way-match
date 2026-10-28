from fastapi.testclient import TestClient

from src.api import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_match_unknown_po():
    r = client.post("/match", json={"invoices": [{
        "po_number": "PO-0000000", "vendor_id": "V0001", "material": "MAT-1001",
        "quantity": 5, "unit_price": 12.0, "invoice_date": "2025-06-01"}]})
    assert r.status_code == 200
    res = r.json()["results"][0]
    assert res["outcome"] == "BLOCK"
    assert res["reasons"]


def test_match_validation_error():
    r = client.post("/match", json={"invoices": [{
        "po_number": "PO-1", "vendor_id": "V1", "material": "M",
        "quantity": -3, "unit_price": 1.0, "invoice_date": "2025-06-01"}]})
    assert r.status_code == 422


def test_exceptions_endpoint():
    r = client.get("/invoices/exceptions?top=5")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] > 0
    assert len(body["results"]) == 5
    outcomes = {x["outcome"] for x in body["results"]}
    assert outcomes <= {"REVIEW", "BLOCK"}
