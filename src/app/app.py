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
# RADAR DE EXPANSAO - ETAPA 7: DASHBOARD STREAMLIT (PONTO DE ENTRADA)
# =============================================================================
#
# OBJETIVO: abrir o dashboard do Radar: configura a pagina, monta o menu com as
#           7 paginas e avisa na tela de onde vieram os dados (API ou copia).
# ENTRADA:  camada gold (via src/app/dados.py)
# SAIDA:    paginas web do dashboard; nao grava nada
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - pandas para filtrar e ordenar tabelas
#   - leitura de dados por API REST com requests
#
# NOVIDADES:
#   1. Streamlit            -> transforma um script Python em pagina web; cada
#                              interacao roda o script de novo, de cima a baixo
#   2. st.navigation/st.Page -> app com varias paginas e menu no topo; cada
#                              pagina e um arquivo em src/app/paginas/
#   3. st.session_state     -> memoria da sessao do visitante (ex.: municipio
#                              escolhido no ranking e aberto na ficha)
#   4. .streamlit/config.toml -> tema do app (cores e fontes), sem CSS
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: streamlit run src/app/app.py      (a partir da raiz do repositorio)
#
# =============================================================================

# ============================== CONFIG ==============================
TITULO_APP = "Radar de Expansão"
MARCA = "RADAR DE EXPANSÃO"
SQUAD = "SQUAD DROP DATABASE"
TITULO_ABA = f"{MARCA} · {SQUAD}"
ICONE_APP = ":material/radar:"
SITE_DE_APOIO = "https://radar-expansao.lovelearning.com.br"
REPOSITORIO = "https://github.com/JJ-Junior/radar-expansao"
# ====================================================================

import streamlit as st

import dados
import formato as fmt

st.set_page_config(
    page_title=TITULO_ABA,
    page_icon=ICONE_APP,
    layout="wide",
    menu_items={
        "About": f"**{TITULO_APP}** · Squad DROP Database #21001. Onde abrir as próximas "
                 f"academias e se o momento econômico favorece abrir agora. "
                 f"Site de apoio: {SITE_DE_APOIO}",
    },
)

paginas = [
    st.Page("paginas/visao_geral.py", title="Visão geral", icon=":material/radar:", default=True),
    st.Page("paginas/ranking.py", title="Ranking", icon=":material/leaderboard:"),
    st.Page("paginas/municipio.py", title="Município", icon=":material/location_city:"),
    st.Page("paginas/simulador.py", title="Simulador de região", icon=":material/travel_explore:"),
    st.Page("paginas/bairros.py", title="Bairros", icon=":material/holiday_village:"),
    st.Page("paginas/contexto_macro.py", title="Momento econômico", icon=":material/monitoring:"),
    st.Page("paginas/metodologia.py", title="Como o ranking é calculado",
            icon=":material/menu_book:"),
]
pagina = st.navigation(paginas, position="top")
# Depois do menu: a aba mostra a marca, e nao o nome da pagina.
st.set_page_config(page_title=TITULO_ABA)

# Cabecalho de todas as paginas: marca em destaque, squad em destaque secundario.
st.markdown(f"#### :primary[{MARCA}] :gray[· {SQUAD}]")

# De onde vieram os dados: aviso visivel quando a API nao respondeu.
gold = dados.carregar_gold()
if gold["fonte"] == "snapshot":
    st.warning(
        f"Dados de {fmt.data_curta(gold['gerado_em'])}: cópia de contingência da camada gold, "
        f"porque {gold['motivo']}. Os números são os da última exportação.",
        icon=":material/history:",
    )

pagina.run()

st.divider()
st.caption(
    f"Fontes oficiais: IBGE e Banco Central do Brasil. "
    f"{'Dados lidos ao vivo da camada gold' if gold['fonte'] == 'api' else 'Cópia da camada gold'}"
    f" · calculados em {fmt.data_hora(gold['gerado_em'])}. "
    f"[Site de apoio]({SITE_DE_APOIO}) · [Repositório]({REPOSITORIO}) · "
    f"Squad DROP Database #21001."
)
