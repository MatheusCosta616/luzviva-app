"""Gera os dados SIMULADOS do MVP no formato dos contratos do roteiro LuzViva.

Por que simulado: nenhum dado aberto diz quais luminarias estao apagadas, e o
robo, a visao e o pipeline nao fazem parte desta entrega. O script cria
luminarias ficticias nas tres areas-piloto, com placas no formato IPxxxxxxx,
e calcula a prioridade com uma regra explicita. A semente e fixa: rodar de
novo gera exatamente o mesmo resultado.

Uso: python scripts/gerar_dados.py
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(2026)
SAIDA = Path(__file__).resolve().parent.parent / "app" / "data"
GERADO_EM = "2026-11-10T22:00:00"
POR_AREA = 16

AREAS = {
    # area: (lat, lon, subprefeitura, ruas)
    "SE": (-23.5505, -46.6340, "Se",
           ["Rua Direita", "Rua XV de Novembro", "Praca da Se", "Rua Benjamin Constant", "Rua do Carmo"]),
    "PINHEIROS": (-23.5670, -46.6930, "Pinheiros",
                  ["Rua dos Pinheiros", "Rua Teodoro Sampaio", "Rua Cardeal Arcoverde", "Rua Fradique Coutinho", "Rua Joao Moura"]),
    "CAMPO LIMPO": (-23.6490, -46.7590, "Campo Limpo",
                    ["Estrada do Campo Limpo", "Rua Domingos de Godoy", "Av. Carlos Lacerda", "Rua Pedro Gil", "Rua Cesar Dias"]),
}


def situacao_por_lux(lux):
    """Limiares do contrato do robo: abaixo de 1 lux apagada, abaixo de 5 insuficiente."""
    if lux < 1:
        return "apagada"
    if lux < 5:
        return "insuficiente"
    return "ok"


def prioridade(situacao, ocorrencias, confianca):
    """Situacao pesa mais (50/25); cada relato soma 10 (ate 3); confianca da visao soma ate 20."""
    base = {"apagada": 50, "insuficiente": 25, "ok": 0}[situacao]
    relatos = min(ocorrencias, 3) * 10
    visao = round(confianca * 20) if ocorrencias else 0
    return min(base + relatos + visao, 100)


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    luminarias, fila, painel = [], [], []
    placas = set()
    ronda = datetime(2026, 11, 10, 19, 0, 0)

    for area, (lat0, lon0, sub, ruas) in AREAS.items():
        contagem = {"ok": 0, "insuficiente": 0, "apagada": 0}
        for _ in range(POR_AREA):
            placa = f"IP07{random.randint(10000, 99999)}"
            while placa in placas:
                placa = f"IP07{random.randint(10000, 99999)}"
            placas.add(placa)

            sorteio = random.random()
            if sorteio < 0.22:
                lux = round(random.uniform(0.1, 0.9), 1)
            elif sorteio < 0.40:
                lux = round(random.uniform(1.2, 4.8), 1)
            else:
                lux = round(random.uniform(8, 30), 1)
            situacao = situacao_por_lux(lux)
            contagem[situacao] += 1
            ocorrencias = random.choice([0, 0, 1, 2, 3]) if situacao != "ok" else 0
            confianca = round(random.uniform(0.7, 0.97), 2) if ocorrencias else None

            item = {
                "id_luminaria": f"L{len(luminarias) + 1:04d}",
                "placa": placa,
                "endereco": f"{random.choice(ruas)}, {random.randint(10, 1500)}",
                "subprefeitura": sub,
                "area_piloto": area,
                "lat": round(lat0 + random.uniform(-0.006, 0.006), 6),
                "lon": round(lon0 + random.uniform(-0.006, 0.006), 6),
                "situacao": situacao,
                "ultimo_lux": lux,
                "ultima_medicao": (ronda + timedelta(minutes=random.randint(0, 300))).isoformat(),
            }
            luminarias.append(item)
            if situacao != "ok":
                campos = ("placa", "endereco", "subprefeitura", "lat", "lon", "situacao", "ultimo_lux", "ultima_medicao")
                fila.append({
                    **{k: item[k] for k in campos},
                    "ocorrencias_app": ocorrencias,
                    "confianca_visao": confianca,
                    "prioridade": prioridade(situacao, ocorrencias, confianca or 0),
                })

        total = sum(contagem.values())
        painel.append({
            "subprefeitura": sub,
            "area_piloto": area,
            "luminarias_monitoradas": total,
            "apagadas": contagem["apagada"],
            "insuficientes": contagem["insuficiente"],
            "ok": contagem["ok"],
            "pct_com_falha": round(100 * (contagem["apagada"] + contagem["insuficiente"]) / total, 1),
            "horas_luminaria_no_escuro_noite": contagem["apagada"] * 12,
        })

    fila.sort(key=lambda x: -x["prioridade"])
    for nome, view, dados in [
        ("luminarias", "vw_mvp_mapa_luminarias", luminarias),
        ("fila", "vw_mvp_fila_manutencao", fila),
        ("painel", "vw_mvp_painel_subprefeitura", painel),
    ]:
        envelope = {"view": view, "gerado_em": GERADO_EM, "linhas": len(dados), "simulado": True, "dados": dados}
        (SAIDA / f"{nome}.json").write_text(json.dumps(envelope, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(luminarias)} luminarias, {len(fila)} na fila")


if __name__ == "__main__":
    main()
