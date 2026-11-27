# +======================================================================================+
# |                                                                                      |
# |    ____    ___   _   _      _     ____      ____     _     ___    ___     _          |
# |   / ___|  / _ \ | | | |    / \   |  _ \     |___ \  / |   / _ \  / _ \   / |         |
# |   \___ \ | | | || | | |   / _ \  | | | |      __) | | |  | | | || | | |  | |         |
# |    ___) || |_| || |_| |  / ___ \ | |_| |     / __/  | |  | |_| || |_| |  | |         |
# |   |____/  \__\_\ \___/  /_/   \_\|____/     |_____| |_|   \___/  \___/   |_|         |
# |                                                                                      |
# +======================================================================================+
#
# =============================================================================
# RADAR DE EXPANSAO - BAIRROS SOB DEMANDA: FUNCOES GEOGRAFICAS
# =============================================================================
#
# OBJETIVO: ponto no poligono (com indice em grade), distancia, centroide,
#           soma num raio e simplificacao de contornos para o mapa.
# ENTRADA:  GeoJSON dos setores censitarios (lon/lat)
# SAIDA:    funcoes importadas pelos outros modulos de src/bairros
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - funcoes com math (radianos, seno, cosseno)
#   - dicionarios como indice
#
# NOVIDADES:
#   1. indice em grade de ~1 km -> cidades com 13 mil setores (Rio) sem
#      comparar cada ponto com todos os poligonos
#   2. shapely para unir setores em bairros e simplificar contornos
#
# COMO RODAR: nao roda sozinho; e importado pelos outros scripts de src/bairros
# =============================================================================

# ============================== CONFIG ==============================
PASSO_GRADE_GRAUS = 0.01      # celula do indice de poligonos (~1 km)
PASSO_GRADE_PONTOS = 0.02     # celula da grade de pontos para somas no raio
RAIO_TERRA_KM = 6371.0
# ====================================================================

import json
import math

from shapely.geometry import mapping, shape
from shapely.ops import unary_union


def poligonos(geo, campo_id):
    """Indice {celula: [(id, bbox, polis)]} a partir de um GeoJSON de (Multi)Polygon em lon/lat."""
    grade = {}
    for ft in geo["features"]:
        g = ft["geometry"]
        if not g:
            continue
        polis = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        xs = [p[0] for poli in polis for p in poli[0]]
        ys = [p[1] for poli in polis for p in poli[0]]
        item = (ft["properties"][campo_id], (min(xs), min(ys), max(xs), max(ys)), polis)
        for i in range(math.floor(min(xs) / PASSO_GRADE_GRAUS), math.floor(max(xs) / PASSO_GRADE_GRAUS) + 1):
            for j in range(math.floor(min(ys) / PASSO_GRADE_GRAUS), math.floor(max(ys) / PASSO_GRADE_GRAUS) + 1):
                grade.setdefault((i, j), []).append(item)
    return grade


def _no_anel(x, y, anel):
    dentro = False
    j = len(anel) - 1
    for i in range(len(anel)):
        xi, yi = anel[i][0], anel[i][1]
        xj, yj = anel[j][0], anel[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def localizar(lon, lat, grade):
    """Id do poligono que contem o ponto (considera buracos), ou None."""
    if lon is None or lat is None or lon != lon or lat != lat:
        return None
    for pid, (x0, y0, x1, y1), polis in grade.get((math.floor(lon / PASSO_GRADE_GRAUS), math.floor(lat / PASSO_GRADE_GRAUS)), []):
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        for poli in polis:
            if _no_anel(lon, lat, poli[0]) and not any(_no_anel(lon, lat, b) for b in poli[1:]):
                return pid
    return None


def distancia_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RAIO_TERRA_KM * math.asin(math.sqrt(a))


def centroide(geom):
    """Centroide de area do maior poligono (formula do laco), em lon/lat."""
    polis = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    melhor, area_max = None, -1
    for poli in polis:
        anel = poli[0]
        a = cx = cy = 0.0
        for (x1, y1), (x2, y2) in zip(anel, anel[1:]):
            c = x1 * y2 - x2 * y1
            a += c
            cx += (x1 + x2) * c
            cy += (y1 + y2) * c
        if abs(a) > area_max and a != 0:
            area_max, melhor = abs(a), (cx / (3 * a), cy / (3 * a))
    return melhor


class GradePontos:
    """Soma valores de pontos num raio (km) usando uma grade, sem comparar todos com todos."""

    def __init__(self, pontos):
        self.grade = {}
        for la, lo, v in pontos:
            if la is None or lo is None or la != la or lo != lo:
                continue
            self.grade.setdefault((math.floor(la / PASSO_GRADE_PONTOS), math.floor(lo / PASSO_GRADE_PONTOS)), []).append((la, lo, v))

    def no_raio(self, la, lo, raio_km):
        if la != la or lo != lo:
            return
        n = math.ceil(raio_km / 111.0 / PASSO_GRADE_PONTOS) + 1
        ci, cj = math.floor(la / PASSO_GRADE_PONTOS), math.floor(lo / PASSO_GRADE_PONTOS)
        for i in range(ci - n, ci + n + 1):
            for j in range(cj - n, cj + n + 1):
                for a, b, v in self.grade.get((i, j), []):
                    if distancia_km(la, lo, a, b) <= raio_km:
                        yield v


def _arredondar(obj, casas):
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(obj[0], casas), round(obj[1], casas)]
        return [_arredondar(o, casas) for o in obj]
    return obj


def simplificar(geom, tolerancia, casas):
    """GeoJSON simplificado e com coordenadas arredondadas (texto JSON), ou None."""
    if not geom:
        return None
    g = shape(geom) if isinstance(geom, dict) else geom
    if g.is_empty:
        return None
    s = g.simplify(tolerancia, preserve_topology=True)
    m = mapping(s)
    return json.dumps({"type": m["type"], "coordinates": _arredondar(m["coordinates"], casas)}, separators=(",", ":"))


def unir(geoms):
    """Uniao de geometrias GeoJSON (contorno de um bairro a partir dos setores)."""
    validas = [shape(g).buffer(0) for g in geoms if g]
    return unary_union(validas) if validas else None
