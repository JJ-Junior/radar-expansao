# Etapa 7 · Simulador de região, simulador de pesos, dólar do mês parcial e semáforo de hoje

- **Data:** 26/11/2026
- **Responsável:** José Martins (Junior)
- **Arquivos afetados:** `src/app/paginas/simulador.py` (novo), `src/app/paginas/ranking.py`, `src/app/paginas/contexto_macro.py`,
  `src/app/paginas/visao_geral.py`, `src/app/paginas/metodologia.py`, `src/app/dados.py`, `src/app/app.py`, `README.md`,
  `spec.md` (v0.14)

## Objetivo
Responder à P9 no dashboard (num raio de X km, quais as melhores candidatas e quanto espaço há para academias), deixar claro
de onde vem cada número do dólar e mostrar o semáforo de hoje que a gold passou a calcular.

## Contexto fornecido
- `prd.md` v0.5/v0.6 (P9 e premissas das estimativas) e `spec.md` (seções 5.1, 5.4 e 9.4): coordenadas, população projetada,
  densidade de referência e lacuna na gold; distância calculada no app por haversine; `gold.momento_atual`.
- Dúvida do squad: o "R$ 5,68" era a média de novembro até o dia 26 (mês parcial), não a cotação do dia.
- Pedido de identidade: "RADAR DE EXPANSÃO · SQUAD DROP DATABASE" no topo e no título da aba.

## Entrada (prompt)
> Tarefa: (1) página "Simulador de região": busca da cidade central (qualquer município), raio de 10 a 300 km (padrão 100),
> distância haversine no app, mapa com o círculo do raio, ranking local com distância, notas, lacuna e população projetada,
> opção de incluir cidades menores, resumo da região e aviso das estimativas; (2) no dólar, mostrar "média de <mês> (parcial,
> até <dia>)" e o último fechamento com a data, e dizer qual período o semáforo usa; (3) opcional: sliders de pesos que refazem
> só a média ponderada das notas da gold, com aviso de simulação e botão de voltar ao oficial.
> Restrições: notas, lacuna e projeção vêm prontas da gold; o ranking oficial e as recomendadas não mudam; exemplo de teste:
> Bauru (SP), 100 km.

## Saída esperada
Bauru com 100 km mostrando as cidades do ranking no raio em ordem de nota, com resumo e aviso; rótulos do dólar sem ambiguidade;
simulação de pesos reversível.

## O que a IA entregou
- Simulador com haversine e círculo vetorizados em numpy; mapa sem servidor externo (divisas das UFs + círculo); Bauru 100 km:
  73 municípios no raio, 8 no ranking (Marília 1ª no raio), +88 academias de lacuna positiva somada.
- Dólar: "Dólar · média de nov/2026 (parcial, até 26/11)" e "Dólar · último fechamento (26/11/2026)" + legenda do semáforo.
- Semáforo da visão geral lido de `gold.momento_atual` (com datas e alerta de câmbio), voltando ao último mês fechado quando a
  tabela não existe; a metodologia lê janela e limiares de `parametro_ranking`.
- Simulador de pesos na página Ranking, com a mesma regra de peso redistribuído da gold.

## O que foi ajustado
- A justificativa da gold passou a trazer datas entre parênteses; a separação das frases por ")." quebraria. Passou a separar
  pelo nome de cada sinal ("Juros:", "Inflação:", "Câmbio:").
- `momento_atual` foi tratada como tabela opcional: a cópia de contingência antiga não a tem e o app não pode cair por isso.
- No mapa do simulador, rótulos com posição e nome só para as 10 primeiras do raio, para não poluir.

## Lições
- Número de mês em andamento sempre com a palavra "parcial" e a data de corte; valor diário sempre com a data.
- Simulação que mexe em pesos precisa de aviso visível e de um caminho de volta ao oficial.
