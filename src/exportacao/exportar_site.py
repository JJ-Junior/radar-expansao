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
#           site/dados/README.md) a partir das tabelas da camada gold.
# ENTRADA:  tabelas gold.* do Supabase autohospedado via Docker (conexao pelo
#           .env, incluindo DB_SSLMODE) + contagem de linhas das camadas
#           bronze, silver e gold
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
#   3. Decimal -> float        -> o Postgres devolve numeric como Decimal, que o
#                                 JSON nao conhece; vira numero comum antes
#   4. information_schema      -> catalogo do Postgres para listar as tabelas de
#                                 cada camada e contar as linhas
#   5. site estatico           -> o navegador le arquivos prontos; nenhuma
#                                 credencial do banco vai para o site
#
# INSTALACAO: pip install -r requirements.txt
# COMO RODAR: python src/exportacao/exportar_site.py
#
# =============================================================================

# ============================== CONFIG ==============================
SCHEMA_GOLD = "gold"
TABELAS = [                   # arquivo site/dados/<tabela>.json  <-  gold.<tabela>
    "indicadores_municipio",
    "ranking_expansao",
    "ranking_criterio",
    "parametro_ranking",
    "contexto_macro",
    "momento_expansao",
]
ORDEM = {                     # ordenacao das linhas em cada arquivo
    "indicadores_municipio": "municipio_id",
    "ranking_expansao": "posicao_brasil",
    "ranking_criterio": "ordem",
    "parametro_ranking": "parametro",
    "contexto_macro": "mes",
    "momento_expansao": "mes",
}
CAMADAS = ["bronze", "silver", "gold"]   # contagem de linhas para a secao "Dados"
POPULACAO_MINIMA = 50_000                # so informativo no meta.json (o corte vale na gold)
ANO_CENSO = 2022
CASAS_DECIMAIS = 6
# ====================================================================

import json
import os
import sys
from datetime import datetime
from decimal import Decimal
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


def maior_ano(df: pd.DataFrame, coluna: str):
    """Maior valor de uma coluna de ano, ou None se a coluna nao existe ou esta vazia."""
    if coluna not in df or df[coluna].dropna().empty:
        return None
    return int(df[coluna].max())


def ler_gold() -> dict:
    """Le as tabelas gold.* e os metadados que o site mostra."""
    engine = conectar_banco()
    tabelas = {t: pd.read_sql(f"SELECT * FROM {SCHEMA_GOLD}.{t} ORDER BY {ORDEM[t]}", engine) for t in TABELAS}
    ind, macro, criterios = tabelas["indicadores_municipio"], tabelas["contexto_macro"], tabelas["ranking_criterio"]
    com_selic = macro.dropna(subset=["selic_meta"])
    ultimo_mes = pd.to_datetime(com_selic["mes"]).max() if len(com_selic) else None
    return {
        "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "periodos": {
            "populacao": maior_ano(ind, "populacao_ano"),
            "censo": ANO_CENSO,
            "pib": maior_ano(ind, "pib_ano"),
            "academias": maior_ano(ind, "academias_ano"),
            "salario": maior_ano(ind, "salario_ano"),
            "macro_ate": f"{ultimo_mes:%Y-%m}" if ultimo_mes is not None else None,
        },
        "versao_pesos": str(criterios["versao_pesos"].iloc[0]) if len(criterios) else None,
        "populacao_minima_universo": POPULACAO_MINIMA,
        "camadas": contar_camadas(engine),
        "tabelas": tabelas,
    }


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    """Decimal vira float; datas viram texto ISO; 'mes' vira AAAA-MM-DD (o contrato pede data sem hora)."""
    df = df.copy()
    for coluna in df.columns:
        if coluna == "mes":
            df[coluna] = pd.to_datetime(df[coluna]).dt.strftime("%Y-%m-%d")
        elif pd.api.types.is_datetime64_any_dtype(df[coluna]):
            df[coluna] = df[coluna].map(lambda v: v.isoformat() if pd.notna(v) else None)
        elif df[coluna].dtype == object and df[coluna].map(lambda v: isinstance(v, Decimal)).any():
            df[coluna] = df[coluna].map(lambda v: float(v) if isinstance(v, Decimal) else v)
    return df


def gravar_tabela(nome: str, df: pd.DataFrame, gerado_em: str) -> int:
    """Grava site/dados/<nome>.json no formato colunar do contrato; devolve o numero de linhas."""
    dividido = json.loads(preparar(df).to_json(orient="split", index=False, double_precision=CASAS_DECIMAIS,
                                               force_ascii=False))
    conteudo = {"tabela": f"{SCHEMA_GOLD}.{nome}", "gerado_em": gerado_em, "colunas": dividido["columns"]}
    # uma linha por registro: arquivo compacto e diff do git legivel
    corpo = ",\n".join(json.dumps(l, ensure_ascii=False, separators=(",", ":")) for l in dividido["data"])
    texto = json.dumps(conteudo, ensure_ascii=False)[:-1] + ',"linhas":[\n' + corpo + "\n]}\n"
    caminho = PASTA_SAIDA / f"{nome}.json"
    caminho.write_text(texto, encoding="utf-8")
    print(f"  {caminho.relative_to(RAIZ)}: {len(df)} linhas ({caminho.stat().st_size / 1024:,.0f} KB)")
    return len(df)


def conferir(tabelas: dict) -> None:
    """Checagens do prd.md (secao 9) antes de publicar."""
    pesos = tabelas["ranking_criterio"]["peso"].astype(float).sum()
    assert abs(pesos - 1) < 1e-6, f"soma dos pesos = {pesos}"
    ranking = tabelas["ranking_expansao"]
    assert ranking["nota_final"].notna().all(), "ha municipio do universo sem nota final"
    notas = ranking.filter(like="nota_").astype(float)
    assert ((notas.isna()) | ((notas >= 0) & (notas <= 100))).all().all(), "ha nota fora de 0-100"
    quantidade = tabelas["parametro_ranking"].set_index("parametro")["valor"].astype(float).get("unidades_recomendadas")
    recomendadas = int(ranking["recomendado_top5"].sum())
    assert quantidade is None or recomendadas == int(quantidade), f"{recomendadas} recomendadas, esperado {quantidade}"


def main() -> None:
    print("Exportando dados do site a partir da camada gold ...")
    dados = ler_gold()
    conferir(dados["tabelas"])
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    print("Gravando:")
    exportado = {nome: gravar_tabela(nome, df, dados["gerado_em"]) for nome, df in dados["tabelas"].items()}

    meta = {
        "gerado_em": dados["gerado_em"],
        "fonte": "gold",
        "eh_previa": False,
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
