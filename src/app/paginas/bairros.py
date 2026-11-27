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
# ENTRADA:  gold.bairro_ranking e gold.bairro_pedido (views so de leitura) e a
#           funcao gold.pedir_bairros (unica escrita exposta pela API)
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
DADOS_FICTICIOS = True           # True ate a 03 aplicar o schema bairros no banco
VIEW_RANKING = "bairro_ranking"
VIEW_PEDIDO = "bairro_pedido"
FUNCAO_PEDIDO = "pedir_bairros"
PARAMETRO_FUNCAO = "cod_municipio"
CIDADE_PADRAO = 3506003          # Bauru (SP)
ATUALIZAR_A_CADA_S = 10          # status da fila
DURACAO_PADRAO_S = 240           # estimativa quando ainda nao ha pedido concluido
TIMEOUT_SEGUNDOS = 15
VALIDADE_CACHE_SEGUNDOS = 600
RAIO_CONCORRENCIA_KM = 1.5
POPULACAO_MINIMA_BAIRRO = 5000
MAX_OPCOES_BUSCA = 60
ESCALAS = {"ibge": "Bairros do IBGE", "popular": "Bairros populares"}
# Colunas esperadas em gold.bairro_ranking (contrato de 27/11; trocar aqui se o DDL mudar)
COL = {
    "municipio": "cod_municipio", "escala": "escala", "nome": "unidade_nome", "populacao": "populacao",
    "publico": "pop_20_59", "renda": "renda_media_resp", "academias": "academias_raio",
    "densidade": "academias_10mil_raio", "massa": "massa_renda_km2", "nota": "nota", "posicao": "posicao",
    "lat": "lat", "lon": "lon", "geometria": "geometria", "calculado_em": "calculado_em",
    "base_cnpj": "base_cnpj_ref",
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


# ------------------------------------------------------------------ busca sem acento

def sem_acento(texto: str) -> str:
    """'São José' -> 'sao jose' (para comparar o que foi digitado com o nome)."""
    return "".join(c for c in unicodedata.normalize("NFD", str(texto)) if unicodedata.category(c) != "Mn").lower()


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


def ler_view(view: str, filtros: dict) -> pd.DataFrame:
    """GET numa view da gold com filtros do PostgREST (ex.: {'cod_municipio': 'eq.3506003'})."""
    url, cabecalhos = conexao()
    resposta = requests.get(f"{url}/rest/v1/{view}", params={"select": "*", **filtros},
                            headers=cabecalhos, timeout=TIMEOUT_SEGUNDOS)
    resposta.raise_for_status()
    return pd.DataFrame(resposta.json())


@st.cache_data(ttl=VALIDADE_CACHE_SEGUNDOS, show_spinner=False)
def _ranking_api(municipio_id: int) -> pd.DataFrame:
    return ler_view(VIEW_RANKING, {COL["municipio"]: f"eq.{municipio_id}"})


@st.cache_data(ttl=VALIDADE_CACHE_SEGUNDOS, show_spinner=False)
def _prontas_api() -> list[int]:
    df = ler_view(VIEW_RANKING, {"select": COL["municipio"]})
    return sorted(df[COL["municipio"]].astype(int).unique()) if not df.empty else []


def ranking_da_cidade(municipio_id: int) -> pd.DataFrame:
    """Resultado ja calculado da cidade (vazio se ainda nao existe); cache de 10 min na API."""
    return ficticio_ranking(municipio_id) if DADOS_FICTICIOS else _ranking_api(municipio_id)


def cidades_prontas() -> list[int]:
    """Cidades que ja tem resultado (para a lista inicial)."""
    if DADOS_FICTICIOS:
        return sorted(st.session_state.setdefault("bairros_ficticio_prontas", set(ficticio_iniciais())))
    return _prontas_api()


def fila() -> pd.DataFrame:
    """Pedidos da fila (sem cache: e o que muda)."""
    if DADOS_FICTICIOS:
        return ficticio_fila()
    return ler_view(VIEW_PEDIDO, {"order": "pedido_em.asc"})


def pedir(municipio_id: int) -> str:
    """Chama gold.pedir_bairros e devolve o status que a funcao respondeu."""
    if DADOS_FICTICIOS:
        return ficticio_pedir(municipio_id)
    url, cabecalhos = conexao()
    resposta = requests.post(f"{url}/rest/v1/rpc/{FUNCAO_PEDIDO}", json={PARAMETRO_FUNCAO: municipio_id},
                             headers={**cabecalhos, "Content-Profile": "gold", "Content-Type": "application/json"},
                             timeout=TIMEOUT_SEGUNDOS)
    resposta.raise_for_status()
    corpo = resposta.json()
    if isinstance(corpo, list):
        corpo = corpo[0] if corpo else {}
    return str(corpo.get("status", corpo) if isinstance(corpo, dict) else corpo)


# ------------------------------------------------------------------ dados ficticios (provisorio)

def ficticio_iniciais() -> list[int]:
    """As 5 recomendadas + Bauru, como no contrato."""
    return sorted({CIDADE_PADRAO, *dados.recomendadas()["municipio_id"].astype(int)})


def ficticio_ranking(municipio_id: int) -> pd.DataFrame:
    """Resultado inventado, sorteado a partir do codigo da cidade (sempre o mesmo)."""
    if municipio_id not in st.session_state.get("bairros_ficticio_prontas", set(ficticio_iniciais())):
        return pd.DataFrame()
    cidade = dados.municipios_completos().set_index("municipio_id").loc[municipio_id]
    gerador = np.random.default_rng(municipio_id)
    linhas = []
    for escala, quantidade in (("ibge", 12), ("popular", 7)):
        for i in range(quantidade):
            dlat, dlon = gerador.normal(0, 0.025, 2)
            lat, lon = float(cidade["latitude"] + dlat), float(cidade["longitude"] + dlon)
            lado = 0.008 + 0.006 * gerador.random()
            quadrado = [[lon - lado, lat - lado], [lon - lado, lat + lado], [lon + lado, lat + lado],
                        [lon + lado, lat - lado], [lon - lado, lat - lado]]
            populacao = int(gerador.integers(5_000, 70_000 if escala == "ibge" else 15_000))
            academias = int(gerador.integers(1, 40))
            linhas.append({
                COL["municipio"]: municipio_id, COL["escala"]: escala,
                COL["nome"]: f"{'Bacia' if escala == 'ibge' else 'Bairro'} fictício {i + 1}",
                COL["populacao"]: populacao, COL["publico"]: int(populacao * 0.58),
                COL["renda"]: float(gerador.integers(1_800, 9_500)), COL["academias"]: academias,
                COL["densidade"]: round(academias / populacao * 10_000, 2),
                COL["massa"]: float(gerador.integers(2, 60)) * 1e6, COL["nota"]: round(90 - i * 6.5, 1),
                COL["posicao"]: i + 1, COL["lat"]: lat, COL["lon"]: lon,
                COL["geometria"]: {"type": "Polygon", "coordinates": [quadrado]} if escala == "ibge" else None,
                COL["calculado_em"]: "2026-11-27T03:00:00-03:00", COL["base_cnpj"]: "2026-11",
            })
    return pd.DataFrame(linhas)


def ficticio_fila() -> pd.DataFrame:
    """Simula o worker: cada pedido fica 15 s pendente e 30 s processando."""
    pedidos = st.session_state.setdefault("bairros_ficticio_fila", [])
    agora = datetime.now().astimezone()
    for p in pedidos:
        idade = (agora - p["pedido_em"]).total_seconds()
        if p["status"] != "pronto" and idade > 45:
            p.update(status="pronto", fim=agora, duracao_s=30)
            st.session_state.setdefault("bairros_ficticio_prontas", set(ficticio_iniciais())).add(p["cod_municipio"])
        elif p["status"] == "pendente" and idade > 15:
            p.update(status="processando", inicio=agora)
    return pd.DataFrame(pedidos)


def ficticio_pedir(municipio_id: int) -> str:
    """Enfileira o pedido inventado (sem duplicar)."""
    pedidos = st.session_state.setdefault("bairros_ficticio_fila", [])
    if not any(p["cod_municipio"] == municipio_id and p["status"] != "erro" for p in pedidos):
        pedidos.append({"id": len(pedidos) + 1, "cod_municipio": municipio_id, "status": "pendente",
                        "pedido_em": datetime.now().astimezone(), "inicio": None, "fim": None,
                        "duracao_s": None, "erro_resumo": None})
    return "pendente"


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
rotulo = lambda i: f"{nomes[i]} ({ufs[i]})"

try:
    prontas = [i for i in cidades_prontas() if i in nomes]
except requests.RequestException as erro:
    if getattr(getattr(erro, "response", None), "status_code", None) == 404:
        st.info("Os bairros sob demanda ainda não estão disponíveis no banco.", icon=":material/construction:")
    else:
        st.error("A API não respondeu ao listar as cidades já calculadas. Tente de novo em instantes.",
                 icon=":material/error:")
    st.stop()

# --- Escolha da cidade (busca sem acento) -----------------------------------------
with st.container(border=True):
    col_busca, col_cidade = st.columns([2, 3], vertical_alignment="bottom")
    with col_busca:
        busca = st.text_input("Buscar cidade", placeholder="parte do nome, com ou sem acento",
                              key="bairros_busca")
    alvo = sem_acento(busca.strip())
    if alvo:
        chaves = municipios.assign(_n=municipios["municipio_nome"].map(sem_acento))
        achadas = chaves[chaves["_n"].str.contains(alvo, regex=False)]
        achadas = achadas.assign(_comeca=~achadas["_n"].str.startswith(alvo)).sort_values(
            ["_comeca", "populacao"], ascending=[True, False])
        opcoes = achadas["municipio_id"].astype(int).head(MAX_OPCOES_BUSCA).tolist()
    else:
        opcoes = prontas or [CIDADE_PADRAO]
    with col_cidade:
        if not opcoes:
            st.selectbox("Cidade", ["Nenhuma cidade com esse nome"], disabled=True)
            st.stop()
        municipio_id = st.selectbox(
            "Cidade" + ("" if alvo else " (já calculadas)"), opcoes, key=f"bairros_cidade_{alvo}",
            index=opcoes.index(CIDADE_PADRAO) if CIDADE_PADRAO in opcoes else 0,
            format_func=lambda i: rotulo(i) + ("  ✓" if i in prontas else ""))

try:
    resultado = ranking_da_cidade(int(municipio_id))
except requests.RequestException:
    st.error("A API não respondeu ao ler os bairros desta cidade. Tente de novo em instantes.",
             icon=":material/error:")
    st.stop()


# --- Cidade sem resultado: pedido e fila ------------------------------------------
@st.fragment(run_every=ATUALIZAR_A_CADA_S)
def acompanhar_pedido(municipio_id: int) -> None:
    """Status do pedido desta cidade; quando fica pronto, recarrega a pagina."""
    try:
        pedidos = fila()
    except requests.RequestException:
        st.warning("Não consegui ler a fila agora; tento de novo em alguns segundos.", icon=":material/sync_problem:")
        return
    meus = pedidos[pedidos[COL["municipio"]] == municipio_id] if not pedidos.empty else pedidos
    if meus.empty:
        st.info(f"Ainda não há resultado para {rotulo(municipio_id)}. O cálculo usa os dados do Censo 2022 por "
                "setor e a base de academias da Receita Federal e leva alguns minutos.", icon=":material/schedule:")
        if st.button("Calcular bairros desta cidade", type="primary", icon=":material/play_arrow:"):
            try:
                pedir(municipio_id)
            except requests.RequestException as erro:
                codigo = getattr(getattr(erro, "response", None), "status_code", None)
                st.error(f"O pedido não foi aceito{f' (HTTP {codigo})' if codigo else ''}. "
                         "A fila pode estar cheia; tente de novo mais tarde.", icon=":material/error:")
                return
            st.rerun(scope="fragment")
        return

    pedido = meus.sort_values("pedido_em").iloc[-1]
    status = pedido["status"]
    if status == "pronto":
        _ranking_api.clear()
        _prontas_api.clear()
        st.rerun(scope="app")
    if status == "erro":
        st.error(f"O cálculo desta cidade falhou: {pedido.get('erro_resumo') or 'erro sem detalhe'}.",
                 icon=":material/error:")
        return

    concluidos = pedidos[pedidos["status"] == "pronto"]["duracao_s"].dropna() if "duracao_s" in pedidos else []
    duracao = float(np.median(concluidos)) if len(concluidos) else DURACAO_PADRAO_S
    pendentes = pedidos[pedidos["status"] == "pendente"].sort_values("pedido_em")
    if status == "pendente":
        posicao = int((pendentes["pedido_em"] < pedido["pedido_em"]).sum()) + 1
        em_andamento = int((pedidos["status"] == "processando").sum())
        espera = (posicao - 1 + em_andamento + 1) * duracao
        st.info(f"**Na fila: posição {posicao}.** Tempo estimado até o resultado: cerca de "
                f"{max(1, round(espera / 60))} min. Esta área se atualiza sozinha a cada {ATUALIZAR_A_CADA_S} s.",
                icon=":material/hourglass_top:")
    else:
        inicio = pd.to_datetime(pedido.get("inicio") or pedido["pedido_em"])
        decorrido = (pd.Timestamp.now(tz=inicio.tz) - inicio).total_seconds() if inicio.tz else 0
        restante = max(duracao - decorrido, 30)
        st.info(f"**Calculando os bairros de {rotulo(municipio_id)}…** Faltam cerca de "
                f"{max(1, round(restante / 60))} min. Esta área se atualiza sozinha a cada {ATUALIZAR_A_CADA_S} s.",
                icon=":material/autorenew:")
    st.progress(0.15 if status == "pendente" else 0.6)


if resultado.empty:
    acompanhar_pedido(int(municipio_id))
    st.stop()

# --- Cidade com resultado: mapa e ranking -----------------------------------------
escala = st.segmented_control("Escala", list(ESCALAS), format_func=ESCALAS.get, default="ibge",
                              key="bairros_escala") or "ibge"
unidades = resultado[resultado[COL["escala"]] == escala].sort_values(COL["posicao"])
st.subheader(f"{rotulo(municipio_id)} · {ESCALAS[escala]}")
if unidades.empty:
    st.info(f"Nenhum bairro com {fmt.numero(POPULACAO_MINIMA_BAIRRO)} habitantes ou mais nesta escala.",
            icon=":material/search_off:")
    st.stop()

base_cnpj = resultado[COL["base_cnpj"]].dropna().iloc[0] if COL["base_cnpj"] in resultado else None
st.info(
    "**Limitações.** População, faixa de 20 a 59 anos e renda vêm do **Censo 2022** por setor. As academias são as "
    f"empresas ativas da Receita Federal{f' (base de {base_cnpj})' if base_cnpj else ''} pelo **endereço fiscal**, "
    "que pode não ser onde a academia funciona. A concorrência é contada num **raio de "
    f"{fmt.numero(RAIO_CONCORRENCIA_KM, 1)} km** do centro de cada bairro. Bairros com menos de "
    f"{fmt.numero(POPULACAO_MINIMA_BAIRRO)} habitantes ficam fora do ranking. Os bairros populares são os nomes de "
    "localidade dos endereços do IBGE, sem limite oficial.",
    icon=":material/info:",
)

# Mapa: poligono quando houver geometria, senao ponto
unidades = unidades.assign(**{COL["nome"]: unidades[COL["nome"]].astype(str)})
textos = [
    f"<b>{r[COL['posicao']]}º {r[COL['nome']]}</b><br>Nota {fmt.nota(r[COL['nota']])} · "
    f"{fmt.compacto(r[COL['populacao']])} hab.<br>Renda média do responsável {fmt.reais(r[COL['renda']], 0)}"
    f"<br>{fmt.numero(r[COL['academias']])} academias no raio ({fmt.numero(r[COL['densidade']], 2)} por 10 mil)"
    for _, r in unidades.iterrows()
]
unidades = unidades.assign(_texto=textos)


def geometria(valor):
    """GeoJSON da unidade (pode vir como texto ou objeto) ou None."""
    if isinstance(valor, str) and valor.strip():
        valor = json.loads(valor)
    return valor if isinstance(valor, dict) and valor.get("type") in ("Polygon", "MultiPolygon") else None


unidades = unidades.assign(_geo=unidades[COL["geometria"]].map(geometria) if COL["geometria"] in unidades else None)
com_geo = unidades[unidades["_geo"].notna()]
sem_geo = unidades[unidades["_geo"].isna()]
figura = go.Figure()
contorno = (dados.malha_municipios_uf(int(municipio_id) // 100_000) or {}).get(int(municipio_id))
if contorno:  # limite do municipio, so como referencia
    contorno_lon, contorno_lat = [], []
    for poligono in contorno["coordinates"]:
        for anel in poligono:
            contorno_lon += [p[0] for p in anel] + [None]
            contorno_lat += [p[1] for p in anel] + [None]
    figura.add_trace(go.Scattergeo(lon=contorno_lon, lat=contorno_lat, mode="lines", hoverinfo="skip",
                                   showlegend=False, line={"color": "rgba(242,241,236,.45)", "width": 1}))
barra = {"title": {"text": "Nota"}, "thickness": 12, "len": 0.6}
if not com_geo.empty:
    figura.add_trace(go.Choropleth(
        geojson={"type": "FeatureCollection", "features": [
            {"type": "Feature", "id": int(i), "geometry": g} for i, g in zip(com_geo.index, com_geo["_geo"])]},
        locations=[int(i) for i in com_geo.index], z=com_geo[COL["nota"]].tolist(), zmin=0, zmax=100,
        colorscale=fmt.ESCALA_DADO, marker={"line": {"color": "#0b0d0f", "width": 0.6}}, colorbar=barra,
        text=com_geo["_texto"].tolist(), hoverinfo="text"))
if not sem_geo.empty:
    figura.add_trace(go.Scattergeo(
        lon=sem_geo[COL["lon"]].astype(float).tolist(), lat=sem_geo[COL["lat"]].astype(float).tolist(),
        mode="markers", text=sem_geo["_texto"].tolist(), hoverinfo="text", showlegend=False,
        marker={"size": (10 + 26 * np.sqrt(sem_geo[COL["populacao"]] / max(unidades[COL["populacao"]].max(), 1))).tolist(),
                "color": sem_geo[COL["nota"]].tolist(), "colorscale": fmt.ESCALA_DADO, "cmin": 0, "cmax": 100,
                "opacity": 0.9, "showscale": com_geo.empty, "colorbar": barra}))
top = unidades.head(10)
figura.add_trace(go.Scattergeo(
    lon=top[COL["lon"]].astype(float).tolist(), lat=top[COL["lat"]].astype(float).tolist(), mode="text",
    text=[f"{p}º {n}" for p, n in zip(top[COL["posicao"]], top[COL["nome"]])], hoverinfo="skip",
    showlegend=False, textposition="top center", textfont={"color": "#f2f1ec", "size": 11}))
lats, lons = unidades[COL["lat"]].astype(float), unidades[COL["lon"]].astype(float)
folga = 0.02
figura.update_geos(projection_type="mercator", visible=False, bgcolor="rgba(0,0,0,0)",
                   lonaxis_range=[float(lons.min() - folga), float(lons.max() + folga)],
                   lataxis_range=[float(lats.min() - folga), float(lats.max() + folga)])
figura.update_layout(separators=",.", height=500, margin={"l": 0, "r": 0, "t": 0, "b": 0},
                     paper_bgcolor="rgba(0,0,0,0)", dragmode="pan")
st.plotly_chart(figura, config={"displaylogo": False, "scrollZoom": True},
                alt=f"Mapa dos bairros de {rotulo(municipio_id)} coloridos pela nota.")

# Ranking
colunas = {
    COL["posicao"]: st.column_config.NumberColumn("Posição", format="%dº", width="small"),
    COL["nome"]: st.column_config.TextColumn("Bairro", pinned=True),
    COL["nota"]: st.column_config.ProgressColumn("Nota", min_value=0, max_value=100, format="%.1f",
                                                 color=fmt.COR_DADO),
    COL["populacao"]: st.column_config.NumberColumn("População", format="localized"),
    COL["publico"]: st.column_config.NumberColumn("20 a 59 anos", format="localized"),
    COL["renda"]: st.column_config.NumberColumn("Renda média resp. (R$)", format="localized"),
    COL["academias"]: st.column_config.NumberColumn(f"Academias no raio de {fmt.numero(RAIO_CONCORRENCIA_KM, 1)} km",
                                                    format="%d"),
    COL["densidade"]: st.column_config.NumberColumn("Por 10 mil hab.", format="%.2f"),
    COL["massa"]: st.column_config.NumberColumn("Massa de renda por km²", format="compact"),
}
colunas = {c: v for c, v in colunas.items() if c in unidades}
st.dataframe(unidades[list(colunas)], column_config=colunas, hide_index=True,
             alt="Ranking dos bairros com nota, população, renda e academias no raio.")
calculado = resultado[COL["calculado_em"]].dropna().iloc[0] if COL["calculado_em"] in resultado else None
st.caption(
    "Nota de 0 a 100 dentro da escala: público de 20 a 59 anos 30 %, renda média do responsável 25 %, academias por "
    "10 mil hab. no raio 30 % (menor é melhor) e massa de renda por km² 15 %."
    + (f" Calculado em {fmt.data_hora(calculado)}." if calculado else "")
)
st.download_button(
    "Baixar CSV dos bairros",
    data=unidades[list(colunas)].to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
    file_name=f"radar_expansao_bairros_{municipio_id}_{escala}.csv", mime="text/csv", icon=":material/download:",
)
