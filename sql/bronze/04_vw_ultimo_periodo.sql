-- =============================================================================
-- RADAR DE EXPANSAO - ETAPA 3: CAMADA BRONZE · 04_vw_ultimo_periodo.sql
-- =============================================================================
-- Ultimo periodo salvo por processo, recurso e lote: e o que a carga incremental
-- compara com a API.
--   IBGE: modificacao_fonte (data de `modificacao` do periodo no /periodos)
--   BCB:  ultima_data (maior data presente nas respostas da serie)
-- Cada cenario filtra a sua propria origem_carga.
-- Rodar como etl_radar. Idempotente.
-- =============================================================================

CREATE OR REPLACE VIEW bronze.vw_ultimo_periodo AS
SELECT
    r.origem_carga,
    r.recurso,
    r.lote,
    max(r.modificacao_fonte) AS modificacao_fonte,
    max(
        CASE WHEN r.fonte = 'BCB' THEN (
            SELECT max(to_date(e ->> 'data', 'DD/MM/YYYY'))
            FROM jsonb_array_elements(r.payload) AS e
        ) END
    )                        AS ultima_data,
    max(r.ingerido_em)       AS ingerido_em,
    count(*)                 AS respostas
FROM bronze.api_resposta AS r
GROUP BY r.origem_carga, r.recurso, r.lote;

COMMENT ON VIEW bronze.vw_ultimo_periodo IS
    'Ultimo periodo (IBGE) ou ultima data (BCB) salvos por origem, recurso e lote: base da carga incremental.';
