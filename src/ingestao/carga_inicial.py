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
# RADAR DE EXPANSAO - ETAPA 3: CAMADA BRONZE (CARGA INICIAL)
# =============================================================================
#
# OBJETIVO: popular a bronze do zero com todo o historico das fontes: localidades
#           e agregados do IBGE e series do BCB, em lotes, sob a trava de carga.
# ENTRADA:  APIs do IBGE e do BCB (via ibge_localidades, ibge_agregados, bcb_sgs)
# SAIDA:    bronze.api_resposta e bronze.execucao (acrescenta). Rodar de novo
#           nao duplica: respostas iguais sao ignoradas pelo hash.
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - importar funcoes de outros arquivos do projeto
#
# NOVIDADES:
#   1. python -m src.ingestao.carga_inicial -> roda o modulo como pacote, a
#      partir da raiz do repositorio, para os imports "src.ingestao..." funcionarem
#   2. orquestrador                          -> este arquivo so define a ordem;
#      cada fonte fica no seu proprio script
#   3. --fonte                               -> roda so o IBGE ou so o BCB
#      (sao os jobs que o n8n dispara no cenario A)
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: python -m src.ingestao.carga_inicial
#             python -m src.ingestao.carga_inicial --fonte bcb
#
# =============================================================================

# ============================== CONFIG ==============================
MODO = "inicial"
FONTES = {
    # fonte: modulos, na ordem de execucao
    "ibge": ["ibge_localidades", "ibge_agregados"],
    "bcb": ["bcb_sgs"],
}
# ====================================================================

import argparse
import importlib
import sys

from src.ingestao.comum import configurar_log, executar_rodada


def etapas_das_fontes(fontes: list[str]) -> list:
    """Devolve as funcoes carregar() dos modulos das fontes escolhidas."""
    return [importlib.import_module(f"src.ingestao.{modulo}").carregar
            for fonte in fontes for modulo in FONTES[fonte]]


def main(modo: str = MODO) -> None:
    parser = argparse.ArgumentParser(description=f"Carga {modo} da bronze.")
    parser.add_argument("--fonte", nargs="+", choices=list(FONTES), default=list(FONTES))
    parser.add_argument("--disparado-por", choices=["manual", "agenda_n8n"], default="manual")
    args = parser.parse_args()
    configurar_log()
    sys.exit(executar_rodada(modo, etapas_das_fontes(args.fonte), args.disparado_por))


if __name__ == "__main__":
    main()
