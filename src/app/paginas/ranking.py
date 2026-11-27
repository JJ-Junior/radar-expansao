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
#   5. simulador de pesos    -> sliders mudam so a media ponderada das notas da
#                              gold, para comparar; o ranking oficial nao muda
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

import numpy as np
import plotly.express as px
import streamlit as st

import acoes
import dados
import formato as fmt

ranking = dados.ranking_completo()

st.title("Ranking de municípios")
st.caption(
    f"{len(ranking)} cidades com 50 mil habitantes ou mais, em ordem de nota final (0 a 100). "
    "Use os filtros para ver o top de cada região ou estado."
)

# --- Simulador de pesos (opcional) ---------------------------------------------
criterios = dados.tabela("ranking_criterio")
PESOS_OFICIAIS = {g: round(float(p) * 100) for g, p in criterios.groupby("grupo")["peso"].sum().items()}


def voltar_ao_oficial() -> None:
    """Devolve os sliders aos pesos oficiais da gold."""
    for chave, peso in PESOS_OFICIAIS.items():
        st.session_state[f"peso_{chave}"] = peso


simular = st.toggle("Simular outros pesos", key="simular_pesos",
                    help="Recalcula só a média ponderada das notas da gold, para comparar. O ranking oficial "
                         "e a lista recomendada não mudam.")
if simular:
    with st.container(border=True):
        st.warning("Simulação: as notas por critério são as oficiais da gold; só os pesos mudam. Nada aqui "
                   "altera o ranking oficial nem as 5 recomendadas.", icon=":material/science:")
        for chave, peso in PESOS_OFICIAIS.items():
            st.session_state.setdefault(f"peso_{chave}", peso)
        colunas_peso = st.columns(len(fmt.CRITERIOS))
        pesos = {}
        for coluna, (chave, rotulo) in zip(colunas_peso, fmt.CRITERIOS.items()):
            with coluna:
                pesos[chave] = st.slider(f"{rotulo} (%)", 0, 50, step=5, key=f"peso_{chave}",
                                         help=f"Oficial: {PESOS_OFICIAIS.get(chave, 0)}%")
        soma = sum(pesos.values())
        with st.container(horizontal=True, vertical_alignment="center"):
            st.caption(f"Soma dos pesos: {soma}% (o cálculo divide pela soma, então não precisa dar 100%).")
            st.button("Voltar ao oficial", icon=":material/restart_alt:", on_click=voltar_ao_oficial,
                      key="voltar_pesos")
    if soma == 0:
        st.error("Dê peso a pelo menos um critério.", icon=":material/error:")
        st.stop()
    # Mesma regra da gold para dado faltante: divide pela soma dos pesos dos criterios disponiveis.
    notas = ranking[[f"nota_{c}" for c in pesos]].to_numpy(dtype=float)
    vetor = np.array(list(pesos.values()), dtype=float)
    disponivel = ~np.isnan(notas)
    ranking["nota_simulada"] = (np.nansum(notas * vetor, axis=1)
                                / np.where(disponivel, vetor, 0).sum(axis=1))
    ranking = ranking.sort_values(["nota_simulada", "populacao"], ascending=[False, False])
    ranking["posicao_simulada"] = range(1, len(ranking) + 1)
    ranking["variacao_posicao"] = ranking["posicao_brasil"] - ranking["posicao_simulada"]

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
grafico.update_traces(customdata=top["municipio_id"].astype(int).tolist())  # lista simples: o clique devolve o codigo
grafico.update_traces(textposition="outside", cliponaxis=False,
                      hovertemplate="%{y}: nota %{x:.1f}<extra></extra>")
grafico.update_layout(separators=",.", xaxis_range=[0, 100], height=40 * len(top) + 60,
                      margin={"l": 0, "r": 20, "t": 30, "b": 0},
                      title={"text": f"Top {len(top)} do recorte", "font": {"size": 15}})
grafico.update_traces(selected={"marker": {"opacity": 1}}, unselected={"marker": {"opacity": 1}})  # o clique nao apaga o resto
evento = st.plotly_chart(grafico, config={"displayModeBar": False}, on_select="rerun", selection_mode="points",
                         key="ranking_barras",
                         alt=f"Barras com a nota final das {len(top)} primeiras cidades do recorte.")
clicada = acoes.codigo_valido(acoes.clicado(evento))
nome_clicada = (top["municipio_nome"] + " (" + top["uf_sigla"] + ")")[top["municipio_id"] == clicada]
acoes.barra_de_acoes(clicada, nome_clicada.iloc[0] if not nome_clicada.empty else "", "ranking_acoes",
                     dica="Clique numa barra para ver a ficha ou os bairros da cidade.", onde="no gráfico")

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
if simular:
    COLUNAS = {
        "posicao_simulada": st.column_config.NumberColumn("Simulada", format="%dº", width="small",
                                                          help="Posição com os pesos simulados"),
        "variacao_posicao": st.column_config.NumberColumn("Variação", format="%+d", width="small",
                                                          help="Posições ganhas (+) ou perdidas (−)"),
        "nota_simulada": st.column_config.ProgressColumn("Nota simulada", min_value=0, max_value=100,
                                                         format="%.1f", color=fmt.COR_DESTAQUE),
        **COLUNAS,
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
