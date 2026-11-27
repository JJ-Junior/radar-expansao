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
# RADAR DE EXPANSAO - ETAPA 7: DASHBOARD - PAGINA "VISAO GERAL"
# =============================================================================
#
# OBJETIVO: a pagina dos 30 segundos: semaforo do momento economico (P7), as 5
#           unidades recomendadas com o porque (P8), mapa do universo e numeros
#           de contexto.
# ENTRADA:  gold.momento_expansao, gold.ranking_expansao, gold.parametro_ranking
#           e o centro de cada municipio (site/dados/territorio.json)
# SAIDA:    pagina web; nao grava nada
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - filtrar e ordenar DataFrame; f-strings
#
# NOVIDADES:
#   1. st.columns + st.container(border=True) -> cards lado a lado
#   2. st.metric / st.badge -> numero em destaque e etiqueta colorida
#   3. mapa sem servidor externo -> divisas das UFs desenhadas a partir da malha
#                              do IBGE (TopoJSON); tamanho = populacao, cor = nota
#   4. st.switch_page       -> botao que abre outra pagina ja com a cidade
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: streamlit run src/app/app.py  (esta pagina abre primeiro)
#
# =============================================================================

# ============================== CONFIG ==============================
TAMANHO_MIN_PONTO = 4    # px, cidade de 50 mil habitantes
TAMANHO_MAX_PONTO = 34   # px, maior cidade do universo
LIMITES_LON = [-74.5, -32.0]   # Brasil inteiro, com folga para os nomes
LIMITES_LAT = [-34.5, 5.8]
DISTANCIA_ROTULO = 2.5          # graus: recomendadas mais perto que isso trocam o lado do nome
ALTURA_MAPA = 520
# ====================================================================

import re

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import acoes
import dados
import formato as fmt

ranking = dados.ranking_completo()
lista = dados.recomendadas()
atual = dados.semaforo_atual()

st.title("Onde abrir as próximas academias")
st.caption(
    f"{len(lista)} cidades recomendadas entre {len(ranking)} municípios com 50 mil habitantes ou mais, "
    "com o sinal do momento econômico para decidir quando."
)

# --- Semaforo do momento (P7) -------------------------------------------------
NOME_SINAL = {"sinal_juros": "Juros", "sinal_inflacao": "Inflação", "sinal_cambio": "Câmbio"}
DATA_DO_SINAL = {"sinal_juros": "ref_juros", "sinal_inflacao": "ref_inflacao", "sinal_cambio": "ref_cambio"}
COR_RECOMENDACAO = {"Expandir agora": "green", "Expandir com cautela": "orange", "Esperar": "red"}
ICONE_RECOMENDACAO = {
    "Expandir agora": ":material/check_circle:",
    "Expandir com cautela": ":material/warning:",
    "Esperar": ":material/pause_circle:",
}


def frases_do_semaforo(justificativa: str) -> dict[str, str]:
    """Separa a justificativa da gold em uma frase por sinal, pelo nome de cada sinal."""
    partes = re.split(r"\s*(?=(?:Juros|Inflação|Câmbio):)", str(justificativa).strip())
    frases = {}
    for parte in partes:
        nome, _, texto = parte.partition(":")
        if texto:
            texto = re.sub(r"\s*\((verde|amarelo|vermelho)\)\.?\s*$", ".", texto.strip())
            frases[nome.strip()] = texto
    return frases


if atual["tipo"] == "atual":
    referencia = (f"Momento econômico · hoje: câmbio até {fmt.data_curta(atual['ref_cambio'])}, "
                  f"Selic de {fmt.data_curta(atual['ref_juros'])}, IPCA até {fmt.mes_curto(atual['ref_inflacao'])}")
else:
    referencia = f"Momento econômico · {fmt.mes_extenso(atual['mes'])} (último mês fechado)"

with st.container(border=True):
    cor = COR_RECOMENDACAO.get(atual["recomendacao"], "gray")
    col_sinal, col_motivos = st.columns([1, 2], vertical_alignment="center")
    with col_sinal:
        st.caption(referencia)
        st.markdown(f"## :{cor}[{ICONE_RECOMENDACAO.get(atual['recomendacao'], '')} "
                    f"{atual['recomendacao']}]")
        alerta = (" Alerta de alta do dólar no curto prazo." if atual.get("alerta_cambio_curto_prazo")
                  else "")
        st.caption(
            f"Pontuação {int(atual['pontuacao']):+d} na soma dos três sinais "
            f"(+1 verde, 0 amarelo, −1 vermelho). Vale igual para todas as cidades.{alerta}"
        )
    with col_motivos:
        frases = frases_do_semaforo(atual["justificativa"])
        for coluna, nome in NOME_SINAL.items():
            sinal = atual[coluna]
            texto = frases.get(nome, "")
            data_ref = atual.get(DATA_DO_SINAL[coluna])
            quando = "" if fmt.ausente(data_ref) else (
                fmt.mes_curto(data_ref) if coluna == "sinal_inflacao" else fmt.data_curta(data_ref)[:5])
            with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                st.badge(f"{nome} · {sinal}" + (f" · {quando}" if quando else ""),
                         color=fmt.COR_SINAL_STREAMLIT.get(sinal, "gray"), width=190,
                         help="Data do dado usado no sinal" if quando else None)
                st.markdown(texto or fmt.TRACO)
        st.page_link("paginas/contexto_macro.py", label="Ver Selic, IPCA e dólar no tempo",
                     icon=":material/arrow_forward:")

# --- As 5 unidades recomendadas (P8) -----------------------------------------
st.subheader(f"As {len(lista)} unidades recomendadas")
trava = dados.parametro("nota_minima_poder_compra", 50)
st.caption(
    f"Ordem da nota final, só com cidades de nota de poder de compra a partir de {fmt.numero(trava)} "
    "(renda acima da mediana do universo) e no máximo uma por região imediata, para as unidades "
    "não disputarem o mesmo público."
)

colunas = st.columns(max(len(lista), 1))
for coluna, (_, cidade) in zip(colunas, lista.iterrows()):
    with coluna, st.container(border=True, height="stretch"):
        st.badge(f"Recomendada nº {int(cidade['ordem_recomendacao'])}", color="primary",
                 icon=":material/star:")
        st.markdown(f"#### {cidade['municipio_nome']}")
        st.caption(f"{cidade['uf_sigla']} · região imediata de {cidade['regiao_imediata_nome']}")
        st.metric("Nota final (0 a 100)", fmt.nota(cidade["nota_final"]),
                  help="Média ponderada das notas dos 6 critérios (página 'Como o ranking é calculado').")
        st.markdown(
            f"**{fmt.ordinal(cidade['posicao_brasil'])}** no Brasil · "
            f"**{fmt.compacto(cidade['populacao'])}** hab."
        )
        fortes = fmt.pontos_fortes(cidade)
        st.markdown("  \n".join(f":material/trending_up: {rotulo} **{fmt.numero(valor)}**"
                                for rotulo, valor in fortes))
        avisos = []
        if cidade["dados_incompletos"]:
            avisos.append("dados incompletos")
        if cidade["verificar_concorrencia"]:
            avisos.append("verificar concorrência")
        if avisos:
            st.caption(":material/info: " + " · ".join(avisos))
        if st.button("Abrir ficha", key=f"ficha_{cidade['municipio_id']}",
                     icon=":material/open_in_new:", width="stretch"):
            st.session_state["municipio_escolhido"] = int(cidade["municipio_id"])
            st.switch_page("paginas/municipio.py")

# Cidades a frente da ultima recomendada que ficaram de fora, com o motivo.
if not lista.empty:
    ultima = lista["posicao_brasil"].max()
    fora = ranking[(~ranking["recomendado_top5"]) & (ranking["posicao_brasil"] < ultima)]
    if not fora.empty:
        itens = "; ".join(
            f"**{fmt.ordinal(r['posicao_brasil'])} {r['municipio_nome']}** ({r['uf_sigla']}): "
            f"{dados.motivo_fora_da_lista(r, lista)}"
            for _, r in fora.iterrows()
        )
        st.caption(f":material/help: Por que não estão na lista? {itens}. O ranking completo não muda.")

# --- Mapa do universo + numeros de contexto ----------------------------------
st.subheader("Todas as cidades avaliadas")
col_mapa, col_kpis = st.columns([3, 1])

with col_mapa:
    mapa = ranking.dropna(subset=["latitude", "longitude"])
    tamanho = TAMANHO_MIN_PONTO + (TAMANHO_MAX_PONTO - TAMANHO_MIN_PONTO) * np.sqrt(
        mapa["populacao"] / mapa["populacao"].max()
    )
    texto_hover = (
        "<b>" + mapa["municipio_nome"] + " (" + mapa["uf_sigla"] + ")</b><br>"
        + "Nota final " + mapa["nota_final"].map(fmt.nota)
        + " · " + mapa["posicao_brasil"].map(fmt.ordinal) + " no Brasil<br>"
        + mapa["populacao"].map(fmt.compacto) + " habitantes"
    )
    figura = go.Figure()
    divisa_lon, divisa_lat = dados.contornos_ufs()
    figura.add_trace(go.Scatter(
        x=divisa_lon, y=divisa_lat, mode="lines", hoverinfo="skip", showlegend=False,
        line={"color": "rgba(242,241,236,.28)", "width": 0.8},
    ))
    figura.add_trace(go.Scatter(
        x=mapa["longitude"], y=mapa["latitude"], mode="markers",
        marker={
            "size": tamanho, "color": mapa["nota_final"], "colorscale": fmt.ESCALA_DADO,
            "cmin": 0, "cmax": 100, "opacity": 0.85, "line": {"width": 0},
            "colorbar": {"title": {"text": "Nota"}, "thickness": 12, "len": 0.6},
        },
        text=texto_hover, hoverinfo="text", name="Cidades do universo",
        customdata=mapa["municipio_id"].astype(int).tolist(),
    ))
    destaque = mapa[mapa["recomendado_top5"]].sort_values("ordem_recomendacao")
    # Rotulo a esquerda quando ha outra recomendada perto, a leste (evita sobrepor nomes).
    posicao_rotulo = [
        "middle left" if any(
            abs(c.latitude - o.latitude) < DISTANCIA_ROTULO and 0 < o.longitude - c.longitude
            < DISTANCIA_ROTULO * 2 for o in destaque.itertuples()
        ) else "middle right"
        for c in destaque.itertuples()
    ]
    figura.add_trace(go.Scatter(
        x=destaque["longitude"], y=destaque["latitude"], mode="markers+text",
        marker={"size": 15, "color": fmt.COR_DESTAQUE, "line": {"width": 2, "color": "#0b0d0f"}},
        text=destaque["ordem_recomendacao"].astype(int).astype(str) + " · "
        + destaque["municipio_nome"],
        textposition=posicao_rotulo, textfont={"color": "#f2f1ec", "size": 13},
        hovertext=texto_hover[destaque.index], hoverinfo="text", name="Recomendadas",
        customdata=destaque["municipio_id"].astype(int).tolist(),
    ))
    eixo = {"visible": False, "showgrid": False, "zeroline": False}
    figura.update_layout(
        separators=",.", xaxis={**eixo, "range": LIMITES_LON},
        # 1 grau de latitude e um pouco maior que 1 de longitude perto do Equador
        yaxis={**eixo, "range": LIMITES_LAT, "scaleanchor": "x", "scaleratio": 1.04},
        margin={"l": 0, "r": 0, "t": 0, "b": 0}, height=ALTURA_MAPA,
        legend={"orientation": "h", "y": 0.02, "x": 0.01},
        plot_bgcolor="rgba(0,0,0,0)", dragmode="pan",
    )
    figura.update_traces(selected={"marker": {"opacity": 1}, "textfont": {"color": "#f2f1ec"}},
                         unselected={"marker": {"opacity": 1}, "textfont": {"color": "#f2f1ec"}})  # o clique nao apaga o resto
    evento = st.plotly_chart(
        figura, config={"displaylogo": False, "scrollZoom": True}, on_select="rerun", selection_mode="points",
        key="visao_geral_mapa",
        alt="Mapa do Brasil com as cidades avaliadas: tamanho do ponto é a população, "
            "cor é a nota final; as recomendadas aparecem em laranja.",
    )
    clicada = acoes.codigo_valido(acoes.clicado(evento))
    nome_clicada = mapa.loc[mapa["municipio_id"] == clicada]
    acoes.barra_de_acoes(clicada, "" if nome_clicada.empty else
                         f"{nome_clicada.iloc[0]['municipio_nome']} ({nome_clicada.iloc[0]['uf_sigla']})",
                         "visao_geral_acoes")

with col_kpis:
    calculado = ranking["calculado_em"].max()
    indicadores = dados.tabela("indicadores_municipio")
    contexto = dados.tabela("contexto_macro")
    with st.container(border=True):
        st.metric("Cidades avaliadas", fmt.numero(len(ranking)),
                  help="Municípios com 50 mil habitantes ou mais na estimativa mais recente do IBGE.")
    with st.container(border=True):
        st.metric("População do universo", fmt.compacto(ranking["populacao"].sum()),
                  help="Soma da população estimada das cidades avaliadas.")
    with st.container(border=True):
        st.metric("Regiões imediatas", fmt.numero(ranking["regiao_imediata_id"].nunique()),
                  help="Polos de comércio e serviços do IBGE; a lista recomendada tem no máximo "
                       "uma cidade por região imediata.")
    with st.container(border=True):
        st.metric("Ranking calculado em", fmt.data_curta(calculado))
        st.caption(
            f"População {int(indicadores['populacao_ano'].max())} · "
            f"PIB {int(indicadores['pib_ano'].max())} · "
            f"academias {int(indicadores['academias_ano'].max())} · "
            f"macro até {fmt.mes_curto(contexto['mes'].max())}"
        )
