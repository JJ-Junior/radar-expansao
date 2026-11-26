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
# RADAR DE EXPANSAO - ETAPA 3: CAMADA BRONZE (CRIACAO DAS TABELAS)
# =============================================================================
#
# OBJETIVO: executar, na ordem, os arquivos .sql de sql/bronze (e, quando
#           existirem, sql/silver e sql/gold) para criar tabelas e views.
# ENTRADA:  arquivos sql/<camada>/NN_*.sql do repositorio
# SAIDA:    tabelas e views nos schemas bronze/silver/gold (os scripts sao
#           idempotentes: rodar de novo nao apaga nem duplica nada)
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - executar SQL pelo Python com psycopg2
#   - ler arquivos de texto
#
# NOVIDADES:
#   1. pathlib.Path.glob("*.sql") + sorted -> roda os arquivos na ordem 01, 02...
#   2. uma transacao por arquivo           -> se um .sql falhar, ele e desfeito
#                                              inteiro e o erro aparece na hora
#   3. argparse                            -> escolher as camadas pela linha de
#                                              comando (--camadas bronze silver)
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: python -m src.transformacao.criar_estrutura            (todas)
#             python -m src.transformacao.criar_estrutura --camadas bronze
#
# =============================================================================

# ============================== CONFIG ==============================
PASTA_SQL = "sql"
CAMADAS = ["bronze", "silver", "gold"]      # ordem de criacao
# ====================================================================

import argparse
import logging
from pathlib import Path

from src.ingestao.comum import conectar, configurar_log

log = logging.getLogger("radar.estrutura")


def executar_arquivo(conn, arquivo: Path) -> None:
    """Executa um arquivo .sql numa transacao propria."""
    sql = arquivo.read_text(encoding="utf-8")
    with conn:  # commit no fim; rollback se der erro
        with conn.cursor() as cur:
            cur.execute(sql)
    log.info("ok  %s", arquivo.as_posix())


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria tabelas e views das camadas a partir de sql/.")
    parser.add_argument("--camadas", nargs="+", choices=CAMADAS, default=CAMADAS)
    args = parser.parse_args()
    configurar_log()

    conn = conectar()
    conn.autocommit = False
    try:
        for camada in CAMADAS:
            if camada not in args.camadas:
                continue
            arquivos = sorted(Path(PASTA_SQL, camada).glob("*.sql"))
            if not arquivos:
                log.info("--  %s: nenhum arquivo .sql ainda", camada)
            for arquivo in arquivos:
                executar_arquivo(conn, arquivo)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
