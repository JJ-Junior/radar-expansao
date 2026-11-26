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
# RADAR DE EXPANSAO - ETAPA 7: DASHBOARD - PAGINA "MOMENTO ECONOMICO"
# =============================================================================
#
# OBJETIVO: contexto macroeconomico (P6) - Selic, IPCA mensal e em 12 meses e
#           dolar ao longo do tempo - e a linha do tempo do semaforo mes a mes
#           (P7), com a justificativa de cada mes.
# ENTRADA:  gold.contexto_macro (1 linha por mes) e gold.momento_expansao
# SAIDA:    pagina web; nao grava nada
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - series temporais no pandas (datas como indice, filtro por periodo)
#
# NOVIDADES:
#   1. st.metric com delta   -> valor atual + variacao; delta_color="inverse"
#                               pinta de verde quando cair e bom (juros, inflacao)
#   2. plotly make_subplots  -> barras (IPCA do mes) e linha (IPCA 12 meses) no
#                               mesmo grafico, com dois eixos
#   3. go.Heatmap discreto   -> a "faixa" do semaforo: uma celula por mes e sinal
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: streamlit run src/app/app.py  (menu "Momento economico")
#
# =============================================================================

# ============================== CONFIG ==============================
PERIODOS = {"12 meses": 12, "3 anos": 36, "5 anos": 60, "Desde 2015": None}
PERIODO_PADRAO = "5 anos"
TETO_IPCA = 4.5   # % - limite usado pelo semaforo (spec.md, secao 5.1)
ALTURA_GRAFICO = 300
# ====================================================================

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import dados
import formato as fmt

macro = dados.tabela("contexto_macro").sort_values("mes")
momento = dados.tabela("momento_expansao").sort_values("mes")

st.title("Momento econômico")
st.caption(
    "Juros, inflação e câmbio pesam na decisão de quando abrir: juros altos alongam o retorno, "
    "inflação aperta a renda do aluno e os custos, e o dólar alto encarece equipamentos importados."
)

# --- Numeros do mes mais recente ------------------------------------------------
ultimo_selic = macro.dropna(subset=["selic_meta"]).iloc[-1]
ultimo_dolar = macro.dropna(subset=["dolar_medio"]).iloc[-1]
com_ipca = macro.dropna(subset=["ipca_12m"])
ultimo_ipca = com_ipca.iloc[-1]
ipca_3m_antes = com_ipca[com_ipca["mes"] <= ultimo_ipca["mes"] - pd.DateOffset(months=3)]
variacao_ipca = (ultimo_ipca["ipca_12m"] - ipca_3m_antes.iloc[-1]["ipca_12m"]
                 if not ipca_3m_antes.empty else None)


def parcial(linha) -> str:
    """Marca o mes ainda em andamento."""
    return " (mês em andamento)" if bool(linha.get("mes_parcial")) else ""


with st.container(horizontal=True):
    st.metric(
        f"Selic (meta) · {fmt.mes_curto(ultimo_selic['mes'])}{parcial(ultimo_selic)}",
        f"{fmt.numero(ultimo_selic['selic_meta'], 2)}% a.a.",
        delta=None if fmt.ausente(ultimo_selic["selic_var_12m_pp"])
        else f"{fmt.pontos(ultimo_selic['selic_var_12m_pp'])} em 12 meses",
        delta_color="inverse", border=True,
    )
    st.metric(
        f"IPCA em 12 meses · {fmt.mes_curto(ultimo_ipca['mes'])}",
        f"{fmt.numero(ultimo_ipca['ipca_12m'], 2)}%",
        delta=None if variacao_ipca is None else f"{fmt.pontos(variacao_ipca)} vs. 3 meses antes",
        delta_color="inverse", border=True,
        help=f"Teto usado pelo semáforo: {fmt.numero(TETO_IPCA, 1)}%.",
    )
    st.metric(
        f"Dólar médio · {fmt.mes_curto(ultimo_dolar['mes'])}{parcial(ultimo_dolar)}",
        fmt.reais(ultimo_dolar["dolar_medio"]),
        delta=None if fmt.ausente(ultimo_dolar["dolar_var_12m_pct"])
        else f"{fmt.porcentagem(ultimo_dolar['dolar_var_12m_pct'] / 100, sinal=True)} em 12 meses",
        delta_color="inverse", border=True,
    )

periodo = st.segmented_control("Período", list(PERIODOS), default=PERIODO_PADRAO,
                               required=True, key="periodo_macro")
meses = PERIODOS[periodo or PERIODO_PADRAO]
inicio = macro["mes"].max() - pd.DateOffset(months=meses - 1) if meses else macro["mes"].min()
recorte = macro[macro["mes"] >= inicio]
recorte_momento = momento[momento["mes"] >= inicio]


def estilo(figura: go.Figure, titulo: str) -> go.Figure:
    """Layout comum dos graficos da pagina."""
    figura.update_layout(
        separators=",.", title={"text": titulo, "font": {"size": 15}}, height=ALTURA_GRAFICO,
        margin={"l": 0, "r": 10, "t": 40, "b": 0}, hovermode="x unified",
        legend={"orientation": "h", "y": -0.2},
    )
    return figura


col1, col2 = st.columns(2)
with col1:
    selic = go.Figure(go.Scatter(
        x=recorte["mes"], y=recorte["selic_meta"], mode="lines", line_shape="hv",
        line={"color": fmt.COR_DADO, "width": 2.5}, name="Selic (meta)",
        hovertemplate="%{y:.2f}% a.a.<extra></extra>",
    ))
    selic.update_yaxes(ticksuffix="%")
    st.plotly_chart(estilo(selic, "Selic: meta no fim do mês (% ao ano)"),
                    config={"displayModeBar": False},
                    alt="Linha da meta da Selic no período escolhido.")
with col2:
    dolar = go.Figure(go.Scatter(
        x=recorte["mes"], y=recorte["dolar_medio"], mode="lines",
        line={"color": fmt.COR_DADO, "width": 2.5}, name="Dólar médio",
        hovertemplate="R$ %{y:.2f}<extra></extra>",
    ))
    dolar.update_yaxes(tickprefix="R$ ")
    st.plotly_chart(estilo(dolar, "Dólar: média do mês (R$)"), config={"displayModeBar": False},
                    alt="Linha do dólar médio mensal no período escolhido.")

ipca = make_subplots(specs=[[{"secondary_y": True}]])
ipca.add_trace(go.Bar(x=recorte["mes"], y=recorte["ipca_mensal"], name="IPCA do mês",
                      marker_color=fmt.COR_DADO_2, opacity=0.55,
                      hovertemplate="mês: %{y:.2f}%<extra></extra>"), secondary_y=False)
ipca.add_trace(go.Scatter(x=recorte["mes"], y=recorte["ipca_12m"], name="IPCA em 12 meses",
                          mode="lines", line={"color": fmt.COR_DADO, "width": 2.5},
                          hovertemplate="12 meses: %{y:.2f}%<extra></extra>"), secondary_y=True)
ipca.add_hline(y=TETO_IPCA, line_dash="dot", line_color=fmt.COR_SINAL["vermelho"],
               annotation_text=f"teto do semáforo ({fmt.numero(TETO_IPCA, 1)}%)",
               annotation_position="top left", secondary_y=True)
ipca.update_yaxes(title_text="mês (%)", ticksuffix="%", secondary_y=False, showgrid=False)
ipca.update_yaxes(title_text="12 meses (%)", ticksuffix="%", secondary_y=True)
st.plotly_chart(estilo(ipca, "Inflação (IPCA): mês a mês e acumulada em 12 meses"),
                config={"displayModeBar": False},
                alt="Barras do IPCA mensal e linha do IPCA acumulado em 12 meses, com o teto de 4,5%.")

# --- Linha do tempo do semaforo --------------------------------------------------
st.subheader("Semáforo mês a mês")
st.caption(
    "Cada sinal vale +1 (verde), 0 (amarelo) ou −1 (vermelho). Soma ≥ +2: expandir agora; "
    "0 ou +1: expandir com cautela; ≤ −1: esperar. Só entram meses com os três sinais "
    "(o IPCA sai cerca de um mês depois)."
)
if recorte_momento.empty:
    st.info("Sem meses com os três sinais neste período.", icon=":material/info:")
else:
    valor_sinal = {"vermelho": -1, "amarelo": 0, "verde": 1}
    valor_recomendacao = {"Esperar": -1, "Expandir com cautela": 0, "Expandir agora": 1}
    linhas = {
        "Juros": recorte_momento["sinal_juros"].map(valor_sinal),
        "Inflação": recorte_momento["sinal_inflacao"].map(valor_sinal),
        "Câmbio": recorte_momento["sinal_cambio"].map(valor_sinal),
        "Recomendação": recorte_momento["recomendacao"].map(valor_recomendacao),
    }
    textos = [
        [f"{fmt.mes_curto(m)}: {t}" for m, t in zip(recorte_momento["mes"], coluna)]
        for coluna in (
            recorte_momento["sinal_juros"], recorte_momento["sinal_inflacao"],
            recorte_momento["sinal_cambio"],
            recorte_momento["recomendacao"] + " (pontuação "
            + recorte_momento["pontuacao"].astype(int).map("{:+d}".format) + ")",
        )
    ]
    escala = [
        [0.0, fmt.COR_SINAL["vermelho"]], [0.333, fmt.COR_SINAL["vermelho"]],
        [0.333, fmt.COR_SINAL["amarelo"]], [0.666, fmt.COR_SINAL["amarelo"]],
        [0.666, fmt.COR_SINAL["verde"]], [1.0, fmt.COR_SINAL["verde"]],
    ]
    faixa = go.Figure(go.Heatmap(
        z=[list(v) for v in linhas.values()][::-1], x=recorte_momento["mes"],
        y=list(linhas)[::-1], text=textos[::-1], hoverinfo="text",
        colorscale=escala, zmin=-1, zmax=1, showscale=False, xgap=2, ygap=4,
    ))
    faixa.update_layout(separators=",.", height=230, margin={"l": 0, "r": 10, "t": 10, "b": 0})
    st.plotly_chart(faixa, config={"displayModeBar": False},
                    alt="Faixa colorida com os sinais de juros, inflação e câmbio e a "
                        "recomendação de cada mês.")

    tabela_meses = recorte_momento.sort_values("mes", ascending=False).assign(
        Mês=lambda d: d["mes"].map(fmt.mes_curto),
    )[["Mês", "recomendacao", "pontuacao", "justificativa"]]
    st.dataframe(
        tabela_meses, hide_index=True, height=320,
        column_config={
            "recomendacao": st.column_config.TextColumn("Recomendação"),
            "pontuacao": st.column_config.NumberColumn("Pontuação", format="%+d"),
            "justificativa": st.column_config.TextColumn("Por quê", width="large"),
        },
        alt="Tabela com a recomendação e a justificativa de cada mês.",
    )

st.caption("Fontes: Banco Central do Brasil (SGS: Selic meta, série 432; dólar, série 10813) e "
           "IBGE (IPCA, agregado 7060).")
