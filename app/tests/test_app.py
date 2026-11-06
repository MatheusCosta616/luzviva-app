from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_metrics_expoe_contadores():
    client.get("/")
    corpo = client.get("/metrics").text
    assert "http_requests_total" in corpo
    assert "http_request_duration_seconds" in corpo


def test_erro_desligado_por_padrao():
    assert client.get("/erro").status_code == 404
