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
# RADAR DE EXPANSAO - ETAPA 7: DASHBOARD (ACOES DE CLIQUE E LINK DIRETO)
# =============================================================================
#
# OBJETIVO: deixar o dashboard navegavel pelo mapa: clicar num municipio mostra
#           os botoes "Ver cidade" e "Ver bairros"; e as paginas Municipio e
#           Bairros aceitam o endereco ?municipio=<codigo IBGE de 7 digitos>.
# ENTRADA:  o clique devolvido por st.plotly_chart(on_select="rerun") e o
#           parametro "municipio" do endereco da pagina
# SAIDA:    nada gravado; so troca de pagina com a cidade escolhida
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - st.session_state e st.switch_page para levar a cidade de uma pagina a outra
#
# NOVIDADES:
#   1. on_select="rerun"    -> o grafico vira um campo de entrada: o clique num
#                              ponto ou poligono roda a pagina de novo e devolve
#                              o "customdata" do que foi clicado
#   2. st.query_params      -> le e escreve o ?municipio= do endereco, para o
#                              site poder abrir o dashboard ja numa cidade
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: nao roda sozinho; e importado pelas paginas do dashboard
#
# =============================================================================

# ============================== CONFIG ==============================
CHAVE_ESCOLHIDO = "municipio_escolhido"   # cidade da pagina Municipio (ja usada pelas outras paginas)
CHAVE_BAIRROS = "bairros_ir_para"         # cidade que a pagina Bairros deve abrir
PARAMETRO_URL = "municipio"
PAGINA_MUNICIPIO = "paginas/municipio.py"
PAGINA_BAIRROS = "paginas/bairros.py"
# ====================================================================

import streamlit as st


def codigo_valido(valor) -> int | None:
    """Codigo IBGE de municipio (7 digitos) ou None."""
    try:
        codigo = int(str(valor).strip())
    except (TypeError, ValueError):
        return None
    return codigo if 1_100_000 <= codigo <= 5_399_999 else None


def municipio_da_url() -> int | None:
    """?municipio=3506003 no endereco da pagina (None se ausente ou invalido)."""
    return codigo_valido(st.query_params.get(PARAMETRO_URL))


def municipio_novo_da_url(chave: str) -> int | None:
    """Municipio da URL so na primeira vez que aparece (depois vale o que a pessoa escolher na tela)."""
    codigo = municipio_da_url()
    if codigo is None or st.session_state.get(chave) == codigo:
        return None
    st.session_state[chave] = codigo
    return codigo


def gravar_na_url(municipio_id: int) -> None:
    """Mantem o endereco igual a cidade da tela (o link copiado abre a mesma cidade)."""
    if st.query_params.get(PARAMETRO_URL) != str(municipio_id):
        st.query_params[PARAMETRO_URL] = str(municipio_id)


def clicado(evento) -> object | None:
    """customdata do ponto ou poligono clicado no grafico (None se nada foi clicado)."""
    try:
        pontos = evento.selection["points"]
    except (AttributeError, KeyError, TypeError):
        return None
    for ponto in pontos:
        valor = ponto.get("customdata")
        if isinstance(valor, list):
            valor = valor[0] if valor else None
        if valor is not None:
            return valor
    return None


def ver_cidade(municipio_id: int) -> None:
    """Abre a ficha do municipio."""
    st.session_state[CHAVE_ESCOLHIDO] = int(municipio_id)
    st.switch_page(PAGINA_MUNICIPIO, query_params={PARAMETRO_URL: str(municipio_id)})


def ver_bairros(municipio_id: int) -> None:
    """Abre a pagina Bairros com a cidade carregada (ou pronta para pedir o calculo)."""
    st.session_state[CHAVE_BAIRROS] = int(municipio_id)
    st.switch_page(PAGINA_BAIRROS, query_params={PARAMETRO_URL: str(municipio_id)})


def barra_de_acoes(municipio_id: int | None, nome: str, chave: str, cidade: bool = True, bairros: bool = True,
                   dica: str = "Clique num município do mapa para ver a ficha ou os bairros dele.",
                   onde: str = "no mapa") -> None:
    """Faixa logo abaixo do grafico com o municipio clicado e os botoes de acao."""
    if municipio_id is None:
        st.caption(dica)
        return
    with st.container(border=True, horizontal=True, vertical_alignment="center"):
        st.markdown(f"**{nome}** selecionado {onde}")
        if cidade and st.button("Ver cidade", icon=":material/location_city:", key=f"{chave}_cidade"):
            ver_cidade(municipio_id)
        if bairros and st.button("Ver bairros", icon=":material/holiday_village:", key=f"{chave}_bairros",
                                 type="primary"):
            ver_bairros(municipio_id)
