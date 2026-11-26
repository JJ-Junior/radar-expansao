# Etapa 5 · Coordenadas e estimativas para o simulador de região (P9)

- **Data:** 26/11/2026
- **Responsável:** _(a preencher)_
- **Arquivos afetados:** `src/ingestao/ibge_localidades.py`, `sql/silver/`, `sql/gold/`, `prd.md` (v0.5), `spec.md` (v0.11), `README.md`

## Objetivo
Preparar a base de um simulador em que o diretor escolhe uma cidade e um raio e vê as melhores candidatas da região e quanto
espaço há para novas academias.

## Contexto fornecido
- Gold com ranking, indicadores por município e parâmetros do ranking.
- Exigência de fontes oficiais (IBGE) e do mesmo contrato da bronze.
- Pedido de métricas "preditivas" simples e explicáveis, com premissas declaradas.

## Entrada (prompt)
> Tarefa: (1) ingerir os centroides dos municípios pela API de Malhas do IBGE, validando o endpoint de verdade, e levar latitude e
> longitude para a silver e para a gold; (2) calcular, para todos os municípios, população projetada, densidade de referência
> de academias pela faixa de renda e lacuna de academias, com as premissas numa tabela de parâmetros e um aviso de estimativa;
> (3) atualizar prd (nova pergunta P9), spec e README.
> Restrições: a gold não guarda pares de distância (o app calcula por haversine); mesmos limites P5–P95 do espaço competitivo;
> testes de qualidade para coordenadas e estimativas.

## Saída esperada
5.571 municípios com coordenada válida, estimativas para todos os que têm dado, testes passando e um exemplo de consulta por raio.

## O que a IA entregou
- Recurso novo na bronze (`ibge_malha_municipios`), coordenadas na `dim_municipio` com o `bronze_id` da malha, e as colunas de
  coordenada e estimativa na gold.
- Faixas de renda por quintis do universo, densidade de referência pela mediana da faixa e lacuna arredondada.
- Cinco testes novos na gold (e dois na silver) e a consulta de exemplo por raio (haversine em SQL).

## O que foi ajustado
- **Versão da API:** o endpoint sugerido (malhas v3) devolve 5.570 municípios e não tem o município criado depois de 2022;
  os parâmetros de período devolvem erro. A v4 devolve os 5.571 numa chamada e passou a ser a fonte.
- **Nome da coluna da projeção:** em vez de um nome com o ano fixo, `populacao_projetada` + `ano_projecao`, porque o ano é um
  parâmetro e pode mudar.
- **Município sem Censo:** sem renda nem crescimento, ele fica sem faixa, lacuna e projeção — isso está escrito nas limitações
  do prd em vez de receber um valor inventado.

## Lições
Validar o endpoint na chamada real antes de codar evitou um buraco silencioso de um município; estimativa só é útil se a
premissa e a limitação vierem junto do número.
