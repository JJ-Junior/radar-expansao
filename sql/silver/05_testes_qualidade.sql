-- =============================================================================
-- RADAR DE EXPANSAO - ETAPA 4: CAMADA SILVER · 05_testes_qualidade.sql
-- =============================================================================
-- Testes do "pronto quando" da silver (docs/responsabilidades.md, F3; spec.md 4).
-- Uma linha por teste: esperado x obtido e se passou.
-- Consultar com: SELECT * FROM silver.vw_testes_qualidade;
-- Rodar como etl_radar. Idempotente.
-- =============================================================================

CREATE OR REPLACE VIEW silver.vw_testes_qualidade AS
WITH
localidades_bronze AS (   -- todos os municipios citados nos agregados vigentes da bronze
    SELECT DISTINCT (s -> 'localidade' ->> 'id')::integer AS municipio_id
    FROM silver.bronze_vigente() AS v
    CROSS JOIN LATERAL jsonb_array_elements(v.payload) AS var
    CROSS JOIN LATERAL jsonb_array_elements(var -> 'resultados') AS r
    CROSS JOIN LATERAL jsonb_array_elements(r -> 'series') AS s
    WHERE v.recurso LIKE 'ibge_agregado_%'
      AND s -> 'localidade' -> 'nivel' ->> 'id' = 'N6'
),
ipca_comparado AS (       -- mesmo mes no IBGE (7060) e no BCB (433)
    SELECT i.data
    FROM silver.fato_indicador_macro AS i
    JOIN silver.fato_indicador_macro AS b
      ON b.data = i.data AND b.indicador_id = 'ipca_mensal_bcb'
    WHERE i.indicador_id = 'ipca_mensal'
      AND abs(i.valor - b.valor) > 0.005
),
testes (ordem, teste, esperado, obtido) AS (
    SELECT 1, 'regioes na dim_regiao', 5::bigint, (SELECT count(*) FROM silver.dim_regiao)
    UNION ALL
    SELECT 2, 'UFs na dim_uf', 27, (SELECT count(*) FROM silver.dim_uf)
    UNION ALL
    SELECT 3, 'municipios na dim_municipio', 5571, (SELECT count(*) FROM silver.dim_municipio)
    UNION ALL
    SELECT 4, 'municipios sem regiao imediata', 0,
           (SELECT count(*) FROM silver.dim_municipio WHERE regiao_imediata_id IS NULL)
    UNION ALL
    SELECT 5, 'municipios da bronze sem par na dim_municipio', 0,
           (SELECT count(*) FROM localidades_bronze AS l
            WHERE NOT EXISTS (SELECT 1 FROM silver.dim_municipio AS m WHERE m.municipio_id = l.municipio_id))
    UNION ALL
    SELECT 6, 'indicadores municipais sem nenhuma linha', 0,
           (SELECT count(*) FROM silver.dim_indicador AS i
            WHERE i.nivel = 'municipal'
              AND NOT EXISTS (SELECT 1 FROM silver.fato_indicador_municipal AS f
                              WHERE f.indicador_id = i.indicador_id))
    UNION ALL
    SELECT 7, 'indicadores macro sem nenhuma linha', 0,
           (SELECT count(*) FROM silver.dim_indicador AS i
            WHERE i.nivel = 'macro'
              AND NOT EXISTS (SELECT 1 FROM silver.fato_indicador_macro AS f
                              WHERE f.indicador_id = i.indicador_id))
    UNION ALL
    SELECT 8, 'valores com formato invalido (flag invalido)', 0,
           (SELECT count(*) FROM silver.fato_indicador_municipal WHERE flag_valor = 'invalido')
         + (SELECT count(*) FROM silver.fato_indicador_macro WHERE flag_valor = 'invalido')
    UNION ALL
    SELECT 9, 'valor nulo com flag ok ou valor preenchido com flag de simbolo', 0,
           (SELECT count(*) FROM silver.fato_indicador_municipal
            WHERE (valor IS NULL) = (flag_valor = 'ok'))
         + (SELECT count(*) FROM silver.fato_indicador_macro
            WHERE (valor IS NULL) = (flag_valor = 'ok'))
    UNION ALL
    SELECT 10, 'linhas da silver sem resposta de origem na bronze', 0,
           (SELECT count(*) FROM silver.fato_indicador_municipal AS f
            WHERE NOT EXISTS (SELECT 1 FROM bronze.api_resposta AS r WHERE r.resposta_id = f.bronze_id))
         + (SELECT count(*) FROM silver.fato_indicador_macro AS f
            WHERE NOT EXISTS (SELECT 1 FROM bronze.api_resposta AS r WHERE r.resposta_id = f.bronze_id))
         + (SELECT count(*) FROM silver.dim_municipio AS d
            WHERE NOT EXISTS (SELECT 1 FROM bronze.api_resposta AS r WHERE r.resposta_id = d.bronze_id))
    UNION ALL
    SELECT 11, 'datas futuras nos fatos macro', 0,
           (SELECT count(*) FROM silver.fato_indicador_macro WHERE data > current_date)
    UNION ALL
    SELECT 12, 'meses com IPCA divergente entre IBGE e BCB', 0,
           (SELECT count(*) FROM ipca_comparado)
)
SELECT ordem, teste, esperado, obtido, esperado = obtido AS ok
FROM testes
ORDER BY ordem;

COMMENT ON VIEW silver.vw_testes_qualidade IS 'Testes de qualidade da silver: esperado x obtido.';
