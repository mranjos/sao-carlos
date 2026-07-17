#!/usr/bin/env python3
"""
Exporta um GLB do recorte do vale do Gregório (centro de São Carlos) para
renderização foto-realista no Blender: terreno real (tiles Terrarium/AWS),
prédios extrudados e o cenário proposto (canal, várzea, praça, calçadões,
pontes, árvores).

Coordenadas em METROS (origem no Mercado Municipal, X=leste, Y=norte,
Z=altitude). No Blender: File → Import → glTF 2.0.

Uso:
    pip install -r pipeline/requirements.txt
    python pipeline/export_glb.py            # gera export/centro-gregorio.glb
"""

from __future__ import annotations

import io
import json
import math
import os

import numpy as np
import requests
import trimesh
from PIL import Image
from shapely.geometry import shape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(ROOT, "export")

# Recorte: vale do Gregório no centro
W, S, E, N = -47.906, -22.030, -47.868, -22.012

# Origem local = Mercado Municipal
LON0, LAT0 = -47.8911, -22.0200
MX = 111_320.0 * math.cos(math.radians(LAT0))   # m por grau de longitude
MY = 110_540.0                                  # m por grau de latitude

Z_TILE = 14

CORES = {
    "terreno":  [196, 189, 175, 255],
    "predio":   [222, 219, 212, 255],
    "canal":    [64, 148, 200, 255],
    "lago":     [96, 168, 214, 255],
    "varzea":   [140, 190, 140, 255],
    "calcadao": [214, 168, 110, 255],
    "ponte":    [84, 98, 108, 255],
    "deck":     [150, 105, 62, 255],
    "praca1":   [230, 208, 168, 255],
    "praca2":   [216, 184, 138, 255],
    "praca3":   [200, 160, 104, 255],
    "tronco":   [110, 84, 60, 255],
    "copa":     [64, 128, 76, 255],
}


def xy(lon: float, lat: float) -> tuple[float, float]:
    return ((lon - LON0) * MX, (lat - LAT0) * MY)


# ---------------------------------------------------------------------------
# Terreno (tiles Terrarium)
# ---------------------------------------------------------------------------

def tile_xy(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def carregar_terreno():
    """Baixa os tiles do recorte e monta grade de elevação georreferenciada."""
    x0, y1 = tile_xy(W, S, Z_TILE)
    x1, y0 = tile_xy(E, N, Z_TILE)
    tx0, tx1 = int(x0), int(x1)
    ty0, ty1 = int(y0), int(y1)
    cols = (tx1 - tx0 + 1) * 256
    rows = (ty1 - ty0 + 1) * 256
    grade = np.zeros((rows, cols), dtype=np.float32)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            url = (f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/"
                   f"{Z_TILE}/{tx}/{ty}.png")
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            px = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"),
                            dtype=np.float32)
            elev = px[:, :, 0] * 256 + px[:, :, 1] + px[:, :, 2] / 256 - 32768
            grade[(ty - ty0) * 256:(ty - ty0 + 1) * 256,
                  (tx - tx0) * 256:(tx - tx0 + 1) * 256] = elev
    print(f"  terreno: {grade.shape[1]}×{grade.shape[0]} px, "
          f"{grade.min():.0f}–{grade.max():.0f} m")

    n = 2 ** Z_TILE

    def lonlat(px_col, px_row):
        xt = tx0 + px_col / 256
        yt = ty0 + px_row / 256
        lon = xt / n * 360 - 180
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yt / n))))
        return lon, lat

    def altura(lon, lat):
        xt, yt = tile_xy(lon, lat, Z_TILE)
        c = min(max((xt - tx0) * 256, 0), cols - 1.001)
        r_ = min(max((yt - ty0) * 256, 0), rows - 1.001)
        c0, r0 = int(c), int(r_)
        fc, fr = c - c0, r_ - r0
        return float(
            grade[r0, c0] * (1 - fc) * (1 - fr) +
            grade[r0, c0 + 1] * fc * (1 - fr) +
            grade[r0 + 1, c0] * (1 - fc) * fr +
            grade[r0 + 1, c0 + 1] * fc * fr)

    return grade, lonlat, altura, (tx0, ty0, cols, rows)


def malha_terreno(grade, lonlat, meta, passo=2):
    tx0, ty0, cols, rows = meta
    # limita ao bbox do recorte
    ci = []
    ri = []
    for c in range(0, cols, passo):
        lon, _ = lonlat(c, 0)
        if W - 0.001 <= lon <= E + 0.001:
            ci.append(c)
    for r in range(0, rows, passo):
        _, lat = lonlat(0, r)
        if S - 0.001 <= lat <= N + 0.001:
            ri.append(r)
    verts = np.zeros((len(ri), len(ci), 3), dtype=np.float64)
    for i, r in enumerate(ri):
        for j, c in enumerate(ci):
            lon, lat = lonlat(c, r)
            x, y = xy(lon, lat)
            verts[i, j] = (x, y, grade[r, c])
    v = verts.reshape(-1, 3)
    faces = []
    nc = len(ci)
    for i in range(len(ri) - 1):
        for j in range(nc - 1):
            a = i * nc + j
            faces.append([a, a + 1, a + nc])
            faces.append([a + 1, a + nc + 1, a + nc])
    m = trimesh.Trimesh(vertices=v, faces=np.array(faces), process=False)
    m.visual.face_colors = CORES["terreno"]
    print(f"  malha do terreno: {len(v)} vértices")
    return m


# ---------------------------------------------------------------------------
# Extrusões
# ---------------------------------------------------------------------------

def extrudar(poly, altura_m, z_base, cor):
    """Extruda um shapely Polygon para [z_base, z_base+altura]."""
    try:
        m = trimesh.creation.extrude_polygon(poly, altura_m)
    except Exception:
        return None
    m.apply_translation([0, 0, z_base])
    m.visual.face_colors = CORES[cor]
    return m


def poly_local(geom):
    """Reprojeta um Polygon lon/lat para metros locais."""
    from shapely.ops import transform
    return transform(lambda lo, la, z=None: xy(lo, la), geom)


def dentro(geom):
    b = geom.bounds
    return not (b[2] < W or b[0] > E or b[3] < S or b[1] > N)


def arvore(x, y, z):
    tronco = trimesh.creation.cylinder(radius=0.5, height=4.0, sections=6)
    tronco.apply_translation([x, y, z + 2.0])
    tronco.visual.face_colors = CORES["tronco"]
    copa = trimesh.creation.icosphere(subdivisions=1, radius=3.2)
    copa.apply_scale([1, 1, 0.85])
    copa.apply_translation([x, y, z + 6.0])
    copa.visual.face_colors = CORES["copa"]
    return [tronco, copa]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("[1/4] terreno…")
    grade, lonlat, altura, meta = carregar_terreno()
    partes = [malha_terreno(grade, lonlat, meta)]

    print("[2/4] prédios…")
    fc = json.load(open(os.path.join(DATA, "buildings.geojson"), encoding="utf-8"))
    n = 0
    for f in fc["features"]:
        g = shape(f["geometry"])
        if not dentro(g):
            continue
        if g.geom_type == "MultiPolygon":
            g = max(g.geoms, key=lambda p: p.area)
        c = g.centroid
        z = altura(c.x, c.y)
        m = extrudar(poly_local(g), float(f["properties"]["h"]), z, "predio")
        if m:
            partes.append(m)
            n += 1
    print(f"  {n} prédios extrudados")

    print("[3/4] cenário proposto…")
    rw = json.load(open(os.path.join(DATA, "proposal-riverwalk.geojson"),
                        encoding="utf-8"))
    estilo = {
        "canal":    (0.6, -0.5, "canal"),
        "lago":     (0.5, -0.3, "lago"),
        "varzea":   (0.4, 0.05, "varzea"),
        "deck":     (0.5, 1.2, "deck"),
    }
    ESPESSURA_PRACA = {1: 0.6, 2: 2.0, 3: 3.5}
    for f in rw["features"]:
        tipo = f["properties"].get("tipo")
        g = shape(f["geometry"])
        if not dentro(g):
            continue
        if tipo in estilo:
            esp, dz, cor = estilo[tipo]
            if g.geom_type == "MultiPolygon":
                g = max(g.geoms, key=lambda p: p.area)
            if g.geom_type != "Polygon":
                continue
            c = g.centroid
            m = extrudar(poly_local(g), esp, altura(c.x, c.y) + dz, cor)
            if m:
                partes.append(m)
        elif tipo == "praca-terraco":
            nivel = int(f["properties"].get("nivel", 2))
            c = g.centroid
            m = extrudar(poly_local(g), ESPESSURA_PRACA[nivel],
                         altura(c.x, c.y) - 0.2, f"praca{nivel}")
            if m:
                partes.append(m)
        elif tipo in ("calcadao", "ponte"):
            from shapely.geometry import LineString
            gl = g if g.geom_type == "LineString" else None
            if gl is None:
                continue
            larg = 6.0 if tipo == "calcadao" else 12.0
            esp = 0.4 if tipo == "calcadao" else 1.2
            dz = 0.4 if tipo == "calcadao" else 1.6
            faixa = poly_local(gl).buffer(larg / 2, cap_style=2)
            c = g.centroid
            m = extrudar(faixa, esp, altura(c.x, c.y) + dz, tipo)
            if m:
                partes.append(m)
        elif tipo == "arvore":
            z = altura(g.x, g.y)
            x, y = xy(g.x, g.y)
            partes += arvore(x, y, z)

    print("[4/4] montando GLB…")
    cena = trimesh.util.concatenate(partes)
    out = os.path.join(OUT_DIR, "centro-gregorio.glb")
    cena.export(out)
    print(f"✓ {out} ({os.path.getsize(out)/1e6:.1f} MB, "
          f"{len(cena.vertices)} vértices)")


if __name__ == "__main__":
    main()
