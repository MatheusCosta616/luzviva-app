import os
import tempfile

os.environ["LUZVIVA_DATA_DIR"] = tempfile.mkdtemp()

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health_e_site():
    assert client.get("/health").json()["status"] == "ok"
    assert "LuzViva" in client.get("/").text


def test_metrics_expoe_contadores():
    client.get("/api/fila")
    corpo = client.get("/metrics").text
    assert "http_requests_total" in corpo and "http_request_duration_seconds" in corpo


def test_erro_desligado_por_padrao():
    assert client.get("/erro").status_code == 404


def test_saidas_do_pipeline_no_envelope():
    for rota, view in [("/api/luminarias", "vw_mvp_mapa_luminarias"), ("/api/fila", "vw_mvp_fila_manutencao"),
                       ("/api/painel", "vw_mvp_painel_subprefeitura")]:
        corpo = client.get(rota).json()
        assert corpo["view"] == view and corpo["linhas"] == len(corpo["dados"]) > 0
    prioridades = [f["prioridade"] for f in client.get("/api/fila").json()["dados"]]
    assert prioridades == sorted(prioridades, reverse=True)


def test_medicao_valida_e_exportada():
    m = {"id_medicao": "M1", "robo_id": "ROBO-01", "data_hora": "2026-11-10T19:24:10", "lat": -23.55,
         "lon": -46.63, "lux": 0.4, "situacao_robo": "apagada", "sensor": "LDR-GL5528",
         "bateria_pct": 87, "area_piloto": "SE", "placa": "IP0723371"}
    assert client.post("/api/medicoes", json=m).status_code == 201
    assert client.post("/api/medicoes", json={**m, "placa": "XX"}).status_code == 422


def test_chamado_sem_duplicar_e_atualiza():
    novo = {"placa": "IP0799999", "area_piloto": "SE", "prioridade": 60, "situacao_detectada": "apagada"}
    criado = client.post("/api/chamados", json=novo)
    assert criado.status_code == 201
    assert client.post("/api/chamados", json=novo).status_code == 409
    id_ = criado.json()["id_chamado"]
    feito = client.patch(f"/api/chamados/{id_}", json={"status": "concluido"}).json()
    assert feito["status"] == "concluido" and feito["concluido_em"]


def test_assistente_responde_com_fonte_ou_recusa():
    placa = client.get("/api/fila").json()["dados"][0]["placa"]
    r = client.post("/api/assistente", json={"pergunta": f"Por que a {placa} esta na frente?"}).json()
    assert not r["recusou"] and r["fontes"]
    assert client.post("/api/assistente", json={"pergunta": "Qual o preco do cafe?"}).json()["recusou"]


def test_export_bloqueia_entrada_invalida():
    assert client.get("/api/export/ocorrencias", params={"data": "../../etc"}).status_code == 422
    assert client.get("/api/export/senhas", params={"data": "2026-11-10"}).status_code == 422


def test_deploy_info_exige_token(monkeypatch):
    assert client.get("/internal/deploy").status_code == 404
    monkeypatch.setenv("LUZVIVA_DEPLOY_TOKEN", "segredo-de-teste")
    monkeypatch.setenv("APP_COMMIT", "abc123")
    assert client.get("/internal/deploy").status_code == 401
    assert client.get("/internal/deploy", headers={"X-Deploy-Token": "errado"}).status_code == 401
    ok = client.get("/internal/deploy", headers={"X-Deploy-Token": "segredo-de-teste"})
    assert ok.json() == {"commit": "abc123"}
    assert "commit" not in client.get("/health").json()
