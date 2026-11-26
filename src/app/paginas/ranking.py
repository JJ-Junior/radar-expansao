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
# RADAR DE EXPANSAO - ETAPA 7: DASHBOARD - PAGINA "RANKING"
# =============================================================================
#
# OBJETIVO: ranking completo das cidades do universo (P2, P5), filtravel por
#           regiao, UF, faixa de populacao e nome, com as notas de cada criterio
#           e download em CSV.
# ENTRADA:  gold.ranking_expansao (ordem e notas ja calculadas na gold)
# SAIDA:    pagina web + arquivo CSV baixado pelo usuario (so o recorte filtrado)
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - filtros com mascaras booleanas no pandas; df.to_csv
#
# NOVIDADES:
#   1. st.pills / st.multiselect / st.segmented_control -> filtros na tela
#   2. st.dataframe + column_config -> tabela com barras de nota e formatos
#   3. on_select="rerun"    -> clicar numa linha devolve a linha escolhida
#   4. st.download_button   -> baixa o recorte filtrado em CSV (padrao Excel BR:
#                              separador ";" e virgula decimal)
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: streamlit run src/app/app.py  (menu "Ranking")
#
# =============================================================================

# ============================== CONFIG ==============================
FAIXAS_POPULACAO = {
    "Todas": (0, None),
    "50 a 100 mil": (50_000, 100_000),
    "100 a 500 mil": (100_000, 500_000),
    "Acima de 500 mil": (500_000, None),
}
TOP_GRAFICO = 10
# ====================================================================

import plotly.express as px
import streamlit as st

import dados
import formato as fmt

ranking = dados.ranking_completo()

st.title("Ranking de municípios")
st.caption(
    f"{len(ranking)} cidades com 50 mil habitantes ou mais, em ordem de nota final (0 a 100). "
    "Use os filtros para ver o top de cada região ou estado."
)

# --- Filtros -----------------------------------------------------------------
with st.container(border=True):
    linha1 = st.columns([3, 2], vertical_alignment="bottom")
    with linha1[0]:
        regioes = st.pills(
            "Região", list(fmt.REGIOES), selection_mode="multi",
            format_func=lambda sigla: fmt.REGIOES[sigla], key="filtro_regiao",
        )
    ufs_disponiveis = sorted(
        ranking.loc[ranking["regiao_sigla"].isin(regioes), "uf_sigla"].unique()
        if regioes else ranking["uf_sigla"].unique()
    )
    with linha1[1]:
        ufs = st.multiselect("Estado (UF)", ufs_disponiveis, placeholder="Todos",
                             key="filtro_uf")
    linha2 = st.columns([3, 2], vertical_alignment="bottom")
    with linha2[0]:
        faixa = st.segmented_control("População", list(FAIXAS_POPULACAO), default="Todas",
                                     required=True, key="filtro_faixa")
    with linha2[1]:
        busca = st.text_input("Buscar cidade pelo nome", placeholder="Ex.: Campinas",
                              icon=":material/search:", key="filtro_busca")
    so_elegiveis = st.toggle(
        "Só cidades que podem entrar na lista recomendada", key="filtro_elegiveis",
        help="Nota de poder de compra a partir da trava de renda (gold.parametro_ranking).",
    )

filtrado = ranking
if regioes:
    filtrado = filtrado[filtrado["regiao_sigla"].isin(regioes)]
if ufs:
    filtrado = filtrado[filtrado["uf_sigla"].isin(ufs)]
minimo, maximo = FAIXAS_POPULACAO[faixa or "Todas"]
filtrado = filtrado[filtrado["populacao"] >= minimo]
if maximo:
    filtrado = filtrado[filtrado["populacao"] < maximo]
if busca:
    filtrado = filtrado[filtrado["municipio_nome"].str.contains(busca.strip(), case=False,
                                                                 regex=False)]
if so_elegiveis:
    filtrado = filtrado[filtrado["elegivel_recomendacao"]]

filtrado = filtrado.copy()
filtrado["recomendada"] = filtrado["ordem_recomendacao"].map(
    lambda v: "" if fmt.ausente(v) else f"nº {int(v)}"
)
filtrado["alertas"] = filtrado.apply(
    lambda r: " · ".join(
        a for a, ligado in (("dados incompletos", r["dados_incompletos"]),
                            ("verificar concorrência", r["verificar_concorrencia"])) if ligado
    ),
    axis=1,
)

st.caption(f"{len(filtrado)} de {len(ranking)} cidades no filtro.")

if filtrado.empty:
    st.info("Nenhuma cidade com esses filtros. Tire um filtro para ver mais cidades.",
            icon=":material/filter_alt_off:")
    st.stop()

# --- Grafico do top do recorte -----------------------------------------------
top = filtrado.nsmallest(TOP_GRAFICO, "posicao_brasil").iloc[::-1]
grafico = px.bar(
    top, x="nota_final", y=top["municipio_nome"] + " (" + top["uf_sigla"] + ")",
    orientation="h", text=top["nota_final"].map(fmt.nota),
    labels={"nota_final": "Nota final", "y": ""},
    color_discrete_sequence=[fmt.COR_DADO],
)
grafico.update_traces(textposition="outside", cliponaxis=False,
                      hovertemplate="%{y}: nota %{x:.1f}<extra></extra>")
grafico.update_layout(separators=",.", xaxis_range=[0, 100], height=40 * len(top) + 60,
                      margin={"l": 0, "r": 20, "t": 30, "b": 0},
                      title={"text": f"Top {len(top)} do recorte", "font": {"size": 15}})
st.plotly_chart(grafico, config={"displayModeBar": False},
                alt=f"Barras com a nota final das {len(top)} primeiras cidades do recorte.")

# --- Tabela --------------------------------------------------------------------
COLUNAS = {
    "posicao_brasil": st.column_config.NumberColumn("Brasil", format="%dº", width="small",
                                                    help="Posição no Brasil"),
    "posicao_regiao": st.column_config.NumberColumn("Região", format="%dº", width="small",
                                                    help="Posição na região (N, NE, SE, S, CO)"),
    "posicao_uf": st.column_config.NumberColumn("UF", format="%dº", width="small",
                                                help="Posição no estado"),
    "municipio_nome": st.column_config.TextColumn("Município", pinned=True),
    "uf_sigla": st.column_config.TextColumn("Estado", width="small"),
    "regiao_nome": st.column_config.TextColumn("Região do país"),
    "populacao": st.column_config.NumberColumn("População", format="localized"),
    "nota_final": st.column_config.ProgressColumn("Nota final", min_value=0, max_value=100,
                                                  format="%.1f", color=fmt.COR_DADO),
    "recomendada": st.column_config.TextColumn("Recomendada", width="small"),
    **{
        f"nota_{chave}": st.column_config.NumberColumn(rotulo, format="%.0f",
                                                       help=f"Nota de {rotulo.lower()} (0 a 100)")
        for chave, rotulo in fmt.CRITERIOS.items()
    },
    "alertas": st.column_config.TextColumn("Alertas"),
}
selecao = st.dataframe(
    filtrado[list(COLUNAS)], column_config=COLUNAS, hide_index=True,
    on_select="rerun", selection_mode="single-row", key="tabela_ranking",
    alt="Tabela do ranking filtrado, com posições, população, nota final e notas por critério.",
)

linhas_escolhidas = [i for i in (selecao.selection.rows if selecao else []) if i < len(filtrado)]
with st.container(horizontal=True, vertical_alignment="center"):
    if linhas_escolhidas:
        escolhida = filtrado.iloc[linhas_escolhidas[0]]
        if st.button(f"Abrir ficha de {escolhida['municipio_nome']}", icon=":material/open_in_new:"):
            st.session_state["municipio_escolhido"] = int(escolhida["municipio_id"])
            st.switch_page("paginas/municipio.py")
    else:
        st.caption("Clique numa linha para abrir a ficha do município.")

    exportar = filtrado[list(COLUNAS)].rename(columns={"regiao_nome": "regiao"})
    st.download_button(
        "Baixar CSV do recorte",
        data=exportar.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
        file_name="radar_expansao_ranking.csv", mime="text/csv",
        icon=":material/download:",
    )
