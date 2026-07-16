#!/usr/bin/env python3
"""
Baixa prédios e ruas de São Carlos/SP do OpenStreetMap (via Overpass API)
e grava GeoJSON em data/ para o viewer web consumir.

Dados © colaboradores do OpenStreetMap, licença ODbL (exige atribuição).

Uso:
    pip install -r pipeline/requirements.txt
    python pipeline/fetch_osm.py
"""

from __future__ import annotations

import json
import os
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

# Mirrors do Overpass — tenta em ordem se um estiver sobrecarregado.
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def load_config() -> dict:
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def overpass_bbox(bbox: dict) -> str:
    """Overpass usa a ordem: sul,oeste,norte,leste (lat/lon)."""
    return f"{bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']}"


def run_overpass(query: str, timeout: int, primary_url: str) -> dict:
    """Executa a query no Overpass com retry e mirrors de fallback."""
    urls = [primary_url] + [u for u in OVERPASS_MIRRORS if u != primary_url]
    last_err: Exception | None = None
    for url in urls:
        for attempt in range(3):
            try:
                print(f"  → Overpass: {url} (tentativa {attempt + 1})")
                resp = requests.post(
                    url,
                    data={"data": query},
                    timeout=timeout + 30,
                    headers={"User-Agent": "sao-carlos-3d/1.0 (OSM data fetch)"},
                )
                if resp.status_code == 200:
                    return resp.json()
                # 429/504: servidor ocupado — espera e tenta de novo.
                print(f"    status {resp.status_code}, aguardando…")
                last_err = RuntimeError(f"HTTP {resp.status_code}")
                time.sleep(5 * (attempt + 1))
            except requests.RequestException as exc:
                last_err = exc
                print(f"    erro: {exc}")
                time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Overpass falhou em todos os mirrors: {last_err}")


def parse_meters(value: str | None) -> float | None:
    """Interpreta tags como '12', '12 m', '12,5' → metros (float) ou None."""
    if not value:
        return None
    v = value.strip().lower().replace(",", ".").replace("m", "").strip()
    try:
        return float(v.split()[0]) if v else None
    except (ValueError, IndexError):
        return None


def building_height(tags: dict, cfg: dict) -> tuple[float, float]:
    """Retorna (render_height, base_height) em metros para um prédio."""
    p = cfg["predios"]
    mpp = p["metros_por_pavimento"]
    hmax = p["altura_maxima_plausivel_m"]

    h = parse_meters(tags.get("height"))
    if h is None:
        levels = parse_meters(tags.get("building:levels"))
        h = levels * mpp if levels is not None else p["altura_padrao_m"]
    h = max(2.0, min(h, hmax))

    base = parse_meters(tags.get("min_height"))
    if base is None:
        min_level = parse_meters(tags.get("building:min_level"))
        base = min_level * mpp if min_level is not None else 0.0
    base = max(0.0, min(base, h - 1.0))
    return round(h, 2), round(base, 2)


def ring_from_geometry(geometry: list[dict]) -> list[list[float]]:
    """Converte a lista de pontos do Overpass (lat/lon) em anel GeoJSON [lon,lat] fechado."""
    coords = [[pt["lon"], pt["lat"]] for pt in geometry if "lon" in pt and "lat" in pt]
    if len(coords) < 3:
        return []
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords


def buildings_to_geojson(elements: list[dict], cfg: dict) -> dict:
    features = []
    for el in elements:
        tags = el.get("tags", {}) or {}
        if "building" not in tags:
            continue
        height, base = building_height(tags, cfg)
        # mesmo esquema do fetch_overture.py: viewer lê a propriedade "h"
        props = {"h": height}
        if base:
            props["base"] = base
        if tags.get("name"):
            props["name"] = tags["name"]

        if el["type"] == "way":
            ring = ring_from_geometry(el.get("geometry", []))
            if not ring:
                continue
            geom = {"type": "Polygon", "coordinates": [ring]}
        elif el["type"] == "relation":
            # Multipolígono: usa os anéis 'outer' como polígonos separados
            # (ignora furos internos — simplificação aceitável p/ visualização).
            polys = []
            for member in el.get("members", []):
                if member.get("role") == "outer" and member.get("geometry"):
                    ring = ring_from_geometry(member["geometry"])
                    if ring:
                        polys.append([ring])
            if not polys:
                continue
            geom = {"type": "MultiPolygon", "coordinates": polys}
        else:
            continue

        features.append({"type": "Feature", "properties": props, "geometry": geom})
    return {"type": "FeatureCollection", "features": features}


def roads_to_geojson(elements: list[dict]) -> dict:
    features = []
    for el in elements:
        if el.get("type") != "way":
            continue
        tags = el.get("tags", {}) or {}
        highway = tags.get("highway")
        if not highway:
            continue
        coords = [[pt["lon"], pt["lat"]] for pt in el.get("geometry", []) if "lon" in pt]
        if len(coords) < 2:
            continue
        # mesmo esquema do fetch_overture.py: viewer estiliza pela prop. "class"
        props = {"class": highway}
        if tags.get("name"):
            props["name"] = tags["name"]
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": {"type": "LineString", "coordinates": coords},
        })
    return {"type": "FeatureCollection", "features": features}


def write_geojson(name: str, fc: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)
    size_kb = os.path.getsize(path) / 1024
    print(f"  ✓ {name}: {len(fc['features'])} feições ({size_kb:.0f} KB)")


def main() -> int:
    cfg = load_config()
    bbox = overpass_bbox(cfg["bbox"])
    timeout = cfg.get("overpass_timeout_s", 180)
    url = cfg.get("overpass_url", OVERPASS_MIRRORS[0])

    print(f"Área: {cfg['cidade']}  bbox(S,W,N,E)={bbox}")

    print("\n[1/2] Baixando prédios (building)…")
    q_buildings = (
        f"[out:json][timeout:{timeout}];"
        f'(way["building"]({bbox});relation["building"]({bbox}););'
        f"out geom;"
    )
    b_data = run_overpass(q_buildings, timeout, url)
    buildings = buildings_to_geojson(b_data.get("elements", []), cfg)
    write_geojson("buildings.geojson", buildings)

    print("\n[2/2] Baixando ruas (highway)…")
    q_roads = (
        f"[out:json][timeout:{timeout}];"
        f'(way["highway"]({bbox}););'
        f"out geom;"
    )
    r_data = run_overpass(q_roads, timeout, url)
    roads = roads_to_geojson(r_data.get("elements", []))
    write_geojson("roads.geojson", roads)

    if not buildings["features"]:
        print("\n⚠ Nenhum prédio retornado — verifique o bbox ou a conexão.")
        return 1
    print("\nConcluído. Sirva o viewer: cd web && python -m http.server 8000")
    return 0


if __name__ == "__main__":
    sys.exit(main())
