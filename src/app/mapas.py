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
# RADAR DE EXPANSAO - ETAPA 7: DASHBOARD (MAPA DE RUAS POR BAIXO)
# =============================================================================
#
# OBJETIVO: deixar os mapas de municipio e bairro com duas vistas: "Mapa de
#           ruas" (tiles publicos do OpenStreetMap, sem chave) e "So
#           contornos" (a vista original, sem servidor de mapas).
# ENTRADA:  a figura montada pela pagina com tracos geograficos (Scattergeo e
#           Choropleth) e a caixa (lon/lat) que o mapa deve enquadrar
# SAIDA:    a mesma figura com tracos de mapa de ruas; nao grava nada
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - plotly.graph_objects para montar mapas com pontos e poligonos
#
# NOVIDADES:
#   1. Scattermap / Choroplethmap -> os mesmos pontos e poligonos sobre um mapa de
#                              ruas (MapLibre); cada traco vira o equivalente
#   2. skip_invalid=True      -> ao converter, o plotly descarta as opcoes que o
#                              mapa de ruas nao tem (ex.: borda do marcador)
#   3. zoom do mapa de ruas   -> calculado da caixa a enquadrar (cada nivel de
#                              zoom dobra a escala)
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: nao roda sozinho; e importado pelas paginas Bairros e Simulador
#
# =============================================================================

# ============================== CONFIG ==============================
RUAS, CONTORNOS = "ruas", "contornos"
ROTULOS_FUNDO = {RUAS: "Mapa de ruas", CONTORNOS: "Só contornos"}
ESTILO_RUAS = "open-street-map"          # tiles do OpenStreetMap, sem chave (os do CARTO passaram a exigir chave)
OPACIDADE_AREAS = 0.6                    # areas semitransparentes: as ruas aparecem por baixo, com contraste no fundo claro
LARGURA_REFERENCIA_PX = 700              # largura usada no zoom (a de uma tela estreita: cabe em todas)
TAMANHO_ALVO_CLIQUE = 26                 # px do ponto invisivel que recebe o clique no centro de cada area
FOLGA_ZOOM = 0.25                       # um pouco mais afastado: legenda e borda nao cobrem a area
CREDITO = "Mapa de fundo: © OpenStreetMap contributors"
# ====================================================================

import math

import plotly.graph_objects as go
import streamlit as st


def seletor_de_fundo(chave: str, padrao: str) -> str:
    """Seletor obrigatorio "Mapa de ruas" | "So contornos" (a escolha fica no session_state)."""
    escolha = st.segmented_control("Fundo do mapa", list(ROTULOS_FUNDO), format_func=ROTULOS_FUNDO.get,
                                   default=padrao, required=True, key=chave)
    return escolha if escolha in ROTULOS_FUNDO else padrao


def zoom_para(caixa: tuple, altura_px: int) -> tuple[dict, float]:
    """Centro e zoom do mapa de ruas que mostram a caixa (lon_min, lon_max, lat_min, lat_max) inteira."""
    lon0, lon1, lat0, lat1 = caixa
    mercator = lambda lat: math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    vao_lon = max(lon1 - lon0, 1e-4)
    vao_y = max(mercator(lat1) - mercator(lat0), 1e-6)
    zoom_x = math.log2(LARGURA_REFERENCIA_PX * 360 / (512 * vao_lon))   # o mundo tem 512 px no zoom 0
    zoom_y = math.log2(altura_px * 2 * math.pi / (512 * vao_y))
    centro_y = (mercator(lat0) + mercator(lat1)) / 2
    centro = {"lon": (lon0 + lon1) / 2, "lat": math.degrees(2 * math.atan(math.exp(centro_y)) - math.pi / 2)}
    return centro, max(min(zoom_x, zoom_y) - FOLGA_ZOOM, 1.0)


def pontos_clicaveis(dados: dict) -> go.Scattermap:
    """Ponto quase invisivel no centro de cada poligono, com o mesmo codigo e hover.

    No mapa de ruas, clicar num poligono (Choroplethmap) nao vira "selecao" para o Streamlit;
    clicar num ponto vira. Assim o clique na area do municipio ou bairro continua funcionando.
    """
    formas = {str(f.get("id")): f.get("geometry") for f in (dados.get("geojson") or {}).get("features", [])}
    lons, lats = [], []
    for local in dados.get("locations") or []:
        geometria = formas.get(str(local)) or {}
        poligonos = geometria.get("coordinates") or []
        if geometria.get("type") == "Polygon":
            poligonos = [poligonos]
        anel = max((p[0] for p in poligonos if p), key=len, default=[])  # borda externa do maior pedaco
        lons.append(sum(p[0] for p in anel) / len(anel) if anel else None)
        lats.append(sum(p[1] for p in anel) / len(anel) if anel else None)
    return go.Scattermap(lon=lons, lat=lats, mode="markers", marker={"size": TAMANHO_ALVO_CLIQUE, "opacity": 0.01},
                         customdata=dados.get("customdata"), text=dados.get("text"),
                         hovertemplate=dados.get("hovertemplate"), hoverinfo=dados.get("hoverinfo"),
                         showlegend=False)


def em_mapa_de_ruas(figura: go.Figure, caixa: tuple, altura_px: int) -> go.Figure:
    """Mesma figura, com os tracos geograficos sobre o mapa de ruas do OpenStreetMap."""
    nova = go.Figure()
    for traco in figura.data:
        dados = traco.to_plotly_json()
        tipo = dados.pop("type")
        dados.pop("geo", None)
        dados.pop("selected", None)
        dados.pop("unselected", None)
        if tipo == "choropleth":
            marcador = dados.setdefault("marker", {})
            marcador["opacity"] = min(marcador.get("opacity", 1), OPACIDADE_AREAS)
            nova.add_trace(go.Choroplethmap(dados, skip_invalid=True))
            if dados.get("customdata") is not None:
                nova.add_trace(pontos_clicaveis(dados))
        elif tipo == "scattergeo":
            # Texto fora do centro do ponto quebra a camada de texto do MapLibre (e com ela o clique);
            # no mapa de ruas os nomes das cidades ja vem do proprio mapa de fundo.
            modo = str(dados.get("mode", ""))
            if "text" in modo and dados.get("textposition", "middle center") != "middle center":
                if modo == "text":
                    continue
                dados["mode"] = modo.replace("+text", "").replace("text+", "")
            marcador = dict(dados.get("marker") or {})
            borda = marcador.pop("line", None) or {}
            marcador.pop("symbol", None)  # o mapa de ruas so desenha circulos
            if borda.get("width") and "markers" in str(dados.get("mode", "")):
                # sem borda no mapa de ruas: um circulo um pouco maior por baixo faz o papel dela
                tamanho = marcador.get("size", 6)
                maior = [s + 2 * borda["width"] for s in tamanho] if isinstance(tamanho, list) else tamanho + 2 * borda["width"]
                nova.add_trace(go.Scattermap(lon=dados.get("lon"), lat=dados.get("lat"), mode="markers",
                                             marker={"size": maior, "color": borda.get("color", "#f2f1ec")},
                                             customdata=dados.get("customdata"),  # clicar na borda vale o mesmo
                                             hovertext=dados.get("hovertext"), text=dados.get("text"),
                                             hovertemplate=dados.get("hovertemplate"), showlegend=False))
            dados["marker"] = marcador
            nova.add_trace(go.Scattermap(dados, skip_invalid=True))
    centro, zoom = zoom_para(caixa, altura_px)
    camada = figura.layout.to_plotly_json()
    for chave in ("geo", "dragmode"):
        camada.pop(chave, None)
    nova.update_layout(camada)
    nova.update_layout(map={"style": ESTILO_RUAS, "center": centro, "zoom": zoom}, height=altura_px)
    return nova
