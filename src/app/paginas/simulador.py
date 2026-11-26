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
circ_lat, circ_lon = circulo(centro["latitude"], centro["longitude"], raio)
meia_altura = (circ_lat.max() - circ_lat.min()) / 2 * FOLGA_MAPA
meia_largura = (circ_lon.max() - circ_lon.min()) / 2 * FOLGA_MAPA
divisa_lon, divisa_lat = dados.contornos_ufs()

figura = go.Figure()
figura.add_trace(go.Scatter(x=divisa_lon, y=divisa_lat, mode="lines", hoverinfo="skip",
                            showlegend=False, line={"color": "rgba(242,241,236,.28)", "width": 0.8}))
figura.add_trace(go.Scatter(x=circ_lon, y=circ_lat, mode="lines", hoverinfo="skip",
                            name=f"Raio de {raio} km",
                            line={"color": fmt.COR_MARCA, "width": 1.5, "dash": "dot"}))


def hover(df: pd.DataFrame) -> pd.Series:
    """Texto ao passar o mouse."""
    texto = ("<b>" + df["municipio_nome"] + " (" + df["uf_sigla"] + ")</b><br>"
             + df["distancia_km"].map(lambda d: fmt.numero(d)) + " km · "
             + df["populacao"].map(fmt.compacto) + " hab.")
    if "nota_final" in df:
        texto = texto + df["nota_final"].map(
            lambda n: "" if fmt.ausente(n) else f"<br>Nota {fmt.nota(n)}")
    if tem_estimativas:
        texto = texto + df["lacuna_academias"].map(
            lambda v: "" if fmt.ausente(v) else f"<br>Lacuna estimada {int(v):+d} academias")
    return texto


tamanho_max = max(regiao["populacao"].max(), 1) if not regiao.empty else 1
if incluir_pequenas and not pequenas.empty:
    figura.add_trace(go.Scatter(
        x=pequenas["longitude"], y=pequenas["latitude"], mode="markers", name="Menos de 50 mil (sem nota)",
        marker={"size": 5, "color": "#8a929b", "opacity": 0.6}, text=hover(pequenas), hoverinfo="text",
    ))
if not universo.empty:
    figura.add_trace(go.Scatter(
        x=universo["longitude"], y=universo["latitude"], mode="markers+text", name="Cidades do ranking",
        marker={"size": 8 + 30 * np.sqrt(universo["populacao"] / tamanho_max),
                "color": universo["nota_final"], "colorscale": fmt.ESCALA_DADO, "cmin": 0, "cmax": 100,
                "opacity": 0.9, "line": {"width": 0},
                "colorbar": {"title": {"text": "Nota"}, "thickness": 12, "len": 0.6}},
        text=[f"{p}º {n}" if p <= ROTULOS_MAPA else ""
              for p, n in zip(universo["posicao_raio"], universo["municipio_nome"])],
        textposition="top center", textfont={"color": "#f2f1ec", "size": 11},
        hovertext=hover(universo), hoverinfo="text",
    ))
figura.add_trace(go.Scatter(
    x=[centro["longitude"]], y=[centro["latitude"]], mode="markers+text", name="Cidade central",
    marker={"symbol": "star", "size": 18, "color": fmt.COR_DESTAQUE, "line": {"width": 1, "color": "#0b0d0f"}},
    text=[centro["municipio_nome"]], textposition="bottom center", textfont={"color": "#f2f1ec", "size": 13},
    hoverinfo="skip",
))
eixo = {"visible": False, "showgrid": False, "zeroline": False}
figura.update_layout(
    separators=",.", height=ALTURA_MAPA, margin={"l": 0, "r": 0, "t": 0, "b": 0},
    xaxis={**eixo, "range": [centro["longitude"] - meia_largura, centro["longitude"] + meia_largura]},
    # um grau de longitude encolhe com o cosseno da latitude
    yaxis={**eixo, "range": [centro["latitude"] - meia_altura, centro["latitude"] + meia_altura],
           "scaleanchor": "x", "scaleratio": 1 / np.cos(np.radians(centro["latitude"]))},
    legend={"orientation": "h", "y": 0.01, "x": 0.01}, plot_bgcolor="rgba(0,0,0,0)", dragmode="pan",
)
st.plotly_chart(figura, config={"displaylogo": False, "scrollZoom": True},
                alt=f"Mapa da região de {fmt.numero(raio)} km em volta de {centro['municipio_nome']}, com "
                    "as cidades coloridas pela nota e dimensionadas pela população.")

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
        **{f"nota_{c}": st.column_config.NumberColumn(r, format="%.0f") for c, r in fmt.CRITERIOS.items()},
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
