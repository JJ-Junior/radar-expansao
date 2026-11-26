# Etapa 5 · Semáforo com janela móvel e alerta de curto prazo no câmbio

- **Data:** 26/11/2026
- **Responsável:** _(a preencher)_
- **Arquivos afetados:** `sql/gold/` (tabelas, função, testes, permissões), `sql/silver/03_funcoes_apoio.sql`,
  `src/transformacao/executar.py`, `prd.md` (v0.6), `spec.md` (v0.13), `README.md`

## Objetivo
Fazer o semáforo "expandir agora ou esperar" refletir o cenário de hoje, e não o do último mês fechado.

## Contexto fornecido
- Semáforo anterior: tudo pelo último mês com IPCA (outubro/2026). Câmbio verde com o dólar médio de outubro (R$ 5,13,
  queda de 4,8% em 12 meses), enquanto novembro teve fechamentos de R$ 5,46 a R$ 5,97.
- Séries diárias do BCB (Selic meta e dólar) já na silver até o último fechamento; IPCA mensal só até outubro.

## Entrada (prompt)
> Tarefa: calcular câmbio e juros numa janela móvel de 30 dias até o último fechamento, comparada com a mesma janela 12 meses
> antes; criar um alerta de alta de curto prazo no câmbio que impeça o sinal verde; manter a inflação pelo último IPCA
> publicado; registrar o momento atual com a data de referência e os valores de cada sinal; incluir o último fechamento no
> contexto macro; levar janela e limiares para a tabela de parâmetros.
> Restrições: histórico mensal mantido, com o mês corrente marcado como parcial; testes de qualidade para as datas de
> referência e para a regra do alerta; prd e spec atualizados com motivo e exemplo.

## Saída esperada
Semáforo atual com datas e valores explícitos, coerente com a alta recente do dólar, e testes passando.

## O que a IA entregou
- Tabela `gold.momento_atual` (uma linha) com as três datas de referência, médias, último fechamento, variações e a
  justificativa já com as datas.
- Regras do semáforo em funções pequenas (`gold.sinal_juros`, `gold.sinal_inflacao`, `gold.sinal_cambio`), reaproveitadas no
  histórico mensal e no momento atual; seis parâmetros novos em `gold.parametro_ranking`.
- `contexto_macro` com o último fechamento do mês e a data da meta da Selic; seis testes novos (20 a 25).

## O que foi ajustado
- **Definição do alerta:** entre "média dos últimos 30 dias contra a dos 30 anteriores" e "fechamento contra fechamento de
  30 dias antes", ficou a comparação de médias, que não dispara por um único dia atípico. No histórico mensal, o alerta usa a
  média do mês contra a do mês anterior.
- **Funções fora da API:** as funções das regras foram criadas no schema da gold, então o `EXECUTE` delas foi revogado para o
  papel de leitura, como já acontecia com a função de carga.
- **Resultado:** com a regra nova, o momento de 26/11/2026 passou de "Expandir com cautela" para **"Esperar"** (câmbio vermelho:
  +10,4% em 30 dias e +5,4% em 12 meses; inflação vermelha; juros verde).

## Lições
Indicador de decisão precisa dizer de quando é cada número; séries com frequências diferentes pedem uma data de referência
por sinal, e não um "mês" único para todos.
