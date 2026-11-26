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
# RADAR DE EXPANSAO - ETAPA 7: DASHBOARD - PAGINA "MUNICIPIO"
# =============================================================================
#
# OBJETIVO: ficha de uma cidade do universo (P1, P3, P4, P8): nota final,
#           posicoes, nota e peso de cada criterio, indicadores com percentil e
#           os alertas (dados incompletos, verificar concorrencia).
# ENTRADA:  gold.ranking_expansao, gold.ranking_criterio,
#           gold.indicadores_municipio
# SAIDA:    pagina web; nao grava nada
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - merge, groupby e mediana no pandas
#
# NOVIDADES:
#   1. st.selectbox com busca -> digitar parte do nome filtra a lista
#   2. st.session_state      -> a cidade escolhida em outra pagina chega aqui
#   3. Series.rank(pct=True) -> percentil do indicador no universo (so para
#                               mostrar; as notas do ranking vem prontas da gold)
#   4. plotly add_vline      -> linha de referencia (nota 50 = mediana)
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: streamlit run src/app/app.py  (menu "Municipio")
#
# =============================================================================

# ============================== CONFIG ==============================
CHAVE_ESCOLHIDO = "municipio_escolhido"   # gravada pela visao geral e pelo ranking
CHAVE_SELETOR = "seletor_municipio"
# Indicadores da ficha: coluna -> (rotulo, coluna do ano, formato)
INDICADORES = {
    "populacao": ("População estimada", "populacao_ano", "inteiro"),
    "populacao_censo_2022": ("População no Censo 2022", None, "inteiro"),
    "crescimento_pop_aa": ("Crescimento da população (ao ano, desde 2022)", "populacao_ano", "taxa"),
    "pib_mil_reais": ("PIB", "pib_ano", "pib"),
    "pib_per_capita": ("PIB per capita", "pib_ano", "reais"),
    "pib_per_capita_tendencia": ("Tendência do PIB per capita (CAGR ao ano)", "pib_ano", "taxa"),
    "renda_dom_per_capita": ("Renda domiciliar per capita", "renda_ano", "reais"),
    "academias_qtd": ("Academias registradas (CNAE 93.13-1)", "academias_ano", "inteiro"),
    "academias_por_10mil_hab": ("Academias por 10 mil habitantes", "academias_ano", "decimal"),
    "salario_medio": ("Salário médio mensal (empregos formais)", "salario_ano", "reais"),
}
# ====================================================================

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import dados
import formato as fmt

ranking = dados.ranking_completo()
indicadores = dados.tabela("indicadores_municipio")
criterios = dados.tabela("ranking_criterio")
lista = dados.recomendadas()

st.title("Ficha do município")

# --- Escolha da cidade -----------------------------------------------------------
opcoes = ranking["municipio_id"].tolist()
rotulos = {
    r.municipio_id: f"{r.municipio_nome} ({r.uf_sigla}) · {r.posicao_brasil}º"
    for r in ranking.itertuples()
}
escolhido = st.session_state.get(CHAVE_ESCOLHIDO, opcoes[0])
if escolhido not in rotulos:
    escolhido = opcoes[0]
if st.session_state.get(CHAVE_SELETOR) != escolhido:
    st.session_state[CHAVE_SELETOR] = escolhido  # antes de desenhar o seletor: permitido



def guardar_escolha() -> None:
    """Guarda a cidade escolhida fora do seletor (a chave do seletor some ao trocar de página)."""
    st.session_state[CHAVE_ESCOLHIDO] = st.session_state[CHAVE_SELETOR]


municipio_id = st.selectbox(
    "Cidade (digite parte do nome)", opcoes, format_func=lambda i: rotulos[i],
    key=CHAVE_SELETOR, on_change=guardar_escolha,
    help="Só cidades com 50 mil habitantes ou mais têm nota no ranking.",
)

cidade = ranking.loc[ranking["municipio_id"] == municipio_id].iloc[0]
ind = indicadores.loc[indicadores["municipio_id"] == municipio_id].iloc[0]

st.header(f"{cidade['municipio_nome']} · {cidade['uf_sigla']}")
st.caption(
    f"Região {fmt.REGIOES.get(cidade['regiao_sigla'], cidade['regiao_sigla'])} · "
    f"região intermediária de {cidade.get('regiao_intermediaria_nome') or fmt.TRACO} · "
    f"região imediata de {cidade['regiao_imediata_nome']}"
)

# --- Situacao na lista recomendada e alertas ------------------------------------
with st.container(horizontal=True):
    if cidade["recomendado_top5"]:
        st.badge(f"Recomendada nº {int(cidade['ordem_recomendacao'])}", color="primary",
                 icon=":material/star:")
    elif cidade["elegivel_recomendacao"]:
        st.badge("Pode entrar na lista recomendada", color="blue", icon=":material/check:")
    else:
        st.badge("Abaixo da trava de renda", color="gray", icon=":material/block:")
    if cidade["dados_incompletos"]:
        ausentes = ", ".join(fmt.COMPONENTES.get(c, (c,))[0] for c in cidade["criterios_ausentes"])
        st.badge("Dados incompletos", color="orange", icon=":material/info:",
                 help=f"Faltou: {ausentes or 'não informado'}. O peso foi redistribuído entre os "
                      "critérios disponíveis.")
    if cidade["verificar_concorrencia"]:
        st.badge("Verificar concorrência", color="orange", icon=":material/search:",
                 help="Nenhuma academia registrada na CNAE 93.13-1: pode ser falta de mercado, "
                      "academias em outra atividade ou estúdios informais. Checar no local.")

if not cidade["recomendado_top5"]:
    motivo = dados.motivo_fora_da_lista(cidade, lista)
    if motivo:
        st.caption(f"Fora da lista recomendada: {motivo}.")

# --- Nota e posicoes ---------------------------------------------------------------
total_regiao = int((ranking["regiao_sigla"] == cidade["regiao_sigla"]).sum())
total_uf = int((ranking["uf_sigla"] == cidade["uf_sigla"]).sum())
with st.container(horizontal=True):
    st.metric("Nota final (0 a 100)", fmt.nota(cidade["nota_final"]), border=True)
    st.metric("No Brasil", fmt.ordinal(cidade["posicao_brasil"]), border=True,
              help=f"de {len(ranking)} cidades")
    st.metric(f"Na região {cidade['regiao_sigla']}", fmt.ordinal(cidade["posicao_regiao"]),
              border=True, help=f"de {total_regiao} cidades")
    st.metric(f"Em {cidade['uf_sigla']}", fmt.ordinal(cidade["posicao_uf"]), border=True,
              help=f"de {total_uf} cidades")

fortes = fmt.pontos_fortes(cidade)
fracos = fmt.pontos_fracos(cidade)
st.markdown(
    "**Pontos fortes:** " + " e ".join(f"{r} ({fmt.numero(v)})" for r, v in fortes)
    + ". **Pontos de atenção:** " + " e ".join(f"{r} ({fmt.numero(v)})" for r, v in fracos) + "."
)

# --- Criterios: nota e peso -------------------------------------------------------
st.subheader("Nota de cada critério")
peso_grupo = criterios.groupby("grupo")["peso"].sum()
col_grafico, col_tabela = st.columns([3, 2])
with col_grafico:
    barras = [
        (f"{rotulo} · {fmt.porcentagem(peso_grupo.get(chave), 0)}", nota_valor)
        for chave, rotulo, nota_valor in fmt.notas_por_criterio(cidade)
    ][::-1]
    figura = go.Figure(go.Bar(
        x=[b[1] for b in barras], y=[b[0] for b in barras], orientation="h",
        marker_color=fmt.COR_DADO, text=[fmt.numero(b[1]) for b in barras],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: nota %{x:.1f}<extra></extra>",
    ))
    figura.add_vline(x=50, line_dash="dot", line_color="#8a929b",
                     annotation_text="mediana do universo", annotation_position="top")
    figura.update_layout(separators=",.", xaxis_range=[0, 105], height=300, margin={"l": 0, "r": 20, "t": 30, "b": 0},
                         xaxis_title="Nota (percentil no universo, 0 a 100)")
    st.plotly_chart(figura, config={"displayModeBar": False},
                    alt=f"Barras com a nota de cada critério de {cidade['municipio_nome']}.")
with col_tabela:
    tabela_criterios = pd.DataFrame([
        {
            "Componente": fmt.COMPONENTES.get(c.criterio, (c.criterio,))[0],
            "Peso": c.peso * 100,
            "Nota": cidade.get(f"nota_{c.criterio}"),
        }
        for c in criterios.sort_values("ordem").itertuples()
    ])
    st.dataframe(
        tabela_criterios, hide_index=True,
        column_config={
            "Peso": st.column_config.NumberColumn(format="%.0f%%"),
            "Nota": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f",
                                                    color=fmt.COR_DADO),
        },
        alt="Tabela com peso e nota de cada componente do ranking.",
    )
    st.caption(
        f"Peso considerado: {fmt.porcentagem(cidade['peso_considerado'], 0)} "
        "(quando falta um critério, o peso dele é redistribuído entre os outros)."
    )

# --- Indicadores com percentil --------------------------------------------------
st.subheader("Indicadores")
universo = indicadores[indicadores["municipio_id"].isin(ranking["municipio_id"])]
mesma_uf = indicadores[indicadores["uf_sigla"] == cidade["uf_sigla"]]


def formatar(valor, tipo: str) -> str:
    """Escreve o indicador no formato certo."""
    if tipo == "inteiro":
        return fmt.numero(valor)
    if tipo == "decimal":
        return fmt.numero(valor, 2)
    if tipo == "taxa":
        return fmt.porcentagem(valor, 2)
    if tipo == "pib":
        return fmt.TRACO if fmt.ausente(valor) else "R$ " + fmt.compacto(float(valor) * 1000)
    return fmt.reais(valor)


linhas = []
for coluna, (rotulo, coluna_ano, tipo) in INDICADORES.items():
    valor = ind.get(coluna)
    percentil = None
    if not fmt.ausente(valor):
        serie = universo[coluna].dropna()
        percentil = float((serie <= valor).mean() * 100) if not serie.empty else None
    if coluna == "pib_per_capita_tendencia" and not fmt.ausente(ind.get("tendencia_ano_inicial")):
        ano = f"{int(ind['tendencia_ano_inicial'])}–{int(ind['pib_ano'])}"
    elif coluna_ano and not fmt.ausente(ind.get(coluna_ano)):
        ano = str(int(ind[coluna_ano]))
    else:
        ano = "2022" if coluna == "populacao_censo_2022" else fmt.TRACO
    linhas.append({
        "Indicador": rotulo,
        "Valor": formatar(valor, tipo),
        "Ano": ano,
        "Percentil no universo": percentil,
        "Mediana do universo": formatar(universo[coluna].median(), tipo),
        f"Mediana de {cidade['uf_sigla']}": formatar(mesma_uf[coluna].median(), tipo),
    })

st.dataframe(
    pd.DataFrame(linhas), hide_index=True,
    column_config={
        "Percentil no universo": st.column_config.ProgressColumn(
            color=fmt.COR_DADO,
            min_value=0, max_value=100, format="%.0f",
            help="Parcela das cidades do universo com valor igual ou menor que o desta cidade.",
        ),
    },
    alt=f"Indicadores de {cidade['municipio_nome']} com percentil e medianas de comparação.",
)
st.caption(
    f"Mediana de {cidade['uf_sigla']}: todos os municípios do estado, inclusive os com menos de "
    "50 mil habitantes. Em academias por habitante, percentil alto quer dizer mais concorrência "
    "(no ranking, menor é melhor)."
)
