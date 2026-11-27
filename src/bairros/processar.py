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
# RADAR DE EXPANSAO - BAIRROS SOB DEMANDA: PIPELINE DE UM MUNICIPIO
# =============================================================================
#
# OBJETIVO: responder "dentro desta cidade, quais bairros?": baixa os dados do
#           IBGE do municipio, geocodifica as academias, calcula os indicadores
#           e o ranking de bairros nas duas escalas e grava o resultado.
# ENTRADA:  codigo IBGE do municipio (7 digitos); bairros.academia (ou o CSV
#           da base, com --sem-banco); arquivos do IBGE (baixados na hora)
# SAIDA:    bairros.ranking, bairros.setor, bairros.academia_ponto e
#           bairros.resumo do municipio (troca tudo numa transacao).
#           Com --sem-banco: CSVs em <DIR_DADOS>/cache/<codigo>/saida.
#           Nao mexe em bairros.pedido (a fila e do worker).
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - argparse para parametros de linha de comando
#   - transacao no Postgres (with conn)
#
# NOVIDADES:
#   1. codigo de saida: 0 = ok; diferente de 0 = erro (o worker marca o pedido)
#   2. cache em disco: agregados nacionais e setores ficam; o CNEFE vai para
#      tmp e e apagado pelo worker depois do pedido
#
# INSTALACAO: pip install -r requirements.txt -r requirements-bairros.txt
# COMO RODAR: python -m src.bairros.processar --municipio 3506003
#             python -m src.bairros.processar --municipio 3506003 --sem-banco
# =============================================================================

# ============================== CONFIG ==============================
VERSAO = "bairros-1.1"
LOTE_INSERT = 1000
# ====================================================================

import argparse
import json
import os
import sys
import time

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.bairros import academias, ibge, indicadores  # noqa: E402
from src.bairros import config as C  # noqa: E402


def log(msg):
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


def memoria_pico_mb():
    try:
        import resource  # Linux (container)
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    except ImportError:  # Windows (PC)
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("a", ctypes.c_size_t), ("b", ctypes.c_size_t), ("c", ctypes.c_size_t),
                        ("d", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return round(pmc.PeakWorkingSetSize / 1e6)


def academias_do_municipio(cod, conn):
    """(DataFrame, base_carregada, data_base). Le do banco ou, sem banco, do CSV nacional."""
    if conn is not None:
        with conn.cursor() as cur:
            cur.execute("SELECT max(data_referencia) FROM bairros.academia")
            data_base = cur.fetchone()[0]
            cur.execute("""SELECT cnpj, academia_principal, tipo_logradouro, logradouro, numero, cep
                             FROM bairros.academia WHERE cod_municipio = %s AND academia_principal""", (int(cod),))
            linhas = cur.fetchall()
        df = pd.DataFrame(linhas, columns=["cnpj", "academia_principal", "tipo_logradouro", "logradouro", "numero", "cep"])
        return df.fillna(""), data_base is not None, data_base
    caminho = C.arquivo_base()
    if not os.path.exists(caminho):
        return pd.DataFrame(columns=["cnpj", "academia_principal", "logradouro", "numero", "cep"]), False, None
    partes = [b[b["cod_municipio"] == cod] for b in pd.read_csv(caminho, sep=";", dtype=str, chunksize=200_000)]
    df = pd.concat(partes).fillna("")
    data = df["data_referencia"].max() if len(df) else None
    return df, True, data


def _limpar(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v.item() if hasattr(v, "item") else v


def gravar(conn, cod, ranking, setores, pts, resumo):
    from psycopg2.extras import execute_values
    cod = int(cod)

    def inserir(cur, tabela, df, jsonb=()):
        cols = list(df.columns)
        tpl = "(" + ", ".join("%s::jsonb" if c in jsonb else "%s" for c in cols) + ")"
        valores = [tuple(_limpar(v) for v in linha) for linha in df.itertuples(index=False, name=None)]
        execute_values(cur, f"INSERT INTO bairros.{tabela} ({', '.join(cols)}) VALUES %s", valores,
                       template=tpl, page_size=LOTE_INSERT)

    with conn, conn.cursor() as cur:
        for t in ["ranking", "setor", "academia_ponto"]:
            cur.execute(f"DELETE FROM bairros.{t} WHERE cod_municipio = %s", (cod,))
        inserir(cur, "ranking", ranking, jsonb=("geojson",))
        inserir(cur, "setor", setores, jsonb=("geojson",))
        inserir(cur, "academia_ponto", pts.assign(cod_municipio=cod)[
            ["cod_municipio", "cnpj", "lat", "lon", "nivel_geocod", "cd_setor", "localidade"]])
        cols = list(resumo)
        cur.execute(f"""INSERT INTO bairros.resumo ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})
                        ON CONFLICT (cod_municipio) DO UPDATE SET {', '.join(f'{c} = EXCLUDED.{c}' for c in cols)}""",
                    [json.dumps(resumo[c], ensure_ascii=False) if isinstance(resumo[c], dict) else resumo[c] for c in cols])


def processar(cod, sem_banco=False):
    t0 = time.time()
    p = C.pastas(cod)
    conn = None
    if not sem_banco:
        from src.ingestao.comum import conectar
        conn = conectar()
    log(f"{cod}: baixando/conferindo arquivos do IBGE")
    meta = ibge.baixar(cod, p)
    t_baixar = time.time()
    log(f"{cod} {meta['nome']}/{meta['uf']}: carregando setores e CNEFE (memoria {memoria_pico_mb()} MB)")
    st, end, geo, renda_bairro, conf = ibge.carregar(cod, p, meta)
    if conf["pop_setores"] != conf["pop_oficial"]:
        raise RuntimeError(f"populacao dos setores ({conf['pop_setores']}) difere da oficial ({conf['pop_oficial']})")
    t_carga = time.time()
    ac, base_ok, data_base = academias_do_municipio(cod, conn)
    if base_ok:
        log(f"{cod}: memoria {memoria_pico_mb()} MB; geocodificando {int(ac['academia_principal'].astype(str).isin(['1', 'True', 'true', 't']).sum())} academias")
        pts, est = academias.geocodificar(cod, p, ac, end, geo)
    else:
        log(f"{cod}: base de academias ausente; concorrencia pendente")
        pts = pd.DataFrame(columns=["cnpj", "lat", "lon", "nivel_geocod", "cd_setor", "localidade"])
        est = {"academias_base": None, "academias_geocodificadas": None, "niveis_geocod": None, "consultas_api_cep": 0}
    t_geo = time.time()
    log(f"{cod}: calculando indicadores (memoria {memoria_pico_mb()} MB)")
    ranking, setores, res = indicadores.calcular(cod, st, end, geo, renda_bairro, pts, base_ok, meta["nome"])
    del end
    log(f"{cod}: gravando (memoria {memoria_pico_mb()} MB)")
    t_ind = time.time()
    resumo = {"cod_municipio": int(cod), "municipio_nome": meta["nome"], "uf_sigla": meta["uf"],
              "duracao_s": round(time.time() - t0, 1), "pop_oficial": conf["pop_oficial"],
              "pop_setores": res["pop_setores"], "pop_rateada": res["pop_rateada"], "concorrencia": res["concorrencia"],
              "data_base_cnpj": data_base, **est,
              **{k: res[k] for k in ["centro_lat", "centro_lon", "centro_origem", "bairros_ibge", "bairros_ibge_ranking",
                                     "bairros_populares", "bairros_populares_ranking", "pesos",
                                     "escala_padrao", "escala_ibge_tipo", "aviso_escala"]},
              "parametros": {**res["parametros"], "versao": VERSAO}}
    ranking = ranking.assign(posicao=ranking["posicao"].astype("Int64"), setores=ranking["setores"].astype("Int64"),
                             acad_unidade=ranking["acad_unidade"].astype("Int64"),
                             acad_raio=ranking["acad_raio"].astype("Int64"), pop_raio=ranking["pop_raio"].astype("Int64"))
    setores = setores.assign(populacao=setores["populacao"].astype("Int64"), pop_20_59=setores["pop_20_59"].round().astype("Int64"))
    for c in ["populacao", "pop_20_59", "dom_ocupados", "area_km2", "renda_media_resp", "densidade_hab_km2",
              "massa_renda_km2", "acad_raio_10k", "dist_centro_km", "nota_mercado", "nota_renda", "nota_espaco",
              "nota_densidade", "nota_final"]:
        ranking[c] = ranking[c].astype(float).round(4 if c in ("area_km2", "acad_raio_10k", "dist_centro_km") else
                                                    1 if c.startswith("nota") or c in ("populacao", "pop_20_59", "dom_ocupados") else 2)
    if sem_banco:
        saida = os.path.join(p["cache"], "saida")
        os.makedirs(saida, exist_ok=True)
        ranking.to_csv(os.path.join(saida, "ranking.csv"), index=False, sep=";")
        setores.drop(columns="geojson").to_csv(os.path.join(saida, "setor.csv"), index=False, sep=";")
        pts.to_csv(os.path.join(saida, "academia_ponto.csv"), index=False, sep=";")
        json.dump(resumo, open(os.path.join(saida, "resumo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    else:
        gravar(conn, cod, ranking, setores, pts, resumo)
        conn.close()
    t_fim = time.time()
    tempos = {"ibge_s": round(t_baixar - t0, 1), "carga_s": round(t_carga - t_baixar, 1), "geocod_s": round(t_geo - t_carga, 1),
              "indicadores_s": round(t_ind - t_geo, 1), "gravar_s": round(t_fim - t_ind, 1), "total_s": round(t_fim - t0, 1),
              "memoria_pico_mb": memoria_pico_mb()}
    log(f"{cod}: pronto | pop {res['pop_setores']} (rateada {res['pop_rateada']}) | concorrencia {res['concorrencia']} | {tempos}")
    for esc in ["ibge", "popular"]:
        top = ranking[(ranking["escala"] == esc) & ranking["elegivel"]].sort_values("posicao").head(3)
        if len(top):
            log(f"  top 3 {esc}: " + "; ".join(f"{n} ({v:.1f})" for n, v in zip(top["unidade_nome"], top["nota_final"])))
    return ranking, resumo, tempos


def main():
    ap = argparse.ArgumentParser(description="Ranking de bairros de um municipio (bairros sob demanda)")
    ap.add_argument("--municipio", required=True, help="codigo IBGE de 7 digitos")
    ap.add_argument("--sem-banco", action="store_true", help="grava CSVs locais em vez do banco")
    a = ap.parse_args()
    cod = a.municipio.strip()
    if not (len(cod) == 7 and cod.isdigit() and cod[:2] in C.UFS):
        print(f"codigo de municipio invalido: {cod!r}", file=sys.stderr)
        sys.exit(2)
    try:
        processar(cod, a.sem_banco)
    except Exception as exc:
        print(f"ERRO {cod}: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
