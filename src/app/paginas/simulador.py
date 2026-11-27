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
# RADAR DE EXPANSAO - ETAPA 7: DASHBOARD - PAGINA "SIMULADOR DE REGIAO"
# =============================================================================
#
# OBJETIVO: responder a P9: num raio de X km de uma cidade, quais sao as melhores
#           candidatas e quanto espaco ha para novas academias. A distancia e
#           calculada aqui (haversine); notas e estimativas vem prontas da gold.
# ENTRADA:  gold.indicadores_municipio (coordenadas, populacao projetada,
#           densidade de referencia, lacuna de academias), gold.ranking_expansao
#           e gold.parametro_ranking (premissas das estimativas)
# SAIDA:    pagina web + CSV baixado pelo usuario; nao grava nada
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - merge, filtro e soma no pandas; numpy para contas com colunas inteiras
#
# NOVIDADES:
#   1. formula de haversine -> distancia em linha reta entre dois pontos da
#                              Terra a partir de latitude e longitude
#   2. contas vetorizadas    -> numpy calcula a distancia para os 5.571
#                              municipios de uma vez, sem laco
#   3. st.slider             -> raio escolhido pelo usuario (10 a 300 km)
#   4. circulo no mapa       -> pontos a uma distancia fixa do centro, em todas
#                              as direcoes (formula do "ponto de destino")
#   5. go.Choropleth         -> pinta o contorno de cada municipio (malha do IBGE,
#                              um TopoJSON por UF, so das UFs do raio) pela nota
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: streamlit run src/app/app.py  (menu "Simulador de regiao")
#
# =============================================================================

# ============================== CONFIG ==============================
RAIO_TERRA_KM = 6371.0
RAIO_MIN_KM, RAIO_MAX_KM, RAIO_PADRAO_KM, PASSO_RAIO_KM = 10, 300, 100, 10
CIDADE_PADRAO = 3506003          # Bauru (SP), exemplo do squad
CHAVE_ESCOLHIDO = "municipio_escolhido"
CHAVE_CENTRO = "simulador_centro"
PONTOS_CIRCULO = 180
FOLGA_MAPA = 1.12                # mapa mostra o circulo com 12% de folga
ALTURA_MAPA = 560
ROTULOS_MAPA = 10                # nome no mapa so para as 10 primeiras do raio
# ====================================================================

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import acoes
import dados
import formato as fmt


def distancia_km(lat0: float, lon0: float, lats, lons) -> np.ndarray:
    """Haversine: distancia em linha reta (km) do ponto (lat0, lon0) ate cada ponto."""
    fi0, fi = np.radians(lat0), np.radians(np.asarray(lats, dtype=float))
    d_fi = fi - fi0
    d_lambda = np.radians(np.asarray(lons, dtype=float) - lon0)
    a = np.sin(d_fi / 2) ** 2 + np.cos(fi0) * np.cos(fi) * np.sin(d_lambda / 2) ** 2
    return 2 * RAIO_TERRA_KM * np.arcsin(np.sqrt(a))


def circulo(lat0: float, lon0: float, raio: float) -> tuple[np.ndarray, np.ndarray]:
    """Pontos (lat, lon) a 'raio' km do centro, em volta inteira."""
    fi0, lambda0, delta = np.radians(lat0), np.radians(lon0), raio / RAIO_TERRA_KM
    rumo = np.linspace(0, 2 * np.pi, PONTOS_CIRCULO)
    fi = np.arcsin(np.sin(fi0) * np.cos(delta) + np.cos(fi0) * np.sin(delta) * np.cos(rumo))
    lam = lambda0 + np.arctan2(np.sin(rumo) * np.sin(delta) * np.cos(fi0),
                               np.cos(delta) - np.sin(fi0) * np.sin(fi))
    return np.degrees(fi), np.degrees(lam)


municipios = dados.municipios_completos().dropna(subset=["latitude", "longitude"])
ano_projecao = int(dados.parametro("ano_projecao_populacao", 2028))
faixas = int(dados.parametro("faixas_renda_referencia", 5))
tem_estimativas = "lacuna_academias" in municipios.columns

st.title("Simulador de região")
st.caption(
    "Escolha uma cidade e um raio: o simulador mostra as melhores candidatas da região, pela nota do ranking, "
    "e quanto espaço estimado há para novas academias. Distância em linha reta entre os centros dos municípios."
)

# --- Entradas ----------------------------------------------------------------------
rotulos = {
    r.municipio_id: f"{r.municipio_nome} ({r.uf_sigla})"
    for r in municipios.sort_values(["municipio_nome", "uf_sigla"]).itertuples()
}
opcoes = list(rotulos)
if CHAVE_CENTRO not in st.session_state:
    inicial = st.session_state.get(CHAVE_ESCOLHIDO, CIDADE_PADRAO)
    st.session_state[CHAVE_CENTRO] = inicial if inicial in rotulos else opcoes[0]

with st.container(border=True):
    col_cidade, col_raio = st.columns([3, 2], vertical_alignment="bottom")
    with col_cidade:
        centro_id = st.selectbox("Cidade central (qualquer município; digite parte do nome)", opcoes,
                                 format_func=lambda i: rotulos[i], key=CHAVE_CENTRO)
    with col_raio:
        raio = st.slider("Raio (km)", RAIO_MIN_KM, RAIO_MAX_KM, RAIO_PADRAO_KM, PASSO_RAIO_KM,
                         key="simulador_raio")
    incluir_pequenas = st.toggle(
        "Incluir cidades com menos de 50 mil habitantes na tabela e no mapa", key="simulador_pequenas",
        help="Elas não têm nota no ranking; aparecem com os indicadores e a lacuna estimada.",
    )

centro = municipios.loc[municipios["municipio_id"] == centro_id].iloc[0]
municipios = municipios.assign(
    distancia_km=distancia_km(centro["latitude"], centro["longitude"],
                              municipios["latitude"], municipios["longitude"])
)
regiao = municipios[municipios["distancia_km"] <= raio].copy()
universo = regiao[regiao["no_universo"]].sort_values("nota_final", ascending=False)
universo["posicao_raio"] = range(1, len(universo) + 1)
pequenas = regiao[~regiao["no_universo"]].sort_values("distancia_km")

# --- Resumo da regiao (todos os municipios do raio) ------------------------------
st.subheader(f"{centro['municipio_nome']} ({centro['uf_sigla']}) e {fmt.numero(raio)} km em volta")
com_renda = regiao.dropna(subset=["renda_dom_per_capita", "populacao"])
renda_media = ((com_renda["renda_dom_per_capita"] * com_renda["populacao"]).sum()
               / com_renda["populacao"].sum()) if not com_renda.empty else None
populacao_total = regiao["populacao"].sum()
academias_total = regiao["academias_qtd"].sum()
with st.container(horizontal=True):
    st.metric("Municípios no raio", fmt.numero(len(regiao)), border=True,
              help=f"{len(universo)} com 50 mil habitantes ou mais (com nota) e {len(pequenas)} menores.")
    st.metric("População", fmt.compacto(populacao_total), border=True,
              help="Soma da população estimada mais recente de todos os municípios do raio.")
    if tem_estimativas:
        st.metric(f"População {ano_projecao} (estimativa)",
                  fmt.compacto(regiao["populacao_projetada"].sum()), border=True)
    st.metric("Renda domiciliar per capita", fmt.reais(renda_media, 0), border=True,
              help="Média ponderada pela população (Censo 2022).")
    st.metric("Academias registradas", fmt.numero(academias_total), border=True,
              help=f"Densidade da região: {fmt.numero(academias_total / populacao_total * 10_000, 2)} "
                   "academias por 10 mil habitantes." if populacao_total else None)
    if tem_estimativas:
        lacunas = regiao["lacuna_academias"].dropna()
        st.metric("Espaço estimado (lacuna)", f"+{fmt.numero(lacunas[lacunas > 0].sum())} academias",
                  border=True,
                  help=f"Soma das lacunas positivas dos municípios do raio. {int((lacunas < 0).sum())} "
                       "municípios estão acima da densidade de referência (saturados).")

if tem_estimativas:
    st.info(
        f"**Estimativas simples, não são previsão garantida.** População {ano_projecao}: população atual × "
        f"(1 + crescimento anual desde o Censo 2022) elevado aos anos até {ano_projecao}. Lacuna de academias: "
        f"(densidade de referência − densidade atual) × população ÷ 10 mil, em que a densidade de referência é a "
        f"mediana de academias por 10 mil habitantes das cidades do universo na mesma faixa de renda "
        f"({faixas} faixas). Positiva = espaço estimado; negativa = mercado saturado em relação a cidades "
        "parecidas. Não considera tamanho nem preço das academias, nem estúdios informais.",
        icon=":material/info:",
    )

# --- Mapa -------------------------------------------------------------------------
# Contorno de cada municipio do raio, pintado pela nota (malha do IBGE por UF, so das UFs
# que aparecem no raio). Sem o arquivo da malha, o municipio vira um ponto, como antes.
circ_lat, circ_lon = circulo(centro["latitude"], centro["longitude"], raio)
meia_altura = (circ_lat.max() - circ_lat.min()) / 2 * FOLGA_MAPA
meia_largura = (circ_lon.max() - circ_lon.min()) / 2 * FOLGA_MAPA
divisa_lon, divisa_lat = dados.contornos_ufs()

contornos: dict = {}
for uf in sorted({int(i) // 100_000 for i in regiao["municipio_id"]}):
    contornos.update(dados.malha_municipios_uf(uf) or {})


def hover(df: pd.DataFrame) -> list[str]:
    """Texto ao passar o mouse: nome, nota, populacao e lacuna."""
    textos = []
    for r in df.itertuples():
        partes = [f"<b>{r.municipio_nome} ({r.uf_sigla})</b>",
                  f"{fmt.numero(r.distancia_km)} km do centro · {fmt.compacto(r.populacao)} hab."]
        if not fmt.ausente(getattr(r, "nota_final", None)):
            partes.append(f"Nota {fmt.nota(r.nota_final)} · {r.posicao_raio}º no raio")
        else:
            partes.append("Sem nota (menos de 50 mil habitantes)")
        if tem_estimativas and not fmt.ausente(r.lacuna_academias):
            partes.append(f"Lacuna estimada {int(r.lacuna_academias):+d} academias")
        textos.append("<br>".join(partes))
    return textos


def poligonos(df: pd.DataFrame, **estilo) -> go.Choropleth | None:
    """Uma camada com o contorno dos municipios de df que tem malha."""
    com_malha = df[df["municipio_id"].isin(contornos.keys())]
    if com_malha.empty:
        return None
    geojson = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": int(i), "geometry": contornos[int(i)]} for i in com_malha["municipio_id"]]}
    return go.Choropleth(geojson=geojson, locations=com_malha["municipio_id"].astype(int).tolist(),
                         customdata=com_malha["municipio_id"].astype(int).tolist(),
                         text=hover(com_malha), hoverinfo="text", **estilo)


def pontos(df: pd.DataFrame, com_nota: bool) -> go.Scattergeo | None:
    """Municipios sem malha (arquivo ausente ou municipio novo) viram pontos, como antes."""
    sem_malha = df[~df["municipio_id"].isin(contornos.keys())]
    if sem_malha.empty:
        return None
    if com_nota:  # tamanho pela populacao, cor pela nota
        marcador = {"size": (8 + 30 * np.sqrt(sem_malha["populacao"] / max(df["populacao"].max(), 1))).tolist(),
                    "color": sem_malha["nota_final"].tolist(), "colorscale": fmt.ESCALA_DADO, "cmin": 0, "cmax": 100,
                    "opacity": 0.9, "showscale": len(sem_malha) == len(df),
                    "colorbar": {"title": {"text": "Nota"}, "thickness": 12, "len": 0.6}}
    else:
        marcador = {"size": 5, "color": "#8a929b", "opacity": 0.6}
    return go.Scattergeo(lon=sem_malha["longitude"].tolist(), lat=sem_malha["latitude"].tolist(), mode="markers",
                         marker=marcador, text=hover(sem_malha), hoverinfo="text", showlegend=False,
                         customdata=sem_malha["municipio_id"].astype(int).tolist())


borda = {"line": {"color": "#0b0d0f", "width": 0.5}}
camadas = []
if incluir_pequenas and not pequenas.empty:
    camadas += [
        poligonos(pequenas, z=[0] * len(pequenas), colorscale=[[0, "#3b4249"], [1, "#3b4249"]],
                  showscale=False, marker=borda, name="Menos de 50 mil (sem nota)"),
        pontos(pequenas, com_nota=False),
    ]
if not universo.empty:
    camadas += [
        poligonos(universo, z=universo.loc[universo["municipio_id"].isin(contornos.keys()), "nota_final"].tolist(),
                  colorscale=fmt.ESCALA_DADO, zmin=0, zmax=100, marker=borda, name="Cidades do ranking",
                  colorbar={"title": {"text": "Nota"}, "thickness": 12, "len": 0.6}),
        pontos(universo, com_nota=True),
    ]
figura = go.Figure([c for c in camadas if c is not None])
figura.add_trace(go.Scattergeo(lon=divisa_lon, lat=divisa_lat, mode="lines", hoverinfo="skip",
                               showlegend=False, line={"color": "rgba(242,241,236,.45)", "width": 1}))
figura.add_trace(go.Scattergeo(lon=circ_lon.tolist(), lat=circ_lat.tolist(), mode="lines", hoverinfo="skip",
                               name=f"Raio de {raio} km",
                               line={"color": fmt.COR_MARCA, "width": 1.5, "dash": "dot"}))
if int(centro_id) in contornos:  # contorno destacado da cidade central
    contorno_lon, contorno_lat = [], []
    for poligono in contornos[int(centro_id)]["coordinates"]:
        for anel in poligono:
            contorno_lon += [p[0] for p in anel] + [None]
            contorno_lat += [p[1] for p in anel] + [None]
    figura.add_trace(go.Scattergeo(lon=contorno_lon, lat=contorno_lat, mode="lines", hoverinfo="skip",
                                   showlegend=False, line={"color": fmt.COR_DESTAQUE, "width": 2.5}))
rotulos_mapa = universo[universo["posicao_raio"] <= ROTULOS_MAPA]
if not rotulos_mapa.empty:
    figura.add_trace(go.Scattergeo(
        lon=rotulos_mapa["longitude"].tolist(), lat=rotulos_mapa["latitude"].tolist(), mode="text", hoverinfo="skip",
        showlegend=False, text=[f"{p}º {n}" for p, n in zip(rotulos_mapa["posicao_raio"],
                                                            rotulos_mapa["municipio_nome"])],
        textposition="top center", textfont={"color": "#f2f1ec", "size": 11},
    ))
figura.add_trace(go.Scattergeo(
    lon=[float(centro["longitude"])], lat=[float(centro["latitude"])], mode="markers+text", name="Cidade central",
    marker={"symbol": "star", "size": 18, "color": fmt.COR_DESTAQUE, "line": {"width": 1, "color": "#0b0d0f"}},
    text=[centro["municipio_nome"]], textposition="bottom center", textfont={"color": "#f2f1ec", "size": 13},
    hoverinfo="skip",
))
figura.update_geos(
    projection_type="mercator", visible=False, bgcolor="rgba(0,0,0,0)",
    lonaxis_range=[float(centro["longitude"] - meia_largura), float(centro["longitude"] + meia_largura)],
    lataxis_range=[float(centro["latitude"] - meia_altura), float(centro["latitude"] + meia_altura)],
)
figura.update_layout(
    separators=",.", height=ALTURA_MAPA, margin={"l": 0, "r": 0, "t": 0, "b": 0},
    legend={"orientation": "h", "y": 0.01, "x": 0.01}, paper_bgcolor="rgba(0,0,0,0)", dragmode="pan",
)
figura.update_traces(selector={"type": "choropleth"}, selected={"marker": {"opacity": 1}}, unselected={"marker": {"opacity": 1}})
figura.update_traces(selector={"type": "scattergeo"}, selected={"marker": {"opacity": 1}, "textfont": {"color": "#f2f1ec"}},
                     unselected={"marker": {"opacity": 1}, "textfont": {"color": "#f2f1ec"}})  # o clique nao apaga o resto
evento = st.plotly_chart(figura, config={"displaylogo": False, "scrollZoom": True}, on_select="rerun",
                         selection_mode="points", key=f"simulador_mapa_{centro_id}_{raio}_{incluir_pequenas}",
                         alt=f"Mapa da região de {fmt.numero(raio)} km em volta de {centro['municipio_nome']}, com "
                             "o contorno de cada município colorido pela nota do ranking.")
clicado = acoes.codigo_valido(acoes.clicado(evento))
no_universo = set(universo["municipio_id"].astype(int))
acoes.barra_de_acoes(clicado, rotulos.get(clicado, str(clicado)), "simulador_acoes",
                     cidade=clicado in no_universo)

# --- Ranking local ----------------------------------------------------------------
st.subheader("Melhores candidatas no raio")
if universo.empty:
    st.info("Nenhuma cidade com 50 mil habitantes ou mais dentro do raio. Aumente o raio ou ligue a opção das "
            "cidades menores.", icon=":material/search_off:")

tabela = pd.concat([universo, pequenas] if incluir_pequenas else [universo], ignore_index=True)
if not tabela.empty:
    tabela["recomendada"] = tabela["ordem_recomendacao"].map(
        lambda v: "" if fmt.ausente(v) else f"nº {int(v)}")
    colunas = {
        "posicao_raio": st.column_config.NumberColumn("No raio", format="%dº", width="small"),
        "posicao_brasil": st.column_config.NumberColumn("Brasil", format="%dº", width="small"),
        "municipio_nome": st.column_config.TextColumn("Município", pinned=True),
        "uf_sigla": st.column_config.TextColumn("UF", width="small"),
        "distancia_km": st.column_config.NumberColumn("Distância (km)", format="%.0f"),
        "nota_final": st.column_config.ProgressColumn("Nota final", min_value=0, max_value=100, format="%.1f",
                                                      color=fmt.COR_DADO),
        **{f"nota_{c}": st.column_config.NumberColumn(
            r, format="%.0f", help=f"{fmt.TEXTO_CURTO_CRITERIO[c]}. Nota de 0 a 100 (percentil).")
           for c, r in fmt.CRITERIOS.items()},
        "populacao": st.column_config.NumberColumn("População", format="localized"),
        "recomendada": st.column_config.TextColumn("Recomendada", width="small"),
    }
    if tem_estimativas:
        colunas["populacao_projetada"] = st.column_config.NumberColumn(
            f"População {ano_projecao} (est.)", format="localized")
        colunas["lacuna_academias"] = st.column_config.NumberColumn(
            "Lacuna (est.)", format="%+d", help="Academias a mais (+) ou a menos (−) que a referência da faixa de renda.")
        colunas["academias_qtd"] = st.column_config.NumberColumn("Academias", format="%d")
    st.dataframe(tabela[list(colunas)], column_config=colunas, hide_index=True,
                 alt="Tabela das cidades no raio com posição, distância, notas e estimativas.")
    st.caption(
        "Posição no raio = ordem da nota final entre as cidades do ranking dentro do raio. "
        + ("Cidades com menos de 50 mil habitantes vêm depois, por distância, sem nota. " if incluir_pequenas else "")
        + "A lista oficial das 5 recomendadas não muda com o simulador."
    )
    st.download_button(
        "Baixar CSV da região",
        data=tabela[list(colunas)].to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
        file_name=f"radar_expansao_regiao_{centro_id}_{raio}km.csv", mime="text/csv",
        icon=":material/download:",
    )
