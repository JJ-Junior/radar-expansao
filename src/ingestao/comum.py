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
# RADAR DE EXPANSAO - ETAPA 3: CAMADA BRONZE (FUNCOES COMUNS DA INGESTAO)
# =============================================================================
#
# OBJETIVO: reunir o que todos os scripts de ingestao usam: conexao com o banco
#           pelo .env, GET com tentativas, gravacao na bronze sem duplicar,
#           log de execucao e trava contra cargas simultaneas.
# ENTRADA:  variaveis DB_* do .env; respostas HTTP das APIs do IBGE e do BCB
# SAIDA:    bronze.api_resposta (acrescenta), bronze.execucao (acrescenta e
#           fecha a linha da execucao), bronze.trava_carga (pega e solta)
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - requests.get com timeout e try/except
#   - conexao com Postgres e INSERT com parametros (%s)
#   - variaveis de ambiente com python-dotenv
#
# NOVIDADES:
#   1. requests.Session()           -> reaproveita a conexao HTTP entre chamadas
#   2. backoff exponencial          -> espera 2 s, 4 s, 8 s entre as tentativas
#   3. psycopg2.extras.Json         -> envia um dict/list do Python como jsonb
#   4. ON CONFLICT ... DO NOTHING   -> idempotencia: a mesma resposta nao entra 2x
#   5. classe com __enter__/__exit__ -> "with Execucao(...)" abre e fecha o log
#      da execucao sozinho, inclusive quando da erro
#   6. UPDATE ... RETURNING         -> pega a trava de forma atomica
#   7. aceitar_sem_conteudo         -> 404/304 do BCB nao sao erro de rede: quem
#      chamou decide o que fazer (nada novo / tentar outra URL)
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: nao roda sozinho; e importado pelos outros scripts de src/ingestao
#
# =============================================================================

# ============================== CONFIG ==============================
ORIGEM_CARGA = "python"                 # cenario A (o cenario B grava 'n8n')
TIMEOUT_PADRAO_SEGUNDOS = 60
TENTATIVAS = 3
ESPERA_BASE_SEGUNDOS = 2                # 2 s, 4 s, 8 s
USER_AGENT = "radar-expansao/0.1 (projeto academico de engenharia de dados)"
TRAVA_EXPIRA_HORAS = 2                  # trava esquecida por processo morto expira
FUSO = "America/Sao_Paulo"
# ====================================================================

import argparse
import logging
import os
import sys
import time
import uuid
from datetime import date, datetime

import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extras import Json

load_dotenv()  # credenciais vem do .env, nunca do codigo

log = logging.getLogger("radar.ingestao")

_sessao = requests.Session()
_sessao.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})


class ErroAPI(Exception):
    """Falha numa chamada de API que pode ser tentada de novo (timeout, 5xx, resposta invalida)."""


class ErroDefinitivo(ErroAPI):
    """Falha que nao adianta repetir (ex.: HTTP 400)."""


# --------------------------------------------------------------------------- log
def configurar_log() -> None:
    """Log simples no terminal, com hora."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )


# --------------------------------------------------------------------------- banco
def conectar():
    """Abre a conexao com o Postgres usando as variaveis DB_* do .env (autocommit ligado)."""
    if not os.getenv("DB_USER"):
        raise RuntimeError("Variaveis do banco ausentes: crie o .env a partir do .env.example.")
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode=os.getenv("DB_SSLMODE", "prefer"),
        connect_timeout=15,
        application_name="radar-ingestao",
        options=f"-c timezone={FUSO}",
    )
    # cada resposta e gravada na hora: um erro no lote 10 nao desfaz os lotes 1 a 9
    conn.autocommit = True
    return conn


# --------------------------------------------------------------------------- HTTP
def buscar_json(url: str, params: dict | None = None,
                timeout: int = TIMEOUT_PADRAO_SEGUNDOS, aceitar_sem_conteudo: bool = False):
    """GET com tentativas e backoff. Devolve (status, dados, url_final).

    Com aceitar_sem_conteudo=True, 404 e 304 voltam como (status, None, url) para quem chamou decidir:
    no BCB, 404 significa "nada novo" e 304 vazio e um comportamento do servidor para certas URLs.
    """
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resposta = _sessao.get(url, params=params, timeout=timeout)
            if resposta.status_code in (304, 404) and aceitar_sem_conteudo:
                return resposta.status_code, None, resposta.url
            if resposta.status_code >= 500 or resposta.status_code == 429:
                raise ErroAPI(f"HTTP {resposta.status_code}")
            if resposta.status_code != 200:
                raise ErroDefinitivo(f"HTTP {resposta.status_code}: {resposta.text[:200]}")
            # o BCB pode devolver HTML com status 200 quando o codigo nao existe
            tipo = resposta.headers.get("content-type", "")
            if "json" not in tipo.lower():
                raise ErroAPI(f"content-type inesperado: {tipo or 'vazio'}")
            return resposta.status_code, resposta.json(), resposta.url
        except ErroDefinitivo:
            raise
        except (requests.Timeout, requests.ConnectionError, ErroAPI, ValueError) as erro:
            ultimo_erro = erro
            if tentativa < TENTATIVAS:
                espera = ESPERA_BASE_SEGUNDOS * 2 ** (tentativa - 1)
                log.warning("  tentativa %d/%d falhou (%s); nova tentativa em %d s",
                            tentativa, TENTATIVAS, erro, espera)
                time.sleep(espera)
    raise ErroAPI(f"falhou apos {TENTATIVAS} tentativas: {ultimo_erro}")


def data_ibge(texto: str | None) -> date | None:
    """Converte 'dd/mm/aaaa' (campo modificacao do IBGE) em date."""
    return datetime.strptime(texto, "%d/%m/%Y").date() if texto else None


# --------------------------------------------------------------------------- execucao
class Execucao:
    """Linha de bronze.execucao para um recurso. Uso: with Execucao(...) as ex: ..."""

    def __init__(self, conn, rodada_id: str, recurso: str, modo: str, disparado_por: str):
        self.conn = conn
        self.rodada_id = rodada_id
        self.recurso = recurso
        self.modo = modo
        self.disparado_por = disparado_por
        self.execucao_id = None
        self.chamadas_ok = 0
        self.chamadas_erro = 0
        self.respostas_novas = 0
        self.lotes_com_erro: list[str] = []
        self.inicio = time.monotonic()

    def __enter__(self):
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO bronze.execucao (rodada_id, origem_carga, disparado_por, modo, recurso)
                   VALUES (%s, %s, %s, %s, %s) RETURNING execucao_id""",
                (self.rodada_id, ORIGEM_CARGA, self.disparado_por, self.modo, self.recurso),
            )
            self.execucao_id = cur.fetchone()[0]
        log.info("[%s] inicio (%s)", self.recurso, self.modo)
        return self

    def __exit__(self, tipo_erro, erro, _rastro):
        if erro is not None:
            status, mensagem = "erro", f"{tipo_erro.__name__}: {erro}"[:1000]
        elif self.lotes_com_erro:
            status = "erro"
            mensagem = f"lotes com erro: {', '.join(self.lotes_com_erro)}"[:1000]
        elif self.respostas_novas > 0:
            status, mensagem = "sucesso", None
        else:
            status, mensagem = "sem_novidade", None
        with self.conn.cursor() as cur:
            cur.execute(
                """UPDATE bronze.execucao
                   SET finalizado_em = now(), status = %s, mensagem = %s,
                       chamadas_ok = %s, chamadas_erro = %s, respostas_novas = %s
                   WHERE execucao_id = %s""",
                (status, mensagem, self.chamadas_ok, self.chamadas_erro,
                 self.respostas_novas, self.execucao_id),
            )
        log.info("[%s] %s | %d chamadas ok | %d novas | %.1f s",
                 self.recurso, status, self.chamadas_ok, self.respostas_novas,
                 time.monotonic() - self.inicio)
        return False  # nao engole o erro: quem chamou decide se segue

    def gravar(self, fonte: str, endpoint: str, parametros: dict, url: str, lote: str,
               http_status: int, payload, modificacao: date | None = None) -> bool:
        """Grava a resposta como veio. Devolve True se era nova; False se ja existia (mesmo hash)."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO bronze.api_resposta
                       (origem_carga, fonte, recurso, endpoint, parametros, url, lote,
                        modificacao_fonte, http_status, payload, execucao_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT ON CONSTRAINT uq_api_resposta DO NOTHING
                   RETURNING resposta_id""",
                (ORIGEM_CARGA, fonte, self.recurso, endpoint, Json(parametros), url, lote,
                 modificacao, http_status, Json(payload), self.execucao_id),
            )
            nova = cur.fetchone() is not None
        if nova:
            self.respostas_novas += 1
        return nova


# --------------------------------------------------------------------------- consultas
def lotes_salvos(conn, recurso: str) -> dict[str, date | None]:
    """Lotes ja gravados por este processo para o recurso, com a maior data de modificacao."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT lote, modificacao_fonte FROM bronze.vw_ultimo_periodo
               WHERE origem_carga = %s AND recurso = %s""",
            (ORIGEM_CARGA, recurso),
        )
        return dict(cur.fetchall())


def ultima_data_salva(conn, recurso: str) -> date | None:
    """Maior data ja gravada de uma serie do BCB por este processo."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT max(ultima_data) FROM bronze.vw_ultimo_periodo
               WHERE origem_carga = %s AND recurso = %s""",
            (ORIGEM_CARGA, recurso),
        )
        return cur.fetchone()[0]


# --------------------------------------------------------------------------- trava
def pegar_trava(conn, rodada_id: str) -> bool:
    """Tenta pegar a trava de carga. False se outra carga estiver rodando."""
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE bronze.trava_carga
               SET em_uso_por = %s, rodada_id = %s, desde = now()
               WHERE trava_id = 1
                 AND (em_uso_por IS NULL OR desde < now() - make_interval(hours => %s))
               RETURNING trava_id""",
            (ORIGEM_CARGA, rodada_id, TRAVA_EXPIRA_HORAS),
        )
        return cur.fetchone() is not None


def soltar_trava(conn, rodada_id: str) -> None:
    """Solta a trava, se ela ainda for desta rodada."""
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE bronze.trava_carga SET em_uso_por = NULL, rodada_id = NULL, desde = NULL
               WHERE trava_id = 1 AND rodada_id = %s""",
            (rodada_id,),
        )


# --------------------------------------------------------------------------- rodada
def executar_rodada(modo: str, etapas: list, disparado_por: str = "manual") -> int:
    """Roda as etapas (funcoes carregar) sob a trava. Devolve 0 se tudo ok, 1 se houve erro."""
    conn = conectar()
    rodada_id = str(uuid.uuid4())
    if not pegar_trava(conn, rodada_id):
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO bronze.execucao (rodada_id, origem_carga, disparado_por, modo, recurso,
                                                finalizado_em, status, mensagem)
                   VALUES (%s, %s, %s, %s, 'rodada', now(), 'ignorada_trava',
                           'outra carga esta em andamento')""",
                (rodada_id, ORIGEM_CARGA, disparado_por, modo),
            )
        log.warning("Outra carga esta em andamento: rodada ignorada.")
        conn.close()
        return 0

    log.info("Rodada %s (%s) iniciada", rodada_id, modo)
    houve_erro = False
    try:
        for etapa in etapas:
            try:
                etapa(conn, rodada_id, modo, disparado_por)
            except Exception:  # uma fonte com erro nao impede as outras
                houve_erro = True
                log.exception("Etapa %s falhou", etapa.__module__)
    finally:
        soltar_trava(conn, rodada_id)
        imprimir_resumo(conn, rodada_id)
        conn.close()
    return 1 if houve_erro else 0


def imprimir_resumo(conn, rodada_id: str) -> None:
    """Mostra no terminal o resultado de cada recurso da rodada."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT recurso, status, chamadas_ok, chamadas_erro, respostas_novas,
                      round(extract(epoch FROM finalizado_em - iniciado_em)::numeric, 1)
               FROM bronze.execucao WHERE rodada_id = %s ORDER BY execucao_id""",
            (rodada_id,),
        )
        linhas = cur.fetchall()
    print("\n{:<24} {:<13} {:>8} {:>6} {:>7} {:>8}".format(
        "recurso", "status", "chamadas", "erros", "novas", "seg"))
    for recurso, status, ok, erros, novas, segundos in linhas:
        print(f"{recurso:<24} {status:<13} {ok:>8} {erros:>6} {novas:>7} {segundos or 0:>8}")


def rodar_cli(etapas: list, descricao: str, modo_fixo: str | None = None) -> None:
    """Ponto de entrada de linha de comando comum aos scripts de ingestao."""
    parser = argparse.ArgumentParser(description=descricao)
    if modo_fixo is None:
        parser.add_argument("--modo", choices=["inicial", "incremental"], default="incremental")
    parser.add_argument("--disparado-por", choices=["manual", "agenda_n8n"], default="manual")
    args = parser.parse_args()
    configurar_log()
    modo = modo_fixo or args.modo
    sys.exit(executar_rodada(modo, etapas, args.disparado_por))
