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
# RADAR DE EXPANSAO - ETAPA 4: CAMADA SILVER (EXECUCAO DA TRANSFORMACAO)
# =============================================================================
#
# OBJETIVO: transformar a bronze em silver chamando a funcao SQL silver.atualizar()
#           (o mesmo caminho usado pelos dois cenarios de ingestao) e rodar os
#           testes de qualidade da silver.
# ENTRADA:  bronze.api_resposta (resposta mais recente de cada recurso e lote)
# SAIDA:    silver.dim_* e silver.fato_* (UPSERT: acrescenta o que e novo e
#           atualiza o que mudou; nao apaga nada)
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - executar SQL pelo Python e ler o resultado com fetchall()
#   - JOIN, GROUP BY e INSERT ... SELECT
#
# NOVIDADES:
#   1. regra de negocio em funcao SQL -> a transformacao mora no banco
#      (sql/silver/04_atualizar_silver.sql); Python e n8n so a chamam, entao
#      existe um unico caminho de codigo para os cenarios A e B
#   2. jsonb_array_elements / jsonb_each_text -> "achatam" o JSON aninhado do
#      IBGE em linhas de localidade + periodo + valor
#   3. DISTINCT ON + ON CONFLICT DO UPDATE -> sem duplicatas; a versao mais nova
#      da bronze vence (o IBGE revisa o PIB de anos anteriores)
#   4. testes de qualidade como view (silver.vw_testes_qualidade) -> esperado x
#      obtido; o script termina com erro (exit 1) se algum teste falhar
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: python -m src.transformacao.executar
#             python -m src.transformacao.executar --origem python   (compara cenarios)
#
# =============================================================================

# ============================== CONFIG ==============================
ORIGEM_CARGA_SILVER = "qualquer"        # 'qualquer' | 'python' | 'n8n'
RODAR_TESTES = True
# ====================================================================

import argparse
import logging
import sys
import time

from src.ingestao.comum import conectar, configurar_log

log = logging.getLogger("radar.transformacao")


def atualizar_silver(conn, origem: str) -> None:
    """Chama silver.atualizar() numa transacao e mostra as linhas gravadas por tabela."""
    inicio = time.monotonic()
    with conn:  # commit no fim; rollback se der erro
        with conn.cursor() as cur:
            cur.execute("SELECT tabela, linhas_gravadas FROM silver.atualizar(%s)", (origem,))
            resultado = cur.fetchall()
    print(f"\n{'tabela':<34} {'linhas gravadas':>16}")
    for tabela, linhas in resultado:
        print(f"{tabela:<34} {linhas:>16}")
    log.info("silver atualizada em %.1f s (origem da bronze: %s)", time.monotonic() - inicio, origem)


def rodar_testes(conn) -> bool:
    """Roda silver.vw_testes_qualidade e devolve True se todos passaram."""
    with conn.cursor() as cur:
        cur.execute("SELECT ordem, teste, esperado, obtido, ok FROM silver.vw_testes_qualidade")
        testes = cur.fetchall()
    print(f"\n{'#':>2} {'teste':<62} {'esperado':>9} {'obtido':>9}  resultado")
    for ordem, teste, esperado, obtido, ok in testes:
        print(f"{ordem:>2} {teste:<62} {esperado:>9} {obtido:>9}  {'ok' if ok else 'FALHOU'}")
    return all(ok for *_, ok in testes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Transforma a bronze em silver e roda os testes.")
    parser.add_argument("--origem", choices=["qualquer", "python", "n8n"], default=ORIGEM_CARGA_SILVER)
    parser.add_argument("--sem-testes", action="store_true")
    args = parser.parse_args()
    configurar_log()

    conn = conectar()
    conn.autocommit = False
    try:
        atualizar_silver(conn, args.origem)
        if RODAR_TESTES and not args.sem_testes and not rodar_testes(conn):
            log.error("Algum teste de qualidade da silver falhou.")
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
