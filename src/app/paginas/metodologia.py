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
# RADAR DE EXPANSAO - ETAPA 7: DASHBOARD - PAGINA "COMO O RANKING E CALCULADO"
# =============================================================================
#
# OBJETIVO: explicar o ranking em linguagem simples (P8): criterios, pesos,
#           sentido, fontes, regras de calculo e da lista recomendada, regras do
#           semaforo e o caminho do dado (bronze -> silver -> gold).
# ENTRADA:  gold.ranking_criterio, gold.parametro_ranking e a contagem de linhas
#           da ultima exportacao (site/dados/meta.json)
# SAIDA:    pagina web; nao grava nada
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - groupby/soma no pandas; Markdown
#
# NOVIDADES:
#   1. pesos lidos da gold  -> a pagina mostra a tabela gold.ranking_criterio;
#                              mudar um peso na gold muda a explicacao sozinho
#   2. grafico de rosca     -> plotly go.Pie com "hole" para os pesos
#   3. Mermaid no Markdown  -> bloco ```mermaid desenha o fluxo das camadas
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: streamlit run src/app/app.py  (menu "Como o ranking e calculado")
#
# =============================================================================

# ============================== CONFIG ==============================
# Regras do semaforo (spec.md, secao 5.1). Os limiares ficam na funcao da gold;
# aqui so o texto que explica cada faixa.
REGRAS_SEMAFORO = [
    {"Sinal": "Juros (Selic, BCB 432)", "Verde (+1)": "caiu 0,5 p.p. ou mais em 12 meses",
     "Amarelo (0)": "variou entre −0,5 e +0,5 p.p.", "Vermelho (−1)": "subiu mais de 0,5 p.p."},
    {"Sinal": "Inflação (IPCA, IBGE 7060)",
     "Verde (+1)": "12 meses ≤ 4,5% e desacelerando (vs. 3 meses antes)",
     "Amarelo (0)": "só uma das duas condições", "Vermelho (−1)": "acima de 4,5% e acelerando"},
    {"Sinal": "Câmbio (dólar, BCB 10813)", "Verde (+1)": "igual ou menor que 12 meses antes",
     "Amarelo (0)": "alta de até 10%", "Vermelho (−1)": "alta de mais de 10%"},
]
# Escala azul do dado (do mais escuro ao mais claro), uma cor por criterio.
CORES_ROSCA = ["#a9cbf3", "#6ea6e8", "#3a7fd0", "#1f5ba3", "#174377", "#102c52"]
# ====================================================================

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import dados
import formato as fmt

criterios = dados.tabela("ranking_criterio").sort_values("ordem")
trava = dados.parametro("nota_minima_poder_compra", 50)
quantidade = int(dados.parametro("unidades_recomendadas", 5))
populacao_minima = int(dados.ler_meta_snapshot().get("populacao_minima_universo", 50_000))

st.title("Como o ranking é calculado")
st.markdown(
    "O Radar dá a cada cidade com **50 mil habitantes ou mais** uma nota de **0 a 100** em seis "
    "critérios e soma as notas com os pesos abaixo. A nota de cada critério é o **percentil** da "
    "cidade no universo: 80 quer dizer que ela está à frente de 80% das cidades avaliadas. "
    "O momento econômico fica **fora** da nota (vale igual para todas) e aparece no semáforo."
)

# --- Criterios e pesos (da gold) -------------------------------------------------
st.subheader("Critérios e pesos")
col_tabela, col_rosca = st.columns([3, 2], vertical_alignment="center")
with col_tabela:
    tabela = pd.DataFrame({
        "Critério": [fmt.COMPONENTES.get(c, (c, ""))[0] for c in criterios["criterio"]],
        "O que mede": [fmt.COMPONENTES.get(c, ("", d))[1] or d
                       for c, d in zip(criterios["criterio"], criterios["descricao"])],
        "Sentido": criterios["sentido"].map(fmt.SENTIDO).fillna(criterios["sentido"]),
        "Peso": criterios["peso"] * 100,
        "Fonte": criterios["fonte"].map(fmt.fonte_legivel),
    })
    st.dataframe(
        tabela, hide_index=True,
        column_config={
            "Peso": st.column_config.ProgressColumn(min_value=0, max_value=30, format="%.0f%%",
                                                    color=fmt.COR_DADO),
            "O que mede": st.column_config.TextColumn(width="large"),
        },
        alt="Tabela dos critérios do ranking com o que medem, sentido, peso e fonte.",
    )
    st.caption(f"Versão dos pesos: {criterios['versao_pesos'].iloc[0]} · soma dos pesos: "
               f"{fmt.porcentagem(criterios['peso'].sum(), 0)}.")
with col_rosca:
    por_grupo = criterios.groupby("grupo", sort=False)["peso"].sum()
    rosca = go.Figure(go.Pie(
        labels=[fmt.CRITERIOS.get(g, g) for g in por_grupo.index], values=por_grupo.values,
        hole=0.55, sort=False, textinfo="percent", direction="clockwise",
        marker={"colors": CORES_ROSCA, "line": {"color": "#0b0d0f", "width": 2}},
        hovertemplate="%{label}: %{percent}<extra></extra>",
    ))
    rosca.update_layout(separators=",.", height=320, margin={"l": 0, "r": 0, "t": 10, "b": 0},
                        legend={"orientation": "v"})
    st.plotly_chart(rosca, config={"displayModeBar": False},
                    alt="Rosca com o peso de cada um dos seis critérios.")

# --- O que compoe a nota (mesmo texto do site de apoio) -----------------------------
st.subheader("O que compõe a nota")
linhas_nota = fmt.composicao_nota(dados.ler_meta_snapshot().get("periodos"))
for par in range(0, len(linhas_nota), 2):  # cartoes de dois em dois: o texto aparece inteiro
    for coluna, linha in zip(st.columns(2), linhas_nota[par:par + 2]):
        with coluna.container(border=True, height="stretch"):
            st.markdown(f"**{linha['Componente']}** · {linha['Peso']} · {linha['Sentido']}")
            st.markdown(linha["O que mede"])
            st.markdown(f"**Fonte:** {linha['De onde vem']}")
            st.markdown(f"**Por que importa:** {linha['Por que importa']}")
st.caption(fmt.FRASE_COMPOSICAO)

# --- Regras ----------------------------------------------------------------------
st.subheader("Regras do cálculo")
c1, c2 = st.columns(2)
with c1, st.container(border=True, height="stretch"):
    st.markdown("**:material/percent: Nota por percentil**")
    st.markdown(
        "Cada critério vira o percentil da cidade no universo (0 a 100). Cidades empatadas ficam "
        "com o mesmo percentil. A nota final é a média ponderada pelos pesos."
    )
with c2, st.container(border=True, height="stretch"):
    st.markdown("**:material/balance: Dado faltante redistribui o peso**")
    st.markdown(
        "Sem dado num critério, o peso dele é dividido entre os outros, na mesma proporção. A "
        "cidade ganha a marca **dados incompletos**, com a lista do que faltou."
    )
c3, c4 = st.columns(2)
with c3, st.container(border=True, height="stretch"):
    st.markdown("**:material/fitness_center: Academias por habitante com limites de 5% e 95%**")
    st.markdown(
        "Antes da nota, academias por 10 mil habitantes ficam entre os percentis 5% e 95% do "
        "universo, para poucos extremos não achatarem a nota das outras cidades. Cidade com zero "
        "academias recebe a nota do limite (não 100) e a marca **verificar concorrência**."
    )
with c4, st.container(border=True, height="stretch"):
    st.markdown(f"**:material/star: Lista das {quantidade} unidades recomendadas**")
    st.markdown(
        f"Segue a ordem da nota final com duas travas: só entra cidade com **nota de poder de "
        f"compra a partir de {fmt.numero(trava)}** (renda acima da mediana do universo) e **no "
        f"máximo uma cidade por região imediata** do IBGE, para as unidades não disputarem o "
        f"mesmo público. O ranking completo não muda."
    )

# --- Semaforo --------------------------------------------------------------------
st.subheader("Semáforo do momento econômico")
st.markdown(
    "Três sinais, cada um verde (+1), amarelo (0) ou vermelho (−1). A soma decide: "
    ":green[**≥ +2 expandir agora**] · :orange[**0 ou +1 expandir com cautela**] · "
    ":red[**≤ −1 esperar**]. \"Esperar\" é uma resposta válida: a cidade certa pode ter de "
    "aguardar o cenário melhorar."
)
st.table(pd.DataFrame(REGRAS_SEMAFORO), hide_index=True,
         alt="Regras de cada sinal do semáforo: juros, inflação e câmbio.")
janela = int(dados.parametro("semaforo_janela_dias", 30))
alerta = dados.parametro("semaforo_alerta_cambio_30d_pct", 5)
st.markdown(
    f"- **Semáforo de hoje:** o câmbio usa a média do dólar nos **{janela} dias** até o último fechamento (contra a "
    f"mesma janela 12 meses antes), os juros usam a meta da Selic do último dia disponível e a inflação, o último "
    f"IPCA publicado.\n"
    f"- **Alerta de alta do dólar no curto prazo:** se a média dos últimos {janela} dias ficar mais de "
    f"{fmt.numero(alerta, 0)}% acima da média dos {janela} dias anteriores, o câmbio não pode ficar verde. Média contra "
    "média, para um dia atípico não disparar o alerta.\n"
    "- **Histórico:** a linha do tempo da página \"Momento econômico\" usa os meses fechados; o mês em andamento "
    "aparece como parcial."
)

# --- Caminho do dado -----------------------------------------------------------
st.subheader("De onde vêm os dados")
st.markdown(
    """
```mermaid
flowchart LR
    IBGE["API do IBGE<br/>população, Censo, PIB,<br/>renda, empresas, IPCA"] --> B
    BCB["API do Banco Central<br/>Selic e dólar"] --> B
    B[("bronze<br/>JSON como veio")] --> S[("silver<br/>modelo estrela")]
    S --> G[("gold<br/>ranking e semáforo")]
    G --> APP["este dashboard<br/>(só leitura)"]
```
"""
)

meta = dados.ler_meta_snapshot()
camadas = meta.get("camadas") or {}
DESCRICAO_CAMADA = {
    "bronze": "Resposta das APIs exatamente como veio, com data, parâmetros e hash. Só recebe "
              "inserções.",
    "silver": "Dados limpos num modelo estrela: dimensões de região, UF, município e calendário; "
              "fatos municipais e macroeconômicos.",
    "gold": "Tabelas prontas para o dashboard: indicadores, ranking, critérios, parâmetros, "
            "contexto macro e semáforo.",
}
colunas = st.columns(3)
for coluna, (nome, descricao) in zip(colunas, DESCRICAO_CAMADA.items()):
    with coluna, st.container(border=True, height="stretch"):
        st.markdown(f"**{nome.capitalize()}**")
        st.caption(descricao)
        tabelas_camada = camadas.get(nome) or []
        if tabelas_camada:
            st.dataframe(
                pd.DataFrame(tabelas_camada).rename(columns={"tabela": "Tabela", "linhas": "Linhas"}),
                hide_index=True,
                column_config={"Linhas": st.column_config.NumberColumn(format="localized")},
                alt=f"Tabelas da camada {nome} e quantidade de linhas.",
            )
if meta.get("gerado_em"):
    st.caption(f"Contagem de linhas da última exportação ({fmt.data_hora(meta['gerado_em'])}). "
               "Fontes oficiais: IBGE (Localidades e Agregados) e Banco Central (SGS). "
               f"Universo: municípios com {fmt.numero(populacao_minima)} habitantes ou mais.")
