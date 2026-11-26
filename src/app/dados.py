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
# RADAR DE EXPANSAO - ETAPA 7: DASHBOARD (CAMADA DE DADOS)
# =============================================================================
#
# OBJETIVO: unico lugar do app que busca dados. Le as 6 tabelas da camada gold
#           pela API REST do Supabase (somente leitura); se a API falhar ou
#           faltar segredo, usa a copia de contingencia em site/dados/*.json.
# ENTRADA:  API REST do Supabase, schema gold (headers apikey + Authorization +
#           Accept-Profile) ou os JSON exportados da gold em site/dados/
# SAIDA:    DataFrames em memoria (cache de 10 minutos); nao grava nada
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - requests.get com timeout, try/except e novas tentativas
#   - python-dotenv para ler o .env; pandas.DataFrame
#
# NOVIDADES:
#   1. API REST do Supabase (PostgREST) -> cada tabela vira um endereco
#      /rest/v1/<tabela>; filtros e ordem vao na URL (order=, limit=, offset=)
#   2. paginacao            -> a API devolve no maximo 1000 linhas por chamada;
#                              o laco pede de 1000 em 1000 ate acabar
#   3. st.secrets           -> segredos do Streamlit Cloud; fora dele, cai no
#                              .env (os nomes das variaveis sao os mesmos)
#   4. st.cache_data(ttl)   -> guarda o resultado por 10 minutos: trocar de
#                              pagina nao chama a API de novo
#   5. fallback             -> sem API, o app continua de pe com a copia da gold
#                              e avisa na tela de quando sao os dados
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: nao roda sozinho; e importado pelas paginas do dashboard
#             (streamlit run src/app/app.py)
#
# =============================================================================

# ============================== CONFIG ==============================
# Tabela da gold -> coluna usada na ordem (a API nao garante ordem sem ela).
TABELAS_GOLD = {
    "ranking_expansao": "posicao_brasil",
    "indicadores_municipio": "municipio_id",
    "ranking_criterio": "ordem",
    "parametro_ranking": "parametro",
    "contexto_macro": "mes",
    "momento_expansao": "mes",
}
# Tabelas que podem ainda nao existir na copia de contingencia (o app segue sem elas).
TABELAS_OPCIONAIS = {"momento_atual": "ref_cambio"}
SEGREDOS = ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_CHAVE_LEITURA")
LINHAS_POR_CHAMADA = 1000      # limite de linhas por resposta da API
TIMEOUT_SEGUNDOS = 10
TENTATIVAS = 2
VALIDADE_CACHE_SEGUNDOS = 600  # 10 minutos
# ====================================================================

import json
import os
import time
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

import formato as fmt

RAIZ = Path(__file__).resolve().parents[2]
PASTA_SNAPSHOT = RAIZ / "site" / "dados"

load_dotenv(RAIZ / ".env")  # credenciais vem do .env, nunca do codigo


def ler_segredo(nome: str) -> str:
    """Le um segredo do st.secrets (nuvem) ou da variavel de ambiente (.env)."""
    valor = ""
    try:
        if nome in st.secrets:
            valor = str(st.secrets[nome])
    except Exception:  # sem secrets.toml o Streamlit levanta erro; segue para o .env
        valor = ""
    valor = (valor or os.getenv(nome, "")).strip()
    return "" if (not valor or "<" in valor) else valor  # "<url-da-api>" e marcador


def buscar_tabela_api(tabela: str, ordem: str, url: str, cabecalhos: dict) -> pd.DataFrame:
    """Busca uma tabela inteira da gold pela API REST, de 1000 em 1000 linhas."""
    linhas: list[dict] = []
    deslocamento = 0
    while True:
        parametros = {
            "select": "*",
            "order": f"{ordem}.asc",
            "limit": LINHAS_POR_CHAMADA,
            "offset": deslocamento,
        }
        lote = None
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                resposta = requests.get(
                    f"{url}/rest/v1/{tabela}",
                    params=parametros,
                    headers=cabecalhos,
                    timeout=TIMEOUT_SEGUNDOS,
                )
                resposta.raise_for_status()
                lote = resposta.json()
                break
            except (requests.RequestException, ValueError):
                if tentativa == TENTATIVAS:
                    raise
                time.sleep(1)
        linhas.extend(lote)
        if len(lote) < LINHAS_POR_CHAMADA:
            break
        deslocamento += LINHAS_POR_CHAMADA
    if not linhas:
        raise ValueError(f"gold.{tabela} veio vazia")
    return pd.DataFrame(linhas)


def ler_json_colunar(caminho: Path) -> pd.DataFrame:
    """Le um JSON no formato {colunas, linhas} do site de apoio."""
    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    return pd.DataFrame(conteudo["linhas"], columns=conteudo["colunas"])


def ler_meta_snapshot() -> dict:
    """Le site/dados/meta.json (data da exportacao e contagem das camadas)."""
    caminho = PASTA_SNAPSHOT / "meta.json"
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}


def preparar(tabelas: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Acerta tipos vindos da API ou do JSON (texto, datas e listas)."""
    for nome in ("ranking_expansao", "indicadores_municipio"):
        df = tabelas[nome]
        df["regiao_sigla"] = df["regiao_sigla"].astype(str).str.strip()  # char(2): "N "
        df["municipio_id"] = df["municipio_id"].astype(int)
    ranking = tabelas["ranking_expansao"]
    ranking["criterios_ausentes"] = ranking["criterios_ausentes"].apply(
        lambda v: list(v) if isinstance(v, (list, tuple)) else []
    )
    for coluna in ("recomendado_top5", "dados_incompletos", "verificar_concorrencia",
                   "elegivel_recomendacao"):
        ranking[coluna] = ranking[coluna].fillna(False).astype(bool)
    for nome in ("contexto_macro", "momento_expansao"):
        tabelas[nome]["mes"] = pd.to_datetime(tabelas[nome]["mes"])
        if "mes_parcial" in tabelas[nome].columns:
            tabelas[nome]["mes_parcial"] = tabelas[nome]["mes_parcial"].fillna(False).astype(bool)
    atual = tabelas.get("momento_atual")
    if atual is not None and not atual.empty:
        for coluna in ("mes", "ref_juros", "ref_cambio", "ref_inflacao"):
            if coluna in atual.columns:
                atual[coluna] = pd.to_datetime(atual[coluna])
    tabelas["parametro_ranking"]["valor"] = pd.to_numeric(tabelas["parametro_ranking"]["valor"])
    return tabelas


@st.cache_data(ttl=VALIDADE_CACHE_SEGUNDOS, show_spinner="Lendo a camada gold...")
def carregar_gold() -> dict:
    """Devolve as 6 tabelas da gold + de onde vieram (API ou copia de contingencia)."""
    segredos = {nome: ler_segredo(nome) for nome in SEGREDOS}
    motivo = ""
    if all(segredos.values()):
        url = segredos["SUPABASE_URL"].rstrip("/")
        cabecalhos = {
            "apikey": segredos["SUPABASE_ANON_KEY"],
            "Authorization": f"Bearer {segredos['SUPABASE_CHAVE_LEITURA']}",
            "Accept-Profile": "gold",
        }
        try:
            tabelas = {t: buscar_tabela_api(t, o, url, cabecalhos) for t, o in TABELAS_GOLD.items()}
            for t, o in TABELAS_OPCIONAIS.items():
                try:
                    tabelas[t] = buscar_tabela_api(t, o, url, cabecalhos)
                except Exception:  # tabela opcional ausente nao derruba a leitura
                    tabelas[t] = pd.DataFrame()
            tabelas = preparar(tabelas)
            return {
                "tabelas": tabelas,
                "fonte": "api",
                "gerado_em": tabelas["ranking_expansao"]["calculado_em"].max(),
                "motivo": "",
            }
        except Exception as erro:  # qualquer falha da API -> copia de contingencia
            codigo = getattr(getattr(erro, "response", None), "status_code", None)
            motivo = f"a API da gold não respondeu (HTTP {codigo})" if codigo else \
                "a API da gold não respondeu"
    else:
        motivo = "os segredos da API não estão configurados"

    tabelas = {t: ler_json_colunar(PASTA_SNAPSHOT / f"{t}.json") for t in TABELAS_GOLD}
    for t in TABELAS_OPCIONAIS:
        caminho = PASTA_SNAPSHOT / f"{t}.json"
        tabelas[t] = ler_json_colunar(caminho) if caminho.exists() else pd.DataFrame()
    tabelas = preparar(tabelas)
    return {
        "tabelas": tabelas,
        "fonte": "snapshot",
        "gerado_em": ler_meta_snapshot().get("gerado_em"),
        "motivo": motivo,
    }


@st.cache_data(ttl=VALIDADE_CACHE_SEGUNDOS)
def carregar_territorio() -> pd.DataFrame:
    """Centro de cada municipio (referencia do IBGE usada so para o mapa)."""
    return ler_json_colunar(PASTA_SNAPSHOT / "territorio.json")


@st.cache_data
def contornos_ufs() -> tuple[list, list]:
    """Divisas das UFs (malha do IBGE em TopoJSON) como listas de longitude e latitude.

    Cada arco da malha vira uma linha; None separa uma linha da outra. Assim o
    mapa nao depende de servidor de mapas na internet.
    """
    malha = json.loads((PASTA_SNAPSHOT / "malha" / "ufs.topo.json").read_text(encoding="utf-8"))
    (escala_x, escala_y), (origem_x, origem_y) = malha["transform"]["scale"],         malha["transform"]["translate"]
    longitudes: list = []
    latitudes: list = []
    for arco in malha["arcs"]:
        x = y = 0
        for dx, dy in arco:  # coordenadas quantizadas e em diferenca (delta)
            x, y = x + dx, y + dy
            longitudes.append(round(x * escala_x + origem_x, 4))
            latitudes.append(round(y * escala_y + origem_y, 4))
        longitudes.append(None)
        latitudes.append(None)
    return longitudes, latitudes


def tabela(nome: str) -> pd.DataFrame:
    """Atalho: uma tabela da gold ja carregada (copia, para a pagina poder mexer)."""
    return carregar_gold()["tabelas"][nome].copy()


def parametro(nome: str, padrao: float) -> float:
    """Valor de gold.parametro_ranking (trava de renda, quantidade recomendada)."""
    df = carregar_gold()["tabelas"]["parametro_ranking"]
    linha = df.loc[df["parametro"] == nome, "valor"]
    return float(linha.iloc[0]) if not linha.empty else padrao


def ranking_completo() -> pd.DataFrame:
    """Ranking da gold + nome da regiao + centro do municipio (para o mapa)."""
    ranking = tabela("ranking_expansao")
    ranking["regiao_nome"] = ranking["regiao_sigla"].map(fmt.REGIOES)
    # A gold traz latitude/longitude (spec 3.3); a copia antiga ainda nao: completa pelo territorio.
    colunas = ["municipio_id", "regiao_intermediaria_nome"] + [
        c for c in ("longitude", "latitude") if c not in ranking.columns
    ]
    territorio = carregar_territorio()[colunas]
    ranking = ranking.merge(territorio, on="municipio_id", how="left")
    ranking[["latitude", "longitude"]] = ranking[["latitude", "longitude"]].apply(
        pd.to_numeric, errors="coerce")
    return ranking.sort_values("posicao_brasil")


def municipios_completos() -> pd.DataFrame:
    """Todos os municipios (indicadores da gold) + notas do ranking quando a cidade esta no universo."""
    indicadores = tabela("indicadores_municipio")
    indicadores["regiao_nome"] = indicadores["regiao_sigla"].map(fmt.REGIOES)
    if "latitude" not in indicadores.columns:  # copia antiga, sem coordenadas na gold
        indicadores = indicadores.merge(
            carregar_territorio()[["municipio_id", "latitude", "longitude"]], on="municipio_id", how="left")
    notas = [c for c in tabela("ranking_expansao").columns if c.startswith(("nota_", "posicao_"))]
    ranking = tabela("ranking_expansao")[
        ["municipio_id", *notas, "recomendado_top5", "ordem_recomendacao", "dados_incompletos",
         "verificar_concorrencia", "elegivel_recomendacao"]
    ]
    completos = indicadores.merge(ranking, on="municipio_id", how="left")
    completos["no_universo"] = completos["nota_final"].notna()
    for coluna in ("latitude", "longitude"):
        completos[coluna] = pd.to_numeric(completos[coluna], errors="coerce")
    return completos


def semaforo_atual() -> dict:
    """Semaforo exibido: gold.momento_atual (janela movel ate o ultimo fechamento) ou,
    se a tabela ainda nao existir, o ultimo mes fechado de gold.momento_expansao."""
    atual = carregar_gold()["tabelas"].get("momento_atual")
    if atual is not None and not atual.empty:
        linha = atual.iloc[0].to_dict()
        linha["tipo"] = "atual"
        return linha
    historico = tabela("momento_expansao").sort_values("mes")
    if "mes_parcial" in historico.columns:
        historico = historico[~historico["mes_parcial"]]
    linha = historico.iloc[-1].to_dict()
    linha["tipo"] = "mes_fechado"
    return linha


def ultimos_fechamentos() -> dict:
    """Ultimo fechamento diario do dolar: colunas dolar_ultimo/_data da gold ou, na copia
    antiga, o valor gravado na exportacao (site/dados/meta.json)."""
    macro = tabela("contexto_macro")
    if {"dolar_ultimo", "dolar_ultimo_data"} <= set(macro.columns):  # gold v0.13 em diante
        com_dado = macro.dropna(subset=["dolar_ultimo", "dolar_ultimo_data"])
        if not com_dado.empty:
            ultima = com_dado.sort_values("mes").iloc[-1]
            return {"dolar_venda": {"data": str(ultima["dolar_ultimo_data"])[:10],
                                    "valor": float(ultima["dolar_ultimo"])}}
    return ler_meta_snapshot().get("ultimos_fechamentos") or {}


def recomendadas() -> pd.DataFrame:
    """As unidades recomendadas, na ordem da gold."""
    ranking = ranking_completo()
    return ranking[ranking["recomendado_top5"]].sort_values("ordem_recomendacao")


def motivo_fora_da_lista(linha: pd.Series, lista: pd.DataFrame) -> str:
    """Explica (sem recalcular) por que uma cidade nao esta entre as recomendadas."""
    if linha["recomendado_top5"]:
        return ""
    if not linha["elegivel_recomendacao"]:
        trava = parametro("nota_minima_poder_compra", 50)
        return (f"poder de compra {fmt.numero(linha['nota_poder_compra'])}, abaixo da trava "
                f"de renda ({fmt.numero(trava)})")
    mesma = lista[lista["regiao_imediata_id"] == linha["regiao_imediata_id"]]
    if not mesma.empty:
        return f"mesma região imediata de {mesma.iloc[0]['municipio_nome']}, que já está na lista"
    return f"vem depois da {len(lista)}ª recomendada no ranking"
