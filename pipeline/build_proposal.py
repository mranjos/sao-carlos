#!/usr/bin/env python3
"""
Gera as camadas de PROJETO da maquete a partir do traçado real do Córrego do
Gregório (data/water.geojson):

  data/interventions.geojson      — intervenções propostas (passo 2 do plano),
                                    com horizonte curto/médio/longo e descrição
  data/proposal-riverwalk.geojson — cenário "River Walk do Gregório" (passo 4):
                                    canal aberto, calçadões, arborização,
                                    passarelas e parque alagável

As propostas seguem docs/alagamentos-casos-e-solucoes.md. Geometrias são
esquemáticas (nível estudo preliminar), desenhadas por offset/buffer sobre o
eixo real do canal.

Uso: python pipeline/build_proposal.py
"""

from __future__ import annotations

import json
import math
import os

from shapely.geometry import LineString, Point, mapping, shape
from shapely.ops import linemerge, unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# ~1 grau ≈ 111 km; fator de metros→graus na latitude de São Carlos
M = 1 / 111_000.0
COS_LAT = math.cos(math.radians(22.02))

# Marcos (dos dados já curados em data/landmarks.geojson)
MERCADO = (-47.8911, -22.0200)
CATEDRAL = (-47.8908, -22.0184)
TEATRO = (-47.8936, -22.0159)
SESC = (-47.9060, -22.0169)
ESTACAO_CULTURA = (-47.8949, -22.0223)
ROTATORIA_CRISTO = (-47.8902, -22.0321)
BICAO = (-47.9072, -22.0311)

# Trechos do Gregório (limites em longitude, oeste→leste)
LON_CONFLUENCIA = -47.9128   # encontro com o Monjolinho
LON_BOULEVARD_W = -47.8970   # início do boulevard (jusante do Mercado)
LON_MERCADO_W = -47.8925     # limite oeste da faixa alagável (engloba o Mercadão)
LON_CHAMINE_W = -47.8865     # Rua São Paulo — início do Parque da Chaminé
LON_CHAMINE_E = -47.8740     # limite leste do parque alagável

# Classes viárias que recebem ponte veicular sobre o canal aberto
CLASSES_PONTE = {"trunk", "primary", "secondary", "tertiary", "residential",
                 "unclassified"}
# Par de binário: vias paralelas existentes que absorvem o tráfego de
# passagem das marginais (uma por sentido) — ver docs do projeto
BINARIO = ["rua jesuíno de arruda", "rua general osório"]


def gregorio_line() -> LineString:
    """Une os segmentos nomeados do Gregório num eixo contínuo."""
    fc = json.load(open(os.path.join(DATA, "water.geojson"), encoding="utf-8"))
    partes = []
    for f in fc["features"]:
        if "gregório" in (f["properties"].get("name") or "").lower():
            g = f["geometry"]
            if g["type"] == "LineString":
                partes.append(LineString(g["coordinates"]))
    linha = linemerge(unary_union(partes))
    if linha.geom_type == "MultiLineString":
        linha = max(linha.geoms, key=lambda l: l.length)
    return linha


def recorte(linha: LineString, lon_min: float, lon_max: float) -> LineString:
    pts = [c for c in linha.coords if lon_min <= c[0] <= lon_max]
    return LineString(pts) if len(pts) >= 2 else None


def feat(geom, **props):
    return {"type": "Feature", "properties": props, "geometry": mapping(geom)}


def write(nome, features):
    path = os.path.join(DATA, nome)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f,
                  ensure_ascii=False, separators=(",", ":"))
    print(f"✓ {nome}: {len(features)} feições ({os.path.getsize(path)/1e3:.0f} kB)")


# ---------------------------------------------------------------------------
# Passo 2 — intervenções propostas (visão geral)
# ---------------------------------------------------------------------------

def build_interventions(greg: LineString) -> None:
    fs = []

    parque = recorte(greg, LON_CHAMINE_W, LON_CHAMINE_E).buffer(90 * M)
    fs.append(feat(
        parque,
        name="Parque Alagável da Chaminé",
        tipo="parque-alagavel", horizonte="curto",
        desc="Reservatório de detenção de ~240.000 m³ já projetado pelo SAAE, "
             "redesenhado como parque alagável (precedentes: Curitiba, "
             "Enghaveparken/Copenhague): lago permanente, várzea gramada que "
             "recebe as cheias, chaminé histórica como marco e memorial das "
             "enchentes."))

    fs.append(feat(
        Point(-47.8922, -22.0206).buffer(45 * M),
        name="Praça d'água do Mercado",
        tipo="praca-dagua", horizonte="curto",
        desc="Praça/estacionamento rebaixado como bacia multiuso "
             "(precedente: Benthemplein/Roterdã) — quadras e arquibancadas "
             "que retêm água nas chuvas fortes."))
    fs.append(feat(
        Point(ROTATORIA_CRISTO[0] - 0.0012, ROTATORIA_CRISTO[1] + 0.0010).buffer(45 * M),
        name="Praça d'água da Vila Prado",
        tipo="praca-dagua", horizonte="curto",
        desc="Segunda bacia multiuso piloto junto à Rotatória do Cristo, "
             "aliviando o Simeão."))

    boulevard = recorte(greg, LON_BOULEVARD_W, LON_CHAMINE_W)
    fs.append(feat(
        boulevard,
        name="Boulevard do Gregório",
        tipo="boulevard", horizonte="medio",
        desc="Requalificação das marginais do canal no trecho central: "
             "calçadas largas, sombra, iluminação cênica e fachadas ativas "
             "voltadas para a água (precedentes: Madrid Río, San Antonio)."))

    fs.append(feat(
        Point(*MERCADO).buffer(35 * M),
        name="Mercadão gastronômico",
        tipo="ancora", horizonte="medio",
        desc="Requalificação do Mercado Municipal como âncora gastronômica do "
             "circuito — todo case turístico de água tem âncora de comida."))

    circuito = LineString([
        SESC, TEATRO, CATEDRAL, MERCADO, ESTACAO_CULTURA, MERCADO,
        (LON_CHAMINE_W, -22.0209), (-47.880, -22.0218),
    ])
    fs.append(feat(
        circuito,
        name="Circuito das Águas do Centro",
        tipo="circuito", horizonte="medio",
        desc="Roteiro turístico a pé conectando SESC → Teatro → Catedral → "
             "Mercadão → Estação Cultura → Parque da Chaminé, todo na "
             "baixada. Sinalização e identidade visual únicas."))

    fs.append(feat(
        Point(*BICAO).buffer(55 * M),
        name="Reservatório do Simeão ampliado",
        tipo="reservatorio", horizonte="curto", aproximado=True,
        desc="Ampliação do reservatório existente na Vila Prado (projeto "
             "SAAE, ~R$ 140 mi) com novas galerias sob a Av. Getúlio Vargas. "
             "Posição aproximada — região do Parque do Bicão."))

    linear = recorte(greg, LON_CONFLUENCIA, LON_BOULEVARD_W)
    fs.append(feat(
        linear,
        name="Parque Linear do Gregório (fase 2)",
        tipo="parque-linear", horizonte="longo",
        desc="Extensão do tratamento até a confluência com o Monjolinho: "
             "renaturalização onde houver margem (precedente: Bishan/"
             "Singapura) e laboratório vivo de drenagem urbana com "
             "sinalização científica (USP/UFSCar)."))

    # binário de tráfego: paralelas existentes viram par de mão única,
    # absorvendo o fluxo de passagem das marginais requalificadas
    ruas = json.load(open(os.path.join(DATA, "roads.geojson"), encoding="utf-8"))
    for alvo in BINARIO:
        partes = []
        for f in ruas["features"]:
            if (f["properties"].get("name") or "").lower() == alvo \
               and f["geometry"]["type"] == "LineString":
                partes.append(LineString(f["geometry"]["coordinates"]))
        if not partes:
            print(f"  ⚠ binário: rua não encontrada: {alvo}")
            continue
        linha = linemerge(unary_union(partes))
        if linha.geom_type == "MultiLineString":
            linha = max(linha.geoms, key=lambda l: l.length)
        fs.append(feat(
            linha,
            name=f"Binário do Gregório — {alvo.title()}",
            tipo="binario", horizonte="medio",
            desc="Par de mão única em vias paralelas existentes que absorve o "
                 "tráfego de passagem das marginais do canal, requalificadas "
                 "como boulevard. Solução consolidada de engenharia de "
                 "tráfego, sem desapropriação. As travessias norte–sul são "
                 "mantidas por pontes sobre o canal."))

    write("interventions.geojson", fs)


# ---------------------------------------------------------------------------
# Passo 4 — cenário "River Walk do Gregório" (detalhe)
# ---------------------------------------------------------------------------

def offset_line(linha: LineString, dist_m: float) -> LineString | None:
    try:
        off = linha.parallel_offset(abs(dist_m) * M, "left" if dist_m > 0 else "right",
                                    join_style=2)
        if off.geom_type == "MultiLineString":
            off = max(off.geoms, key=lambda l: l.length)
        return off if off.geom_type == "LineString" and len(off.coords) >= 2 else None
    except Exception:
        return None


def pontos_ao_longo(linha: LineString, passo_m: float, offset_m: float):
    """Pontos espaçados ao longo da linha, deslocados perpendicularmente."""
    total = linha.length
    passo = passo_m * M
    out = []
    d = passo / 2
    while d < total:
        p = linha.interpolate(d)
        # direção local para o offset perpendicular
        p2 = linha.interpolate(min(d + 5 * M, total))
        dx, dy = p2.x - p.x, p2.y - p.y
        n = math.hypot(dx, dy) or 1e-12
        out.append(Point(p.x - dy / n * offset_m * M, p.y + dx / n * offset_m * M))
        d += passo
    return out


def build_riverwalk(greg: LineString) -> None:
    fs = []
    trecho = recorte(greg, LON_BOULEVARD_W, LON_CHAMINE_E)

    # canal aberto (lâmina d'água)
    fs.append(feat(trecho.buffer(8 * M), tipo="canal",
                   name="Canal do Gregório aberto"))

    # calçadões fluviais nos dois níveis/margens
    for lado in (+16, -16):
        cal = offset_line(trecho, lado)
        if cal:
            fs.append(feat(cal, tipo="calcadao", name="Calçadão fluvial"))

    # arborização das margens (fileiras alternadas)
    for lado in (+24, -24):
        for p in pontos_ao_longo(trecho, 40, lado):
            fs.append(feat(p, tipo="arvore"))

    # passarelas de travessia a cada ~200 m
    total = trecho.length
    d = 100 * M
    while d < total:
        p = trecho.interpolate(d)
        p2 = trecho.interpolate(min(d + 5 * M, total))
        dx, dy = p2.x - p.x, p2.y - p.y
        n = math.hypot(dx, dy) or 1e-12
        ux, uy = -dy / n, dx / n
        fs.append(feat(LineString([(p.x + ux * 20 * M, p.y + uy * 20 * M),
                                   (p.x - ux * 20 * M, p.y - uy * 20 * M)]),
                       tipo="passarela", name="Passarela"))
        d += 200 * M

    # parque alagável da Chaminé: várzea + lago permanente
    trecho_parque = recorte(greg, LON_CHAMINE_W, LON_CHAMINE_E)
    fs.append(feat(trecho_parque.buffer(90 * M), tipo="varzea",
                   name="Parque Alagável da Chaminé — várzea"))
    fs.append(feat(trecho_parque.buffer(32 * M), tipo="lago",
                   name="Lago permanente"))

    # faixa alagável linear estendendo o parque até o Mercadão
    # (mais estreita, respeitando o casario do centro)
    trecho_mercado = recorte(greg, LON_MERCADO_W, LON_CHAMINE_W)
    fs.append(feat(trecho_mercado.buffer(38 * M), tipo="varzea",
                   name="Faixa alagável do centro (até o Mercadão)"))

    # pontes: mantêm as travessias veiculares existentes sobre o canal
    ruas = json.load(open(os.path.join(DATA, "roads.geojson"), encoding="utf-8"))
    canal_zona = trecho.buffer(20 * M)
    n_pontes = 0
    for f in ruas["features"]:
        p = f["properties"]
        if p.get("class") not in CLASSES_PONTE:
            continue
        if f["geometry"]["type"] != "LineString":
            continue
        g = shape(f["geometry"])
        if not g.intersects(trecho):
            continue
        ponte = g.intersection(canal_zona)
        if ponte.geom_type == "MultiLineString":
            ponte = max(ponte.geoms, key=lambda l: l.length)
        if ponte.geom_type != "LineString" or ponte.is_empty:
            continue
        fs.append(feat(ponte, tipo="ponte",
                       name=f"Ponte — {p.get('name') or 'via local'}"))
        n_pontes += 1
    print(f"  {n_pontes} pontes geradas sobre o canal")

    write("proposal-riverwalk.geojson", fs)


if __name__ == "__main__":
    greg = gregorio_line()
    print(f"Eixo do Gregório: {len(greg.coords)} vértices, "
          f"{greg.length / M / 1000:.1f} km")
    build_interventions(greg)
    build_riverwalk(greg)
