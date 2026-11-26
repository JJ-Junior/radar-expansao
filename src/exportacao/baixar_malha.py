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
# RADAR DE EXPANSAO - ETAPA 6: SITE DE APOIO (MALHA DOS MUNICIPIOS)
# =============================================================================
#
# OBJETIVO: baixar a malha oficial dos municipios do IBGE (TopoJSON, qualidade
#           minima) e salvar como arquivo estatico para o mapa do site.
# ENTRADA:  API de Malhas v3 do IBGE (/api/v3/malhas/paises/BR)
# SAIDA:    site/dados/malha/municipios.topo.json (substitui o arquivo inteiro)
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - requests.get com parametros, timeout e tratamento de erro
#   - gravar arquivos com pathlib
#
# NOVIDADES:
#   1. TopoJSON          -> formato de mapa que guarda cada fronteira uma vez so
#                           (vizinhos compartilham a mesma linha); fica bem menor
#                           que o GeoJSON equivalente
#   2. qualidade=minima  -> o proprio IBGE simplifica o desenho dos poligonos;
#                           para um mapa do Brasil inteiro na tela e suficiente
#   3. content-type      -> conferir que a resposta e JSON antes de gravar
#
# INSTALACAO: pip install requests   (ou: pip install -r requirements.txt)
# COMO RODAR: python src/exportacao/baixar_malha.py
#
# =============================================================================

# ============================== CONFIG ==============================
URL_MALHA = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
PARAMETROS = {
    "formato": "application/json",   # application/json = TopoJSON nesta API
    "qualidade": "minima",           # minima | intermediaria | maxima
    "intrarregiao": "municipio",     # um poligono por municipio
}
OBJETO_ESPERADO = "BRMU"             # nome do objeto dentro do TopoJSON
MINIMO_MUNICIPIOS = 5_500            # abaixo disso a resposta veio incompleta
TIMEOUT_SEGUNDOS = 60
TENTATIVAS = 3
USER_AGENT = "radar-expansao/0.1 (projeto academico; dados publicos)"
# ====================================================================

import json
import time
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO_SAIDA = RAIZ / "site" / "dados" / "malha" / "municipios.topo.json"


def baixar_malha() -> dict:
    """Chama a API de Malhas com ate TENTATIVAS tentativas e devolve o TopoJSON."""
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resposta = requests.get(URL_MALHA, params=PARAMETROS, timeout=TIMEOUT_SEGUNDOS,
                                    headers={"User-Agent": USER_AGENT})
            resposta.raise_for_status()
            if "json" not in resposta.headers.get("content-type", ""):
                raise ValueError(f"resposta nao e JSON: {resposta.headers.get('content-type')}")
            return resposta.json()
        except (requests.RequestException, ValueError) as erro:
            print(f"  tentativa {tentativa} falhou: {erro}")
            if tentativa == TENTATIVAS:
                raise
            time.sleep(2 ** tentativa)  # espera 2 s, 4 s...


def validar_malha(topo: dict) -> int:
    """Confere o objeto e a quantidade de municipios; devolve a quantidade."""
    if topo.get("type") != "Topology" or OBJETO_ESPERADO not in topo.get("objects", {}):
        raise ValueError(f"TopoJSON inesperado: objetos {list(topo.get('objects', {}))}")
    geometrias = topo["objects"][OBJETO_ESPERADO]["geometries"]
    if len(geometrias) < MINIMO_MUNICIPIOS:
        raise ValueError(f"so {len(geometrias)} municipios na malha")
    return len(geometrias)


def main() -> None:
    print(f"Baixando a malha de {URL_MALHA} ...")
    topo = baixar_malha()
    quantidade = validar_malha(topo)
    ARQUIVO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    # separators sem espaco: o arquivo fica menor e o conteudo e o mesmo que veio da API
    ARQUIVO_SAIDA.write_text(json.dumps(topo, separators=(",", ":")), encoding="utf-8")
    tamanho_kb = ARQUIVO_SAIDA.stat().st_size / 1024
    print(f"OK: {quantidade} municipios gravados em {ARQUIVO_SAIDA.relative_to(RAIZ)} ({tamanho_kb:,.0f} KB)")


if __name__ == "__main__":
    main()
