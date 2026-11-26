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
# RADAR DE EXPANSAO - ETAPA 6: SITE DE APOIO (MALHAS E TERRITORIO)
# =============================================================================
#
# OBJETIVO: baixar as malhas oficiais do IBGE (regioes, UFs, regioes
#           intermediarias e imediatas) para o mapa do site e montar o arquivo
#           territorio.json: municipio -> regiao imediata/intermediaria + ponto
#           central (longitude, latitude) calculado da malha municipal.
# ENTRADA:  API de Malhas v3 e API de Localidades do IBGE
# SAIDA:    site/dados/malha/*.topo.json e site/dados/territorio.json
#           (substitui os arquivos inteiros a cada execucao)
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - requests.get com parametros, timeout e novas tentativas
#   - gravar JSON com o modulo json
#
# NOVIDADES:
#   1. TopoJSON          -> formato de mapa que guarda cada fronteira uma vez so
#                           (vizinhos compartilham a mesma linha); fica pequeno
#   2. arcos quantizados -> as coordenadas vem como inteiros e diferencas
#                           (delta); "transform" (scale + translate) as devolve
#                           para longitude/latitude
#   3. centroide         -> ponto de equilibrio de um poligono (formula do
#                           cadarco / shoelace), ponderado pela area
#   4. hierarquia do IBGE -> municipio < regiao imediata < regiao intermediaria
#                           < UF < regiao geografica
#
# INSTALACAO: pip install requests   (ou: pip install -r requirements.txt)
# COMO RODAR: python src/exportacao/baixar_territorio.py
#
# =============================================================================

# ============================== CONFIG ==============================
URL_MALHA = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
URL_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
QUALIDADE = "minima"                 # minima | intermediaria | maxima
CAMADAS = {                          # arquivo salvo -> (intrarregiao da API, objeto esperado, minimo de poligonos)
    "regioes": ("regiao", "BRGR", 5),
    "ufs": ("UF", "BRUF", 27),
    "intermediarias": ("regiao-intermediaria", "BRIN", 130),
    "imediatas": ("regiao-imediata", "BRIM", 500),
}
CASAS_COORDENADA = 4                 # ~11 m de precisao: suficiente para um ponto no mapa
TIMEOUT_SEGUNDOS = 60
TENTATIVAS = 3
USER_AGENT = "radar-expansao/0.1 (projeto academico; dados publicos)"
# ====================================================================

import json
import time
from datetime import datetime
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[2]
PASTA_DADOS = RAIZ / "site" / "dados"
PASTA_MALHA = PASTA_DADOS / "malha"


def chamar_api(url: str, params: dict) -> object:
    """GET com ate TENTATIVAS tentativas; confere que a resposta e JSON."""
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resposta = requests.get(url, params=params, timeout=TIMEOUT_SEGUNDOS, headers={"User-Agent": USER_AGENT})
            resposta.raise_for_status()
            if "json" not in resposta.headers.get("content-type", ""):
                raise ValueError(f"resposta nao e JSON: {resposta.headers.get('content-type')}")
            return resposta.json()
        except (requests.RequestException, ValueError) as erro:
            print(f"  tentativa {tentativa} falhou: {erro}")
            if tentativa == TENTATIVAS:
                raise
            time.sleep(2 ** tentativa)


def baixar_malha(intrarregiao: str, objeto: str, minimo: int) -> dict:
    """Baixa uma camada da malha do Brasil em TopoJSON e confere o conteudo."""
    print(f"  malha {intrarregiao} ...")
    topo = chamar_api(URL_MALHA, {"formato": "application/json", "qualidade": QUALIDADE, "intrarregiao": intrarregiao})
    geometrias = topo.get("objects", {}).get(objeto, {}).get("geometries", [])
    if topo.get("type") != "Topology" or len(geometrias) < minimo:
        raise ValueError(f"malha {intrarregiao} inesperada: {len(geometrias)} poligonos")
    return topo


# ------------------------------------------------------------ centroide a partir do TopoJSON

def decodificar_arcos(topo: dict) -> list:
    """Arcos quantizados (inteiros + delta) -> listas de (longitude, latitude)."""
    (sx, sy), (tx, ty) = topo["transform"]["scale"], topo["transform"]["translate"]
    arcos = []
    for arco in topo["arcs"]:
        x = y = 0
        pontos = []
        for dx, dy in arco:
            x += dx
            y += dy
            pontos.append((x * sx + tx, y * sy + ty))
        arcos.append(pontos)
    return arcos


def montar_anel(indices: list, arcos: list) -> list:
    """Junta os arcos de um anel; indice negativo (~i) = arco i de tras para frente."""
    anel = []
    for i in indices:
        pontos = arcos[i] if i >= 0 else arcos[~i][::-1]
        anel.extend(pontos if not anel else pontos[1:])  # o 1o ponto repete o ultimo do arco anterior
    return anel


def area_e_centroide(anel: list) -> tuple:
    """Area (com sinal) e centroide de um anel pela formula do cadarco."""
    area = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(anel, anel[1:] + anel[:1]):
        cruz = x0 * y1 - x1 * y0
        area += cruz
        cx += (x0 + x1) * cruz
        cy += (y0 + y1) * cruz
    area /= 2
    if area == 0:
        return 0.0, anel[0]
    return area, (cx / (6 * area), cy / (6 * area))


def centroides_municipios(topo: dict) -> dict:
    """codigo do municipio -> (longitude, latitude) do centroide ponderado pela area."""
    arcos = decodificar_arcos(topo)
    resultado = {}
    for geometria in topo["objects"]["BRMU"]["geometries"]:
        poligonos = [geometria["arcs"]] if geometria["type"] == "Polygon" else geometria["arcs"]
        soma_area = soma_x = soma_y = 0.0
        for poligono in poligonos:
            area, (x, y) = area_e_centroide(montar_anel(poligono[0], arcos))  # anel externo
            soma_area += abs(area)
            soma_x += abs(area) * x
            soma_y += abs(area) * y
        if soma_area > 0:
            resultado[int(geometria["properties"]["codarea"])] = (
                round(soma_x / soma_area, CASAS_COORDENADA), round(soma_y / soma_area, CASAS_COORDENADA))
    return resultado


def main() -> None:
    PASTA_MALHA.mkdir(parents=True, exist_ok=True)
    print("Baixando as malhas do IBGE:")
    for arquivo, (intrarregiao, objeto, minimo) in CAMADAS.items():
        topo = baixar_malha(intrarregiao, objeto, minimo)
        caminho = PASTA_MALHA / f"{arquivo}.topo.json"
        caminho.write_text(json.dumps(topo, separators=(",", ":")), encoding="utf-8")
        print(f"    {caminho.relative_to(RAIZ)} ({caminho.stat().st_size / 1024:,.0f} KB)")

    print("Montando o territorio (municipio -> regioes + ponto central):")
    malha_municipios = baixar_malha("municipio", "BRMU", 5500)  # usada so em memoria, para os centroides
    centros = centroides_municipios(malha_municipios)
    municipios = chamar_api(URL_MUNICIPIOS, {"view": "nivelado"})
    colunas = ["municipio_id", "regiao_imediata_id", "regiao_imediata_nome",
               "regiao_intermediaria_id", "regiao_intermediaria_nome", "longitude", "latitude"]
    linhas = []
    for m in sorted(municipios, key=lambda x: x["municipio-id"]):
        lon, lat = centros.get(m["municipio-id"], (None, None))  # municipio novo pode nao ter malha
        linhas.append([m["municipio-id"], m["regiao-imediata-id"], m["regiao-imediata-nome"],
                       m["regiao-intermediaria-id"], m["regiao-intermediaria-nome"], lon, lat])
    sem_ponto = sum(1 for l in linhas if l[5] is None)

    conteudo = {"tabela": "ibge.territorio", "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
                "colunas": colunas}
    corpo = ",\n".join(json.dumps(l, ensure_ascii=False, separators=(",", ":")) for l in linhas)
    texto = json.dumps(conteudo, ensure_ascii=False)[:-1] + ',"linhas":[\n' + corpo + "\n]}\n"
    caminho = PASTA_DADOS / "territorio.json"
    caminho.write_text(texto, encoding="utf-8")
    print(f"    {caminho.relative_to(RAIZ)}: {len(linhas)} municipios, {sem_ponto} sem ponto "
          f"({caminho.stat().st_size / 1024:,.0f} KB)")


if __name__ == "__main__":
    main()
