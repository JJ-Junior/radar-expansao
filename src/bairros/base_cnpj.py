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
# RADAR DE EXPANSAO - BAIRROS SOB DEMANDA: BASE NACIONAL DE ACADEMIAS (CNPJ)
# =============================================================================
#
# OBJETIVO: montar a base mensal de academias do Brasil a partir dos dados
#           abertos do CNPJ (Receita Federal) e carregar em bairros.academia.
# ENTRADA:  Estabelecimentos0..9.zip e Municipios.zip da Receita (pasta publica,
#           mes em CNPJ_MES); lista de municipios do IBGE (API de localidades)
# SAIDA:    --baixar   -> <DIR_DADOS>/base/academias_brasil.csv (so ativas com
#                         CNAE 93.13-1 principal/secundaria ou 85.91-1)
#           --carregar -> bairros.academia (troca a base inteira numa transacao)
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - ler CSV com o modulo csv
#   - gravar no Postgres com psycopg2 (src.ingestao.comum.conectar)
#
# NOVIDADES:
#   1. download em fluxo com retomada (HTTP Range): cada zip (ate 2,3 GB) e
#      baixado, filtrado e apagado antes do proximo
#   2. de-para do codigo de municipio da Receita para o codigo do IBGE pelo
#      nome normalizado + UF
#
# LGPD: nao grava nome fantasia, razao social, telefone, e-mail nem socios.
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: python -I src/bairros/base_cnpj.py --baixar      (~5,5 GB em fluxo, ~30 min)
#             python -m src.bairros.base_cnpj --carregar        (precisa do .env do banco)
# =============================================================================

# ============================== CONFIG ==============================
ARQUIVOS = [f"Estabelecimentos{i}.zip" for i in range(10)]
NOME_SAIDA = "academias_brasil.csv"
COLUNAS = ["cnpj", "cnae_principal", "academia_principal", "academia_secundaria", "ensino_esportes_8591",
           "situacao", "data_inicio", "tipo_logradouro", "logradouro", "numero", "bairro", "cep", "uf",
           "municipio_receita", "cod_municipio", "data_referencia"]
# nomes que a Receita grafa diferente do IBGE (normalizados, UF + nome Receita -> nome IBGE)
GRAFIAS = {("RR", "SAO LUIZ"): "SAO LUIZ DO ANAUA", ("RN", "ARES"): "AREZ", ("TO", "FORTALEZA DO TABOCAO"): "TABOCAO",
           ("TO", "SAO VALERIO DA NATIVIDADE"): "SAO VALERIO", ("RN", "BOA SAUDE"): "JANUARIO CICCO"}
SEMELHANCA_NOME_MIN = 0.8   # aproximacao de nome (difflib) para o que nao casou exato
# ====================================================================

import argparse
import base64
import csv
import difflib
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
import zipfile

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.bairros import config as C  # noqa: E402

WEBDAV = "https://arquivos.receitafederal.gov.br/public.php/webdav/Dados/Cadastros/CNPJ/" + C.CNPJ_MES + "/"
AUTH = "Basic " + base64.b64encode((C.CNPJ_COMPARTILHAMENTO + ":").encode()).decode()


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S ") + msg, flush=True)


def norm(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]", " ", t)).strip()


def requisitar(url, headers=None, metodo="GET", timeout=300):
    req = urllib.request.Request(url, headers={"Authorization": AUTH, **(headers or {})}, method=metodo)
    return urllib.request.urlopen(req, timeout=timeout)


def baixar(nome, tmp):
    with requisitar(WEBDAV + nome, {"Depth": "0"}, "PROPFIND") as r:
        esperado = int(re.search(r"<d:getcontentlength>(\d+)<", r.read().decode("utf-8", "replace")).group(1))
    destino = os.path.join(tmp, nome)
    for _ in range(30):
        atual = os.path.getsize(destino) if os.path.exists(destino) else 0
        if atual == esperado:
            return destino, esperado
        if atual > esperado:
            os.remove(destino)
            atual = 0
        try:
            with requisitar(WEBDAV + nome, {"Range": f"bytes={atual}-"}) as r, open(destino, "ab") as f:
                if atual and r.status != 206:
                    raise RuntimeError(f"servidor nao retomou (HTTP {r.status})")
                while bloco := r.read(4 * 1024 * 1024):
                    f.write(bloco)
        except Exception as exc:  # rede instavel: retoma do ponto onde parou
            log(f"  {nome}: falha ({exc}); retomando em 20 s")
            time.sleep(20)
    raise RuntimeError(f"{nome}: muitas falhas de download")


def de_para_municipios(tmp):
    """(UF, codigo Receita) -> codigo IBGE, pelo nome normalizado."""
    caminho, _ = baixar("Municipios.zip", tmp)
    with zipfile.ZipFile(caminho) as z:
        receita = list(csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="latin-1"), delimiter=";"))
    req = urllib.request.Request(C.LOCALIDADES_TODOS + "?view=nivelado", headers={"User-Agent": C.USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        ibge = json.loads(r.read().decode("utf-8"))
    por_nome = {(m["UF-sigla"], norm(m["municipio-nome"])): str(m["municipio-id"]) for m in ibge}
    return {cod_rf: norm(nome) for cod_rf, nome in receita}, por_nome


def _mais_parecido(uf, nome, por_nome):
    """Codigo IBGE do municipio da UF com o nome mais parecido (difflib), se a semelhanca for alta."""
    nomes = {n: cod for (u, n), cod in por_nome.items() if u == uf}
    achado = difflib.get_close_matches(nome, list(nomes), n=1, cutoff=SEMELHANCA_NOME_MIN)
    return nomes[achado[0]] if achado else ""


def cmd_baixar():
    pasta_base = os.path.join(C.dir_dados(), "base")
    tmp = os.path.join(C.dir_dados(), "tmp", "cnpj")
    os.makedirs(pasta_base, exist_ok=True)
    os.makedirs(tmp, exist_ok=True)
    estado_path = os.path.join(tmp, "estado.json")
    estado = json.load(open(estado_path, encoding="utf-8")) if os.path.exists(estado_path) else {}
    parcial = os.path.join(tmp, "academias_sem_ibge.csv")
    if not estado:
        with open(parcial, "w", newline="", encoding="utf-8") as f:
            csv.writer(f, delimiter=";").writerow(COLUNAS[:-2])
    alvo = [C.CNAE_ACADEMIA.encode(), C.CNAE_ENSINO_ESPORTES.encode()]
    t_geral = time.time()
    for nome in ARQUIVOS:
        if estado.get(nome, {}).get("concluido"):
            log(f"{nome}: ja processado")
            continue
        t0 = time.time()
        log(f"{nome}: baixando")
        caminho, tam = baixar(nome, tmp)
        t1 = time.time()
        n = lidas = 0
        with zipfile.ZipFile(caminho) as z, open(parcial, "a", newline="", encoding="utf-8") as out:
            w = csv.writer(out, delimiter=";")
            for interno in z.namelist():
                for linha in z.open(interno):
                    lidas += 1
                    if not (alvo[0] in linha or alvo[1] in linha):  # filtro rapido em bytes
                        continue
                    c = next(csv.reader([linha.decode("latin-1")], delimiter=";"))
                    if len(c) < 21 or c[5] != "02":  # so ativas
                        continue
                    sec = set(c[12].split(","))
                    pri = c[11] == C.CNAE_ACADEMIA
                    secd = not pri and C.CNAE_ACADEMIA in sec
                    ens = C.CNAE_ENSINO_ESPORTES in ({c[11]} | sec) and not (pri or secd)
                    if not (pri or secd or ens):
                        continue
                    # sem nome fantasia (c[4]), telefones (c[21:27]) e e-mail (c[27])
                    w.writerow([c[0] + c[1] + c[2], c[11], int(pri), int(secd), int(ens), c[5], c[10],
                                c[13].strip(), c[14].strip(), c[15].strip(), c[17].strip(), c[18].strip(),
                                c[19].strip(), c[20].strip()])
                    n += 1
        os.remove(caminho)
        estado[nome] = {"linhas_brasil": lidas, "gravadas": n, "mb": round(tam / 1e6, 1),
                        "min_download": round((t1 - t0) / 60, 1), "min_filtro": round((time.time() - t1) / 60, 1),
                        "concluido": True}
        json.dump(estado, open(estado_path, "w", encoding="utf-8"), indent=2)
        log(f"{nome}: {estado[nome]}; zip apagado")

    nome_rf, por_nome = de_para_municipios(tmp)
    sem_ibge, total, aproximado = {}, 0, {}
    saida = os.path.join(pasta_base, NOME_SAIDA)
    with open(parcial, encoding="utf-8") as f, open(saida + ".parcial", "w", newline="", encoding="utf-8") as out:
        r = csv.DictReader(f, delimiter=";")
        w = csv.writer(out, delimiter=";")
        w.writerow(COLUNAS)
        for row in r:
            nome = nome_rf.get(row["municipio_receita"], "")
            cod = por_nome.get((row["uf"], GRAFIAS.get((row["uf"], nome), nome)), "")
            if not cod and nome:  # grafia diferente (ex.: PARATI x PARATY): nome mais parecido na mesma UF
                cod = aproximado.setdefault((row["uf"], nome), _mais_parecido(row["uf"], nome, por_nome))
            if not cod:
                k = (row["uf"], row["municipio_receita"], nome)
                sem_ibge[k] = sem_ibge.get(k, 0) + 1
            w.writerow([row[c] for c in COLUNAS[:-2]] + [cod, C.CNPJ_MES])
            total += 1
    os.replace(saida + ".parcial", saida)
    resumo = {"linhas": total, "sem_codigo_ibge": sum(sem_ibge.values()),
              "municipios_sem_codigo_ibge": len(sem_ibge),
              "maiores_sem_codigo": sorted(([*k, v] for k, v in sem_ibge.items()), key=lambda x: -x[3])[:30],
              "casados_por_aproximacao": sorted(f"{uf} {nome} -> {cod}" for (uf, nome), cod in aproximado.items() if cod),
              "minutos": round((time.time() - t_geral) / 60, 1), "arquivos": estado}
    json.dump(resumo, open(os.path.join(pasta_base, "academias_brasil_resumo.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    log(f"FIM: {total} linhas; {resumo['sem_codigo_ibge']} sem codigo IBGE; {saida}")


def cmd_carregar():
    from src.ingestao.comum import conectar
    caminho = C.arquivo_base()
    conn = conectar()
    with conn, conn.cursor() as cur, open(caminho, encoding="utf-8") as f:
        cur.execute("TRUNCATE bairros.academia")
        cur.copy_expert(f"COPY bairros.academia ({', '.join(COLUNAS)}) FROM STDIN "
                        "WITH (FORMAT csv, DELIMITER ';', HEADER true, NULL '')", f)
        cur.execute("SELECT count(*), count(cod_municipio) FROM bairros.academia")
        total, com_ibge = cur.fetchone()
    log(f"bairros.academia: {total} linhas ({com_ibge} com codigo IBGE)")


def main():
    ap = argparse.ArgumentParser(description="Base nacional de academias (CNPJ da Receita)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--baixar", action="store_true", help="baixa e filtra os zips (~5,5 GB em fluxo)")
    g.add_argument("--carregar", action="store_true", help="carrega o CSV em bairros.academia")
    a = ap.parse_args()
    cmd_baixar() if a.baixar else cmd_carregar()


if __name__ == "__main__":
    main()
