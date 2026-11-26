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
# RADAR DE EXPANSAO - ETAPAS 4 E 5: SILVER E GOLD (EXECUCAO DA TRANSFORMACAO)
# =============================================================================
#
# OBJETIVO: transformar a bronze em silver (silver.atualizar()) e a silver em
#           gold (gold.atualizar()) - o mesmo caminho usado pelos dois cenarios de
#           ingestao - e rodar os testes de qualidade de cada camada.
# ENTRADA:  bronze.api_resposta (resposta mais recente de cada recurso e lote)
# SAIDA:    silver.dim_* e silver.fato_* (UPSERT: acrescenta o novo e atualiza o
#           que mudou) e gold.* (SUBSTITUI: a gold e recalculada inteira)
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
#   4. testes de qualidade como view (silver/gold.vw_testes_qualidade) -> esperado
#      x obtido; o script termina com erro (exit 1) se algum teste falhar
#   5. percentil com empates e winsorizacao (gold) -> notas 0-100 justas mesmo com
#      muitos valores iguais ou extremos; ver sql/gold/02_atualizar_gold.sql
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: python -m src.transformacao.executar                  (silver + gold)
#             python -m src.transformacao.executar --camadas gold    (so a gold)
#             python -m src.transformacao.executar --origem python   (compara cenarios)
#
# =============================================================================

# ============================== CONFIG ==============================
ORIGEM_CARGA_SILVER = "qualquer"        # 'qualquer' | 'python' | 'n8n'
POPULACAO_MINIMA_UNIVERSO = 50_000      # universo do ranking (prd.md, secao 4)
CAMADAS = ["silver", "gold"]            # ordem de execucao
RODAR_TESTES = True
# ====================================================================

import argparse
import logging
import sys
import time

from src.ingestao.comum import conectar, configurar_log

log = logging.getLogger("radar.transformacao")


def atualizar_camada(conn, camada: str, parametro) -> None:
    """Chama <camada>.atualizar() numa transacao e mostra as linhas gravadas por tabela."""
    inicio = time.monotonic()
    with conn:  # commit no fim; rollback se der erro
        with conn.cursor() as cur:
            cur.execute(f"SELECT tabela, linhas_gravadas FROM {camada}.atualizar(%s)", (parametro,))
            resultado = cur.fetchall()
            if camada == "gold":
                cur.execute("NOTIFY pgrst, 'reload schema'")  # a API REST rele o schema
    print(f"\n{'tabela':<34} {'linhas gravadas':>16}")
    for tabela, linhas in resultado:
        print(f"{tabela:<34} {linhas:>16}")
    log.info("%s atualizada em %.1f s", camada, time.monotonic() - inicio)


def rodar_testes(conn, camada: str) -> bool:
    """Roda <camada>.vw_testes_qualidade e devolve True se todos passaram."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT ordem, teste, esperado, obtido, ok FROM {camada}.vw_testes_qualidade")
        testes = cur.fetchall()
    print(f"\nTestes da {camada}")
    print(f"{'#':>2} {'teste':<62} {'esperado':>9} {'obtido':>9}  resultado")
    for ordem, teste, esperado, obtido, ok in testes:
        print(f"{ordem:>2} {teste:<62} {str(esperado):>9} {str(obtido):>9}  {'ok' if ok else 'FALHOU'}")
    return all(ok for *_, ok in testes)


def imprimir_resumo_gold(conn) -> None:
    """Mostra as 5 unidades recomendadas, o top 10 e o semaforo mais recente."""
    with conn.cursor() as cur:
        cur.execute("""SELECT ordem_recomendacao, municipio_nome, uf_sigla, regiao_imediata_nome,
                              nota_final, posicao_brasil
                         FROM gold.ranking_expansao WHERE recomendado_top5 ORDER BY ordem_recomendacao""")
        print("\n5 unidades recomendadas (uma por regiao imediata)")
        for ordem, nome, uf, imediata, nota, posicao in cur.fetchall():
            print(f"  {ordem}. {nome}/{uf} - nota {nota} (posicao {posicao}; regiao imediata {imediata})")
        cur.execute("""SELECT posicao_brasil, municipio_nome, uf_sigla, nota_final
                         FROM gold.ranking_expansao ORDER BY posicao_brasil LIMIT 10""")
        print("\nTop 10 do ranking")
        for posicao, nome, uf, nota in cur.fetchall():
            print(f"  {posicao:>2}. {nome}/{uf} - {nota}")
        cur.execute("""SELECT to_char(mes, 'MM/YYYY'), recomendacao, justificativa
                         FROM gold.momento_expansao ORDER BY mes DESC LIMIT 1""")
        linha = cur.fetchone()
        if linha:
            print(f"\nMomento ({linha[0]}): {linha[1]}\n  {linha[2]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Transforma bronze -> silver -> gold e roda os testes.")
    parser.add_argument("--camadas", nargs="+", choices=CAMADAS, default=CAMADAS)
    parser.add_argument("--origem", choices=["qualquer", "python", "n8n"], default=ORIGEM_CARGA_SILVER)
    parser.add_argument("--sem-testes", action="store_true")
    args = parser.parse_args()
    configurar_log()

    conn = conectar()
    conn.autocommit = False
    try:
        for camada in CAMADAS:
            if camada not in args.camadas:
                continue
            parametro = args.origem if camada == "silver" else POPULACAO_MINIMA_UNIVERSO
            atualizar_camada(conn, camada, parametro)
            if RODAR_TESTES and not args.sem_testes and not rodar_testes(conn, camada):
                log.error("Algum teste de qualidade da %s falhou.", camada)
                sys.exit(1)
        if "gold" in args.camadas:
            imprimir_resumo_gold(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
