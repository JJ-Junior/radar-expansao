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
# RADAR DE EXPANSAO - ETAPA 3: CAMADA BRONZE (BANCO CENTRAL - SGS)
# =============================================================================
#
# OBJETIVO: baixar as series do Sistema Gerenciador de Series Temporais do BCB
#           (Selic meta, dolar e IPCA) e guardar cada resposta inteira na bronze.
#           Carga inicial em janelas de ate 10 anos; incremental a partir da
#           ultima data salva menos 30 dias.
# ENTRADA:  API BCB SGS /dados/serie/bcdata.sgs.{codigo}/dados
# SAIDA:    bronze.api_resposta (acrescenta; resposta igual a ja salva nao entra)
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - requests com parametros (params=...)
#   - datas com datetime e formatacao com strftime
#
# NOVIDADES:
#   1. janelas de datas    -> series diarias aceitam no maximo 10 anos por
#                             chamada; o script fatia o periodo em janelas
#   2. HTTP 404 = nada novo -> no SGS, periodo sem dado volta 404; tratamos como
#                             "sem novidade", nao como erro
#   3. margem de 30 dias   -> o incremental volta 30 dias para pegar revisoes
#                             recentes; o hash evita gravar resposta repetida
#   4. date.replace(year=...) -> soma anos a uma data sem biblioteca extra
#   5. HTTP 304 vazio      -> para algumas URLs exatas o SGS devolve 304 sem
#                             conteudo; pedimos a mesma janela com a data final
#                             1, 2 ou 3 dias depois (o filtro de datas da silver
#                             descarta o que passar de hoje)
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: python -m src.ingestao.bcb_sgs --modo inicial
#             python -m src.ingestao.bcb_sgs --modo incremental
#
# =============================================================================

# ============================== CONFIG ==============================
BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
SERIES = {
    # codigo: descricao
    "432": "Meta da Selic (% a.a., diaria)",
    "10813": "Dolar comercial - venda (R$, dias uteis)",
    "433": "IPCA mensal (%) - conferencia com o IBGE 7060",
}
DATA_INICIO = "2015-01-01"              # inicio do historico (AAAA-MM-DD)
JANELA_MAXIMA_ANOS = 10                 # limite do SGS para series diarias
MARGEM_INCREMENTAL_DIAS = 30
VARIACOES_304 = 3                       # novas datas finais tentadas quando o SGS devolve 304 vazio
TIMEOUT_SEGUNDOS = 60
# ====================================================================

import logging
from datetime import date, timedelta

from src.ingestao.comum import Execucao, buscar_json, rodar_cli, ultima_data_salva

log = logging.getLogger("radar.ingestao")


def br(dia: date) -> str:
    """Data no formato exigido pelo SGS (dd/MM/aaaa)."""
    return dia.strftime("%d/%m/%Y")


def janelas(inicio: date, fim: date) -> list[tuple[date, date]]:
    """Fatia [inicio, fim] em janelas de no maximo JANELA_MAXIMA_ANOS anos."""
    resultado = []
    atual = inicio
    while atual <= fim:
        limite = atual.replace(year=atual.year + JANELA_MAXIMA_ANOS) - timedelta(days=1)
        resultado.append((atual, min(limite, fim)))
        atual = limite + timedelta(days=1)
    return resultado


def baixar_janela(ex: Execucao, codigo: str, inicio: date, fim: date | None) -> None:
    """Faz uma chamada (com ou sem data final) e grava a resposta."""
    endpoint = f"/dados/serie/bcdata.sgs.{codigo}/dados"
    lote = f"{inicio.isoformat()}_{fim.isoformat() if fim else 'aberto'}"
    # 1a tentativa: a janela pedida; se vier 304 vazio, a data final anda 1, 2, 3 dias
    base_fim = fim or date.today()
    finais = [fim] + [base_fim + timedelta(days=d) for d in range(1, VARIACOES_304 + 1)]

    for fim_tentado in finais:
        params = {"formato": "json", "dataInicial": br(inicio)}
        if fim_tentado is not None:
            params["dataFinal"] = br(fim_tentado)
        status, dados, url = buscar_json(BASE_URL.format(codigo=codigo), params,
                                         TIMEOUT_SEGUNDOS, aceitar_sem_conteudo=True)
        ex.chamadas_ok += 1
        if status != 304:
            break
        log.warning("  [%s] %s: HTTP 304 vazio; tentando outra data final", ex.recurso, lote)
    else:
        raise RuntimeError(f"{lote}: o SGS devolveu 304 vazio em todas as variacoes")

    if status == 404 or not dados:
        log.info("  [%s] %s: nada novo", ex.recurso, lote)
        return
    nova = ex.gravar("BCB", endpoint, {"serie": codigo, **params}, url, lote, status, dados)
    log.info("  [%s] %s: %d registros, %s", ex.recurso, lote, len(dados),
             "gravado" if nova else "ja existia")


def carregar_serie(conn, rodada_id: str, modo: str, disparado_por: str, codigo: str) -> None:
    """Carga inicial em janelas; incremental a partir da ultima data salva - margem."""
    recurso = f"bcb_sgs_{codigo}"
    hoje = date.today()
    with Execucao(conn, rodada_id, recurso, modo, disparado_por) as ex:
        ultima = ultima_data_salva(conn, recurso) if modo == "incremental" else None
        if ultima is None:
            # carga inicial (ou incremental de uma serie que ainda nao tem nada salvo)
            for inicio, fim in janelas(date.fromisoformat(DATA_INICIO), hoje):
                baixar_janela(ex, codigo, inicio, fim)
        else:
            # a Selic meta tem datas futuras (vale ate o proximo Copom): parte de hoje no maximo
            inicio = min(ultima, hoje) - timedelta(days=MARGEM_INCREMENTAL_DIAS)
            baixar_janela(ex, codigo, inicio, None)


def carregar(conn, rodada_id: str, modo: str, disparado_por: str) -> None:
    """Carrega todas as series do CONFIG; uma serie com erro nao impede as outras."""
    falhas = []
    for codigo in SERIES:
        try:
            carregar_serie(conn, rodada_id, modo, disparado_por, codigo)
        except Exception as erro:
            log.error("[bcb_sgs_%s] erro: %s", codigo, erro)
            falhas.append(codigo)
    if falhas:
        raise RuntimeError(f"series com erro: {', '.join(falhas)}")


if __name__ == "__main__":
    rodar_cli([carregar], "Ingestao das series do BCB (SGS) na bronze.")
