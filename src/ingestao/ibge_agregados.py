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
# RADAR DE EXPANSAO - ETAPA 3: CAMADA BRONZE (IBGE AGREGADOS)
# =============================================================================
#
# OBJETIVO: baixar os indicadores municipais e o IPCA da API de Agregados v3 do
#           IBGE em lotes (um ano por chamada) e guardar cada resposta inteira
#           na bronze. No modo incremental, so busca periodos novos ou
#           modificados, comparando o /periodos com o que ja esta salvo.
# ENTRADA:  API IBGE /api/v3/agregados (6579, 4714, 10295, 5938, 7060, 9509, 9418)
# SAIDA:    bronze.api_resposta (acrescenta; resposta igual a ja salva nao entra)
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - requests com parametros na URL e leitura de JSON
#   - dicionarios e listas; datas com datetime
#
# NOVIDADES:
#   1. limite de volume da API -> o IBGE derruba (HTTP 500) chamadas com mais de
#      ~100 mil valores; o script estima periodos x variaveis x localidades e
#      divide em lotes (por ano e, se ainda passar, por UF)
#   2. /periodos + modificacao -> carga incremental: o IBGE informa a data em que
#      cada periodo foi publicado ou revisado; so baixamos o que e novo ou mudou
#   3. lote mensal agrupado por ano -> o IPCA (AAAAMM) vira um lote por ano;
#      quando sai um mes novo, o ano inteiro e baixado de novo
#   4. classificacao=315[7169] -> pega so uma categoria (o indice geral do IPCA)
#      em vez das centenas de subitens
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: python -m src.ingestao.ibge_agregados --modo inicial
#             python -m src.ingestao.ibge_agregados --modo incremental
#
# =============================================================================

# ============================== CONFIG ==============================
BASE_API = "https://servicodados.ibge.gov.br/api"
LIMITE_VALORES_POR_CHAMADA = 50_000      # metade do limite pratico (~100 mil), como margem
MUNICIPIOS_ESTIMADOS = 5_571
UFS = [11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27, 28, 29,
       31, 32, 33, 35, 41, 42, 43, 50, 51, 52, 53]
TIMEOUT_PADRAO_SEGUNDOS = 60

AGREGADOS = {
    # agregado: configuracao da chamada
    "6579": {"descricao": "Populacao residente estimada",
             "variaveis": [9324]},
    "4714": {"descricao": "Censo 2022: populacao, area e densidade",
             "variaveis": [93, 6318, 614]},
    "10295": {"descricao": "Censo 2022: rendimento domiciliar per capita",
              "variaveis": [13431],
              "classificacao": "2[6794]|86[95251]|58[95253]"},   # totais (obrigatorio)
    "5938": {"descricao": "PIB dos Municipios (mil R$)",
             "variaveis": [37],
             # componentes setoriais so existem ate 2021 (depois vem "...")
             "variaveis_extras": [498, 513, 517, 6575, 525, 543],
             "extras_ate_ano": 2021},
    "7060": {"descricao": "IPCA mensal e acumulado em 12 meses",
             "variaveis": [63, 2265],
             "classificacao": "315[7169]",                       # indice geral
             "nivel": "N1",
             "agrupar_por_ano": True},
    "9509": {"descricao": "Cadastro Central de Empresas: salario medio",
             "variaveis": [10143]},
    "9418": {"descricao": "Cadastro Central de Empresas: academias (CNAE 93.13-1)",
             "variaveis": [2585],
             "classificacao": "12762[117856]",
             "timeout": 120},                                   # chamada lenta (11-22 s)
}
# ====================================================================

import logging
from collections import defaultdict

from src.ingestao.comum import Execucao, buscar_json, data_ibge, lotes_salvos, rodar_cli

log = logging.getLogger("radar.ingestao")


def agrupar_lotes(periodos: list[dict], por_ano: bool) -> dict[str, dict]:
    """Agrupa os periodos do /periodos em lotes. Lote = o proprio periodo ou o ano (mensais)."""
    lotes: dict[str, dict] = defaultdict(lambda: {"periodos": [], "modificacao": None})
    for periodo in periodos:
        chave = periodo["id"][:4] if por_ano else periodo["id"]
        lote = lotes[chave]
        lote["periodos"].append(periodo["id"])
        modificacao = data_ibge(periodo.get("modificacao"))
        if modificacao and (lote["modificacao"] is None or modificacao > lote["modificacao"]):
            lote["modificacao"] = modificacao
    return dict(sorted(lotes.items()))


def precisa_baixar(lote: str, modificacao, salvos: dict) -> bool:
    """Incremental: baixa se o lote nunca foi salvo ou se o IBGE o modificou depois."""
    # lotes divididos por UF ficam salvos como '2024-31', '2024-35'...
    datas = [data for nome, data in salvos.items() if nome == lote or nome.startswith(f"{lote}-")]
    if not datas:
        return True
    mais_recente = max((d for d in datas if d is not None), default=None)
    return modificacao is not None and (mais_recente is None or modificacao > mais_recente)


def montar_chamadas(agregado: str, cfg: dict, lote: str, periodos: list[str]) -> list[tuple]:
    """Monta as chamadas de um lote, dividindo por UF se passar do limite de valores."""
    variaveis = list(cfg["variaveis"])
    if "variaveis_extras" in cfg and int(lote[:4]) <= cfg["extras_ate_ano"]:
        variaveis += cfg["variaveis_extras"]
    nivel = cfg.get("nivel", "N6")
    locais = MUNICIPIOS_ESTIMADOS if nivel == "N6" else 1
    estimativa = len(periodos) * len(variaveis) * locais

    caminho = (f"/v3/agregados/{agregado}/periodos/{'|'.join(periodos)}"
               f"/variaveis/{'|'.join(str(v) for v in variaveis)}")
    base = {"classificacao": cfg["classificacao"]} if "classificacao" in cfg else {}

    if estimativa <= LIMITE_VALORES_POR_CHAMADA:
        return [(lote, caminho, {"localidades": f"{nivel}[all]", **base}, variaveis)]
    log.info("  lote %s estimado em %d valores: dividindo por UF", lote, estimativa)
    return [(f"{lote}-{uf}", caminho, {"localidades": f"N6[N3[{uf}]]", **base}, variaveis)
            for uf in UFS]


def carregar_agregado(conn, rodada_id: str, modo: str, disparado_por: str,
                      agregado: str, cfg: dict) -> None:
    """Baixa um agregado em lotes e grava cada resposta na bronze."""
    recurso = f"ibge_agregado_{agregado}"
    timeout = cfg.get("timeout", TIMEOUT_PADRAO_SEGUNDOS)
    with Execucao(conn, rodada_id, recurso, modo, disparado_por) as ex:
        _, periodos, _ = buscar_json(f"{BASE_API}/v3/agregados/{agregado}/periodos", timeout=timeout)
        ex.chamadas_ok += 1
        lotes = agrupar_lotes(periodos, cfg.get("agrupar_por_ano", False))
        salvos = lotes_salvos(conn, recurso) if modo == "incremental" else {}

        for lote, info in lotes.items():
            if modo == "incremental" and not precisa_baixar(lote, info["modificacao"], salvos):
                continue
            for nome_lote, caminho, params, variaveis in montar_chamadas(
                    agregado, cfg, lote, info["periodos"]):
                try:
                    status, dados, url = buscar_json(BASE_API + caminho, params, timeout)
                except Exception as erro:  # um lote com erro nao impede os demais
                    log.error("  [%s] lote %s: %s", recurso, nome_lote, erro)
                    ex.chamadas_erro += 1
                    ex.lotes_com_erro.append(nome_lote)
                    continue
                ex.chamadas_ok += 1
                parametros = {"agregado": agregado, "periodos": info["periodos"],
                              "variaveis": variaveis, **params}
                nova = ex.gravar("IBGE", caminho, parametros, url, nome_lote, status, dados,
                                 info["modificacao"])
                log.info("  [%s] lote %s: %s", recurso, nome_lote, "gravado" if nova else "ja existia")
    if ex.lotes_com_erro:
        raise RuntimeError(f"lotes com erro: {', '.join(ex.lotes_com_erro)}")


def carregar(conn, rodada_id: str, modo: str, disparado_por: str) -> None:
    """Carrega todos os agregados do CONFIG; um agregado com erro nao impede os outros."""
    falhas = []
    for agregado, cfg in AGREGADOS.items():
        try:
            carregar_agregado(conn, rodada_id, modo, disparado_por, agregado, cfg)
        except Exception as erro:
            log.error("[ibge_agregado_%s] erro: %s", agregado, erro)
            falhas.append(agregado)
    if falhas:
        raise RuntimeError(f"agregados com erro: {', '.join(falhas)}")


if __name__ == "__main__":
    rodar_cli([carregar], "Ingestao dos agregados do IBGE na bronze.")
