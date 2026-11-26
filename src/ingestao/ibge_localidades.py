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
# RADAR DE EXPANSAO - ETAPA 3: CAMADA BRONZE (IBGE LOCALIDADES)
# =============================================================================
#
# OBJETIVO: baixar regioes, estados e municipios da API de Localidades do IBGE
#           e guardar cada resposta inteira na bronze (base das dimensoes).
# ENTRADA:  API IBGE /api/v1/localidades (regioes, estados, municipios nivelado)
# SAIDA:    bronze.api_resposta (acrescenta; resposta igual a ja salva nao entra)
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - chamar uma API com requests e ler o JSON
#   - laco for sobre uma lista de tuplas
#
# NOVIDADES:
#   1. view=nivelado   -> o IBGE devolve o municipio "achatado" (sem JSON
#                         aninhado), pronto para virar a dimensao de municipios
#   2. lote 'snapshot' -> recarga completa toda vez; se nada mudou, o hash e
#                         igual e a execucao fica como "sem_novidade"
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: python -m src.ingestao.ibge_localidades
#
# =============================================================================

# ============================== CONFIG ==============================
BASE_URL = "https://servicodados.ibge.gov.br/api"
RECURSOS = [
    # (recurso na bronze, endpoint, parametros)
    ("ibge_regioes", "/v1/localidades/regioes", {}),
    ("ibge_estados", "/v1/localidades/estados", {}),
    ("ibge_municipios", "/v1/localidades/municipios", {"view": "nivelado"}),
]
LOTE = "snapshot"
TIMEOUT_SEGUNDOS = 60
# ====================================================================

import logging

from src.ingestao.comum import Execucao, buscar_json, rodar_cli

log = logging.getLogger("radar.ingestao")


def carregar(conn, rodada_id: str, modo: str, disparado_por: str) -> None:
    """Baixa as tres listas de localidades (mesmo comportamento no modo inicial e incremental)."""
    falhas = []
    for recurso, endpoint, parametros in RECURSOS:
        try:
            with Execucao(conn, rodada_id, recurso, modo, disparado_por) as ex:
                status, dados, url = buscar_json(BASE_URL + endpoint, parametros, TIMEOUT_SEGUNDOS)
                ex.chamadas_ok += 1
                ex.gravar("IBGE", endpoint, parametros, url, LOTE, status, dados)
        except Exception as erro:  # registrado em bronze.execucao; segue para o proximo recurso
            log.error("[%s] erro: %s", recurso, erro)
            falhas.append(recurso)
    if falhas:
        raise RuntimeError(f"recursos com erro: {', '.join(falhas)}")


if __name__ == "__main__":
    rodar_cli([carregar], "Ingestao das localidades do IBGE na bronze.")
