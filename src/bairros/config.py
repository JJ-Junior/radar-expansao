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
# RADAR DE EXPANSAO - BAIRROS SOB DEMANDA: CONFIGURACAO COMUM
# =============================================================================
#
# OBJETIVO: reunir num lugar so os parametros do ranking de bairros (raio,
#           populacao minima, pesos) e os enderecos das fontes do IBGE e da
#           Receita Federal usados pelos outros scripts de src/bairros.
# ENTRADA:  variavel de ambiente DIR_DADOS (opcional)
# SAIDA:    constantes e funcoes de pasta importadas pelos outros modulos
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - constantes no bloco CONFIG
#   - os.path para montar caminhos
#
# NOVIDADES:
#   1. pasta de dados por variavel de ambiente -> o mesmo codigo roda no PC
#      (C:\dados\estudo-bairros) e no container (/dados)
#
# COMO RODAR: nao roda sozinho; e importado pelos outros scripts de src/bairros
# =============================================================================

# ============================== CONFIG ==============================
DIR_DADOS_PADRAO = r"C:\dados\estudo-bairros"   # no container: DIR_DADOS=/dados
RAIO_KM = 1.5            # concorrencia e populacao no entorno de cada bairro
POP_MIN = 5000           # so bairros com pelo menos esta populacao entram no ranking (escala do IBGE)
POP_MIN_POPULAR = 2000   # bairros populares sao menores (loteamentos): Bauru tem 7 com 5 mil hab. e 54 com 2 mil
PESOS = {"mercado": 0.30, "renda": 0.25, "espaco": 0.30, "densidade": 0.15}
NUMERACAO_QUADRA = {"3506003"}  # municipios com numero "quadra-casa" (ex.: 9-50)
CASAS_GEOJSON = 4        # casas decimais das coordenadas guardadas (~11 m)
TOLERANCIA_SIMPLIFICAR = 0.0003  # graus (~30 m) para simplificar contornos

FTP_CENSO = "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/"
AGREGADOS = {
    "basico": FTP_CENSO + "Agregados_por_Setores_Censitarios/Agregados_por_Setor_csv/Agregados_por_setores_basico_BR_20260520.zip",
    "demografia": FTP_CENSO + "Agregados_por_Setores_Censitarios/Agregados_por_Setor_csv/Agregados_por_setores_demografia_BR.zip",
    "renda": FTP_CENSO + "Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel/Agregados_por_setores_renda_responsavel_BR_20260508_csv.zip",
    "renda_bairro": FTP_CENSO + "Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel/Agregados_por_bairros_renda_responsavel_BR_20260508_csv.zip",
}
CNEFE_MUN = ("https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/"
             "Arquivos_CNEFE/CSV/Municipio/")
WFS_SETORES = ("https://geoservicos.ibge.gov.br/geoserver/wfs?service=WFS&version=2.0.0&request=GetFeature"
               "&typeNames=CGMAT:qg_2022_600_setcensitario__v02&outputFormat=application/json")
SIDRA_POP = "https://apisidra.ibge.gov.br/values/t/4714/n6/{cod}/v/93/p/2022"
LOCALIDADES_MUN = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios/{cod}"
LOCALIDADES_TODOS = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
API_CEP = "https://cep.awesomeapi.com.br/json/{cep}"   # so o CEP e enviado
MAX_CONSULTAS_CEP = 150   # teto por municipio (o resto fica sem coordenada)
PAUSA_CEP_SEGUNDOS = 0.5
USER_AGENT = "radar-expansao/0.1 (projeto academico de engenharia de dados)"

CNPJ_MES = "2026-11"
CNPJ_COMPARTILHAMENTO = "gn672Ad4CF8N6TK"
CNAE_ACADEMIA = "9313100"
CNAE_ENSINO_ESPORTES = "8591100"
UFS = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA", "22": "PI",
       "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
       "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}
# ====================================================================

import os


def dir_dados():
    return os.getenv("DIR_DADOS") or DIR_DADOS_PADRAO


def pastas(cod):
    """Pastas de um municipio: cache (fica entre pedidos) e tmp (o worker apaga depois de cada pedido)."""
    raiz = dir_dados()
    p = {"comum": os.path.join(raiz, "cache", "_comum"), "cache": os.path.join(raiz, "cache", cod),
         "tmp": os.path.join(raiz, "tmp", cod), "base": os.path.join(raiz, "base")}
    for v in p.values():
        os.makedirs(v, exist_ok=True)
    return p


def arquivo_base():
    """CSV nacional de academias (sem banco). BASE_ACADEMIAS permite apontar outro arquivo (testes)."""
    return os.getenv("BASE_ACADEMIAS") or os.path.join(dir_dados(), "base", "academias_brasil.csv")


def arquivo_agregado(p, chave):
    return os.path.join(p["comum"], AGREGADOS[chave].rsplit("/", 1)[1])
