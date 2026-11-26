# Etapa 5 · Trava de renda mínima nas unidades recomendadas

- **Data:** 26/11/2026
- **Responsável:** _(a preencher)_
- **Arquivos afetados:** `sql/gold/` (tabelas, função, testes e permissões), `prd.md` (v0.4), `spec.md` (v0.8), `README.md`

## Objetivo
Garantir que a lista das 5 unidades recomendadas seja coerente com o perfil do cliente: uma academia de padrão intermediário
a alto não deve ser recomendada para uma cidade grande de renda baixa, mesmo que ela tenha nota final alta.

## Contexto fornecido
- Resultado da primeira versão da gold: uma cidade com nota de poder de compra abaixo de 40 aparecia entre as 5 recomendadas,
  puxada por tamanho de mercado, espaço competitivo e crescimento.
- Pergunta de teste 1 do `prd.md` ("cidade populosa com renda baixa é oportunidade ou armadilha?").
- Decisão do responsável pelo produto: a regra vale só para a lista recomendada; o ranking geral não muda.

## Entrada (prompt)
> Tarefa: aplicar uma trava de renda mínima na escolha das 5 unidades recomendadas: só é elegível quem tem nota de poder de
> compra ≥ 50, mantendo a regra de no máximo uma cidade por região imediata.
> Restrições: o ranking geral não muda (posições e notas iguais); o valor da trava fica num lugar único e fácil de achar;
> um teste de qualidade confere a regra; `prd.md` e `spec.md` atualizados junto.
> Formato: alteração nos arquivos de `sql/gold/` e documentação.

## Saída esperada
Ranking idêntico ao anterior; lista recomendada só com cidades acima da mediana de renda do universo; testes passando.

## O que a IA entregou
- Tabela `gold.parametro_ranking` com a quantidade de recomendadas (5) e a nota mínima de poder de compra (50); a função e o
  teste leem o mesmo valor, e o dashboard pode mostrá-lo na metodologia.
- Coluna `elegivel_recomendacao` no ranking, para explicar por que uma cidade bem colocada ficou fora da lista.
- Teste 14 ("recomendadas abaixo da trava de renda") e o teste da quantidade de recomendadas lendo o parâmetro.

## O que foi ajustado
- **Onde guardar a trava:** em vez de uma constante dentro da função, o valor foi para uma tabela de parâmetros, para não existir
  um número repetido na função e no teste.
- **Banco já existente:** a coluna nova entrou também com `ADD COLUMN IF NOT EXISTS`, para o mesmo script funcionar num banco
  novo e no banco que já tinha a gold.
- **Resultado conferido:** o ranking não mudou; Manaus (5ª, nota de poder de compra 36,7) e Porto Velho (6ª, 48,0) ficaram fora
  da lista, e entrou Santana de Parnaíba (7ª, 99,3). 344 dos 687 municípios do universo são elegíveis.

## Lições
Uma regra de negócio que afasta um resultado "estranho" deve virar parâmetro explícito e teste, não um ajuste manual na lista.
