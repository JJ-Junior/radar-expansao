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
# RADAR DE EXPANSAO - INFRA: DISPARADOR HTTP INTERNO DO CONTAINER radar-etl
# =============================================================================
#
# OBJETIVO: deixar o n8n disparar os scripts Python (cenario A) com um no
#           HTTP Request, sem expor nada para fora da rede Docker.
# ENTRADA:  POST /rodar/cenario-a  -> carga incremental da bronze + transformacao
#           POST /rodar/transformar -> so a transformacao (cenario B, que ja
#                                      esta com a trava de carga do banco)
#           GET  /saude             -> livre | ocupado (sem token)
#           Os POST exigem o header X-Radar-Token igual a RADAR_ETL_TOKEN.
# SAIDA:    JSON com status, duracao, codigo de saida de cada etapa, resumo de
#           bronze.execucao da rodada e o fim da saida dos scripts.
#           HTTP 200 sucesso | 409 ocupado ou trava | 500 erro | 401 token.
#           Log completo de cada execucao em /logs (as ultimas MAX_LOGS).
#
# TRAVAS (nada roda em dobro):
#   1. trava local: um job por vez neste container (o segundo recebe 409 na hora)
#   2. trava do banco (bronze.trava_carga), a mesma do cenario B:
#      - a carga incremental pega e solta a trava sozinha
#      - no cenario A, a transformacao roda com a trava pega de novo aqui
#      - /rodar/transformar so roda se a trava estiver com o cenario B ('n8n')
#
# So biblioteca padrao + o codigo do projeto montado em /app.
# COMO RODAR: python disparador.py   (dentro do container; ver compose.yml)
# =============================================================================

# ============================== CONFIG ==============================
PORTA = 9000
DIR_APP = "/app"                       # codigo do projeto (somente leitura)
DIR_LOGS = "/logs"                     # um arquivo por execucao
MAX_LOGS = 60                          # quantos logs de execucao guardar
TIMEOUT_ETAPA_SEGUNDOS = 30 * 60       # cada script tem ate 30 min
LINHAS_SAIDA_RESPOSTA = 40             # fim da saida que volta no JSON
ORIGEM_CENARIO_B = "n8n"
CMD_CARGA = ["python", "-m", "src.ingestao.carga_incremental", "--disparado-por", "agenda_n8n"]
CMD_TRANSFORMAR = ["python", "-m", "src.transformacao.executar"]
# ====================================================================

import hmac
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, DIR_APP)
from src.ingestao.comum import conectar, pegar_trava, soltar_trava  # noqa: E402

TOKEN = os.environ.get("RADAR_ETL_TOKEN", "")
TRAVA_LOCAL = threading.Lock()


def agora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def registrar(msg: str) -> None:
    """Linha curta no docker logs."""
    print(f"{agora()} {msg}", flush=True)


def commit_do_codigo() -> str:
    """Commit do clone montado em /app (sem precisar do git no container)."""
    git = Path(DIR_APP, ".git")
    try:
        head = (git / "HEAD").read_text().strip()
        if not head.startswith("ref: "):
            return head[:12]
        ref = head[5:]
        arquivo = git / ref
        if arquivo.exists():
            return arquivo.read_text().strip()[:12]
        for linha in (git / "packed-refs").read_text().splitlines():
            if linha.endswith(" " + ref):
                return linha.split()[0][:12]
    except OSError:
        pass
    return "desconhecido"


def rodar_etapa(cmd: list, log) -> dict:
    """Roda um script do projeto e devolve codigo de saida, duracao e saida."""
    inicio = time.monotonic()
    log.write(f"\n===== {agora()} $ {' '.join(cmd)}\n")
    try:
        proc = subprocess.run(
            cmd, cwd=DIR_APP, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=TIMEOUT_ETAPA_SEGUNDOS,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        codigo, saida = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as erro:
        codigo = -1
        partes = [p.decode("utf-8", "replace") if isinstance(p, bytes) else (p or "")
                  for p in (erro.stdout, erro.stderr)]
        saida = "".join(partes) + f"\nTEMPO ESGOTADO ({TIMEOUT_ETAPA_SEGUNDOS} s)"
    log.write(saida)
    log.write(f"\n===== codigo de saida {codigo}\n")
    return {"comando": " ".join(cmd[2:3]), "codigo_saida": codigo,
            "duracao_s": round(time.monotonic() - inicio, 1), "_saida": saida}


def resumo_bronze(desde: datetime) -> list:
    """Linhas de bronze.execucao gravadas pelo cenario A desde o inicio deste disparo."""
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT recurso, status, respostas_novas
                     FROM bronze.execucao
                    WHERE origem_carga = 'python' AND iniciado_em >= %s
                    ORDER BY execucao_id""",
                (desde,),
            )
            return [{"recurso": r, "status": s, "respostas_novas": n} for r, s, n in cur.fetchall()]
    finally:
        conn.close()


def trava_do_banco_com(origem: str) -> bool:
    """True se a trava de carga do banco esta com a origem dada (e nao expirou)."""
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT em_uso_por = %s AND desde >= now() - interval '2 hours'
                     FROM bronze.trava_carga WHERE trava_id = 1""",
                (origem,),
            )
            linha = cur.fetchone()
            return bool(linha and linha[0])
    finally:
        conn.close()


def job_cenario_a(log) -> tuple[int, dict]:
    inicio = datetime.now().astimezone()
    etapas = [rodar_etapa(CMD_CARGA, log)]
    bronze = resumo_bronze(inicio)
    corpo = {"bronze": bronze}
    if etapas[0]["codigo_saida"] != 0:
        return 500, {**corpo, "status": "erro", "etapas": etapas, "motivo": "carga incremental falhou"}
    if any(b["status"] == "ignorada_trava" for b in bronze):
        return 409, {**corpo, "status": "ignorada_trava", "etapas": etapas,
                     "motivo": "outra carga esta com a trava do banco"}
    corpo["resultado_carga"] = ("sem_novidade" if bronze and all(b["status"] == "sem_novidade" for b in bronze)
                                else "com_novidade")

    # a transformacao roda com a trava do banco: o cenario B nao comeca a gravar no meio
    conn = conectar()
    rodada_id = str(uuid.uuid4())
    try:
        if not pegar_trava(conn, rodada_id):
            return 409, {**corpo, "status": "ignorada_trava", "etapas": etapas,
                         "motivo": "trava do banco ocupada antes da transformacao"}
        try:
            etapas.append(rodar_etapa(CMD_TRANSFORMAR, log))
        finally:
            soltar_trava(conn, rodada_id)
    finally:
        conn.close()
    if etapas[1]["codigo_saida"] != 0:
        return 500, {**corpo, "status": "erro", "etapas": etapas, "motivo": "transformacao falhou"}
    return 200, {**corpo, "status": "sucesso", "etapas": etapas}


def job_transformar(log) -> tuple[int, dict]:
    if not trava_do_banco_com(ORIGEM_CENARIO_B):
        return 409, {"status": "sem_trava",
                     "motivo": "o cenario B precisa pegar a trava do banco antes de chamar a transformacao"}
    etapa = rodar_etapa(CMD_TRANSFORMAR, log)
    if etapa["codigo_saida"] != 0:
        return 500, {"status": "erro", "etapas": [etapa], "motivo": "transformacao falhou"}
    return 200, {"status": "sucesso", "etapas": [etapa]}


JOBS = {"/rodar/cenario-a": ("cenario-a", job_cenario_a),
        "/rodar/transformar": ("transformar", job_transformar)}


def limpar_logs_antigos() -> None:
    arquivos = sorted(Path(DIR_LOGS).glob("*.log"))
    for velho in arquivos[:-MAX_LOGS]:
        velho.unlink(missing_ok=True)


def executar_job(nome: str, funcao) -> tuple[int, dict]:
    if not TRAVA_LOCAL.acquire(blocking=False):
        return 409, {"job": nome, "status": "ocupado", "motivo": "ja existe um job rodando neste container"}
    inicio = time.monotonic()
    caminho_log = Path(DIR_LOGS, f"{datetime.now():%Y%m%d-%H%M%S}-{nome}.log")
    try:
        registrar(f"job {nome} iniciado (log {caminho_log.name})")
        with open(caminho_log, "w", encoding="utf-8") as log:
            try:
                codigo_http, corpo = funcao(log)
            except Exception as erro:  # erro do proprio disparador (ex.: banco fora)
                log.write(f"\nERRO DO DISPARADOR: {erro!r}\n")
                codigo_http, corpo = 500, {"status": "erro", "motivo": f"erro no disparador: {type(erro).__name__}"}
        saida = "".join(e.pop("_saida", "") for e in corpo.get("etapas", []))
        corpo = {"job": nome, **corpo, "duracao_s": round(time.monotonic() - inicio, 1),
                 "commit": commit_do_codigo(), "log": caminho_log.name,
                 "saida_final": saida.strip().splitlines()[-LINHAS_SAIDA_RESPOSTA:]}
        registrar(f"job {nome} terminou: {corpo['status']} (HTTP {codigo_http}, {corpo['duracao_s']} s)")
        limpar_logs_antigos()
        return codigo_http, corpo
    finally:
        TRAVA_LOCAL.release()


class Disparador(BaseHTTPRequestHandler):
    server_version = "radar-etl"
    sys_version = ""

    def responder(self, codigo: int, corpo: dict) -> None:
        dados = json.dumps(corpo, ensure_ascii=False, indent=1).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        if self.path == "/saude":
            self.responder(200, {"status": "ocupado" if TRAVA_LOCAL.locked() else "livre",
                                 "commit": commit_do_codigo()})
        else:
            self.responder(404, {"status": "nao_encontrado"})

    def do_POST(self):
        if self.path not in JOBS:
            self.responder(404, {"status": "nao_encontrado"})
            return
        enviado = self.headers.get("X-Radar-Token", "")
        if not TOKEN or not hmac.compare_digest(enviado.encode(), TOKEN.encode()):
            self.responder(401, {"status": "nao_autorizado"})
            return
        self.responder(*executar_job(*JOBS[self.path]))

    def log_message(self, formato, *args):  # access log curto, sem cabecalhos
        if self.path == "/saude" and self.client_address[0] == "127.0.0.1":
            return  # healthcheck do proprio container: nao polui o log
        registrar(f"{self.address_string()} {formato % args}")


if __name__ == "__main__":
    if not TOKEN:
        sys.exit("RADAR_ETL_TOKEN ausente: defina no .env.")
    Path(DIR_LOGS).mkdir(parents=True, exist_ok=True)
    registrar(f"disparador ouvindo na porta {PORTA} (commit {commit_do_codigo()})")
    ThreadingHTTPServer(("0.0.0.0", PORTA), Disparador).serve_forever()
