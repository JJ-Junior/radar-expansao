# Etapa 1 · Validação do código CNAE das academias na API do IBGE

- **Data:** 26/11/2026
- **Responsável:** _(a preencher)_
- **Arquivos afetados:** `spec.md` (seção 2.3), `prd.md` (critério "espaço competitivo")

## Objetivo
Confirmar se o critério de concorrência (academias por habitante) é viável: qual o código da categoria CNAE 93.13-1 no
agregado 9418 do IBGE e se existe dado por município.

## Contexto fornecido
- Agregado 9418 (Cadastro Central de Empresas por CNAE 2.0) e a classificação 12762.
- Limite prático da API (≈ 100 mil valores por chamada).

## Entrada (prompt)
> Tarefa: consultar os metadados do agregado 9418, achar a categoria "93.13-1" na classificação 12762, listar os níveis
> territoriais e os períodos, e fazer uma chamada real por município (N6) para cada ano disponível.
> Formato: tabela com a chamada feita e o resultado; contagem de municípios com número, com "-" e com "X" por variável.

## Saída esperada
Código da categoria, confirmação do nível municipal e uma recomendação de qual variável usar no ranking.

## O que a IA entregou
- Categoria `117856` = "93.13-1 Atividades de condicionamento físico"; nível N6 disponível; anos 2022, 2023 e 2024.
- 5.570 municípios por ano; total Brasil de 65.346 empresas em 2024.
- Contagem de símbolos: a variável 707 (pessoal ocupado) vem com sigilo ("X") em cerca de metade dos municípios.

## O que foi ajustado
- O critério passou a usar **só a variável 2585 (número de empresas)**, que não tem sigilo; a variável 707 foi descartada.
- `"-"` foi definido como **zero academias** na gold (na silver fica nulo com a flag `zero_absoluto`).
- A chamada leva 11 a 22 s: o timeout do agregado 9418 foi aumentado para 120 s no `spec.md`.

## Lições
Antes de escolher uma variável para o ranking, contar os símbolos (`-`, `...`, `X`) na resposta real.
