-- =============================================================================
-- RADAR DE EXPANSAO - ETAPA 3: CAMADA BRONZE · 03_trava_carga.sql
-- =============================================================================
-- Trava que impede duas cargas ao mesmo tempo (cenario A e cenario B, ou duas
-- rodadas do mesmo cenario). Uma unica linha; vale entre processos e conexoes
-- diferentes e expira sozinha se um processo morrer no meio (spec.md, secao 8.3).
-- Rodar como etl_radar. Idempotente.
-- =============================================================================

CREATE TABLE IF NOT EXISTS bronze.trava_carga (
    trava_id     smallint     PRIMARY KEY DEFAULT 1 CHECK (trava_id = 1),
    em_uso_por   text,                 -- 'python' | 'n8n' | nulo = livre
    rodada_id    uuid,                 -- rodada que esta com a trava
    desde        timestamptz
);

INSERT INTO bronze.trava_carga (trava_id) VALUES (1)
ON CONFLICT (trava_id) DO NOTHING;

COMMENT ON TABLE bronze.trava_carga IS 'Trava de carga (linha unica): evita cargas simultaneas.';
