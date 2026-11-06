"""App PLACEHOLDER para testar a infra. O app real é o do Caíque (luzviva-app).
Contrato mínimo que o DevOps exige dele: GET /health e GET /metrics."""
import os
import time

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

app = FastAPI(title="LuzViva (placeholder)")

REQUESTS = Counter("http_requests_total", "Requisições (tráfego e erros)",
                   ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Latência das requisições",
                    ["method", "path"])

FAULT_ENABLED = os.getenv("ENABLE_FAULT_ENDPOINT", "false").lower() == "true"


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


@app.get("/")
def raiz():
    return {"produto": "LuzViva", "status": "no ar"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/erro")
def erro():
    """Gera 500 de propósito (para disparar o alerta). Só existe com ENABLE_FAULT_ENDPOINT=true."""
    if not FAULT_ENABLED:
        raise HTTPException(status_code=404)
    raise HTTPException(status_code=500, detail="erro simulado")


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
