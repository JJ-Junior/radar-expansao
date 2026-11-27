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
# RADAR DE EXPANSAO - BAIRROS SOB DEMANDA: INDICADORES E RANKING DE BAIRROS
# =============================================================================
#
# OBJETIVO: calcular, para cada bairro do municipio, mercado (20 a 59 anos),
#           renda do responsavel, concorrencia no raio e massa de renda por
#           km2, e ordenar os bairros com a mesma logica de percentis do
#           ranking de cidades.
# ENTRADA:  setores e enderecos (src/bairros/ibge.py) e academias
#           geocodificadas (src/bairros/academias.py)
# SAIDA:    linhas de bairros.ranking (escalas ibge e popular), bairros.setor
#           e o resumo de conferencias (bairros.resumo)
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - groupby/agg do pandas
#   - percentis com rank, como no ranking de cidades
#
# NOVIDADES:
#   1. duas escalas: bairros oficiais do IBGE (quando o municipio tem) e
#      "bairros populares" = localidade do endereco no CNEFE, com a populacao
#      de cada setor rateada pelos enderecos residenciais
#   2. sem base de academias, o ranking sai provisorio (pesos reescalonados)
#
# COMO RODAR: nao roda sozinho; e chamado por src/bairros/processar.py
# =============================================================================

# ============================== CONFIG ==============================
LIMITE_FORTE, LIMITE_FRACO = 70, 30   # nota para "forte em" / "fraco em" na frase
NAO_BAIRRO = "ZONA RURAL|SEM LOCALIDADE|FORA DE BAIRRO"
ROTULOS = {"mercado": "público de 20 a 59 anos", "renda": "renda do responsável",
           "espaco": "pouca concorrência no raio de 1,5 km", "densidade": "poder de compra concentrado"}
# ====================================================================

import re
import unicodedata

import pandas as pd

from src.bairros import config as C
from src.bairros.geo import GradePontos, distancia_km, simplificar, unir


def titulo(txt):
    menores = {"da", "de", "do", "das", "dos", "e"}
    return " ".join(p.lower() if p.lower() in menores and i else p.capitalize() for i, p in enumerate(str(txt).split()))


def chave(txt):
    t = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]", " ", t)).strip()


def percentil(s, menor_melhor=False):
    v = -s if menor_melhor else s
    n = v.notna().sum()
    return (v.rank(method="average") - 1) / (n - 1) * 100 if n > 1 else v * 0 + 50


def pesos(concorrencia):
    if concorrencia:
        return dict(C.PESOS)
    sem = {k: v for k, v in C.PESOS.items() if k != "espaco"}
    return {k: v / sum(sem.values()) for k, v in sem.items()}


def preparar_setores(st, renda_bairro):
    total_resp = st["responsaveis"].sum()
    renda_mun = (st["responsaveis"] * st["renda_media_resp"]).sum() / total_resp
    imputar = st["renda_media_resp"].isna() & (st["dom_ocupados"] > 0)
    st["renda_imputada"] = imputar
    st["renda_uso"] = st["renda_media_resp"]
    st.loc[imputar, "renda_uso"] = st.loc[imputar, "cd_bairro"].map(renda_bairro).astype(float).fillna(renda_mun)
    st["resp_uso"] = st["responsaveis"].fillna(st["dom_ocupados"])
    st["massa_renda"] = (st["resp_uso"] * st["renda_uso"]).fillna(0)
    return st


def definir_centro(st, end):
    """Bairro IBGE "Centro"; senao a localidade CENTRO do CNEFE; senao o setor com mais estabelecimentos."""
    cb = st.loc[st["nm_bairro"].fillna("").str.strip().str.upper() == "CENTRO", "cd_bairro"]
    if len(cb):
        pts = end[end["cd_setor_final"].isin(set(st.loc[st["cd_bairro"] == cb.iloc[0], "cd_setor"]))]
        origem = "bairro IBGE Centro"
    else:
        pts = end[end["localidade"].astype(str).str.upper() == "CENTRO"]
        origem = "localidade CENTRO do CNEFE"
        if pts.empty:
            com = end[(end["especie"] == "6") & (end["cd_setor_final"] != "")]
            top = com["cd_setor_final"].astype(str).value_counts().index[0]
            pts = com[com["cd_setor_final"] == top]
            origem = "setor com mais estabelecimentos"
    return (float(pts["lat"].mean()), float(pts["lon"].mean())), origem


def _indicadores(u, g_pop, g_ac, centro, concorrencia):
    u["renda_media_resp"] = u["massa"] / u["resp"]
    u["densidade_hab_km2"] = u["pop"] / u["area_km2"]
    u["massa_renda_km2"] = u["massa"] / u["area_km2"]
    u["pop_raio"] = [sum(g_pop.no_raio(la, lo, C.RAIO_KM)) for la, lo in zip(u["lat"], u["lon"])]
    if concorrencia:
        u["acad_raio"] = [sum(1 for _ in g_ac.no_raio(la, lo, C.RAIO_KM)) for la, lo in zip(u["lat"], u["lon"])]
        u["acad_raio_10k"] = u["acad_raio"] / u["pop_raio"].where(u["pop_raio"] > 0) * 1e4
    else:
        u["acad_raio"] = u["acad_raio_10k"] = float("nan")
    u["dist_centro_km"] = [distancia_km(la, lo, *centro) if la == la else None for la, lo in zip(u["lat"], u["lon"])]
    return u


def _ranquear(u, concorrencia):
    w = pesos(concorrencia)
    u["elegivel"] = (u["pop"] >= C.POP_MIN) & ~u["nome"].str.upper().str.contains(NAO_BAIRRO, regex=True)
    el = u[u["elegivel"]].copy()
    el["nota_mercado"] = percentil(el["pop_20_59"])
    el["nota_renda"] = percentil(el["renda_media_resp"])
    el["nota_espaco"] = percentil(el["acad_raio_10k"], menor_melhor=True) if concorrencia else float("nan")
    el["nota_densidade"] = percentil(el["massa_renda_km2"])
    el["nota_final"] = sum(el[f"nota_{k}"] * p for k, p in w.items())
    el = el.sort_values("nota_final", ascending=False)
    el["posicao"] = range(1, len(el) + 1)

    def frase(r):
        fortes = [ROTULOS[k] for k in w if r[f"nota_{k}"] >= LIMITE_FORTE]
        fracos = [ROTULOS[k] for k in w if r[f"nota_{k}"] <= LIMITE_FRACO]
        partes = (["forte em " + ", ".join(fortes)] if fortes else []) + (["fraco em " + ", ".join(fracos)] if fracos else [])
        return "; ".join(partes) or "equilibrado, sem destaque"
    el["frase"] = el.apply(frase, axis=1) if len(el) else pd.Series(dtype=str)
    cols = ["nota_mercado", "nota_renda", "nota_espaco", "nota_densidade", "nota_final", "posicao", "frase"]
    return pd.concat([el, u[~u["elegivel"]]]).reindex(columns=list(u.columns) + cols)


def calcular(cod, st, end, geo, renda_bairro, pts, concorrencia):
    """Devolve (ranking, setores para o mapa, resumo)."""
    st = preparar_setores(st, renda_bairro)
    res = end[(end["especie"] == "1") & (end["cd_setor_final"] != "")]
    # setores com moradores mas sem domicilio particular no CNEFE: rateio pelos domicilios coletivos
    sem_res = end[(end["especie"] == "2") & (end["cd_setor_final"] != "") & ~end["cd_setor_final"].isin(res["cd_setor_final"])]
    res = pd.concat([res, sem_res], ignore_index=True)[["cd_setor_final", "localidade", "lat", "lon"]]
    res["cd_setor_final"] = res["cd_setor_final"].astype(str)
    res["localidade"] = res["localidade"].astype(str).replace("", "(SEM LOCALIDADE)")
    centro, origem_centro = definir_centro(st, end)
    g_pop = GradePontos(zip(st["lat"], st["lon"], st["pop"]))
    g_ac = GradePontos(zip(pts["lat"], pts["lon"], [1] * len(pts)))
    w = pesos(concorrencia)
    saidas = []

    # escala 1: bairros do IBGE (nem todo municipio tem)
    cent = res.groupby("cd_setor_final", observed=True)[["lat", "lon"]].agg(["mean", "count"])
    st["lat_res"] = st["cd_setor"].map(cent[("lat", "mean")])
    st["lon_res"] = st["cd_setor"].map(cent[("lon", "mean")])
    st["n_res"] = st["cd_setor"].map(cent[("lat", "count")]).fillna(0)
    st["chave_b"] = st["cd_bairro"].fillna("fora")
    st["nome_b"] = st["nm_bairro"].fillna("(fora de bairro)")
    n_ibge = n_ibge_rank = 0
    geos = {ft["properties"]["cd_setor"]: ft["geometry"] for ft in geo["features"]}
    if st["cd_bairro"].notna().any():
        b = st.groupby("chave_b").apply(lambda g: pd.Series({
            "nome": g["nome_b"].iloc[0], "setores": len(g), "pop": g["pop"].sum(), "pop_20_59": g["pop_20_59"].sum(),
            "dom_ocupados": g["dom_ocupados"].sum(), "resp": g["resp_uso"].sum(), "massa": g["massa_renda"].sum(),
            "area_km2": g["area_km2"].sum(),
            "lat": (g["lat_res"] * g["n_res"]).sum() / g["n_res"].sum() if g["n_res"].sum() else g["lat"].mean(),
            "lon": (g["lon_res"] * g["n_res"]).sum() / g["n_res"].sum() if g["n_res"].sum() else g["lon"].mean(),
        }), include_groups=False).reset_index().rename(columns={"chave_b": "unidade_id"})
        setor_bairro = dict(zip(st["cd_setor"], st["chave_b"]))
        b["acad_unidade"] = b["unidade_id"].map(pts["cd_setor"].map(setor_bairro).value_counts()).fillna(0) \
            if concorrencia else float("nan")
        b = _ranquear(_indicadores(b, g_pop, g_ac, centro, concorrencia), concorrencia)
        setores_de = st.groupby("chave_b")["cd_setor"].apply(list)
        b["geojson"] = [simplificar(unir([geos.get(s) for s in setores_de.get(k, [])]), C.TOLERANCIA_SIMPLIFICAR,
                                    C.CASAS_GEOJSON) if k != "fora" else None for k in b["unidade_id"]]
        b["escala"] = "ibge"
        n_ibge, n_ibge_rank = int((b["unidade_id"] != "fora").sum()), int(b["elegivel"].sum())
        saidas.append(b)

    # escala 2: bairros populares (localidade do CNEFE; populacao rateada por endereco residencial)
    tot = res.groupby("cd_setor_final", observed=True).size().rename("n_setor")
    par = res.groupby(["cd_setor_final", "localidade"], observed=True).agg(n=("lat", "size"), lat=("lat", "mean"), lon=("lon", "mean")).reset_index()
    par = par.merge(tot, left_on="cd_setor_final", right_index=True)
    par["fr"] = par["n"] / par["n_setor"]
    par = par.merge(st[["cd_setor", "pop", "pop_20_59", "dom_ocupados", "resp_uso", "massa_renda", "area_km2"]],
                    left_on="cd_setor_final", right_on="cd_setor")
    for c in ["pop", "pop_20_59", "dom_ocupados", "resp_uso", "massa_renda", "area_km2"]:
        par[c] = par[c] * par["fr"]
    u = par.groupby("localidade").apply(lambda g: pd.Series({
        "setores": g["cd_setor"].nunique(), "pop": g["pop"].sum(), "pop_20_59": g["pop_20_59"].sum(),
        "dom_ocupados": g["dom_ocupados"].sum(), "resp": g["resp_uso"].sum(), "massa": g["massa_renda"].sum(),
        "area_km2": g["area_km2"].sum(),
        "lat": (g["lat"] * g["n"]).sum() / g["n"].sum(), "lon": (g["lon"] * g["n"]).sum() / g["n"].sum(),
    }), include_groups=False).reset_index().rename(columns={"localidade": "nome"})
    u["acad_unidade"] = u["nome"].map(pts["localidade"].value_counts()).fillna(0) if concorrencia else float("nan")
    u = _ranquear(_indicadores(u, g_pop, g_ac, centro, concorrencia), concorrencia)
    u["unidade_id"] = u["nome"].map(chave)
    u["geojson"] = None
    u["escala"] = "popular"
    saidas.append(u)

    r = pd.concat(saidas, ignore_index=True)
    r["unidade_nome"] = r["nome"].map(titulo)
    r["concorrencia"] = "ok" if concorrencia else "pendente"
    r["cod_municipio"] = int(cod)
    r = r.rename(columns={"pop": "populacao"})
    ranking = r[["cod_municipio", "escala", "unidade_id", "unidade_nome", "elegivel", "posicao", "setores", "populacao",
                 "pop_20_59", "dom_ocupados", "renda_media_resp", "area_km2", "densidade_hab_km2", "massa_renda_km2",
                 "acad_unidade", "pop_raio", "acad_raio", "acad_raio_10k", "dist_centro_km", "nota_mercado", "nota_renda",
                 "nota_espaco", "nota_densidade", "nota_final", "frase", "concorrencia", "lat", "lon", "geojson"]]

    setores = pd.DataFrame({
        "cod_municipio": int(cod), "cd_setor": st["cd_setor"], "bairro_ibge": st["nm_bairro"],
        "urbano": st["situacao"] == "Urbana", "populacao": st["pop"], "pop_20_59": st["pop_20_59"],
        "renda_media_resp": st["renda_uso"].round(2), "renda_imputada": st["renda_imputada"],
        "geojson": [simplificar(geos.get(s), C.TOLERANCIA_SIMPLIFICAR, C.CASAS_GEOJSON) for s in st["cd_setor"]],
    })
    pop_ibge = float(r.loc[r["escala"] == "ibge", "populacao"].sum())
    resumo = {
        "pop_setores": int(st["pop"].sum()),
        "pop_rateada": int(round(float(u["pop"].sum()))),
        "pop_bairros_ibge": int(round(pop_ibge)) if n_ibge else None,
        "concorrencia": "ok" if concorrencia else "pendente",
        "centro_lat": centro[0], "centro_lon": centro[1], "centro_origem": origem_centro,
        "bairros_ibge": n_ibge, "bairros_ibge_ranking": n_ibge_rank,
        "bairros_populares": int(len(u)), "bairros_populares_ranking": int(u["elegivel"].sum()),
        "pesos": {k: round(v, 4) for k, v in w.items()},
        "parametros": {"raio_km": C.RAIO_KM, "pop_min": C.POP_MIN},
    }
    return ranking, setores, resumo
