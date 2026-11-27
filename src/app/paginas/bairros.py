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
# RADAR DE EXPANSAO - ETAPA 7: DASHBOARD - PAGINA "BAIRROS" (SOB DEMANDA)
# =============================================================================
#
# OBJETIVO: dentro de uma cidade, quais bairros sao melhores para a academia.
#           Se o resultado da cidade ja existe, mostra mapa e ranking nas duas
#           escalas (bairros do IBGE e bairros populares); se nao existe, pede o
#           calculo pela API e acompanha a fila ate ficar pronto.
# ENTRADA:  views gold.bairro_resumo, bairro_ranking, bairro_setor,
#           bairro_academia e bairro_pedido (so leitura) e a funcao
#           gold.pedir_bairros (unica escrita exposta pela API)
# SAIDA:    pagina web + CSV baixado pelo usuario; grava so o pedido na fila
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - requests.get com headers e timeout; pandas para filtrar e ordenar
#
# NOVIDADES:
#   1. RPC do PostgREST     -> POST /rest/v1/rpc/<funcao> chama uma funcao do
#                              banco; o header Content-Profile escolhe o schema
#   2. st.fragment(run_every) -> so um pedaco da pagina roda de novo a cada N
#                              segundos (o status da fila), sem recarregar tudo
#   3. busca sem acento     -> unicodedata tira os acentos do nome e do texto
#                              digitado antes de comparar
#   4. dados ficticios      -> enquanto o banco nao tem as tabelas, a pagina
#                              simula a fila e o resultado (DADOS_FICTICIOS)
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: streamlit run src/app/app.py  (menu "Bairros")
#
# =============================================================================

# ============================== CONFIG ==============================
DADOS_FICTICIOS = False          # True so para testar o visual sem o banco
VIEWS = {"resumo": "bairro_resumo", "ranking": "bairro_ranking", "setor": "bairro_setor",
         "academia": "bairro_academia", "pedido": "bairro_pedido"}
FUNCAO_PEDIDO = "pedir_bairros"
CIDADE_PADRAO = 3506003          # Bauru (SP)
ATUALIZAR_A_CADA_S = 10          # status da fila
TIMEOUT_SEGUNDOS = 20
VALIDADE_CACHE_SEGUNDOS = 600
RAIO_PADRAO_KM, POPULACAO_MINIMA_PADRAO = 1.5, 5000   # se o resumo nao trouxer os parametros
MAX_OPCOES_BUSCA = 60
ROTULOS_MAPA = 10
ESCALAS = {"ibge": "Bairros do IBGE", "popular": "Bairros populares"}
NOTAS = {"nota_mercado": "Público 20–59", "nota_renda": "Renda", "nota_espaco": "Pouca concorrência",
         "nota_densidade": "Poder de compra concentrado"}
PESOS_ROTULO = {"mercado": "público de 20 a 59 anos", "renda": "renda média do responsável",
                "espaco": "pouca concorrência no raio (menos academias por 10 mil hab.)",
                "densidade": "massa de renda por km²"}
MENSAGENS_PEDIDO = {   # status devolvido por gold.pedir_bairros
    "invalido": ("error", "O código desta cidade não foi reconhecido pelo banco."),
    "fila_cheia": ("warning", "A fila de cálculo está cheia agora. Tente de novo em alguns minutos."),
    "limite_hora": ("warning", "Muitos pedidos na última hora. Tente de novo mais tarde."),
}
# ====================================================================

import json
import unicodedata
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

import dados
import formato as fmt


# ------------------------------------------------------------------ utilitarios

def sem_acento(texto: str) -> str:
    """'São José' -> 'sao jose' (para comparar o que foi digitado com o nome)."""
    return "".join(c for c in unicodedata.normalize("NFD", str(texto)) if unicodedata.category(c) != "Mn").lower()


def geometria(valor) -> dict | None:
    """GeoJSON (objeto ou texto, geometria ou Feature) com a borda externa no sentido que o mapa espera."""
    if isinstance(valor, str) and valor.strip():
        valor = json.loads(valor)
    if isinstance(valor, dict) and valor.get("type") == "Feature":
        valor = valor.get("geometry")
    if not isinstance(valor, dict) or valor.get("type") not in ("Polygon", "MultiPolygon"):
        return None
    poligonos = [valor["coordinates"]] if valor["type"] == "Polygon" else valor["coordinates"]
    return {"type": "MultiPolygon", "coordinates": [
        [dados._orientar([tuple(p) for p in anel], horario=(n == 0)) for n, anel in enumerate(poligono)]
        for poligono in poligonos]}


def linhas_de_contorno(geo: dict) -> tuple[list, list]:
    """Contorno de uma geometria como listas de lon/lat separadas por None."""
    lons, lats = [], []
    for poligono in geo["coordinates"]:
        for anel in poligono:
            lons += [p[0] for p in anel] + [None]
            lats += [p[1] for p in anel] + [None]
    return lons, lats


# ------------------------------------------------------------------ acesso a API

def conexao() -> tuple[str, dict] | None:
    """Endereco e cabecalhos da API; None se faltar segredo ou a gold veio da copia."""
    segredos = {n: dados.ler_segredo(n) for n in dados.SEGREDOS}
    if not all(segredos.values()) or dados.carregar_gold()["fonte"] != "api":
        return None
    return segredos["SUPABASE_URL"].rstrip("/"), {
        "apikey": segredos["SUPABASE_ANON_KEY"],
        "Authorization": f"Bearer {segredos['SUPABASE_CHAVE_LEITURA']}",
        "Accept-Profile": "gold",
    }


def ler_view(nome: str, filtros: dict) -> pd.DataFrame:
    """GET numa view da gold com filtros do PostgREST (ex.: {'cod_municipio': 'eq.3506003'})."""
    url, cabecalhos = conexao()
    linhas, deslocamento = [], 0
    while True:  # a API devolve no maximo 1000 linhas por chamada
        resposta = requests.get(f"{url}/rest/v1/{VIEWS[nome]}",
                                params={"select": "*", **filtros, "limit": 1000, "offset": deslocamento},
                                headers=cabecalhos, timeout=TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
        lote = resposta.json()
        linhas += lote
        if len(lote) < 1000:
            return pd.DataFrame(linhas)
        deslocamento += 1000


@st.cache_data(ttl=VALIDADE_CACHE_SEGUNDOS, show_spinner="Lendo os bairros…")
def _resultado_api(municipio_id: int) -> dict:
    filtro = {"cod_municipio": f"eq.{municipio_id}"}
    resumo = ler_view("resumo", filtro)
    if resumo.empty:
        return {"resumo": None}
    return {"resumo": resumo.iloc[0].to_dict(), "ranking": ler_view("ranking", filtro),
            "academia": ler_view("academia", filtro)}


@st.cache_data(ttl=VALIDADE_CACHE_SEGUNDOS, show_spinner="Lendo os setores…")
def _setores_api(municipio_id: int) -> pd.DataFrame:
    """Setores so quando pedidos no mapa (uma capital tem dezenas de milhares)."""
    return ler_view("setor", {"cod_municipio": f"eq.{municipio_id}", "select": "cd_setor,geojson"})


def setores(municipio_id: int) -> pd.DataFrame:
    """Contorno dos setores censitarios da cidade."""
    return ficticio_resultado(municipio_id)["setor"] if DADOS_FICTICIOS else _setores_api(municipio_id)


@st.cache_data(ttl=VALIDADE_CACHE_SEGUNDOS, show_spinner=False)
def _prontas_api() -> list[int]:
    df = ler_view("resumo", {"select": "cod_municipio"})
    return sorted(df["cod_municipio"].astype(int).unique()) if not df.empty else []


def resultado(municipio_id: int) -> dict:
    """{'resumo': dict | None, 'ranking', 'setor', 'academia': DataFrames} da cidade."""
    return ficticio_resultado(municipio_id) if DADOS_FICTICIOS else _resultado_api(municipio_id)


def cidades_prontas() -> list[int]:
    """Cidades que ja tem resultado (para a lista inicial)."""
    return sorted(ficticio_prontas()) if DADOS_FICTICIOS else _prontas_api()


def pedido_atual(municipio_id: int) -> dict | None:
    """Ultimo pedido da cidade em gold.bairro_pedido (sem cache: e o que muda)."""
    if DADOS_FICTICIOS:
        return ficticio_pedido(municipio_id)
    df = ler_view("pedido", {"cod_municipio": f"eq.{municipio_id}"})
    return df.iloc[0].to_dict() if not df.empty else None


def pedir(municipio_id: int) -> dict:
    """Chama gold.pedir_bairros: {status, pedido_id, posicao_fila, estimativa_s, mensagem}."""
    if DADOS_FICTICIOS:
        return ficticio_pedir(municipio_id)
    url, cabecalhos = conexao()
    resposta = requests.post(f"{url}/rest/v1/rpc/{FUNCAO_PEDIDO}", json={"cod_municipio": municipio_id},
                             headers={**cabecalhos, "Content-Profile": "gold", "Content-Type": "application/json"},
                             timeout=TIMEOUT_SEGUNDOS)
    resposta.raise_for_status()
    corpo = resposta.json()
    corpo = (corpo[0] if corpo else {}) if isinstance(corpo, list) else corpo
    return corpo if isinstance(corpo, dict) else {"status": str(corpo)}


def limpar_cache() -> None:
    """Apaga o cache da API (depois que um pedido fica pronto)."""
    _resultado_api.clear()
    _prontas_api.clear()
    _setores_api.clear()


# ------------------------------------------------------------------ dados ficticios (provisorio)
# Mesmo formato das views da gold; somem quando DADOS_FICTICIOS = False.

def ficticio_prontas() -> set:
    """As 5 recomendadas + Bauru ja calculadas, como no contrato."""
    iniciais = {CIDADE_PADRAO, *dados.recomendadas()["municipio_id"].astype(int)}
    return st.session_state.setdefault("bairros_ficticio_prontas", iniciais)


def ficticio_resultado(municipio_id: int) -> dict:
    """Resultado inventado (sorteado a partir do codigo; codigo impar = concorrencia pendente)."""
    if municipio_id not in ficticio_prontas():
        return {"resumo": None}
    cidade = dados.municipios_completos().set_index("municipio_id").loc[municipio_id]
    sorteio = np.random.default_rng(municipio_id)
    concorrencia = "pendente" if municipio_id % 2 else "ok"
    ranking, setores, academias = [], [], []
    for escala, quantidade in (("ibge", 12), ("popular", 9)):
        for i in range(quantidade):
            lat, lon = (float(cidade["latitude"] + sorteio.normal(0, 0.02)),
                        float(cidade["longitude"] + sorteio.normal(0, 0.02)))
            lado = 0.006 + 0.004 * sorteio.random()
            quadrado = [[lon - lado, lat - lado], [lon + lado, lat - lado], [lon + lado, lat + lado],
                        [lon - lado, lat + lado], [lon - lado, lat - lado]]
            populacao = float(sorteio.integers(1_000, 60_000 if escala == "ibge" else 14_000))
            acad = int(sorteio.integers(0, 30))
            ranking.append({
                "cod_municipio": municipio_id, "escala": escala, "unidade_id": f"{escala}{i}",
                "unidade_nome": f"{'Bacia' if escala == 'ibge' else 'Vila'} fictícia {i + 1}",
                "elegivel": populacao >= POPULACAO_MINIMA_PADRAO, "posicao": None,
                "setores": int(sorteio.integers(5, 60)), "populacao": populacao,
                "pop_20_59": round(populacao * 0.57, 1), "renda_media_resp": float(sorteio.integers(1_800, 9_000)),
                "massa_renda_km2": float(sorteio.integers(2, 60)) * 1e6, "acad_raio": acad,
                "pop_raio": int(populacao * 1.4), "acad_raio_10k": round(acad / populacao * 1e4, 3),
                "dist_centro_km": round(float(np.hypot(lat - cidade["latitude"], lon - cidade["longitude"]) * 111), 3),
                **{n: float(sorteio.integers(5, 100)) for n in NOTAS}, "nota_final": None, "frase": None,
                "concorrencia": concorrencia, "lat": lat, "lon": lon,
                "geojson": {"type": "Polygon", "coordinates": [quadrado]} if escala == "ibge" else None,
                "processado_em": "2026-11-27T03:00:00-03:00",
            })
            if escala == "ibge":
                setores.append({"cod_municipio": municipio_id, "cd_setor": f"{municipio_id}{i:08d}",
                                "geojson": {"type": "Polygon", "coordinates": [quadrado]}})
    for _ in range(25 if concorrencia == "ok" else 0):
        academias.append({"cod_municipio": municipio_id, "lat": float(cidade["latitude"] + sorteio.normal(0, 0.02)),
                          "lon": float(cidade["longitude"] + sorteio.normal(0, 0.02)),
                          "nivel_geocod": "cep", "localidade": None})
    ranking = pd.DataFrame(ranking)
    for escala in ESCALAS:
        el = ranking[(ranking["escala"] == escala) & ranking["elegivel"]].copy()
        if concorrencia == "pendente":
            el["nota_espaco"] = np.nan
        el["nota_final"] = el[list(NOTAS)].mean(axis=1).round(1)
        el["posicao"] = el["nota_final"].rank(ascending=False, method="first").astype(int)
        el["frase"] = "forte em público de 20 a 59 anos; fraco em renda do responsável"
        for coluna in ("nota_espaco", "nota_final", "posicao", "frase"):
            ranking.loc[el.index, coluna] = el[coluna]
    resumo = {"cod_municipio": municipio_id, "municipio_nome": cidade["municipio_nome"], "uf_sigla": cidade["uf_sigla"],
              "processado_em": "2026-11-27T03:00:00-03:00", "duracao_s": 150, "concorrencia": concorrencia,
              "data_base_cnpj": "2026-11" if concorrencia == "ok" else None, "academias_base": len(academias) + 3,
              "academias_geocodificadas": len(academias),
              "pesos": {"mercado": 0.3, "renda": 0.25, "espaco": 0.3, "densidade": 0.15} if concorrencia == "ok"
              else {"mercado": 0.43, "renda": 0.36, "densidade": 0.21},
              "parametros": {"raio_km": 1.5, "pop_min": 5000, "versao": "ficticio"}}
    return {"resumo": resumo, "ranking": ranking, "setor": pd.DataFrame(setores), "academia": pd.DataFrame(academias)}


def ficticio_pedido(municipio_id: int) -> dict | None:
    """Simula o worker: 15 s pendente, 30 s processando, depois pronto."""
    pedido = st.session_state.get("bairros_ficticio_fila", {}).get(municipio_id)
    if not pedido:
        return None
    idade = (datetime.now() - pedido["pedido_em"]).total_seconds()
    if idade > 45:
        ficticio_prontas().add(municipio_id)
        return {**pedido, "status": "pronto", "posicao_fila": None, "estimativa_s": None}
    if idade > 15:
        return {**pedido, "status": "processando", "posicao_fila": None, "estimativa_s": int(45 - idade)}
    return {**pedido, "status": "pendente", "posicao_fila": 1, "estimativa_s": int(45 - idade)}


def ficticio_pedir(municipio_id: int) -> dict:
    """Enfileira o pedido inventado (sem duplicar)."""
    fila = st.session_state.setdefault("bairros_ficticio_fila", {})
    fila.setdefault(municipio_id, {"id": len(fila) + 1, "cod_municipio": municipio_id, "pedido_em": datetime.now()})
    return {"status": "pendente", "pedido_id": fila[municipio_id]["id"], "posicao_fila": 1, "estimativa_s": 45,
            "mensagem": "pedido registrado"}


# ------------------------------------------------------------------ pagina

st.title("Bairros")
st.caption(
    "Dentro de uma cidade, quais bairros juntam mais público com renda e menos academias por perto. "
    "O resultado de cada cidade é calculado uma vez, sob demanda, e fica guardado."
)
if DADOS_FICTICIOS:
    st.warning("**Dados fictícios de teste.** Esta página ainda não está ligada ao banco: nomes, números e a fila "
               "são simulados para conferir o visual e o fluxo.", icon=":material/science:")
elif conexao() is None:
    st.info("O cálculo de bairros sob demanda precisa da conexão com a API da camada gold, que não está "
            "disponível agora (o dashboard está usando a cópia de contingência). Tente de novo mais tarde.",
            icon=":material/cloud_off:")
    st.stop()

municipios = dados.municipios_completos()
nomes = municipios.set_index("municipio_id")["municipio_nome"].to_dict()
ufs = municipios.set_index("municipio_id")["uf_sigla"].to_dict()


def rotulo(i: int) -> str:
    """'Bauru (SP)'."""
    return f"{nomes[i]} ({ufs[i]})"


def falha_api(erro: Exception, acao: str) -> None:
    """Mensagem para erro da API (404 = modulo de bairros ainda nao instalado no banco)."""
    if getattr(getattr(erro, "response", None), "status_code", None) == 404:
        st.info("Os bairros sob demanda ainda não estão disponíveis no banco.", icon=":material/construction:")
    else:
        st.error(f"A API não respondeu ao {acao}. Tente de novo em instantes.", icon=":material/error:")
    st.stop()


try:
    prontas = [i for i in cidades_prontas() if i in nomes]
except requests.RequestException as erro:
    falha_api(erro, "listar as cidades já calculadas")

# --- Escolha da cidade (busca sem acento) -----------------------------------------
with st.container(border=True):
    col_busca, col_cidade = st.columns([2, 3], vertical_alignment="bottom")
    with col_busca:
        busca = st.text_input("Buscar cidade", placeholder="parte do nome, com ou sem acento", key="bairros_busca")
    alvo = sem_acento(busca.strip())
    if alvo:
        chaves = municipios.assign(_n=municipios["municipio_nome"].map(sem_acento))
        achadas = chaves[chaves["_n"].str.contains(alvo, regex=False)]
        achadas = achadas.assign(_depois=~achadas["_n"].str.startswith(alvo)).sort_values(
            ["_depois", "populacao"], ascending=[True, False])
        opcoes = achadas["municipio_id"].astype(int).head(MAX_OPCOES_BUSCA).tolist()
    else:
        opcoes = prontas or [CIDADE_PADRAO]
    with col_cidade:
        if not opcoes:
            st.selectbox("Cidade", ["Nenhuma cidade com esse nome"], disabled=True)
            st.stop()
        municipio_id = int(st.selectbox(
            "Cidade" + ("" if alvo else " (já calculadas)"), opcoes, key=f"bairros_cidade_{alvo}",
            index=opcoes.index(CIDADE_PADRAO) if CIDADE_PADRAO in opcoes else 0,
            format_func=lambda i: rotulo(i) + ("  ✓" if i in prontas else "")))

try:
    res = resultado(municipio_id)
except requests.RequestException as erro:
    falha_api(erro, "ler os bairros desta cidade")


# --- Cidade sem resultado: pedido e fila ------------------------------------------
def minutos(segundos) -> str:
    """Tempo estimado em palavras."""
    return "menos de 1 min" if fmt.ausente(segundos) or segundos < 60 else f"cerca de {round(segundos / 60)} min"


@st.fragment(run_every=ATUALIZAR_A_CADA_S)
def acompanhar_pedido(municipio_id: int) -> None:
    """Status do pedido desta cidade; quando fica pronto, recarrega a pagina."""
    try:
        pedido = pedido_atual(municipio_id)
    except requests.RequestException:
        st.warning("Não consegui ler a fila agora; tento de novo em alguns segundos.", icon=":material/sync_problem:")
        return
    status = (pedido or {}).get("status")

    if status == "pronto":
        if st.session_state.get("bairros_recarregou") != municipio_id:  # evita laco se o cache demorar
            st.session_state["bairros_recarregou"] = municipio_id
            limpar_cache()
            st.rerun(scope="app")
        st.info("O resultado ficou pronto. Recarregue a página se ele não aparecer.", icon=":material/check_circle:")
        return
    if status == "pendente":
        posicao = pedido.get("posicao_fila")
        st.info(f"**Na fila{'' if fmt.ausente(posicao) else f': posição {int(posicao)}'}.** "
                f"Tempo estimado até o resultado: {minutos(pedido.get('estimativa_s'))}. "
                f"Esta área se atualiza sozinha a cada {ATUALIZAR_A_CADA_S} s; pode sair e voltar depois.",
                icon=":material/hourglass_top:")
        st.progress(0.15)
        return
    if status == "processando":
        st.info(f"**Calculando os bairros de {rotulo(municipio_id)}…** Faltam {minutos(pedido.get('estimativa_s'))}. "
                f"Esta área se atualiza sozinha a cada {ATUALIZAR_A_CADA_S} s.", icon=":material/autorenew:")
        st.progress(0.6)
        return

    # sem pedido (ou o ultimo deu erro): oferece o calculo
    if status == "erro":
        st.error("O último cálculo desta cidade falhou. Você pode pedir de novo.", icon=":material/error:")
    else:
        st.info(f"Ainda não há resultado para {rotulo(municipio_id)}. O cálculo usa os setores do Censo 2022 e a base "
                "de academias da Receita Federal e leva alguns minutos.", icon=":material/schedule:")
    if not st.button("Calcular bairros desta cidade", type="primary", icon=":material/play_arrow:"):
        return
    try:
        resposta = pedir(municipio_id)
    except requests.RequestException as erro:
        codigo = getattr(getattr(erro, "response", None), "status_code", None)
        st.error(f"O pedido não chegou ao banco{f' (HTTP {codigo})' if codigo else ''}. Tente de novo em instantes.",
                 icon=":material/error:")
        return
    novo = resposta.get("status")
    if novo == "pronto":
        limpar_cache()
        st.rerun(scope="app")
    if novo in MENSAGENS_PEDIDO:
        tipo, texto = MENSAGENS_PEDIDO[novo]
        getattr(st, tipo)(texto, icon=":material/error:" if tipo == "error" else ":material/schedule:")
        return
    if novo not in ("pendente", "processando"):
        st.warning(f"Resposta inesperada do banco: {resposta.get('mensagem') or novo}.", icon=":material/help:")
        return
    st.rerun(scope="fragment")


if res["resumo"] is None:
    acompanhar_pedido(municipio_id)
    st.stop()

# --- Cidade com resultado ---------------------------------------------------------
resumo, ranking = res["resumo"], res["ranking"]
parametros = resumo.get("parametros") or {}
parametros = json.loads(parametros) if isinstance(parametros, str) else parametros
raio = float(parametros.get("raio_km", RAIO_PADRAO_KM))
pop_min = int(parametros.get("pop_min", POPULACAO_MINIMA_PADRAO))
concorrencia_ok = resumo.get("concorrencia") == "ok"

if not concorrencia_ok:
    st.warning(
        "**A concorrência ainda não entrou neste resultado.** A base nacional de academias da Receita Federal está "
        "sendo carregada; por enquanto a nota usa só público, renda e poder de compra concentrado (pesos "
        "redistribuídos), e o mapa não mostra as academias.", icon=":material/pending:")

com_dados = [e for e in ESCALAS if (ranking["escala"] == e).any()] or list(ESCALAS)
escala = st.segmented_control("Escala", list(ESCALAS), format_func=ESCALAS.get, default=com_dados[0],
                              key=f"bairros_escala_{municipio_id}") or com_dados[0]
unidades = ranking[ranking["escala"] == escala].copy()
unidades["elegivel"] = unidades["elegivel"].astype(bool)
elegiveis = unidades[unidades["elegivel"]].sort_values("posicao")
fora = unidades[~unidades["elegivel"]]
st.subheader(f"{rotulo(municipio_id)} · {ESCALAS[escala]}")

base = resumo.get("data_base_cnpj")
geocod, total_acad = resumo.get("academias_geocodificadas"), resumo.get("academias_base")
st.info(
    "**Limitações.** População, faixa de 20 a 59 anos e renda vêm do **Censo 2022** por setor. As academias são as "
    f"empresas ativas da Receita Federal{f' (base de {base})' if base else ''} pelo **endereço fiscal**, que pode não ser "
    "onde a academia funciona"
    + (f"; {fmt.numero(geocod)} de {fmt.numero(total_acad)} foram localizadas no mapa"
       if concorrencia_ok and not fmt.ausente(geocod) and not fmt.ausente(total_acad) else "")
    + f". A concorrência é contada num **raio de {fmt.numero(raio, 1)} km** do centro de cada bairro. Bairros com menos de "
    f"{fmt.numero(pop_min)} habitantes ou só área rural ficam fora do ranking. Os bairros populares são os nomes de "
    "localidade dos endereços do IBGE, sem limite oficial (no mapa, um ponto no centro de cada um).",
    icon=":material/info:",
)
if unidades.empty:
    outra = next(iter(set(ESCALAS) - {escala}))
    st.info(f"Esta cidade não tem {ESCALAS[escala].lower().replace('ibge', 'IBGE')} no Censo 2022. "
            f"Veja a escala \"{ESCALAS[outra]}\".", icon=":material/search_off:")
    st.stop()
if elegiveis.empty:
    st.info(f"Nenhum bairro com {fmt.numero(pop_min)} habitantes ou mais nesta escala.", icon=":material/search_off:")


# --- Mapa: bairros (poligono ou ponto), setores e academias -------------------------
def texto_hover(r) -> str:
    """Nome, nota, populacao, renda, academias no raio e a frase da gold."""
    posicao = "" if fmt.ausente(r["posicao"]) else f"{int(r['posicao'])}º "
    partes = [f"<b>{posicao}{r['unidade_nome']}</b>",
              f"Nota {fmt.nota(r['nota_final'])}" if r["elegivel"] else "Fora do ranking",
              f"{fmt.compacto(r['populacao'])} hab. · renda média do responsável {fmt.reais(r['renda_media_resp'], 0)}"]
    if concorrencia_ok and not fmt.ausente(r.get("acad_raio")):
        partes.append(f"{fmt.numero(r['acad_raio'])} academias no raio "
                      f"({fmt.numero(r['acad_raio_10k'], 2)} por 10 mil hab.)")
    if isinstance(r.get("frase"), str) and r["frase"]:
        partes.append(r["frase"])
    return "<br>".join(partes)


with st.container(horizontal=True):
    ver_academias = st.toggle("Academias", value=concorrencia_ok, disabled=not concorrencia_ok,
                              key=f"bairros_ver_academias_{concorrencia_ok}")  # sem concorrencia, fica travado
    ver_setores = st.toggle("Setores do Censo", value=False, key="bairros_ver_setores",
                            help="Contorno dos setores censitários, a menor área com dados do Censo 2022.")

unidades["_texto"] = [texto_hover(r) for _, r in unidades.iterrows()]
unidades["_geo"] = unidades["geojson"].map(geometria) if "geojson" in unidades else None
figura = go.Figure()
barra = {"title": {"text": "Nota"}, "thickness": 12, "len": 0.6}
contorno = (dados.malha_municipios_uf(municipio_id // 100_000) or {}).get(municipio_id)
if contorno:  # limite do municipio, so como referencia
    lon_c, lat_c = linhas_de_contorno(contorno)
    figura.add_trace(go.Scattergeo(lon=lon_c, lat=lat_c, mode="lines", hoverinfo="skip", showlegend=False,
                                   line={"color": "rgba(242,241,236,.45)", "width": 1}))
tabela_setores = setores(municipio_id) if ver_setores else pd.DataFrame()
if not tabela_setores.empty:
    lon_s, lat_s = [], []
    for g in tabela_setores["geojson"].map(geometria).dropna():
        lo, la = linhas_de_contorno(g)
        lon_s += lo
        lat_s += la
    figura.add_trace(go.Scattergeo(lon=lon_s, lat=lat_s, mode="lines", hoverinfo="skip", showlegend=False,
                                   line={"color": "rgba(242,241,236,.18)", "width": 0.5}))
com_geo = unidades[unidades["_geo"].notna()]
for grupo, cinza in ((com_geo[~com_geo["elegivel"]], True), (com_geo[com_geo["elegivel"]], False)):
    if grupo.empty:
        continue
    figura.add_trace(go.Choropleth(
        geojson={"type": "FeatureCollection", "features": [
            {"type": "Feature", "id": str(i), "geometry": g} for i, g in zip(grupo["unidade_id"], grupo["_geo"])]},
        locations=grupo["unidade_id"].astype(str).tolist(),
        z=[0] * len(grupo) if cinza else grupo["nota_final"].astype(float).tolist(),
        zmin=0, zmax=100, colorscale=[[0, "#3b4249"], [1, "#3b4249"]] if cinza else fmt.ESCALA_DADO,
        showscale=not cinza, colorbar=barra, marker={"line": {"color": "#0b0d0f", "width": 0.6}},
        text=grupo["_texto"].tolist(), hoverinfo="text"))
sem_geo = unidades[unidades["_geo"].isna() & unidades["lat"].notna() & unidades["elegivel"]]  # so os do ranking
if not sem_geo.empty:
    maior = max(float(sem_geo["populacao"].max()), 1.0)
    figura.add_trace(go.Scattergeo(
        lon=sem_geo["lon"].astype(float).tolist(), lat=sem_geo["lat"].astype(float).tolist(), mode="markers",
        text=sem_geo["_texto"].tolist(), hoverinfo="text", showlegend=False,
        marker={"size": (8 + 24 * np.sqrt(sem_geo["populacao"].astype(float) / maior)).tolist(),
                "color": [float(n) if e and not fmt.ausente(n) else 0
                          for n, e in zip(sem_geo["nota_final"], sem_geo["elegivel"])],
                "colorscale": fmt.ESCALA_DADO, "cmin": 0, "cmax": 100, "opacity": 0.9,
                "showscale": com_geo.empty, "colorbar": barra}))
if ver_academias and not res["academia"].empty:
    figura.add_trace(go.Scattergeo(
        lon=res["academia"]["lon"].astype(float).tolist(), lat=res["academia"]["lat"].astype(float).tolist(),
        mode="markers", name="Academia (endereço fiscal)", hoverinfo="name",
        marker={"size": 5, "color": fmt.COR_DESTAQUE, "symbol": "diamond", "line": {"width": 0}}))
top = elegiveis.head(ROTULOS_MAPA)
if not top.empty:
    figura.add_trace(go.Scattergeo(
        lon=top["lon"].astype(float).tolist(), lat=top["lat"].astype(float).tolist(), mode="text", hoverinfo="skip",
        showlegend=False, text=[f"{int(p)}º {n}" for p, n in zip(top["posicao"], top["unidade_nome"])],
        textposition="top center", textfont={"color": "#f2f1ec", "size": 11}))
pontos = unidades[unidades["lat"].notna()]
if not pontos.empty:
    folga = 0.02
    figura.update_geos(lonaxis_range=[float(pontos["lon"].min() - folga), float(pontos["lon"].max() + folga)],
                       lataxis_range=[float(pontos["lat"].min() - folga), float(pontos["lat"].max() + folga)])
figura.update_geos(projection_type="mercator", visible=False, bgcolor="rgba(0,0,0,0)")
figura.update_layout(separators=",.", height=520, margin={"l": 0, "r": 0, "t": 0, "b": 0},
                     paper_bgcolor="rgba(0,0,0,0)", dragmode="pan",
                     legend={"orientation": "h", "y": 0.01, "x": 0.01})
st.plotly_chart(figura, config={"displaylogo": False, "scrollZoom": True},
                alt=f"Mapa dos bairros de {rotulo(municipio_id)} coloridos pela nota.")

# --- Ranking --------------------------------------------------------------------------
colunas = {
    "posicao": st.column_config.NumberColumn("Posição", format="%dº", width="small"),
    "unidade_nome": st.column_config.TextColumn("Bairro", pinned=True),
    "nota_final": st.column_config.ProgressColumn("Nota", min_value=0, max_value=100, format="%.1f",
                                                  color=fmt.COR_DADO),
    **{c: st.column_config.NumberColumn(r, format="%.0f") for c, r in NOTAS.items()},
    "populacao": st.column_config.NumberColumn("População", format="localized"),
    "pop_20_59": st.column_config.NumberColumn("20 a 59 anos", format="localized"),
    "renda_media_resp": st.column_config.NumberColumn("Renda média resp. (R$)", format="localized"),
    "acad_raio": st.column_config.NumberColumn(f"Academias no raio de {fmt.numero(raio, 1)} km", format="%d"),
    "acad_raio_10k": st.column_config.NumberColumn("Por 10 mil hab. no raio", format="%.2f"),
    "massa_renda_km2": st.column_config.NumberColumn("Massa de renda por km²", format="compact"),
    "dist_centro_km": st.column_config.NumberColumn("Distância do centro (km)", format="%.1f"),
    "frase": st.column_config.TextColumn("Leitura", width="large"),
}
if not concorrencia_ok:
    for coluna in ("nota_espaco", "acad_raio", "acad_raio_10k"):
        colunas.pop(coluna)
colunas = {c: v for c, v in colunas.items() if c in unidades}
if not elegiveis.empty:
    st.dataframe(elegiveis[list(colunas)], column_config=colunas, hide_index=True,
                 alt="Ranking dos bairros com nota, população, renda e academias no raio.")
pesos = resumo.get("pesos") or {}
pesos = json.loads(pesos) if isinstance(pesos, str) else pesos
st.caption(
    "Nota de 0 a 100 dentro da escala (percentil entre os bairros da cidade): "
    + ", ".join(f"{PESOS_ROTULO.get(k, k)} {fmt.numero(v * 100)} %" for k, v in pesos.items()) + ". "
    + f"Calculado em {fmt.data_hora(resumo.get('processado_em'))}."
)
if not fora.empty:
    with st.expander(f"Fora do ranking: {len(fora)} {'bairro' if len(fora) == 1 else 'bairros'} "
                     f"(menos de {fmt.numero(pop_min)} hab. ou área rural)"):
        colunas_fora = ["unidade_nome", "populacao", "renda_media_resp"]
        st.dataframe(fora[colunas_fora].sort_values("populacao", ascending=False),
                     column_config={c: colunas[c] for c in colunas_fora}, hide_index=True)
st.download_button(
    "Baixar CSV dos bairros",
    data=unidades[["elegivel", *colunas]].sort_values("posicao")
    .to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
    file_name=f"radar_expansao_bairros_{municipio_id}_{escala}.csv", mime="text/csv", icon=":material/download:",
)
