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
# RADAR DE EXPANSAO - INFRA: WORKER DA FILA DE BAIRROS (container radar-bairros)
# =============================================================================
#
# OBJETIVO: atender os pedidos de "bairros sob demanda", um por vez: pega o
#           pedido pendente mais antigo, roda o pipeline do municipio e marca
#           o pedido como pronto ou erro.
# ENTRADA:  bairros.pedido (status 'pendente'), gravado pela funcao
#           gold.pedir_bairros chamada pela API
# SAIDA:    bairros.pedido atualizado (processando -> pronto | erro, inicio,
#           fim, duracao_s, erro_resumo). O ranking e gravado pelo pipeline.
#           Log de cada pedido em /logs (os ultimos MAX_LOGS).
#
# CONTRATO COM O PIPELINE (src/bairros/processar.py):
#   - chamado como: python -m src.bairros.processar --municipio <codigo IBGE>
#   - grava bairros.ranking da cidade e sai com codigo 0; erro -> codigo != 0
#   - pode usar DIR_DADOS/cache (fica) e DIR_DADOS/tmp (apagado apos cada pedido)
#
# NOVIDADES:
#   1. FOR UPDATE SKIP LOCKED -> fila no proprio Postgres, sem broker
#   2. pedido "preso" em processando (container reiniciado) volta para pendente
#
# COMO RODAR: python worker.py   (dentro do container; ver compose.yml)
# =============================================================================

# ============================== CONFIG ==============================
DIR_APP = "/app"                       # codigo do projeto (somente leitura)
DIR_DADOS = "/dados"                   # cache dos arquivos do IBGE
DIR_LOGS = "/logs"
MAX_LOGS = 200
INTERVALO_SEGUNDOS = 10                # espera entre consultas a fila vazia
TIMEOUT_PEDIDO_SEGUNDOS = 45 * 60      # um municipio grande nao passa disso
TAMANHO_ERRO_RESUMO = 300              # caracteres guardados em erro_resumo
ARQUIVO_BATIMENTO = "/tmp/batimento"   # o healthcheck olha a hora deste arquivo
CMD_PIPELINE = ["python", "-m", "src.bairros.processar", "--municipio"]
# ====================================================================

import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, DIR_APP)
from src.ingestao.comum import conectar  # noqa: E402

parar = False
filho: subprocess.Popen | None = None


def registrar(msg: str) -> None:
    print(f"{datetime.now().astimezone().isoformat(timespec='seconds')} {msg}", flush=True)


def bater() -> None:
    Path(ARQUIVO_BATIMENTO).touch()


def ao_receber_sinal(signum, _frame) -> None:
    """docker stop: interrompe o pipeline; o pedido volta para a fila."""
    global parar
    parar = True
    if filho and filho.poll() is None:
        filho.terminate()


def executar(conn, sql: str, params=()) -> list:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else []


def devolver_presos(conn) -> None:
    """Um worker so: o que estiver 'processando' na partida ficou preso."""
    linhas = executar(conn, """UPDATE bairros.pedido SET status = 'pendente', inicio = NULL
                                WHERE status = 'processando' RETURNING id""")
    if linhas:
        registrar(f"{len(linhas)} pedido(s) preso(s) voltaram para a fila")


def pegar_pedido(conn):
    linhas = executar(conn, """
        UPDATE bairros.pedido SET status = 'processando', inicio = now()
         WHERE id = (SELECT id FROM bairros.pedido WHERE status = 'pendente'
                      ORDER BY pedido_em, id FOR UPDATE SKIP LOCKED LIMIT 1)
        RETURNING id, cod_municipio""")
    return linhas[0] if linhas else None


def resumo_erro(saida: str) -> str:
    """Ultimas linhas uteis da saida, sem nada que pareca segredo."""
    texto = " | ".join(l.strip() for l in saida.strip().splitlines()[-5:] if l.strip())
    texto = re.sub(r"(password|senha|token|key)\S*", "[omitido]", texto, flags=re.I)
    return texto[-TAMANHO_ERRO_RESUMO:] or "sem saida"


def rodar_pipeline(cod_municipio: int, caminho_log: Path) -> tuple[int, str]:
    global filho
    with open(caminho_log, "w+", encoding="utf-8") as log:
        filho = subprocess.Popen(
            CMD_PIPELINE + [str(cod_municipio)], cwd=DIR_APP, stdout=log, stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "DIR_DADOS": DIR_DADOS},
        )
        inicio = time.monotonic()
        while filho.poll() is None:  # espera batendo o coracao para o healthcheck
            bater()
            if time.monotonic() - inicio > TIMEOUT_PEDIDO_SEGUNDOS:
                filho.kill()
                filho.wait()
                log.write(f"\nTEMPO ESGOTADO ({TIMEOUT_PEDIDO_SEGUNDOS} s)\n")
                break
            time.sleep(5)
        codigo = filho.returncode if filho.returncode is not None else -1
        log.seek(0)
        return codigo, log.read()


def limpar_temporarios() -> None:
    shutil.rmtree(Path(DIR_DADOS, "tmp"), ignore_errors=True)
    for velho in sorted(Path(DIR_LOGS).glob("*.log"))[:-MAX_LOGS]:
        velho.unlink(missing_ok=True)


def atender(conn, pedido_id: int, cod_municipio: int) -> None:
    caminho_log = Path(DIR_LOGS, f"{datetime.now():%Y%m%d-%H%M%S}-{cod_municipio}.log")
    registrar(f"pedido {pedido_id} ({cod_municipio}) iniciado")
    t0 = time.monotonic()
    codigo, saida = rodar_pipeline(cod_municipio, caminho_log)
    duracao = round(time.monotonic() - t0, 1)
    if parar:  # interrompido pelo docker stop: volta para a fila
        executar(conn, "UPDATE bairros.pedido SET status = 'pendente', inicio = NULL WHERE id = %s",
                 (pedido_id,))
        registrar(f"pedido {pedido_id} interrompido; voltou para a fila")
        return
    status = "pronto" if codigo == 0 else "erro"
    executar(conn, """UPDATE bairros.pedido
                         SET status = %s, fim = now(), duracao_s = %s, erro_resumo = %s
                       WHERE id = %s""",
             (status, duracao, None if codigo == 0 else resumo_erro(saida), pedido_id))
    registrar(f"pedido {pedido_id} ({cod_municipio}) {status} em {duracao} s (log {caminho_log.name})")
    limpar_temporarios()


def main() -> None:
    signal.signal(signal.SIGTERM, ao_receber_sinal)
    signal.signal(signal.SIGINT, ao_receber_sinal)
    Path(DIR_LOGS).mkdir(parents=True, exist_ok=True)
    Path(DIR_DADOS, "cache").mkdir(parents=True, exist_ok=True)
    registrar("worker de bairros iniciado")
    conn = None
    while not parar:
        bater()
        try:
            if conn is None or conn.closed:
                conn = conectar()  # autocommit: cada UPDATE vale na hora
                devolver_presos(conn)
            pedido = pegar_pedido(conn)
            if pedido:
                atender(conn, *pedido)
                continue
        except Exception as erro:  # banco fora ou schema ainda nao criado: tenta de novo
            registrar(f"falha: {type(erro).__name__}: {str(erro).strip()[:200]}")
            if conn is not None:
                conn.close()
            conn = None
            time.sleep(30)
        time.sleep(INTERVALO_SEGUNDOS)
    registrar("worker encerrado")


if __name__ == "__main__":
    main()
