#!/usr/bin/env python3
"""
Baixa prédios e vias de São Carlos/SP do Overture Maps (GeoParquet no S3)
e grava GeoJSON em data/ para o viewer web consumir.

Fonte: Overture Maps Foundation (dados abertos: OSM + footprints ML da
Microsoft/Google/Esri), licenças ODbL/CDLA — exigem atribuição.

A consulta usa DuckDB com filtro espacial (poda por row group via coluna
`bbox` do GeoParquet), então só os blocos que intersectam São Carlos são
baixados — alguns MB de um dataset planetário de centenas de GB.

Uso:
    pip install -r pipeline/requirements.txt
    python pipeline/fetch_overture.py [--somente predios|vias]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
import xml.etree.ElementTree as ET

import duckdb
import requests
from shapely import set_precision, simplify
from shapely.geometry import mapping
import shapely.wkb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

S3_BASE = "https://overturemaps-us-west-2.s3.amazonaws.com"
RELEASE = "2026-06-17.0"

# Classes de via mantidas (subtype=road) — da mais à menos estrutural.
ROAD_CLASSES = [
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "residential", "living_street", "unclassified", "service",
    "pedestrian", "footway", "cycleway", "track", "steps", "path",
]

# Hidrografia mantida (theme=base/type=water) — exclui piscinas, bicas etc.
WATER_SUBTYPES = ["stream", "river", "canal", "reservoir", "lake", "pond", "water"]

# Pontos de referência: pool de candidatos vindo dessas categorias inteiras…
LANDMARK_CATEGORIES = ["bus_station", "train_station", "airport"]
# …mais qualquer lugar cujo nome case com este regex amplo. A seleção final
# é feita por CURATED_LANDMARKS (uma feição por regra, a de maior confiança).
LANDMARK_NAME_REGEX = (
    r"(?i)UFSCar|Universidade Federal de S|Universidade de S.o Paulo|"
    r"Campus.*USP|USP.*Campus|Instituto Federal|IFSP|"
    r"Santa Casa|Hospital Universit|Hospital Escola|"
    r"Mercado Municipal|Shopping Iguatemi|Passeio S|Catedral|"
    r"Teatro Municipal|Esta..o Cultura|Kart.dromo|SESC"
)

# (regex sobre o nome, rótulo exibido, categoria p/ estilo no viewer)
CURATED_LANDMARKS = [
    (r"(?i)^universidade federal de s.o carlos$", "UFSCar", "universidade"),
    (r"(?i)^universidade de s.o paulo - campus", "USP São Carlos", "universidade"),
    (r"(?i)instituto federal de s.o paulo - c.mpus|ifsp campus s.o carlos",
     "IFSP", "universidade"),
    (r"(?i)^rodovi.ria de s.o carlos", "Rodoviária", "transporte"),
    (r"(?i)^esta..o de s.o carlos$", "Estação Ferroviária", "transporte"),
    (r"(?i)^aeroporto", "Aeroporto", "transporte"),
    (r"(?i)^irmandade da santa casa", "Santa Casa", "saude"),
    (r"(?i)^hospital universit.rio", "Hospital Universitário (UFSCar)", "saude"),
    (r"(?i)^hospital escola", "Hospital Escola Municipal", "saude"),
    (r"(?i)^mercado municipal", "Mercado Municipal", "comercio"),
    (r"(?i)^shopping iguatemi", "Shopping Iguatemi", "comercio"),
    (r"(?i)^passeio s.o carlos$", "Passeio São Carlos", "comercio"),
    (r"(?i)^catedral", "Catedral", "cultura"),
    (r"(?i)^teatro municipal", "Teatro Municipal", "cultura"),
    (r"(?i)^sesc s.o carlos$", "SESC", "cultura"),
    (r"(?i)^esta..o cultura$", "Estação Cultura", "cultura"),
    (r"(?i)^parque do kart.dromo$", "Parque do Kartódromo", "parque"),
]


def load_config() -> dict:
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def list_parquet_urls(prefix: str) -> list[str]:
    """Lista os arquivos .parquet de um prefixo do bucket público do Overture."""
    keys: list[str] = []
    token = None
    while True:
        params = {"list-type": "2", "prefix": prefix}
        if token:
            params["continuation-token"] = token
        resp = requests.get(f"{S3_BASE}/", params=params, timeout=60)
        resp.raise_for_status()
        ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
        root = ET.fromstring(resp.text)
        for c in root.findall("s3:Contents", ns):
            key = c.find("s3:Key", ns).text
            if key.endswith(".parquet"):
                keys.append(key)
        nxt = root.find("s3:NextContinuationToken", ns)
        if nxt is None:
            break
        token = nxt.text
    return [f"{S3_BASE}/{k}" for k in keys]


def duckdb_connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    # A extensão httpfs vem do pacote pip duckdb-extension-httpfs
    # (o repositório padrão de extensões pode estar bloqueado em sandboxes).
    candidates = glob.glob(
        os.path.join(
            os.path.dirname(duckdb.__file__), "..",
            "duckdb_extension_httpfs", "extensions", "*", "httpfs.duckdb_extension",
        )
    )
    if candidates:
        con.execute(f"LOAD '{os.path.abspath(candidates[0])}';")
    else:  # fallback: repositório oficial de extensões
        con.execute("INSTALL httpfs; LOAD httpfs;")
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        con.execute(f"SET http_proxy='{proxy}';")
    con.execute("SET http_keep_alive=true;")
    return con


def bbox_where(cfg: dict) -> str:
    b = cfg["bbox"]
    return (
        f"bbox.xmin <= {b['max_lon']} AND bbox.xmax >= {b['min_lon']} "
        f"AND bbox.ymin <= {b['max_lat']} AND bbox.ymax >= {b['min_lat']}"
    )


def to_feature(wkb: bytes, props: dict, tol_deg: float) -> dict | None:
    """WKB → Feature GeoJSON, com simplificação leve e precisão de ~0,1 m."""
    geom = shapely.wkb.loads(wkb)
    if tol_deg:
        geom = simplify(geom, tol_deg, preserve_topology=True)
    geom = set_precision(geom, 1e-6)  # ~0,11 m — arredonda coords no JSON
    if geom.is_empty:
        return None
    return {"type": "Feature", "properties": props, "geometry": mapping(geom)}


def write_geojson(name: str, features: list[dict]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, name)
    fc = {"type": "FeatureCollection", "features": features}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  ✓ {name}: {len(features)} feições ({os.path.getsize(path)/1e6:.1f} MB)")


def fetch_buildings(con: duckdb.DuckDBPyConnection, cfg: dict) -> None:
    print("\n[prédios] listando arquivos do Overture…")
    urls = list_parquet_urls(f"release/{RELEASE}/theme=buildings/type=building/")
    print(f"  {len(urls)} arquivos; consultando bbox (pode levar alguns minutos)…")
    t0 = time.time()
    p = cfg["predios"]
    rows = con.execute(
        f"""
        SELECT geometry AS g, height, num_floors
        FROM read_parquet($urls, hive_partitioning=0)
        WHERE {bbox_where(cfg)}
        """,
        {"urls": urls},
    ).fetchall()
    print(f"  {len(rows)} prédios baixados em {time.time()-t0:.0f}s; convertendo…")

    hmax = p["altura_maxima_plausivel_m"]
    features = []
    for g, height, floors in rows:
        h = height
        if h is None and floors:
            h = floors * p["metros_por_pavimento"]
        if h is None:
            h = p["altura_padrao_m"]
        h = max(2.0, min(float(h), hmax))
        # tolerância ~0,3 m em graus: reduz vértices dos footprints ML
        feat = to_feature(bytes(g), {"h": round(h, 1)}, tol_deg=3e-6)
        if feat:
            features.append(feat)
    write_geojson("buildings.geojson", features)


def fetch_roads(con: duckdb.DuckDBPyConnection, cfg: dict) -> None:
    print("\n[vias] listando arquivos do Overture…")
    urls = list_parquet_urls(f"release/{RELEASE}/theme=transportation/type=segment/")
    print(f"  {len(urls)} arquivos; consultando bbox…")
    t0 = time.time()
    classes = ",".join(f"'{c}'" for c in ROAD_CLASSES)
    rows = con.execute(
        f"""
        SELECT geometry AS g, class, names.primary AS name, subtype
        FROM read_parquet($urls, hive_partitioning=0)
        WHERE {bbox_where(cfg)}
          AND (subtype = 'rail' OR (subtype = 'road' AND class IN ({classes})))
        """,
        {"urls": urls},
    ).fetchall()
    print(f"  {len(rows)} segmentos baixados em {time.time()-t0:.0f}s; convertendo…")

    features = []
    for g, cls, name, subtype in rows:
        props = {"class": "rail" if subtype == "rail" else cls}
        if name:
            props["name"] = name
        feat = to_feature(bytes(g), props, tol_deg=0)
        if feat:
            features.append(feat)
    write_geojson("roads.geojson", features)


def fetch_water(con: duckdb.DuckDBPyConnection, cfg: dict) -> None:
    print("\n[água] listando arquivos do Overture…")
    urls = list_parquet_urls(f"release/{RELEASE}/theme=base/type=water/")
    print(f"  {len(urls)} arquivos; consultando bbox…")
    t0 = time.time()
    subtypes = ",".join(f"'{s}'" for s in WATER_SUBTYPES)
    rows = con.execute(
        f"""
        SELECT geometry AS g, subtype, names.primary AS name
        FROM read_parquet($urls, hive_partitioning=0)
        WHERE {bbox_where(cfg)} AND subtype IN ({subtypes})
        """,
        {"urls": urls},
    ).fetchall()
    print(f"  {len(rows)} feições de água em {time.time()-t0:.0f}s; convertendo…")

    features = []
    for g, subtype, name in rows:
        props = {"class": subtype}
        if name:
            props["name"] = name
        feat = to_feature(bytes(g), props, tol_deg=0)
        if feat:
            features.append(feat)
    write_geojson("water.geojson", features)


def fetch_landmarks(con: duckdb.DuckDBPyConnection, cfg: dict) -> None:
    """Pontos de referência: POIs curados + polígonos de campus universitário."""
    print("\n[referências] POIs (places)…")
    urls = list_parquet_urls(f"release/{RELEASE}/theme=places/type=place/")
    cats = ",".join(f"'{c}'" for c in LANDMARK_CATEGORIES)
    rows = con.execute(
        f"""
        SELECT geometry AS g, names.primary AS name,
               categories.primary AS cat, confidence
        FROM read_parquet($urls, hive_partitioning=0)
        WHERE {bbox_where(cfg)} AND names.primary IS NOT NULL
          AND (categories.primary IN ({cats})
               OR regexp_matches(names.primary, '{LANDMARK_NAME_REGEX}'))
        ORDER BY confidence DESC
        """,
        {"urls": urls},
    ).fetchall()

    # uma feição por regra curada: candidatos vêm ordenados por confiança,
    # desempate pelo nome mais curto (evita "Farmácia X | Shopping Y")
    import re
    features = []
    for regex, rotulo, cat in CURATED_LANDMARKS:
        candidatos = [(g, name) for g, name, _, _ in rows if re.search(regex, name)]
        if not candidatos:
            print(f"  ⚠ sem candidato para: {rotulo}")
            continue
        g, _ = min(candidatos, key=lambda c: len(c[1]))
        feat = to_feature(bytes(g), {"name": rotulo, "cat": cat}, tol_deg=0)
        if feat:
            features.append(feat)
    print(f"  {len(features)} referências curadas (de {len(rows)} candidatos)")

    print("[referências] campi (land_use educação)…")
    urls = list_parquet_urls(f"release/{RELEASE}/theme=base/type=land_use/")
    rows = con.execute(
        f"""
        SELECT geometry AS g, names.primary AS name, class
        FROM read_parquet($urls, hive_partitioning=0)
        WHERE {bbox_where(cfg)} AND subtype = 'education'
          AND class IN ('university', 'college')
        """,
        {"urls": urls},
    ).fetchall()
    campi = []
    for g, name, cls in rows:
        props = {"class": cls}
        if name:
            props["name"] = name
        feat = to_feature(bytes(g), props, tol_deg=0)
        if feat:
            campi.append(feat)
    print(f"  {len(campi)} polígonos de campus")
    write_geojson("landmarks.geojson", features)
    write_geojson("campuses.geojson", campi)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--somente",
        choices=["predios", "vias", "agua", "referencias"],
        default=None,
    )
    args = ap.parse_args()

    cfg = load_config()
    b = cfg["bbox"]
    print(f"Área: {cfg['cidade']}  bbox(W,S,E,N)="
          f"{b['min_lon']},{b['min_lat']},{b['max_lon']},{b['max_lat']}")
    print(f"Overture release: {RELEASE}")

    con = duckdb_connect()
    if args.somente in (None, "predios"):
        fetch_buildings(con, cfg)
    if args.somente in (None, "vias"):
        fetch_roads(con, cfg)
    if args.somente in (None, "agua"):
        fetch_water(con, cfg)
    if args.somente in (None, "referencias"):
        fetch_landmarks(con, cfg)
    print("\nConcluído. Sirva o viewer: python -m http.server 8000  (na raiz do repo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
