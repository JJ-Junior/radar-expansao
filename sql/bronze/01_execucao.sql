-- =============================================================================
-- RADAR DE EXPANSAO - ETAPA 3: CAMADA BRONZE · 01_execucao.sql
-- =============================================================================
-- Log de cada execucao de carga: uma linha por recurso processado numa rodada.
-- Rodar como etl_radar (python -m src.transformacao.criar_estrutura). Idempotente.
-- =============================================================================

CREATE TABLE IF NOT EXISTS bronze.execucao (
    execucao_id      bigserial    PRIMARY KEY,
    rodada_id        uuid         NOT NULL,      -- agrupa os recursos de uma mesma carga (inicial ou incremental)
    origem_carga     text         NOT NULL CHECK (origem_carga IN ('python', 'n8n')),   -- quem chamou as APIs
    disparado_por    text         NOT NULL,      -- 'manual' | 'agenda_n8n'
    modo             text         NOT NULL CHECK (modo IN ('inicial', 'incremental')),
    recurso          text         NOT NULL,      -- ex.: 'ibge_agregado_6579', 'bcb_sgs_432'; 'rodada' = registro da trava
    iniciado_em      timestamptz  NOT NULL DEFAULT now(),
    finalizado_em    timestamptz,
    status           text         NOT NULL DEFAULT 'em_andamento'
                     CHECK (status IN ('em_andamento', 'sucesso', 'sem_novidade', 'erro', 'ignorada_trava')),
    chamadas_ok      integer      NOT NULL DEFAULT 0,   -- chamadas HTTP bem-sucedidas (inclui 404 "nada novo" do BCB)
    chamadas_erro    integer      NOT NULL DEFAULT 0,   -- chamadas que falharam depois de todas as tentativas
    respostas_novas  integer      NOT NULL DEFAULT 0,   -- respostas gravadas (as repetidas nao contam)
    mensagem         text
);

CREATE INDEX IF NOT EXISTS ix_execucao_rodada ON bronze.execucao (rodada_id);
CREATE INDEX IF NOT EXISTS ix_execucao_recurso ON bronze.execucao (recurso, iniciado_em DESC);

COMMENT ON TABLE bronze.execucao IS 'Log das cargas da bronze: uma linha por recurso processado em cada rodada.';
