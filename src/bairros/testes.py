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
# RADAR DE EXPANSAO - BAIRROS SOB DEMANDA: TESTES BASICOS
# =============================================================================
#
# OBJETIVO: conferir as regras do pipeline de bairros e reproduzir Bauru, o
#           municipio de referencia do estudo (379.146 habitantes no Censo 2022).
# ENTRADA:  funcoes de src/bairros; Bauru roda de verdade (arquivos do IBGE em
#           cache ou baixados) contra a base de academias (CSV ou banco)
# SAIDA:    "OK"/"FALHOU" por teste; codigo de saida 1 se algum falhar
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - assert de regras e valores conhecidos
#   - codigo de saida (sys.exit)
#
# NOVIDADES:
#   1. teste de ponta a ponta com valores conhecidos (populacao e top 3)
#
# COMO RODAR: python -m src.bairros.testes            (so regras, sem rede)
#             python -m src.bairros.testes --bauru    (roda Bauru, sem banco)
# =============================================================================

# ============================== CONFIG ==============================
BAURU = "3506003"
POP_BAURU = 379146
TOP3_BAURU = {"ibge": ["Bacia do Córrego Água da Grama", "Bacia do Córrego Água do Sobrado",
                       "Bacia do Córrego Água do Castelo"],
              "popular": ["Vila Industrial", "Nucleo Habitacional Mary Dota", "Jardim Terra Branca"]}
# ====================================================================

import argparse
import sys

import pandas as pd

from src.bairros import config as C
from src.bairros.academias import numero_simples, partir_quadra
from src.bairros.indicadores import avaliar_escala_ibge, chave, percentil, pesos

falhas = []


def checar(nome, cond, detalhe=""):
    print(("OK      " if cond else "FALHOU  ") + nome + (f" ({detalhe})" if detalhe and not cond else ""))
    if not cond:
        falhas.append(nome)


def regras():
    checar("pesos somam 100% com concorrencia", abs(sum(pesos(True).values()) - 1) < 1e-9)
    checar("pesos somam 100% sem concorrencia (reescalonados)", abs(sum(pesos(False).values()) - 1) < 1e-9)
    checar("sem concorrencia nao usa o criterio espaco", "espaco" not in pesos(False))
    checar("numero quadra-casa '9-50'", partir_quadra("9-50") == (9, 50))
    checar("numero quadra-casa '950'", partir_quadra("950") == (9, 50))
    checar("numero quadra-casa 'SN'", partir_quadra("SN") == (None, None))
    checar("numero simples '1045 A'", numero_simples("1045 A") == (None, 1045))
    p = percentil(pd.Series([10, 20, 30]))
    checar("percentil vai de 0 a 100", list(p) == [0, 50, 100])
    checar("percentil menor-melhor inverte", list(percentil(pd.Series([10, 20, 30]), True)) == [100, 50, 0])
    checar("chave normaliza acentos", chave("Água  da Grama") == "AGUA DA GRAMA")
    checar("raio e populacao minima do CONFIG", C.RAIO_KM == 1.5 and C.POP_MIN == 5000 and C.POP_MIN_POPULAR == 2000)
    bacias = ["BACIA DO CORREGO AGUA DA GRAMA", "BACIA DO RIBEIRAO VARGEM LIMPA", "BACIA DO CORREGO BARREIRINHO"]
    checar("escala IBGE de bacias cai para a popular", avaliar_escala_ibge("bairro", bacias, 30, 5)[:2] == ("regiao", "popular"))
    reais = [f"BAIRRO {i}" for i in range(20)]
    checar("escala IBGE de bairros reais fica como padrao", avaliar_escala_ibge("bairro", reais, 40, 10) == ("bairro", "ibge", None))
    checar("poucas unidades IBGE (menos de 10% das localidades) cai para a popular",
           avaliar_escala_ibge("bairro", reais[:5], 400, 10)[:2] == ("regiao", "popular"))
    checar("distritos (Sao Paulo) caem para a popular, com aviso", avaliar_escala_ibge("distrito", reais, 2000, 400)[1:2] == ("popular",)
           and avaliar_escala_ibge("distrito", reais, 2000, 400)[2])
    checar("sem escala IBGE: popular", avaliar_escala_ibge(None, [], 80, 8)[:2] == (None, "popular"))
    checar("setor de Goiania (Setor Bueno) e bairro", avaliar_escala_ibge("bairro", ["SETOR BUENO", "SETOR OESTE"] * 5, 20, 5)[1] == "ibge")


def bauru():
    from src.bairros.processar import processar
    r, resumo, _ = processar(BAURU, sem_banco=True)
    checar("Bauru: populacao dos setores = 379.146", resumo["pop_setores"] == POP_BAURU, resumo["pop_setores"])
    checar("Bauru: populacao oficial = 379.146", resumo["pop_oficial"] == POP_BAURU, resumo["pop_oficial"])
    checar("Bauru: populacao rateada nos bairros populares = 379.146", resumo["pop_rateada"] == POP_BAURU,
           resumo["pop_rateada"])
    soma_ibge = round(r.loc[r["escala"] == "ibge", "populacao"].sum())
    checar("Bauru: populacao dos bairros IBGE = 379.146", soma_ibge == POP_BAURU, soma_ibge)
    el = r[r["elegivel"]]
    checar("notas entre 0 e 100", el["nota_final"].between(0, 100).all())
    checar("IBGE: so unidades com 5 mil hab. ou mais no ranking", (el.loc[el["escala"] == "ibge", "populacao"] >= C.POP_MIN).all())
    checar("popular: so bairros com 2 mil hab. ou mais no ranking",
           (el.loc[el["escala"] == "popular", "populacao"] >= C.POP_MIN_POPULAR).all())
    n_pop = int((el["escala"] == "popular").sum())
    checar("Bauru: 54 bairros populares no ranking", n_pop == 54, n_pop)
    checar("Bauru: escala IBGE (bacias) nao e o padrao; padrao = popular, com aviso",
           (resumo["escala_ibge_tipo"], resumo["escala_padrao"]) == ("regiao", "popular") and bool(resumo["aviso_escala"]),
           (resumo["escala_ibge_tipo"], resumo["escala_padrao"]))
    for esc in ["ibge", "popular"]:
        e = el[el["escala"] == esc]
        checar(f"Bauru: posicoes {esc} 1..n sem buraco", sorted(e["posicao"]) == list(range(1, len(e) + 1)))
    if resumo["concorrencia"] == "ok":
        for esc, esperado in TOP3_BAURU.items():
            top = list(el[el["escala"] == esc].sort_values("posicao")["unidade_nome"].head(3))
            checar(f"Bauru: top 3 {esc}", top == esperado, top)
        checar("Bauru: 185 academias (93.13-1 principal) geocodificadas",
               resumo["academias_geocodificadas"] == 185, resumo["academias_geocodificadas"])
    else:
        print("AVISO   base de academias ausente: top 3 de Bauru nao conferido (ranking provisorio)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bauru", action="store_true", help="roda Bauru de ponta a ponta (sem banco)")
    a = ap.parse_args()
    regras()
    if a.bauru:
        bauru()
    print(f"\n{'TODOS OS TESTES PASSARAM' if not falhas else f'{len(falhas)} FALHA(S)'}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
