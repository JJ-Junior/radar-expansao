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
# RADAR DE EXPANSAO - BAIRROS SOB DEMANDA: DADOS DO IBGE DE UM MUNICIPIO
# =============================================================================
#
# OBJETIVO: baixar e carregar o que o IBGE tem por setor censitario de um
#           municipio: populacao, faixa de 20 a 59 anos, renda do responsavel,
#           contorno dos setores e os enderecos do CNEFE 2022.
# ENTRADA:  FTP do Censo 2022 (agregados nacionais por setor, CNEFE por
#           municipio), WFS de setores, SIDRA (populacao oficial), Localidades
# SAIDA:    DataFrames de setores e enderecos + GeoJSON dos setores + meta
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - pandas.read_csv com chunksize e usecols
#   - requisicoes HTTP com tentativas
#
# NOVIDADES:
#   1. WFS em paginas (2.000 feicoes por vez) com filtro CQL por municipio
#   2. setor "final": enderecos do CNEFE com codigo de setor preliminar vao
#      para o setor da malha que contem o ponto
#
# COMO RODAR: nao roda sozinho; e chamado por src/bairros/processar.py
# =============================================================================

# ============================== CONFIG ==============================
TAMANHO_PAGINA_WFS = 2000
TENTATIVAS = 5
ESPERA_SEGUNDOS = 15
LINHAS_POR_BLOCO = 200_000
COLUNAS_CNEFE = ["COD_SETOR", "CEP", "DSC_LOCALIDADE", "NOM_TITULO_SEGLOGR", "NOM_SEGLOGR", "NUM_ENDERECO",
                 "LATITUDE", "LONGITUDE", "COD_ESPECIE"] + [f"{p}{i}" for i in range(1, 6)
                                                            for p in ("NOM_COMP_ELEM", "VAL_COMP_ELEM")]
COLUNAS_CATEGORIA = ["cd_setor", "quadra", "cep", "localidade", "titulo_logr", "nome_logr", "numero", "especie"]
# ====================================================================

import io
import json
import os
import re
import time
import urllib.request
import zipfile

import pandas as pd

from src.bairros import config as C
from src.bairros.geo import centroide, localizar, poligonos


def _get(url, timeout=300):
    for tentativa in range(TENTATIVAS):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": C.USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as exc:
            if tentativa == TENTATIVAS - 1:
                raise RuntimeError(f"falha ao baixar {url.split('?')[0]}: {exc}") from exc
            time.sleep(ESPERA_SEGUNDOS)


def _salvar(url, destino):
    if os.path.exists(destino) and os.path.getsize(destino) > 0:
        return
    dados = _get(url)
    with open(destino + ".parcial", "wb") as f:
        f.write(dados)
    os.replace(destino + ".parcial", destino)


def baixar(cod, p):
    """Baixa (ou reaproveita do cache) os arquivos do IBGE do municipio. Devolve o meta."""
    for chave, url in C.AGREGADOS.items():
        _salvar(url, C.arquivo_agregado(p, chave))
    meta_path = os.path.join(p["cache"], "meta.json")
    if os.path.exists(meta_path):
        meta = json.load(open(meta_path, encoding="utf-8"))
    else:
        loc = json.loads(_get(C.LOCALIDADES_MUN.format(cod=cod)))
        if not loc:
            raise RuntimeError(f"municipio {cod} inexistente no IBGE")
        sid = json.loads(_get(C.SIDRA_POP.format(cod=cod)))
        pasta_uf = C.CNEFE_MUN + f"{cod[:2]}_{C.UFS[cod[:2]]}/"
        nomes = set(re.findall(rf'href="({cod}_[^"]+\.zip)"', _get(pasta_uf).decode("latin-1")))
        if len(nomes) != 1:
            raise RuntimeError(f"CNEFE de {cod} nao encontrado")
        meta = {"codigo": cod, "nome": loc["nome"], "uf": C.UFS[cod[:2]], "pop_oficial_2022": int(sid[1]["V"]),
                "cnefe_zip": nomes.pop(), "cnefe_url": pasta_uf}
    # CNEFE (grande) vai para tmp; o worker apaga depois do pedido
    cnefe = os.path.join(p["tmp"], meta["cnefe_zip"])
    _salvar(meta["cnefe_url"] + meta["cnefe_zip"], cnefe)
    geo_path = os.path.join(p["cache"], "setores_2022.geojson")
    if not os.path.exists(geo_path):
        feats, inicio = [], 0
        while True:
            url = (C.WFS_SETORES + f"&CQL_FILTER=cd_mun=%27{cod}%27&sortBy=cd_setor"
                   f"&count={TAMANHO_PAGINA_WFS}&startIndex={inicio}")
            lote = json.loads(_get(url))["features"]
            feats += [{"type": "Feature", "geometry": f["geometry"],
                       "properties": {"cd_setor": f["properties"]["cd_setor"]}} for f in lote]
            if len(lote) < TAMANHO_PAGINA_WFS:
                break
            inicio += TAMANHO_PAGINA_WFS
        if not feats:
            raise RuntimeError(f"WFS sem setores para {cod}")
        with open(geo_path + ".parcial", "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": feats}, f)
        os.replace(geo_path + ".parcial", geo_path)
    with open(geo_path, encoding="utf-8") as f:
        meta["setores_malha"] = len(json.load(f)["features"])
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    meta["cnefe_path"], meta["geo_path"] = cnefe, geo_path
    return meta


def _ler_zip_csv(caminho, filtro_col, prefixo, colunas=None):
    with zipfile.ZipFile(caminho) as z, z.open(z.namelist()[0]) as f:
        blocos = pd.read_csv(io.TextIOWrapper(f, encoding="latin-1"), sep=";", dtype=str,
                             chunksize=LINHAS_POR_BLOCO, usecols=colunas)
        partes = [b[b[filtro_col].str.startswith(prefixo, na=False)] for b in blocos]
    return pd.concat(partes) if partes else pd.DataFrame(columns=colunas or [])


def _num(s, decimal=","):
    s = s.astype(str).str.strip()
    if decimal == ",":
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def _bloco_cnefe(cn):
    """Bloco do CNEFE reduzido as colunas usadas; a quadra sai do complemento "QUADRA" (cidades "quadra-casa")."""
    quadra = pd.Series("", index=cn.index)
    for i in range(5, 0, -1):
        eh = cn[f"NOM_COMP_ELEM{i}"].fillna("").str.strip().str.upper() == "QUADRA"
        quadra = quadra.where(~eh, cn[f"VAL_COMP_ELEM{i}"].fillna("").str.strip())
    return pd.DataFrame({
        "cd_setor": cn["COD_SETOR"].str[:15], "quadra": quadra, "cep": cn["CEP"].fillna(""),
        "localidade": cn["DSC_LOCALIDADE"].fillna("").str.strip(), "titulo_logr": cn["NOM_TITULO_SEGLOGR"].fillna(""),
        "nome_logr": cn["NOM_SEGLOGR"].fillna(""), "numero": cn["NUM_ENDERECO"].fillna(""),
        "lat": pd.to_numeric(cn["LATITUDE"], errors="coerce"), "lon": pd.to_numeric(cn["LONGITUDE"], errors="coerce"),
        "especie": cn["COD_ESPECIE"].fillna(""),
    })


def _ler_cnefe(caminho):
    """CNEFE em blocos; textos repetidos viram categoria (o Rio cabe em ~1 GB em vez de ~3 GB)."""
    partes = []
    with zipfile.ZipFile(caminho) as z, z.open(z.namelist()[0]) as f:
        for cn in pd.read_csv(io.TextIOWrapper(f, encoding="utf-8", errors="replace"), sep=";", dtype=str,
                              usecols=COLUNAS_CNEFE, chunksize=LINHAS_POR_BLOCO):
            partes.append(_bloco_cnefe(cn))
    end = pd.concat(partes, ignore_index=True)
    del partes
    for c in COLUNAS_CATEGORIA:
        end[c] = end[c].astype("category")
    return end


def carregar(cod, p, meta):
    """Setores (Censo 2022) e enderecos (CNEFE) do municipio, com conferencias."""
    conf = {}
    bas = _ler_zip_csv(C.arquivo_agregado(p, "basico"), "CD_MUN", cod)
    bas = bas[bas["CD_MUN"] == cod]
    st = pd.DataFrame({
        "cd_setor": bas["CD_SETOR"], "situacao": bas["SITUACAO"], "area_km2": _num(bas["AREA_KM2"]),
        "cd_dist": bas["CD_DIST"], "nm_dist": bas["NM_DIST"], "cd_subdist": bas["CD_SUBDIST"],
        "nm_subdist": bas["NM_SUBDIST"].replace(".", None), "cd_bairro": bas["CD_BAIRRO"].replace(".", None),
        "nm_bairro": bas["NM_BAIRRO"].replace(".", None), "pop": _num(bas["v0001"]),
        "dom_ocupados": _num(bas["v0007"]),
    })
    dom_particulares = int(_num(bas["v0003"]).sum())
    del bas
    dem = _ler_zip_csv(C.arquivo_agregado(p, "demografia"), "CD_setor", cod,
                       ["CD_setor", "V01035", "V01036", "V01037", "V01038", "V01039"]).set_index("CD_setor")
    idade = sum(_num(dem[c], ".").fillna(0) for c in ["V01035", "V01036", "V01037", "V01038", "V01039"])
    st["pop_20_59"] = st["cd_setor"].map(idade)
    ren = _ler_zip_csv(C.arquivo_agregado(p, "renda"), "CD_SETOR", cod,
                       ["CD_SETOR", "V06001", "V06004"]).set_index("CD_SETOR")
    st["responsaveis"] = st["cd_setor"].map(_num(ren["V06001"], "."))
    st["renda_media_resp"] = st["cd_setor"].map(_num(ren["V06004"], "."))
    rb = _ler_zip_csv(C.arquivo_agregado(p, "renda_bairro"), "CD_BAIRRO", cod, ["CD_BAIRRO", "V06004"])
    renda_bairro = dict(zip(rb["CD_BAIRRO"], _num(rb["V06004"])))

    with open(meta["geo_path"], encoding="utf-8") as f:
        geo = json.load(f)
    cent = {ft["properties"]["cd_setor"]: centroide(ft["geometry"]) for ft in geo["features"] if ft["geometry"]}
    st["lon"] = st["cd_setor"].map(lambda s: (cent.get(s) or (None, None))[0])
    st["lat"] = st["cd_setor"].map(lambda s: (cent.get(s) or (None, None))[1])
    conf.update({"setores": int(len(st)), "pop_setores": int(st["pop"].sum()),
                 "pop_oficial": meta["pop_oficial_2022"], "dom_particulares_censo": dom_particulares})

    end = _ler_cnefe(meta["cnefe_path"])
    end = end[end["lat"].notna()].reset_index(drop=True)
    conf["cnefe_enderecos"] = int(len(end))
    conf["cnefe_domicilios_particulares"] = int((end["especie"] == "1").sum())

    grade = poligonos(geo, "cd_setor")
    validos = set(st["cd_setor"])
    final = end["cd_setor"].astype(object).where(end["cd_setor"].isin(validos))
    fora = final.isna()
    final.loc[fora] = [localizar(lo, la, grade) for lo, la in zip(end.loc[fora, "lon"], end.loc[fora, "lat"])]
    end["cd_setor_final"] = final.fillna("").astype("category")
    del final
    conf["cnefe_reatribuidos"] = int(fora.sum())
    conf["cnefe_sem_setor"] = int((end["cd_setor_final"] == "").sum())
    return st, end, geo, renda_bairro, conf
