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
# RADAR DE EXPANSAO - ETAPA 6: SITE DE APOIO (EXPORTACAO DOS DADOS)
# =============================================================================
#
# OBJETIVO: gerar os arquivos JSON que o site de apoio le (contrato em
#           site/dados/README.md), a partir da camada gold ou, enquanto ela nao
#           existe, de uma previa calculada direto das APIs (previa_api.py).
# ENTRADA:  FONTE = "gold": tabelas gold.* do Supabase autohospedado via Docker
#           (conexao pelo .env, incluindo DB_SSLMODE) + contagem de linhas
#           das camadas bronze, silver e gold
#           FONTE = "api":  APIs do IBGE e do BCB
# SAIDA:    site/dados/*.json (substitui os arquivos inteiros a cada execucao)
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - pandas.read_sql com SQLAlchemy e credenciais no .env
#   - gravar JSON com o modulo json
#
# NOVIDADES:
#   1. JSON colunar            -> {"colunas": [...], "linhas": [[...]]}: os nomes
#                                 das colunas aparecem uma vez so; arquivo menor
#   2. df.to_json(orient="split") -> o pandas ja entrega colunas + linhas e troca
#                                 NaN por null (o JSON nao aceita NaN)
#   3. information_schema      -> catalogo do Postgres para listar as tabelas de
#                                 cada camada e contar as linhas
#   4. site estatico           -> o navegador le arquivos prontos; nenhuma
#                                 credencial do banco vai para o site
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: python src/exportacao/exportar_site.py
#
# =============================================================================

# ============================== CONFIG ==============================
FONTE = "api"                 # "gold" (oficial) | "api" (previa enquanto a gold nao existe)
SCHEMA_GOLD = "gold"
TABELAS = [                   # arquivo site/dados/<tabela>.json  <-  gold.<tabela>
    "indicadores_municipio",
    "ranking_expansao",
    "ranking_criterio",
    "contexto_macro",
    "momento_expansao",
]
ORDEM = {                     # ordenacao das linhas em cada arquivo
    "indicadores_municipio": "municipio_id",
    "ranking_expansao": "posicao_brasil",
    "ranking_criterio": "peso DESC, criterio",
    "contexto_macro": "mes",
    "momento_expansao": "mes",
}
CAMADAS = ["bronze", "silver", "gold"]   # contagem de linhas para a secao "Arquitetura"
POPULACAO_MINIMA = 50_000                # so informativo no meta.json (o corte vale na gold)
CASAS_DECIMAIS = 6
# ====================================================================

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
PASTA_SAIDA = RAIZ / "site" / "dados"


def conectar_banco():
    """Cria a engine do SQLAlchemy com as variaveis do .env (Supabase autohospedado via Docker)."""
    from dotenv import load_dotenv
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL

    load_dotenv(RAIZ / ".env")  # credenciais vem do .env, nunca do codigo
    faltando = [v for v in ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"] if not os.getenv(v)]
    if faltando:
        sys.exit(f"Variaveis ausentes no .env: {', '.join(faltando)}")
    url = URL.create("postgresql+psycopg2", username=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"),
                     host=os.getenv("DB_HOST"), port=int(os.getenv("DB_PORT")), database=os.getenv("DB_NAME"),
                     query={"sslmode": os.getenv("DB_SSLMODE") or "prefer"})  # prefer | require | disable
    return create_engine(url)


def contar_camadas(engine) -> dict:
    """Tabelas e quantidade de linhas de cada camada (bronze, silver, gold)."""
    from sqlalchemy import text

    resultado = {}
    with engine.connect() as conexao:
        for camada in CAMADAS:
            tabelas = conexao.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_type = 'BASE TABLE' ORDER BY table_name"
            ), {"schema": camada}).scalars().all()
            # nomes vem do catalogo do proprio banco, por isso podem entrar na consulta
            resultado[camada] = [
                {"tabela": f"{camada}.{t}",
                 "linhas": conexao.execute(text(f'SELECT count(*) FROM "{camada}"."{t}"')).scalar()}
                for t in tabelas
            ] or None
    return resultado


def ler_gold() -> dict:
    """Le as tabelas gold.* e monta o mesmo dicionario que a previa devolve."""
    engine = conectar_banco()
    tabelas = {t: pd.read_sql(f"SELECT * FROM {SCHEMA_GOLD}.{t} ORDER BY {ORDEM[t]}", engine) for t in TABELAS}
    ind, macro = tabelas["indicadores_municipio"], tabelas["contexto_macro"]
    criterios = tabelas["ranking_criterio"]
    ultimo_mes = pd.to_datetime(macro.dropna(subset=["selic_meta"])["mes"]).max()
    return {
        "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "periodos": {
            "populacao": int(ind["populacao_ano"].max()),
            "censo": 2022,
            "pib": int(ind["pib_ano"].max()),
            "academias": int(ind["academias_ano"].max()),
            "salario": None,  # a gold nao guarda o ano do salario medio
            "macro_ate": f"{ultimo_mes:%Y-%m}" if pd.notna(ultimo_mes) else None,
        },
        "versao_pesos": str(criterios["versao_pesos"].iloc[0]) if len(criterios) else None,
        "populacao_minima_universo": POPULACAO_MINIMA,
        "camadas": contar_camadas(engine),
        "tabelas": tabelas,
    }


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    """Datas viram texto ISO; 'mes' vira AAAA-MM-DD (o contrato pede data sem hora)."""
    df = df.copy()
    for coluna in df.columns:
        if coluna == "mes":
            df[coluna] = pd.to_datetime(df[coluna]).dt.strftime("%Y-%m-%d")
        elif pd.api.types.is_datetime64_any_dtype(df[coluna]):
            df[coluna] = df[coluna].map(lambda v: v.isoformat() if pd.notna(v) else None)
    return df


def gravar_tabela(nome: str, df: pd.DataFrame, gerado_em: str) -> int:
    """Grava site/dados/<nome>.json no formato colunar do contrato; devolve o numero de linhas."""
    dividido = json.loads(preparar(df).to_json(orient="split", index=False, double_precision=CASAS_DECIMAIS,
                                               force_ascii=False))
    conteudo = {"tabela": f"{SCHEMA_GOLD}.{nome}", "gerado_em": gerado_em,
                "colunas": dividido["columns"], "linhas": dividido["data"]}
    caminho = PASTA_SAIDA / f"{nome}.json"
    # uma linha por registro: arquivo compacto e diff do git legivel
    corpo = ",\n".join(json.dumps(l, ensure_ascii=False, separators=(",", ":")) for l in conteudo["linhas"])
    cabecalho = {k: v for k, v in conteudo.items() if k != "linhas"}
    texto = json.dumps(cabecalho, ensure_ascii=False)[:-1] + ',"linhas":[\n' + corpo + "\n]}\n"
    caminho.write_text(texto, encoding="utf-8")
    print(f"  {caminho.relative_to(RAIZ)}: {len(df)} linhas ({caminho.stat().st_size / 1024:,.0f} KB)")
    return len(df)


def conferir(tabelas: dict) -> None:
    """Checagens do prd.md (secao 9) antes de publicar."""
    pesos = tabelas["ranking_criterio"]["peso"].astype(float).sum()
    assert abs(pesos - 1) < 1e-6, f"soma dos pesos = {pesos}"
    notas = tabelas["ranking_expansao"].filter(like="nota_")
    assert notas.notna().all().all(), "ha municipio do universo sem nota"
    assert ((notas >= 0) & (notas <= 100)).all().all(), "ha nota fora de 0-100"


def main() -> None:
    if FONTE not in ("gold", "api"):
        sys.exit('FONTE deve ser "gold" ou "api"')
    print(f"Exportando dados do site (FONTE = {FONTE!r}) ...")
    if FONTE == "gold":
        dados = ler_gold()
    else:
        from previa_api import montar_previa
        dados = montar_previa()
        dados["camadas"] = {camada: None for camada in CAMADAS}

    conferir(dados["tabelas"])
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    print("Gravando:")
    exportado = {nome: gravar_tabela(nome, df, dados["gerado_em"]) for nome, df in dados["tabelas"].items()}

    meta = {
        "gerado_em": dados["gerado_em"],
        "fonte": FONTE,
        "eh_previa": FONTE != "gold",
        "versao_pesos": dados["versao_pesos"],
        "populacao_minima_universo": dados["populacao_minima_universo"],
        "periodos": dados["periodos"],
        "camadas": dados["camadas"],
        "exportado": exportado,
    }
    (PASTA_SAIDA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("  site/dados/meta.json")
    print("Pronto.")


if __name__ == "__main__":
    main()
