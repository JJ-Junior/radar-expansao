-- =============================================================================
-- RADAR DE EXPANSAO - ETAPA 5: CAMADA GOLD · 03_testes_qualidade.sql
-- =============================================================================
-- gold.vw_rastreio_exemplo : um numero da gold seguido ate a resposta da bronze
-- gold.vw_testes_qualidade : testes do "pronto quando" da gold (esperado x obtido)
-- As duas views sao internas: o papel de leitura da API nao as enxerga (04_permissoes.sql).
-- Rodar como etl_radar. Idempotente.
-- =============================================================================

-- Rastreio: academias do 1o colocado do ranking, da gold ate o JSON da bronze --
CREATE OR REPLACE VIEW gold.vw_rastreio_exemplo AS
WITH alvo AS (
    SELECT r.municipio_id, r.municipio_nome, r.uf_sigla, i.academias_qtd, i.academias_ano
      FROM gold.ranking_expansao AS r
      JOIN gold.indicadores_municipio AS i USING (municipio_id)
     WHERE r.posicao_brasil = 1
),
silver_fato AS (
    SELECT f.municipio_id, f.valor, f.flag_valor, f.bronze_id
      FROM silver.fato_indicador_municipal AS f
      JOIN alvo AS a ON a.municipio_id = f.municipio_id
     WHERE f.indicador_id = 'academias_qtd' AND f.ano = a.academias_ano
),
bronze_valor AS (   -- o valor lido direto do JSON original
    SELECT b.resposta_id, b.recurso, b.lote, b.url, b.ingerido_em,
           s -> 'serie' ->> (a.academias_ano::text) AS valor_no_json
      FROM silver_fato AS sf
      JOIN alvo AS a ON a.municipio_id = sf.municipio_id
      JOIN bronze.api_resposta AS b ON b.resposta_id = sf.bronze_id
      CROSS JOIN LATERAL jsonb_array_elements(b.payload) AS var
      CROSS JOIN LATERAL jsonb_array_elements(var -> 'resultados') AS res
      CROSS JOIN LATERAL jsonb_array_elements(res -> 'series') AS s
     WHERE s -> 'localidade' ->> 'id' = a.municipio_id::text
)
SELECT a.municipio_id, a.municipio_nome, a.uf_sigla,
       'academias_qtd'::text  AS indicador,
       a.academias_ano        AS ano,
       a.academias_qtd        AS valor_gold,
       sf.valor               AS valor_silver,
       sf.flag_valor          AS flag_silver,
       sf.bronze_id,
       bv.recurso             AS recurso_bronze,
       bv.lote                AS lote_bronze,
       bv.valor_no_json       AS valor_bronze_json,
       bv.url                 AS url_api,
       bv.ingerido_em
  FROM alvo AS a
  LEFT JOIN silver_fato AS sf ON sf.municipio_id = a.municipio_id
  LEFT JOIN bronze_valor AS bv ON bv.resposta_id = sf.bronze_id;

COMMENT ON VIEW gold.vw_rastreio_exemplo IS
    'Rastreio de um numero da gold (academias do 1o colocado) ate a resposta original na bronze.';

-- Testes de qualidade da gold ----------------------------------------------
CREATE OR REPLACE VIEW gold.vw_testes_qualidade AS
WITH
universo AS (SELECT count(*) AS n FROM gold.indicadores_municipio WHERE populacao >= 50000),
notas AS (
    SELECT unnest(ARRAY[nota_mercado, nota_poder_compra, nota_espaco_competitivo, nota_crescimento,
                        nota_riqueza_nivel, nota_riqueza_tendencia, nota_riqueza, nota_mercado_formal,
                        nota_final]) AS nota
      FROM gold.ranking_expansao
),
ultimo_mes_silver AS (
    SELECT to_char(max(data), 'YYYY-MM') AS mes
      FROM silver.fato_indicador_macro
     WHERE indicador_id IN ('selic_meta', 'dolar_venda', 'ipca_mensal', 'ipca_12m') AND valor IS NOT NULL
),
ultimo_mes_ipca AS (
    SELECT to_char(max(mes), 'YYYY-MM') AS mes FROM gold.contexto_macro WHERE ipca_12m IS NOT NULL
),
rastreio AS (SELECT * FROM gold.vw_rastreio_exemplo),
testes (ordem, teste, esperado, obtido) AS (
    SELECT 1, 'soma dos pesos dos criterios', '1.000',
           (SELECT to_char(sum(peso), 'FM0.000') FROM gold.ranking_criterio)
    UNION ALL
    SELECT 2, 'municipios do universo (>= 50 mil hab.) no ranking',
           (SELECT n::text FROM universo), (SELECT count(*)::text FROM gold.ranking_expansao)
    UNION ALL
    SELECT 3, 'municipios do ranking sem nota final', '0',
           (SELECT count(*)::text FROM gold.ranking_expansao WHERE nota_final IS NULL)
    UNION ALL
    SELECT 4, 'notas fora do intervalo 0-100', '0',
           (SELECT count(*)::text FROM notas WHERE nota < 0 OR nota > 100)
    UNION ALL
    SELECT 5, 'peso considerado fora de (0, 1]', '0',
           (SELECT count(*)::text FROM gold.ranking_expansao WHERE peso_considerado <= 0 OR peso_considerado > 1)
    UNION ALL
    SELECT 6, 'dados incompletos coerentes com o peso considerado', '0',
           (SELECT count(*)::text FROM gold.ranking_expansao
             WHERE dados_incompletos <> (peso_considerado < 1) OR dados_incompletos <> (criterios_ausentes IS NOT NULL))
    UNION ALL
    SELECT 7, 'posicoes no Brasil unicas e sem buraco',
           (SELECT count(*)::text FROM gold.ranking_expansao),
           (SELECT count(DISTINCT posicao_brasil)::text FROM gold.ranking_expansao
             WHERE posicao_brasil BETWEEN 1 AND (SELECT count(*) FROM gold.ranking_expansao))
    UNION ALL
    SELECT 8, 'unidades recomendadas (top 5)', '5',
           (SELECT count(*)::text FROM gold.ranking_expansao WHERE recomendado_top5)
    UNION ALL
    SELECT 9, 'regioes imediatas diferentes entre as recomendadas', '5',
           (SELECT count(DISTINCT regiao_imediata_id)::text FROM gold.ranking_expansao WHERE recomendado_top5)
    UNION ALL
    SELECT 10, 'cidades sem academia marcadas para verificar concorrencia',
           (SELECT count(*)::text FROM gold.indicadores_municipio WHERE populacao >= 50000 AND academias_qtd = 0),
           (SELECT count(*)::text FROM gold.ranking_expansao WHERE verificar_concorrencia)
    UNION ALL
    SELECT 11, 'contexto macro ate o ultimo mes com dado na silver',
           (SELECT mes FROM ultimo_mes_silver), (SELECT to_char(max(mes), 'YYYY-MM') FROM gold.contexto_macro)
    UNION ALL
    SELECT 12, 'semaforo no ultimo mes com IPCA',
           (SELECT mes FROM ultimo_mes_ipca), (SELECT to_char(max(mes), 'YYYY-MM') FROM gold.momento_expansao)
    UNION ALL
    SELECT 13, 'rastreio gold -> silver -> bronze (academias do 1o colocado)',
           'iguais',
           (SELECT CASE WHEN valor_gold IS NOT NULL
                         AND valor_gold = coalesce(valor_silver, 0)
                         AND bronze_id IS NOT NULL
                         AND coalesce(nullif(valor_bronze_json, '-'), '0')::numeric = valor_gold
                        THEN 'iguais' ELSE 'divergente' END
              FROM rastreio LIMIT 1)
)
SELECT ordem, teste, esperado, obtido, esperado IS NOT DISTINCT FROM obtido AS ok
  FROM testes
 ORDER BY ordem;

COMMENT ON VIEW gold.vw_testes_qualidade IS 'Testes de qualidade da gold: esperado x obtido.';
