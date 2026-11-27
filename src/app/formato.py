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
# RADAR DE EXPANSAO - ETAPA 7: DASHBOARD (TEXTOS, CORES E FORMATOS)
# =============================================================================
#
# OBJETIVO: guardar num lugar so os rotulos dos criterios, as cores do tema e
#           as funcoes que escrevem numeros no padrao brasileiro (1.234,5).
# ENTRADA:  valores vindos das tabelas da gold (ja carregados em DataFrame)
# SAIDA:    textos prontos para a tela; nao grava nada
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - dicionarios e f-strings com casas decimais ({valor:,.2f})
#
# NOVIDADES:
#   1. troca de separadores  -> o Python formata 1,234.5 (padrao EUA); trocar
#                               "," e "." da o padrao brasileiro 1.234,5
#   2. pd.isna               -> numero ausente vira um traco em vez de "nan" na tela
#   3. modulo compartilhado  -> as paginas importam daqui; mudar um rotulo aqui
#                               muda o dashboard inteiro
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: nao roda sozinho; e importado por src/app/app.py e pelas paginas
#
# =============================================================================

# ============================== CONFIG ==============================
# Cores alinhadas ao site de apoio: MARCA (limao), DADO (escala azul + laranja
# das cidades em destaque) e ESTADO (semaforo). Marca e dado nunca se misturam.
COR_MARCA = "#c4f03b"
COR_DESTAQUE = "#ff5a1f"
ESCALA_DADO = [
    [0.0, "#102c52"], [0.2, "#174377"], [0.4, "#1f5ba3"],
    [0.6, "#3a7fd0"], [0.8, "#6ea6e8"], [1.0, "#a9cbf3"],
]
COR_DADO = "#6ea6e8"
COR_DADO_2 = "#a9cbf3"
COR_SINAL = {"verde": "#0ca30c", "amarelo": "#fab219", "vermelho": "#d03b3b"}
COR_SINAL_STREAMLIT = {"verde": "green", "amarelo": "orange", "vermelho": "red"}
TRACO = "—"
# ====================================================================

import pandas as pd

REGIOES = {
    "N": "Norte",
    "NE": "Nordeste",
    "SE": "Sudeste",
    "S": "Sul",
    "CO": "Centro-Oeste",
}

# Os 6 criterios do prd.md (secao 4), na ordem de peso. "riqueza" junta nivel e
# tendencia do PIB per capita (5% + 5%), como a coluna nota_riqueza da gold.
CRITERIOS = {
    "mercado": "Tamanho de mercado",
    "poder_compra": "Poder de compra",
    "espaco_competitivo": "Espaço competitivo",
    "crescimento": "Crescimento",
    "riqueza": "Riqueza local",
    "mercado_formal": "Mercado formal",
}

# Rotulos com acento para os 7 componentes de gold.ranking_criterio (a gold
# guarda a descricao sem acento); a chave e a coluna "criterio".
COMPONENTES = {
    "mercado": ("Tamanho de mercado", "População estimada mais recente"),
    "poder_compra": ("Poder de compra", "Renda domiciliar per capita média (Censo 2022)"),
    "espaco_competitivo": (
        "Espaço competitivo",
        "Academias (CNAE 93.13-1) por 10 mil habitantes, limitadas aos percentis 5% e 95%",
    ),
    "crescimento": ("Crescimento", "Crescimento anual da população desde o Censo 2022"),
    "riqueza_nivel": ("Riqueza local · nível", "PIB per capita do último ano"),
    "riqueza_tendencia": (
        "Riqueza local · tendência",
        "Taxa média anual (CAGR) do PIB per capita em 5 anos",
    ),
    "mercado_formal": ("Mercado formal", "Salário médio mensal dos empregos formais"),
}

# O que compoe a nota: o MESMO texto do site de apoio (site/js/indicadores.js). Anos entre chaves
# vem de site/dados/meta.json ("periodos"), como no site.
TEXTO_CURTO_CRITERIO = {
    "mercado": "População: mais moradores, mais clientes possíveis",
    "poder_compra": "Renda por pessoa: quem pode pagar mensalidade",
    "espaco_competitivo": "Menos academias por habitante dá nota maior",
    "crescimento": "Quanto a população cresce por ano",
    "riqueza": "PIB por habitante: nível e tendência",
    "mercado_formal": "Salário médio dos empregos formais",
}
COMPOSICAO_NOTA = [  # (grupo, peso, sentido, o que mede, de onde vem, por que importa)
    ("mercado", "25%", "maior é melhor",
     "Quantas pessoas moram na cidade (população estimada mais recente).",
     "IBGE, estimativa de população (tabela 6579), {populacao}.",
     "Mais moradores querem dizer mais clientes possíveis para uma unidade."),
    ("poder_compra", "25%", "maior é melhor",
     "Renda média por pessoa das famílias, em R$ por mês.",
     "IBGE, Censo {censo} (tabela 10295).",
     "Mostra se os moradores conseguem pagar a mensalidade. Também é a trava das recomendadas."),
    ("espaco_competitivo", "20%", "menor é melhor",
     "Academias formais (CNAE 93.13-1, condicionamento físico) para cada 10 mil habitantes.",
     "IBGE, Cadastro Central de Empresas (tabela 9418), {academias}, dividido pela população.",
     "Menos academias por habitante deixa mais espaço para uma nova. A escala é invertida e os extremos são "
     "limitados aos percentis 5% e 95%."),
    ("crescimento", "15%", "maior é melhor",
     "Crescimento anual da população desde o Censo {censo}.",
     "IBGE, Censo {censo} (tabela 4714) e estimativa de população (tabela 6579).",
     "Cidade que cresce traz clientes novos nos próximos anos."),
    ("riqueza", "10%", "maior é melhor",
     "PIB por habitante: o valor do último ano (metade do peso) e o crescimento médio anual em 5 anos "
     "(a outra metade).",
     "IBGE, PIB dos Municípios (tabela 5938), até {pib}, dividido pela população.",
     "Uma economia local forte e em alta sustenta o consumo."),
    ("mercado_formal", "5%", "maior é melhor",
     "Salário médio mensal dos empregos formais, em R$.",
     "IBGE, Cadastro Central de Empresas (tabela 9509), {salario}.",
     "Emprego formal dá renda estável para um gasto que se repete todo mês."),
]
FRASE_COMPOSICAO = (
    "Cada nota vai de 0 a 100 e é o percentil da cidade entre as que têm 50 mil habitantes ou mais: nota 80 quer "
    "dizer que ela está à frente de 80% delas naquele critério. A nota final é a média ponderada pelos pesos."
)
PERIODOS_PADRAO = {"populacao": 2026, "censo": 2022, "pib": 2023, "academias": 2024, "salario": 2024}


def composicao_nota(periodos: dict | None = None) -> list[dict]:
    """Linhas do bloco "O que compoe a nota", com os anos da ultima exportacao."""
    anos = {**PERIODOS_PADRAO, **{k: v for k, v in (periodos or {}).items() if v}}
    return [
        {"Componente": CRITERIOS[g], "Peso": peso, "Sentido": sentido, "O que mede": mede.format(**anos),
         "De onde vem": fonte.format(**anos), "Por que importa": porque}
        for g, peso, sentido, mede, fonte, porque in COMPOSICAO_NOTA
    ]


# Nome das pesquisas citadas em gold.ranking_criterio.fonte ("IBGE 6579" etc.)
PESQUISAS_IBGE = {
    "6579": "Estimativas de população",
    "10295": "Censo 2022 · renda",
    "9418": "Cadastro Central de Empresas · empresas",
    "4714": "Censo 2022 · população",
    "5938": "PIB dos Municípios",
    "9509": "Cadastro Central de Empresas · salários",
}

SENTIDO = {"maior_melhor": "maior é melhor", "menor_melhor": "menor é melhor"}

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_EXTENSO = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def ausente(valor) -> bool:
    """Diz se o valor e nulo (None, NaN ou NaT)."""
    if valor is None:
        return True
    try:
        return bool(pd.isna(valor))
    except (TypeError, ValueError):
        return False


def numero(valor, casas: int = 0) -> str:
    """Escreve um numero no padrao brasileiro: 1.234,5."""
    if ausente(valor):
        return TRACO
    texto = f"{float(valor):,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def porcentagem(fracao, casas: int = 1, sinal: bool = False) -> str:
    """Fracao 0.0123 -> '1,2%' (com '+' opcional)."""
    if ausente(fracao):
        return TRACO
    texto = numero(float(fracao) * 100, casas) + "%"
    return f"+{texto}" if sinal and float(fracao) > 0 else texto


def pontos(valor, casas: int = 2, sinal: bool = True) -> str:
    """Valor ja em pontos percentuais: -1.25 -> '-1,25 p.p.'."""
    if ausente(valor):
        return TRACO
    texto = numero(valor, casas) + " p.p."
    return f"+{texto}" if sinal and float(valor) > 0 else texto


def reais(valor, casas: int = 2) -> str:
    """Valor em reais: 'R$ 1.234,56'."""
    return TRACO if ausente(valor) else f"R$ {numero(valor, casas)}"


def compacto(valor) -> str:
    """Populacao e PIB em forma curta: 1,59 mi / 54,1 mil."""
    if ausente(valor):
        return TRACO
    v = float(valor)
    if abs(v) >= 1e9:
        return f"{numero(v / 1e9, 2)} bi"
    if abs(v) >= 1e6:
        return f"{numero(v / 1e6, 2)} mi"
    if abs(v) >= 1e3:
        return f"{numero(v / 1e3, 1)} mil"
    return numero(v, 0)


def nota(valor) -> str:
    """Nota de 0 a 100 com uma casa."""
    return numero(valor, 1)


def ordinal(valor) -> str:
    """3 -> '3º'."""
    return TRACO if ausente(valor) else f"{int(valor)}º"


def mes_curto(data) -> str:
    """2026-10-01 -> 'out/2026'."""
    if ausente(data):
        return TRACO
    d = pd.Timestamp(data)
    return f"{MESES[d.month - 1]}/{d.year}"


def mes_extenso(data) -> str:
    """2026-10-01 -> 'outubro de 2026'."""
    if ausente(data):
        return TRACO
    d = pd.Timestamp(data)
    return f"{MESES_EXTENSO[d.month - 1]} de {d.year}"


def data_hora(valor) -> str:
    """Data e hora ISO -> '26/11/2026 16:24' no horario de Brasilia."""
    if ausente(valor):
        return TRACO
    d = pd.Timestamp(valor)
    if d.tzinfo is not None:
        d = d.tz_convert("America/Sao_Paulo")
    return d.strftime("%d/%m/%Y %H:%M")


def data_curta(valor) -> str:
    """Data ISO -> '26/11/2026'."""
    return TRACO if ausente(valor) else data_hora(valor)[:10]


def fonte_legivel(fonte: str) -> str:
    """'IBGE 9418 / 6579' -> 'IBGE · Cadastro Central de Empresas · empresas (9418) + ...'."""
    if ausente(fonte):
        return TRACO
    texto = str(fonte)
    if not texto.startswith("IBGE"):
        return texto
    codigos = [c.strip() for c in texto.removeprefix("IBGE").split("/")]
    partes = [f"{PESQUISAS_IBGE.get(c, 'agregado')} ({c})" for c in codigos if c]
    return "IBGE · " + " + ".join(partes)




def notas_por_criterio(linha) -> list[tuple[str, str, float]]:
    """(chave, rotulo, nota) dos 6 criterios de uma linha do ranking, sem os ausentes."""
    return [
        (chave, rotulo, float(linha[f"nota_{chave}"]))
        for chave, rotulo in CRITERIOS.items()
        if not ausente(linha.get(f"nota_{chave}"))
    ]


def pontos_fortes(linha, quantidade: int = 2) -> list[tuple[str, float]]:
    """Os criterios com as maiores notas da cidade (so leitura das notas da gold)."""
    notas = sorted(notas_por_criterio(linha), key=lambda x: x[2], reverse=True)
    return [(rotulo, valor) for _, rotulo, valor in notas[:quantidade]]


def pontos_fracos(linha, quantidade: int = 2) -> list[tuple[str, float]]:
    """Os criterios com as menores notas da cidade."""
    notas = sorted(notas_por_criterio(linha), key=lambda x: x[2])
    return [(rotulo, valor) for _, rotulo, valor in notas[:quantidade]]
