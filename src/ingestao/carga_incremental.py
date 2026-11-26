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
# RADAR DE EXPANSAO - ETAPA 3: CAMADA BRONZE (CARGA INCREMENTAL)
# =============================================================================
#
# OBJETIVO: buscar so o que e novo nas fontes: periodos do IBGE novos ou
#           modificados (pelo /periodos) e dados do BCB a partir da ultima data
#           salva. E o que o n8n dispara toda semana no cenario A.
# ENTRADA:  APIs do IBGE e do BCB + bronze.vw_ultimo_periodo (o que ja foi salvo)
# SAIDA:    bronze.api_resposta e bronze.execucao (acrescenta). Sem dado novo, a
#           execucao termina como "sem_novidade" e nada e gravado.
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - reaproveitar funcoes de outro modulo com import
#
# NOVIDADES:
#   1. carga incremental        -> compara a fonte com o ultimo periodo salvo
#      (bronze.vw_ultimo_periodo) em vez de baixar tudo de novo
#   2. codigo de saida (exit 0/1) -> o n8n sabe se a carga deu erro pelo codigo
#      de retorno do processo
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: python -m src.ingestao.carga_incremental
#             python -m src.ingestao.carga_incremental --fonte ibge --disparado-por agenda_n8n
#
# =============================================================================

# ============================== CONFIG ==============================
MODO = "incremental"
# fontes e ordem: as mesmas da carga inicial (src/ingestao/carga_inicial.py)
# ====================================================================

from src.ingestao.carga_inicial import main

if __name__ == "__main__":
    main(MODO)
