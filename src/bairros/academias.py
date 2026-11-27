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
# RADAR DE EXPANSAO - BAIRROS SOB DEMANDA: GEOCODIFICACAO DAS ACADEMIAS
# =============================================================================
#
# OBJETIVO: dar coordenada as academias ativas do municipio (CNAE 93.13-1
#           principal) casando o endereco fiscal com os enderecos do CNEFE.
# ENTRADA:  academias do municipio (bairros.academia ou o CSV da base) e os
#           enderecos do CNEFE ja carregados
# SAIDA:    DataFrame com lat, lon, nivel de geocodificacao, setor e localidade
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - normalizar texto (acentos, maiusculas)
#   - filtrar DataFrame por condicao
#
# NOVIDADES:
#   1. casamento em niveis: CEP + numero -> logradouro + numero -> centroide do
#      CEP -> centroide do logradouro -> API publica de CEP (so o CEP e enviado,
#      com cache e teto de consultas por municipio)
#   2. cidades com numeracao "quadra-casa" (ex.: Bauru, 9-50) usam a quadra
#
# COMO RODAR: nao roda sozinho; e chamado por src/bairros/processar.py
# =============================================================================

# ============================== CONFIG ==============================
DIST_MAX_CASAMENTO_KM = 0.5    # candidatos mais espalhados que isso nao valem
DIST_MAX_LOGRADOURO_KM = 3.0   # centroide de logradouro so se a rua for curta
SEMELHANCA_MIN = 0.5
PALAVRAS_IGNORADAS = set("""DR DOUTOR DRA DOUTORA PROF PROFESSOR PROFESSORA ENG ENGENHEIRO CEL CORONEL GAL GENERAL SEN
SENADOR DEP DEPUTADO PRES PRESIDENTE VER VEREADOR PE PADRE STA STO CAP CAPITAO MAJ MAJOR TEN TENENTE ALM ALMIRANTE MAL
MARECHAL DONA D DA DE DO DAS DOS E R RUA AV AVENIDA AL ALAMEDA TV TRAVESSA PCA PRACA ROD RODOVIA VIA ESTRADA EST
ENGO AVIADOR CONEGO MONSENHOR COMENDADOR CDOR JORNALISTA FREI IRMAO""".split())
# ====================================================================

import json
import os
import re
import time
import unicodedata
import urllib.request

import pandas as pd

from src.bairros import config as C
from src.bairros.geo import distancia_km, localizar, poligonos


def norm(txt):
    txt = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9 ]", " ", txt)


def tokens(txt):
    return {t for t in norm(txt).split() if t not in PALAVRAS_IGNORADAS}


def semelhanca(a, b):
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / min(len(ta), len(tb)) if ta and tb else 0.0


def partir_quadra(numero):
    """Cidades "quadra-casa": '9-50' -> (9, 50); '950' -> (9, 50); '50' -> (None, 50); 'SN' -> (None, None)."""
    s = norm(numero).strip()
    m = re.match(r"^(\d{1,3})\s+(\d{1,3})\b", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^(\d+)", s)
    if not m:
        return None, None
    d = m.group(1).lstrip("0") or "0"
    if len(d) <= 2:
        return None, int(d)
    if len(d) <= 4:
        return int(d[:-2]), int(d[-2:])
    return None, None


def numero_simples(numero):
    m = re.match(r"^(\d+)", norm(numero).strip())
    return (None, int(m.group(1))) if m else (None, None)


def _inteiro(x):
    try:
        return int(str(x).strip())
    except ValueError:
        return None


def geocodificar(cod, p, ac, end, geo):
    """ac: academias ativas do municipio (colunas da base). Devolve (DataFrame geocodificado, estatisticas)."""
    ac = ac[ac["academia_principal"].astype(str).isin(["1", "True", "true", "t"])].copy()
    quadra_casa = cod in C.NUMERACAO_QUADRA
    partir = partir_quadra if quadra_casa else numero_simples

    # so os enderecos dos CEPs e logradouros das academias (cidades grandes: evita copiar milhoes de linhas)
    ceps_ac = set(ac["cep"].astype(str).str.replace(r"\D", "", regex=True))
    toks_ac = {" ".join(sorted(tokens(x))) for x in ac["logradouro"]}
    logr_cat = (end["titulo_logr"].astype(str) + " " + end["nome_logr"].astype(str)).str.strip().astype("category")
    cats = pd.Series(logr_cat.cat.categories)
    tok_de = dict(zip(cats, cats.map(lambda x: " ".join(sorted(tokens(x))))))
    codigos_ok = [i for i, c in enumerate(cats) if tok_de[c] in toks_ac]
    mascara = logr_cat.cat.codes.isin(codigos_ok) | end["cep"].isin(ceps_ac)
    e = end.loc[mascara, ["cep", "quadra", "numero", "lat", "lon", "cd_setor_final", "localidade"]].copy()
    e["logr"] = logr_cat[mascara].astype(str)
    del logr_cat
    for c in ["cep", "quadra", "numero", "cd_setor_final", "localidade"]:
        e[c] = e[c].astype(str)
    e["logr_tok"] = e["logr"].map(tok_de)
    e["q"] = e["quadra"].map(_inteiro)
    e["c"] = e["numero"].map(_inteiro)
    por_cep = {k: g for k, g in e[e["cep"].isin(ceps_ac)].groupby("cep")}
    por_logr = {k: g for k, g in e[e["logr_tok"].isin(toks_ac)].groupby("logr_tok") if k}
    # grade dos enderecos residenciais (indices em vez de listas Python de milhoes de pontos)
    res = end.loc[end["especie"] == "1", ["lat", "lon", "localidade"]].reset_index(drop=True)
    res_lat, res_lon, res_loc = res["lat"].to_numpy(), res["lon"].to_numpy(), res["localidade"].astype(str).to_numpy()
    grade_res = res.groupby([res["lat"].map(lambda v: round(v, 2)), res["lon"].map(lambda v: round(v, 2))]).indices
    del res
    lat_min, lat_max, lon_min, lon_max = end.lat.min(), end.lat.max(), end.lon.min(), end.lon.max()
    polis = poligonos(geo, "cd_setor")

    def localidade_proxima(la, lo):
        melhor, dmin = "", 9e9
        for dy in (-0.01, 0, 0.01):
            for dx in (-0.01, 0, 0.01):
                idx = grade_res.get((round(la + dy, 2), round(lo + dx, 2)))
                if idx is None:
                    continue
                d = (res_lat[idx] - la) ** 2 + (res_lon[idx] - lo) ** 2
                k = int(d.argmin())
                if d[k] < dmin:
                    dmin, melhor = float(d[k]), res_loc[idx[k]]
        return melhor

    def escolher_rua(cand, logr_cnpj):
        if cand["logr"].nunique() <= 1:
            return cand
        s = cand["logr"].map(lambda x: semelhanca(x, logr_cnpj))
        return cand[s == s.max()] if s.max() >= SEMELHANCA_MIN else cand.iloc[0:0]

    cache_path = os.path.join(p["cache"], "cache_api_cep.json")
    cache = {}
    if os.path.exists(cache_path):
        cache = {k: tuple(v) if v else None for k, v in json.load(open(cache_path, encoding="utf-8")).items()}
    consultas = 0

    def api_cep(cep):
        nonlocal consultas
        if cep not in cache:
            if consultas >= C.MAX_CONSULTAS_CEP:
                return None
            consultas += 1
            try:
                req = urllib.request.Request(C.API_CEP.format(cep=cep), headers={"User-Agent": C.USER_AGENT})
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.loads(r.read().decode("utf-8"))
                cache[cep] = (float(d["lat"]), float(d["lng"]))
            except Exception:
                cache[cep] = None
            time.sleep(C.PAUSA_CEP_SEGUNDOS)
        return cache[cep]

    linhas = []
    for _, r in ac.iterrows():
        q, c = partir(r["numero"])
        logr_cnpj = r["logradouro"] or ""
        cep = re.sub(r"\D", "", str(r["cep"] or ""))
        lat = lon = None
        nivel, ref = "nao_geocodificado", None
        cand_cep = escolher_rua(por_cep[cep], logr_cnpj) if cep in por_cep else None
        cand_logr = por_logr.get(" ".join(sorted(tokens(logr_cnpj))))

        def tentar(cand, filtro, rotulo):
            nonlocal lat, lon, nivel, ref
            if lat is not None or cand is None or cand.empty:
                return
            m = cand[filtro(cand)]
            if not m.empty and distancia_km(m.lat.min(), m.lon.min(), m.lat.max(), m.lon.max()) < DIST_MAX_CASAMENTO_KM:
                lat, lon, nivel = m.lat.mean(), m.lon.mean(), rotulo
                ref = m.iloc[0]

        if quadra_casa:
            if q is not None and c is not None:
                tentar(cand_cep, lambda d: (d.q == q) & (d.c == c), "1_cep_quadra_casa")
                tentar(cand_logr, lambda d: (d.q == q) & (d.c == c), "2_logradouro_quadra_casa")
                tentar(cand_cep, lambda d: d.q == q, "3_cep_quadra")
                tentar(cand_logr, lambda d: d.q == q, "3_logradouro_quadra")
            if c is not None:
                tentar(cand_cep, lambda d: d.c == c, "4_cep_casa")
        elif c is not None:
            tentar(cand_cep, lambda d: d.c == c, "1_cep_numero")
            tentar(cand_logr, lambda d: d.c == c, "2_logradouro_numero")
        if lat is None and cand_cep is not None and not cand_cep.empty:
            lat, lon, nivel = cand_cep.lat.mean(), cand_cep.lon.mean(), "5_centroide_cep"
        if lat is None and cand_logr is not None and not cand_logr.empty:
            if distancia_km(cand_logr.lat.min(), cand_logr.lon.min(), cand_logr.lat.max(),
                            cand_logr.lon.max()) < DIST_MAX_LOGRADOURO_KM:
                lat, lon, nivel = cand_logr.lat.mean(), cand_logr.lon.mean(), "6_centroide_logradouro"
        if lat is None and len(cep) == 8:
            achado = api_cep(cep)
            if achado and lat_min - 0.05 < achado[0] < lat_max + 0.05 and lon_min - 0.05 < achado[1] < lon_max + 0.05:
                (lat, lon), nivel = achado, "7_api_cep"
        if lat is None:
            continue
        setor = ref["cd_setor_final"] if ref is not None else localizar(lon, lat, polis)
        localidade = ref["localidade"] if ref is not None else localidade_proxima(lat, lon)
        linhas.append({"cnpj": r["cnpj"], "lat": lat, "lon": lon, "nivel_geocod": nivel,
                       "cd_setor": setor or None, "localidade": localidade})
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1)
    pts = pd.DataFrame(linhas, columns=["cnpj", "lat", "lon", "nivel_geocod", "cd_setor", "localidade"])
    est = {"academias_base": int(len(ac)), "academias_geocodificadas": int(len(pts)),
           "niveis_geocod": pts["nivel_geocod"].value_counts().sort_index().to_dict(), "consultas_api_cep": consultas}
    return pts, est
