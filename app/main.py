"""LuzViva MVP: site e API com dados simulados no formato dos contratos do grupo.

Rotas seguem a secao "API do app" do roteiro. Leitura (mapa, fila, painel) vem dos
JSON gerados por scripts/gerar_dados.py. Escrita (medicoes, ocorrencias, chamados)
grava arquivos diarios em LUZVIVA_DATA_DIR, que fica fora do container.
"""
import hmac
import json
import os
import threading
import time
from datetime import date, datetime
from pathlib import Path
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent
DADOS_FIXOS = BASE / "data"
DATA_DIR = Path(os.getenv("LUZVIVA_DATA_DIR", "/tmp/luzviva-data"))
FAULT_ENABLED = os.getenv("ENABLE_FAULT_ENDPOINT", "false").lower() == "true"
TZ = ZoneInfo("America/Sao_Paulo")
LOCK = threading.Lock()
AREAS = Literal["SE", "PINHEIROS", "CAMPO LIMPO"]

app = FastAPI(title="LuzViva", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

REQUESTS = Counter("http_requests_total", "Requisicoes (trafego e erros)", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Latencia das requisicoes", ["method", "path"])
NEGOCIO = Counter("luzviva_eventos_total", "Eventos de negocio recebidos", ["tipo"])


@app.middleware("http")
async def medir(request: Request, call_next):
    inicio = time.perf_counter()
    status = 500
    try:
        resposta = await call_next(request)
        status = resposta.status_code
        return resposta
    finally:
        rota = request.scope.get("route")
        caminho = rota.path if rota else "nao_mapeado"  # evita cardinalidade alta
        LATENCY.labels(request.method, caminho).observe(time.perf_counter() - inicio)
        REQUESTS.labels(request.method, caminho, str(status)).inc()


# ---------- utilidades ----------
def agora() -> str:
    return datetime.now(TZ).replace(tzinfo=None, microsecond=0).isoformat()


def ler_fixo(nome: str) -> dict:
    return json.loads((DADOS_FIXOS / f"{nome}.json").read_text(encoding="utf-8"))


def gravar_evento(fonte: str, registro: dict) -> None:
    """Um arquivo JSONL por fonte e por dia: e o que o pipeline baixa em /api/export."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    arquivo = DATA_DIR / f"{fonte}_{date.today().isoformat()}.jsonl"
    with LOCK, arquivo.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    NEGOCIO.labels(fonte).inc()


def chamados_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "chamados.json"


def ler_chamados() -> list:
    p = chamados_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def salvar_chamados(chamados: list) -> None:
    chamados_path().write_text(json.dumps(chamados, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- contratos (secao 5 do roteiro) ----------
class Medicao(BaseModel):
    id_medicao: str = Field(max_length=40)
    robo_id: str = Field(max_length=20)
    data_hora: datetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    lux: float = Field(ge=0)
    situacao_robo: Literal["apagada", "insuficiente", "ok"]
    sensor: str = Field(max_length=40)
    bateria_pct: int = Field(ge=0, le=100)
    area_piloto: AREAS
    placa: Optional[str] = Field(default=None, pattern=r"^IP\d{7}$")


class Ocorrencia(BaseModel):
    id_ocorrencia: Optional[str] = Field(default=None, max_length=40)
    data_hora: Optional[datetime] = None
    categoria: Literal["luminaria_apagada", "luminaria_acesa", "luminaria_acesa_de_dia",
                       "luminaria_piscando", "poste_danificado"]
    origem: str = Field(default="app_foto_cidadao", max_length=40)
    confianca_visao: Optional[float] = Field(default=None, ge=0, le=1)
    modelo_visao: Optional[str] = Field(default=None, max_length=60)
    foto_id: Optional[str] = Field(default=None, max_length=64)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)
    area_piloto: AREAS
    placa: str = Field(pattern=r"^IP\d{7}$")


class NovoChamado(BaseModel):
    placa: str = Field(pattern=r"^IP\d{7}$")
    area_piloto: AREAS
    prioridade: int = Field(ge=0, le=100)
    situacao_detectada: str = Field(max_length=20)
    equipe: str = Field(default="EQUIPE-CENTRO", max_length=30)
    origem: str = Field(default="rpa", max_length=20)


class AtualizaChamado(BaseModel):
    status: Literal["aberto", "em_atendimento", "concluido", "cancelado"]
    equipe: Optional[str] = Field(default=None, max_length=30)


class Pergunta(BaseModel):
    pergunta: str = Field(min_length=3, max_length=500)
    placa: Optional[str] = Field(default=None, pattern=r"^IP\d{7}$")


# ---------- site e operacao ----------
@app.get("/", include_in_schema=False)
def site():
    return FileResponse(BASE / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "versao": app.version}


@app.get("/internal/deploy", include_in_schema=False)
def deploy_info(x_deploy_token: Optional[str] = Header(default=None)):
    """Commit em execucao, so para o pipeline (token vindo do GitHub Secrets / SSM).
    Sem token configurado no servidor, a rota nao existe."""
    esperado = os.getenv("LUZVIVA_DEPLOY_TOKEN", "")
    if not esperado:
        raise HTTPException(status_code=404)
    if not x_deploy_token or not hmac.compare_digest(x_deploy_token, esperado):
        raise HTTPException(status_code=401, detail="token invalido")
    return {"commit": os.getenv("APP_COMMIT", "local")}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/erro", include_in_schema=False)
def erro():
    """Gera 500 de proposito para disparar o alerta. So existe com ENABLE_FAULT_ENDPOINT=true."""
    if not FAULT_ENABLED:
        raise HTTPException(status_code=404)
    raise HTTPException(status_code=500, detail="erro simulado")


# ---------- leitura (saidas do pipeline) ----------
@app.get("/api/luminarias")
def luminarias():
    return ler_fixo("luminarias")


@app.get("/api/fila")
def fila():
    return ler_fixo("fila")


@app.get("/api/painel")
def painel():
    return ler_fixo("painel")


# ---------- escrita (robo, visao, site, RPA) ----------
@app.post("/api/medicoes", status_code=201)
def nova_medicao(m: Medicao):
    gravar_evento("medicoes", m.model_dump(mode="json"))
    return {"ok": True, "id_medicao": m.id_medicao}


@app.post("/api/ocorrencias", status_code=201)
def nova_ocorrencia(o: Ocorrencia):
    registro = o.model_dump(mode="json")
    registro["data_hora"] = registro["data_hora"] or agora()
    registro["id_ocorrencia"] = registro["id_ocorrencia"] or f"O{datetime.now(TZ):%Y%m%d-%H%M%S}"
    gravar_evento("ocorrencias", registro)
    return {"ok": True, "id_ocorrencia": registro["id_ocorrencia"]}


@app.get("/api/chamados")
def listar_chamados(status: Optional[str] = None):
    chamados = ler_chamados()
    if status:
        chamados = [c for c in chamados if c["status"] == status]
    return {"linhas": len(chamados), "dados": chamados}


@app.post("/api/chamados", status_code=201)
def abrir_chamado(c: NovoChamado):
    with LOCK:
        chamados = ler_chamados()
        if any(x["placa"] == c.placa and x["status"] in ("aberto", "em_atendimento") for x in chamados):
            raise HTTPException(status_code=409, detail="Ja existe chamado aberto para esta placa")
        ts = agora()
        novo = {
            "id_chamado": f"CH-{datetime.now(TZ):%Y%m%d}-{c.placa}",
            **c.model_dump(),
            "status": "aberto",
            "aberto_em": ts,
            "atualizado_em": ts,
            "concluido_em": None,
        }
        chamados.append(novo)
        salvar_chamados(chamados)
    gravar_evento("chamados", novo)
    return novo


@app.patch("/api/chamados/{id_chamado}")
def atualizar_chamado(id_chamado: str, a: AtualizaChamado):
    with LOCK:
        chamados = ler_chamados()
        alvo = next((x for x in chamados if x["id_chamado"] == id_chamado), None)
        if not alvo:
            raise HTTPException(status_code=404, detail="Chamado nao encontrado")
        alvo["status"] = a.status
        if a.equipe:
            alvo["equipe"] = a.equipe
        alvo["atualizado_em"] = agora()
        alvo["concluido_em"] = alvo["atualizado_em"] if a.status == "concluido" else None
        salvar_chamados(chamados)
    gravar_evento("chamados", alvo)
    return alvo


# ---------- assistente (modo simulado) ----------
@app.post("/api/assistente")
def assistente(p: Pergunta):
    """Responde a partir da fila, com fonte; sem dado na base, recusa ("nao consta").
    No produto final esta rota repassa para o servico GenAI (POST /perguntar)."""
    texto = p.pergunta.upper()
    itens = ler_fixo("fila")["dados"]
    alvo = next((i for i in itens if i["placa"] == p.placa or i["placa"] in texto), None)
    if not alvo:
        return {"resposta": "Nao consta na base do LuzViva.", "fontes": [], "recusou": True,
                "confianca": 0.0, "modo": "simulado"}
    posicao = itens.index(alvo) + 1
    resposta = (f"A {alvo['placa']} ({alvo['endereco']}) esta em {posicao}o na fila: situacao "
                f"{alvo['situacao']} com {alvo['ultimo_lux']} lux na ultima ronda e "
                f"{alvo['ocorrencias_app']} relato(s) de cidadaos. Prioridade {alvo['prioridade']}.")
    return {"resposta": resposta,
            "fontes": [{"titulo": "Fila de manutencao LuzViva", "trecho": f"prioridade {alvo['prioridade']}"}],
            "recusou": False, "confianca": 0.9, "modo": "simulado"}


# ---------- exportacao para o pipeline ----------
@app.get("/api/export/{fonte}")
def exportar(fonte: Literal["medicoes", "ocorrencias", "chamados"],
             data: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$")):
    dia = date.fromisoformat(data)  # valida e normaliza: impede path traversal
    arquivo = DATA_DIR / f"{fonte}_{dia.isoformat()}.jsonl"
    if not arquivo.exists():
        return {"fonte": fonte, "data": dia.isoformat(), "linhas": 0, "dados": []}
    linhas = [json.loads(x) for x in arquivo.read_text(encoding="utf-8").splitlines() if x.strip()]
    return {"fonte": fonte, "data": dia.isoformat(), "linhas": len(linhas), "dados": linhas}
