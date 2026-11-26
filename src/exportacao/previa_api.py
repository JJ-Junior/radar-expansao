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
# RADAR DE EXPANSAO - ETAPA 6: SITE DE APOIO (PREVIA DIRETO DAS APIS)
# =============================================================================
#
# OBJETIVO: enquanto a camada gold nao existe, montar as mesmas tabelas da gold
#           (spec.md 3.3) direto das APIs do IBGE e do BCB, com as regras do
#           spec.md 5.1 a 5.3. O resultado e uma PREVIA: o site avisa isso.
# ENTRADA:  IBGE Localidades, IBGE Agregados v3 (6579, 4714, 5938, 10295, 9418,
#           9509, 7060) e BCB SGS (432, 10813)
# SAIDA:    DataFrames em memoria; quem grava e o exportar_site.py
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - requests com timeout, try/except e novas tentativas
#   - pandas: DataFrame, merge, groupby, shift
#
# NOVIDADES:
#   1. rank(method="min")  -> reproduz o percent_rank() do Postgres:
#                             (posicao - 1) / (quantidade - 1)
#   2. CAGR                -> crescimento anual composto: (fim/inicio)^(1/anos) - 1
#   3. resample("MS")      -> agrupa uma serie diaria em meses (MS = inicio do mes)
#   4. /periodos do IBGE   -> descobre o ultimo ano publicado em vez de fixar no codigo
#
# INSTALACAO: pip install requests pandas   (ou: pip install -r requirements.txt)
# COMO RODAR: nao roda sozinho; e chamado por python src/exportacao/exportar_site.py
#
# =============================================================================

# ============================== CONFIG ==============================
# Anos de cada fonte. None = descobre o ultimo periodo publicado pela API.
ANO_POPULACAO = None          # IBGE 6579 (estimativa)
ANO_PIB = None                # IBGE 5938
ANO_ACADEMIAS = None          # IBGE 9418 (CNAE 93.13-1)
ANO_SALARIO = None            # IBGE 9509
ANO_CENSO = 2022              # IBGE 4714 e 10295
ANOS_TENDENCIA_PIB = 5        # janela da tendencia do PIB per capita

# Universo e pesos do ranking (prd.md, secao 4). Soma dos pesos = 1.
POPULACAO_MINIMA = 50_000
VERSAO_PESOS = "prd-v0.2"
PESOS = {
    "mercado": 0.25,
    "poder_compra": 0.25,
    "espaco_competitivo": 0.20,
    "crescimento": 0.15,
    "riqueza": 0.10,            # 5% nivel + 5% tendencia do PIB per capita
    "mercado_formal": 0.05,
}
NOTA_NEUTRA = 50.0            # nota de um criterio sem dado (prd.md, secao 4)

# Momento economico (spec.md 5.1). Limiares iniciais, a validar com o squad.
DATA_INICIO_BCB = "2015-01-01"
JUROS_LIMITE_PP = 0.5         # variacao da Selic em 12 meses, em p.p.
IPCA_META = 4.5               # IPCA 12 meses, %
IPCA_MESES_TENDENCIA = 3      # acelerando/desacelerando contra N meses antes
DOLAR_ALTA_MAXIMA_PCT = 10.0  # alta do dolar em 12 meses, %

# Chamadas de API (spec.md, secao 6)
TIMEOUT_SEGUNDOS = 60
TIMEOUT_LONGO_SEGUNDOS = 120  # 9418 (CNAE) demora 11-22 s
TENTATIVAS = 3
USER_AGENT = "radar-expansao/0.1 (projeto academico; dados publicos)"
URL_IBGE = "https://servicodados.ibge.gov.br/api"
URL_BCB = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
# ====================================================================

import math
import time
from datetime import date, datetime, timedelta

import pandas as pd
import requests

# Simbolos do IBGE no lugar de numero (spec.md 2.2)
SIMBOLOS_NULOS = {"...", "X", "..", ""}
SIMBOLO_ZERO = "-"


# ------------------------------------------------------------------ chamadas

def chamar_api(url: str, params: dict | None = None, timeout: int = TIMEOUT_SEGUNDOS,
               aceitar_404: bool = False):
    """GET com ate TENTATIVAS tentativas; devolve o JSON (ou [] num 404 aceito)."""
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resposta = requests.get(url, params=params, timeout=timeout,
                                    headers={"User-Agent": USER_AGENT})
            if aceitar_404 and resposta.status_code == 404:
                return []  # BCB: periodo sem dado = nada novo, nao e erro
            resposta.raise_for_status()
            if "json" not in resposta.headers.get("content-type", ""):
                raise ValueError(f"resposta nao e JSON ({resposta.headers.get('content-type')})")
            return resposta.json()
        except (requests.RequestException, ValueError) as erro:
            print(f"    tentativa {tentativa} falhou: {erro}")
            if tentativa == TENTATIVAS:
                raise
            time.sleep(2 ** tentativa)


def ultimo_periodo(agregado: int) -> int:
    """Ultimo periodo publicado de um agregado anual do IBGE."""
    periodos = chamar_api(f"{URL_IBGE}/v3/agregados/{agregado}/periodos")
    return max(int(p["id"]) for p in periodos)


def converter_valor(texto, traco_vira_zero: bool = False) -> float:
    """Texto da API -> numero; simbolos viram NaN (ou 0 para o '-' quando pedido)."""
    if texto is None or texto in SIMBOLOS_NULOS:
        return math.nan
    if texto == SIMBOLO_ZERO:
        return 0.0 if traco_vira_zero else math.nan
    return float(texto)


def buscar_agregado_municipios(agregado: int, periodo: int, variavel: int,
                               classificacao: str | None = None,
                               traco_vira_zero: bool = False,
                               timeout: int = TIMEOUT_SEGUNDOS) -> pd.Series:
    """Um periodo x uma variavel x todos os municipios (~5.570 valores, bem abaixo do limite)."""
    url = f"{URL_IBGE}/v3/agregados/{agregado}/periodos/{periodo}/variaveis/{variavel}"
    params = {"localidades": "N6[all]"}
    if classificacao:
        params["classificacao"] = classificacao
    print(f"  IBGE {agregado}/{variavel} periodo {periodo} ...")
    dados = chamar_api(url, params=params, timeout=timeout)
    valores = {}
    for serie in dados[0]["resultados"][0]["series"]:
        codigo = int(serie["localidade"]["id"])
        valores[codigo] = converter_valor(serie["serie"].get(str(periodo)), traco_vira_zero)
    return pd.Series(valores, name=f"{agregado}_{variavel}_{periodo}", dtype="float64")


def buscar_municipios() -> pd.DataFrame:
    """Lista oficial de municipios com UF e regiao."""
    print("  IBGE localidades/municipios ...")
    dados = chamar_api(f"{URL_IBGE}/v1/localidades/municipios", params={"view": "nivelado"})
    return pd.DataFrame({
        "municipio_id": [m["municipio-id"] for m in dados],
        "municipio_nome": [m["municipio-nome"] for m in dados],
        "uf_sigla": [m["UF-sigla"] for m in dados],
        "regiao_sigla": [m["regiao-sigla"] for m in dados],
    }).set_index("municipio_id", drop=False)


# ------------------------------------------------------------- municipios

def cagr(fim: pd.Series, inicio: pd.Series, anos: int) -> pd.Series:
    """Crescimento anual composto; NaN quando falta dado ou o inicio e zero."""
    razao = fim / inicio.where(inicio > 0)
    return razao ** (1 / anos) - 1


def calcular_indicadores(agora: str) -> tuple[pd.DataFrame, dict]:
    """Monta gold.indicadores_municipio (spec.md 5.2) direto das APIs."""
    ano_pop = ANO_POPULACAO or ultimo_periodo(6579)
    ano_pib = ANO_PIB or ultimo_periodo(5938)
    ano_acad = ANO_ACADEMIAS or ultimo_periodo(9418)
    ano_sal = ANO_SALARIO or ultimo_periodo(9509)

    mun = buscar_municipios()
    censo = buscar_agregado_municipios(4714, ANO_CENSO, 93)
    estimativas: dict[int, pd.Series] = {}

    def populacao_do_ano(ano: int) -> pd.Series:
        """Populacao de um ano: Censo em 2022, interpolacao geometrica em 2023, estimativa nos demais."""
        if ano == ANO_CENSO:
            return censo
        if ano == ANO_CENSO + 1:  # 2023 nao existe na fonte (spec.md 5.2)
            return (populacao_do_ano(ANO_CENSO) * populacao_do_ano(ANO_CENSO + 2)) ** 0.5
        if ano not in estimativas:
            estimativas[ano] = buscar_agregado_municipios(6579, ano, 9324)
        return estimativas[ano]

    pop = populacao_do_ano(ano_pop)
    pib = buscar_agregado_municipios(5938, ano_pib, 37)
    pib_base = buscar_agregado_municipios(5938, ano_pib - ANOS_TENDENCIA_PIB, 37)
    renda = buscar_agregado_municipios(10295, ANO_CENSO, 13431,
                                       classificacao="2[6794]|86[95251]|58[95253]")
    academias = buscar_agregado_municipios(9418, ano_acad, 2585, classificacao="12762[117856]",
                                           traco_vira_zero=True, timeout=TIMEOUT_LONGO_SEGUNDOS)
    salario = buscar_agregado_municipios(9509, ano_sal, 10143)

    pib_pc = pib * 1000 / populacao_do_ano(ano_pib)
    pib_pc_base = pib_base * 1000 / populacao_do_ano(ano_pib - ANOS_TENDENCIA_PIB)

    ind = mun.copy()
    ind["populacao"] = pop.reindex(ind.index)
    ind["populacao_ano"] = ano_pop
    ind["populacao_censo_2022"] = censo.reindex(ind.index)
    ind["crescimento_pop_aa"] = cagr(ind["populacao"], ind["populacao_censo_2022"], ano_pop - ANO_CENSO)
    ind["pib_mil_reais"] = pib.reindex(ind.index)
    ind["pib_ano"] = ano_pib
    ind["pib_per_capita"] = pib_pc.reindex(ind.index)
    ind["pib_per_capita_tendencia"] = cagr(pib_pc, pib_pc_base, ANOS_TENDENCIA_PIB).reindex(ind.index)
    ind["renda_dom_per_capita"] = renda.reindex(ind.index)
    ind["academias_qtd"] = academias.reindex(ind.index)
    ind["academias_ano"] = ano_acad
    pop_acad = populacao_do_ano(ano_acad).reindex(ind.index)
    ind["academias_por_10mil_hab"] = ind["academias_qtd"] / pop_acad.where(pop_acad > 0) * 10_000
    ind["salario_medio"] = salario.reindex(ind.index)
    ind["atualizado_em"] = agora

    # Arredondamentos no padrao das colunas da gold (spec.md 3.3)
    ind = ind.round({"crescimento_pop_aa": 4, "pib_per_capita": 2, "pib_per_capita_tendencia": 4,
                     "renda_dom_per_capita": 2, "academias_por_10mil_hab": 3, "salario_medio": 2})
    for coluna in ["populacao", "populacao_censo_2022", "academias_qtd"]:
        ind[coluna] = ind[coluna].round().astype("Int64")
    ind.loc[ind["academias_qtd"].isna(), "academias_ano"] = pd.NA
    ind["academias_ano"] = ind["academias_ano"].astype("Int64")

    periodos = {"populacao": ano_pop, "censo": ANO_CENSO, "pib": ano_pib,
                "academias": ano_acad, "salario": ano_sal}
    return ind.reset_index(drop=True), periodos


def percentil(valores: pd.Series, menor_melhor: bool = False) -> pd.Series:
    """Nota 0-100 igual ao percent_rank() do Postgres; NaN continua NaN."""
    base = -valores if menor_melhor else valores
    quantidade = base.notna().sum()
    if quantidade <= 1:
        return base * 0 + 100
    return (base.rank(method="min") - 1) / (quantidade - 1) * 100


def calcular_ranking(ind: pd.DataFrame, agora: str) -> pd.DataFrame:
    """Monta gold.ranking_expansao (spec.md 5.3) para o universo >= POPULACAO_MINIMA."""
    uni = ind[ind["populacao"] >= POPULACAO_MINIMA].copy()
    pop = uni["populacao"].astype("float64")

    notas = pd.DataFrame(index=uni.index)
    notas["nota_mercado"] = percentil(pop)
    notas["nota_poder_compra"] = percentil(uni["renda_dom_per_capita"])
    notas["nota_espaco_competitivo"] = percentil(uni["academias_por_10mil_hab"], menor_melhor=True)
    notas["nota_crescimento"] = percentil(uni["crescimento_pop_aa"])
    nivel = percentil(uni["pib_per_capita"])
    tendencia = percentil(uni["pib_per_capita_tendencia"])
    notas["nota_mercado_formal"] = percentil(uni["salario_medio"])

    incompleto = notas.isna().any(axis=1) | nivel.isna() | tendencia.isna()
    notas["nota_riqueza"] = (nivel.fillna(NOTA_NEUTRA) + tendencia.fillna(NOTA_NEUTRA)) / 2
    notas = notas.fillna(NOTA_NEUTRA)

    final = sum(notas[f"nota_{criterio}"] * peso for criterio, peso in PESOS.items())

    rk = uni[["municipio_id", "municipio_nome", "uf_sigla", "regiao_sigla", "populacao"]].copy()
    for coluna in ["nota_mercado", "nota_poder_compra", "nota_espaco_competitivo",
                   "nota_crescimento", "nota_riqueza", "nota_mercado_formal"]:
        rk[coluna] = notas[coluna].round(2)
    rk["nota_final"] = final.round(2)
    rk = rk.sort_values(["nota_final", "populacao"], ascending=[False, False])
    rk["posicao_brasil"] = range(1, len(rk) + 1)
    rk["posicao_uf"] = rk.groupby("uf_sigla").cumcount() + 1
    rk["dados_incompletos"] = incompleto.reindex(rk.index)
    rk["versao_pesos"] = VERSAO_PESOS
    rk["calculado_em"] = agora
    return rk.reset_index(drop=True)


def montar_criterios() -> pd.DataFrame:
    """Monta gold.ranking_criterio com os pesos do prd.md."""
    linhas = [
        ("mercado", "Tamanho de mercado: população estimada mais recente",
         "IBGE 6579 (estimativas de população)", "maior_melhor"),
        ("poder_compra", "Poder de compra: renda domiciliar per capita média",
         "IBGE 10295 (Censo 2022)", "maior_melhor"),
        ("espaco_competitivo", "Espaço competitivo: academias (CNAE 93.13-1) por 10 mil habitantes",
         "IBGE 9418 (Cadastro Central de Empresas)", "menor_melhor"),
        ("crescimento", "Crescimento anual da população desde o Censo 2022",
         "IBGE 4714 (Censo 2022) + 6579 (estimativas)", "maior_melhor"),
        ("riqueza", "Riqueza local: PIB per capita (nível 5% + tendência de 5 anos 5%)",
         "IBGE 5938 (PIB dos Municípios)", "maior_melhor"),
        ("mercado_formal", "Mercado formal: salário médio mensal dos empregos formais",
         "IBGE 9509 (Cadastro Central de Empresas)", "maior_melhor"),
    ]
    df = pd.DataFrame(linhas, columns=["criterio", "descricao", "fonte", "sentido"])
    df["peso"] = df["criterio"].map(PESOS)
    df["versao_pesos"] = VERSAO_PESOS
    if abs(df["peso"].sum() - 1) > 1e-9:
        raise ValueError(f"soma dos pesos = {df['peso'].sum()}, deveria ser 1")
    return df[["criterio", "descricao", "fonte", "peso", "sentido", "versao_pesos"]]


# ------------------------------------------------------------------ macro

def buscar_sgs(codigo: int, inicio: date, fim: date) -> pd.Series:
    """Serie diaria do BCB em janelas de ate 10 anos (limite da API)."""
    pedacos = []
    janela_inicio = inicio
    while janela_inicio <= fim:
        janela_fim = min(date(janela_inicio.year + 10, janela_inicio.month, 1) - timedelta(days=1), fim)
        print(f"  BCB {codigo} de {janela_inicio:%d/%m/%Y} a {janela_fim:%d/%m/%Y} ...")
        dados = chamar_api(URL_BCB.format(codigo=codigo), aceitar_404=True,
                           params={"formato": "json", "dataInicial": f"{janela_inicio:%d/%m/%Y}",
                                   "dataFinal": f"{janela_fim:%d/%m/%Y}"})
        pedacos.extend(dados)
        janela_inicio = janela_fim + timedelta(days=1)
    serie = pd.Series({pd.to_datetime(d["data"], format="%d/%m/%Y"): float(d["valor"]) for d in pedacos})
    serie = serie.sort_index()
    return serie[serie.index <= pd.Timestamp(fim)]  # a Selic traz datas futuras (spec.md 2.4)


def buscar_ipca() -> pd.DataFrame:
    """IPCA mensal e 12 meses (IBGE 7060), todos os meses listados em /periodos."""
    periodos = [p["id"] for p in chamar_api(f"{URL_IBGE}/v3/agregados/7060/periodos")]
    print(f"  IBGE 7060 ({len(periodos)} meses) ...")
    dados = chamar_api(f"{URL_IBGE}/v3/agregados/7060/periodos/{'|'.join(periodos)}/variaveis/63|2265",
                       params={"localidades": "N1[all]", "classificacao": "315[7169]"})
    colunas = {}
    for variavel in dados:
        nome = "ipca_mensal" if variavel["id"] == "63" else "ipca_12m"
        serie = variavel["resultados"][0]["series"][0]["serie"]
        colunas[nome] = {pd.Timestamp(year=int(p[:4]), month=int(p[4:]), day=1): converter_valor(v)
                         for p, v in serie.items()}
    return pd.DataFrame(colunas)


def calcular_contexto_macro(agora: str) -> pd.DataFrame:
    """Monta gold.contexto_macro (spec.md 5.1): uma linha por mes."""
    hoje = date.today()
    inicio = date.fromisoformat(DATA_INICIO_BCB)
    selic = buscar_sgs(432, inicio, hoje).resample("MS").last()     # vigente no ultimo dia do mes
    dolar = buscar_sgs(10813, inicio, hoje).resample("MS").mean()   # media dos dias uteis
    ipca = buscar_ipca()

    meses = pd.date_range(inicio, pd.Timestamp(hoje).to_period("M").to_timestamp(), freq="MS")
    macro = pd.DataFrame(index=meses)
    macro["selic_meta"] = selic.reindex(meses)
    macro["selic_var_12m_pp"] = macro["selic_meta"] - macro["selic_meta"].shift(12)
    macro["dolar_medio"] = dolar.reindex(meses)
    macro["dolar_var_12m_pct"] = (macro["dolar_medio"] / macro["dolar_medio"].shift(12) - 1) * 100
    macro = macro.join(ipca, how="left")
    macro = macro.round({"selic_meta": 2, "selic_var_12m_pp": 2, "dolar_medio": 4,
                         "dolar_var_12m_pct": 2, "ipca_mensal": 2, "ipca_12m": 2})
    macro["atualizado_em"] = agora
    macro.index.name = "mes"
    return macro.reset_index()[["mes", "selic_meta", "selic_var_12m_pp", "dolar_medio",
                                "dolar_var_12m_pct", "ipca_mensal", "ipca_12m", "atualizado_em"]]


def numero_br(valor: float, casas: int = 2, sinal: bool = False) -> str:
    """Formata 1234.5 como '1.234,50' (com '+' opcional) para a frase do semaforo."""
    texto = f"{valor:{'+' if sinal else ''},.{casas}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def calcular_momento(macro: pd.DataFrame, agora: str) -> pd.DataFrame:
    """Monta gold.momento_expansao: semaforo por mes com os tres sinais (spec.md 5.1)."""
    m = macro.set_index("mes")
    ipca_antes = m["ipca_12m"].shift(IPCA_MESES_TENDENCIA)
    linhas = []
    for mes, l in m.iterrows():
        antes = ipca_antes.loc[mes]
        if any(pd.isna(v) for v in (l["selic_var_12m_pp"], l["dolar_var_12m_pct"], l["ipca_12m"], antes)):
            continue  # so meses com os tres sinais

        var_juros = l["selic_var_12m_pp"]
        juros = "verde" if var_juros <= -JUROS_LIMITE_PP else "vermelho" if var_juros > JUROS_LIMITE_PP else "amarelo"

        dentro_meta = l["ipca_12m"] <= IPCA_META
        desacelerando, acelerando = l["ipca_12m"] < antes, l["ipca_12m"] > antes
        inflacao = ("verde" if dentro_meta and desacelerando
                    else "vermelho" if not dentro_meta and acelerando else "amarelo")

        var_dolar = l["dolar_var_12m_pct"]
        cambio = "verde" if var_dolar <= 0 else "amarelo" if var_dolar <= DOLAR_ALTA_MAXIMA_PCT else "vermelho"

        pontos = {"verde": 1, "amarelo": 0, "vermelho": -1}
        pontuacao = pontos[juros] + pontos[inflacao] + pontos[cambio]
        recomendacao = ("Expandir agora" if pontuacao >= 2
                        else "Expandir com cautela" if pontuacao >= 0 else "Esperar")
        tendencia = "desacelerando" if desacelerando else "acelerando" if acelerando else "estável"
        justificativa = (
            f"Selic em {numero_br(l['selic_meta'])}% a.a. ({numero_br(var_juros, sinal=True)} p.p. em 12 meses); "
            f"IPCA de {numero_br(l['ipca_12m'])}% em 12 meses, {tendencia}; "
            f"dólar {numero_br(var_dolar, 1, sinal=True)}% em 12 meses."
        )
        linhas.append((mes, juros, inflacao, cambio, pontuacao, recomendacao, justificativa, agora))

    return pd.DataFrame(linhas, columns=["mes", "sinal_juros", "sinal_inflacao", "sinal_cambio", "pontuacao",
                                         "recomendacao", "justificativa", "atualizado_em"])


def montar_previa() -> dict:
    """Roda tudo e devolve as tabelas no formato da gold + os periodos usados."""
    agora = datetime.now().astimezone().isoformat(timespec="seconds")
    print("Municipios (IBGE):")
    indicadores, periodos = calcular_indicadores(agora)
    ranking = calcular_ranking(indicadores, agora)
    print("Momento economico (BCB + IBGE):")
    macro = calcular_contexto_macro(agora)
    momento = calcular_momento(macro, agora)
    ultimo_mes = macro.dropna(subset=["selic_meta"])["mes"].max()
    periodos["macro_ate"] = f"{ultimo_mes:%Y-%m}"
    return {
        "gerado_em": agora,
        "periodos": periodos,
        "versao_pesos": VERSAO_PESOS,
        "populacao_minima_universo": POPULACAO_MINIMA,
        "tabelas": {
            "indicadores_municipio": indicadores,
            "ranking_expansao": ranking,
            "ranking_criterio": montar_criterios(),
            "contexto_macro": macro,
            "momento_expansao": momento,
        },
    }
