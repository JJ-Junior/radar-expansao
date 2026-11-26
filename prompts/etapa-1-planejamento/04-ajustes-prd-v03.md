# Etapa 1 · Ajustes nas regras do ranking (prd v0.3)

- **Data:** 26/11/2026
- **Responsável:** _(a preencher)_
- **Arquivos afetados:** `prd.md` (seções 3, 4, 6 e 9), `spec.md` (seções 3.3, 5.2 e 5.3)

## Objetivo
Revisar as regras de cálculo do ranking antes de construir a camada gold, corrigindo pontos em que a primeira versão
podia gerar recomendações enganosas para uma rede de academias.

## Contexto fornecido
- `prd.md` v0.2 (critérios, pesos, dado faltante com nota neutra 50, top 5 sem restrição geográfica).
- Silver já carregada: distribuição real de academias por 10 mil habitantes, municípios sem academia registrada e a série
  do PIB, que atravessa a pandemia.
- Revisão do responsável pelo produto, com quatro pontos aprovados.

## Entrada (prompt)
> Tarefa: aplicar ao `prd.md` quatro ajustes nas regras do ranking e refletir cada um nas regras da gold do `spec.md`.
> (1) dado faltante: redistribuir o peso do critério sem dado entre os disponíveis, mantendo a marca de dados incompletos;
> (2) as 5 unidades recomendadas: no máximo uma cidade por região imediata do IBGE; o ranking completo não muda;
> (3) espaço competitivo: limitar academias por 10 mil hab. aos percentis 5% e 95% antes da nota inversa; cidade com zero
> academias recebe a nota do limite e uma marca para verificação;
> (4) tendência do PIB per capita: taxa média anual (CAGR) entre o primeiro e o último ano da janela de 5 anos, explicando
> o efeito da pandemia.
> Formato: texto do prd para o diretor de expansão; fórmulas e colunas no spec.

## Saída esperada
Regras sem ambiguidade, com fórmula reproduzível, novas colunas na gold e novos testes de aceite.

## O que a IA entregou
- `prd.md` v0.3 com a seção "Regras de cálculo", a regra da recomendação das 5 unidades e duas novas perguntas de teste.
- `spec.md` v0.6 com a fórmula da redistribuição, o percentil com empates pela posição média, os limites P5/P95, o algoritmo
  do top 5 por região imediata e as colunas novas da gold (`criterios_ausentes`, `peso_considerado`,
  `verificar_concorrencia`, `recomendado_top5`, `ordem_recomendacao`, notas separadas de nível e tendência da riqueza).

## O que foi ajustado
- **"Nota do limite" menor que 100:** com o percentil comum, todas as cidades empatadas no limite inferior ficariam com nota
  100, e a regra (3) não teria efeito. O empate passou a receber o percentil da **posição média**, o que dá a essas cidades uma
  nota alta, mas abaixo de 100, igual para todas.
- **Riqueza local em dois componentes:** para a redistribuição funcionar, nível e tendência do PIB per capita (5% cada) viraram
  componentes separados — uma cidade sem a tendência perde só esses 5%.
- **Texto para o diretor:** a justificativa de cada regra foi escrita em linguagem de negócio (canibalização, verificação local),
  deixando fórmulas só no spec.

## Lições
Regras de ranking precisam ser testadas contra casos extremos reais (zero academias, empates, dado faltante) antes da gold;
cada regra nova virou um teste de aceite no "Como saber que deu certo".
