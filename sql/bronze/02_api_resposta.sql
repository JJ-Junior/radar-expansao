-- =============================================================================
-- RADAR DE EXPANSAO - ETAPA 3: CAMADA BRONZE · 02_api_resposta.sql
-- =============================================================================
-- O "cofre": uma linha por chamada bem-sucedida, com o JSON exatamente como veio.
-- Contrato unico para os dois cenarios de ingestao (origem_carga 'python' | 'n8n').
-- Rodar como etl_radar. Idempotente.
-- =============================================================================

CREATE TABLE IF NOT EXISTS bronze.api_resposta (
    resposta_id        bigserial    PRIMARY KEY,
    origem_carga       text         NOT NULL CHECK (origem_carga IN ('python', 'n8n')),
    fonte              text         NOT NULL CHECK (fonte IN ('IBGE', 'BCB')),
    recurso            text         NOT NULL,      -- ex.: 'ibge_agregado_6579', 'ibge_municipios', 'bcb_sgs_432'
    endpoint           text         NOT NULL,      -- caminho chamado, sem o host
    parametros         jsonb        NOT NULL,      -- parametros usados (periodos, variaveis, localidades, datas)
    url                text         NOT NULL,      -- URL completa, para reproduzir a chamada
    lote               text         NOT NULL,      -- ano, ano-UF, janela de datas ou 'snapshot'
    modificacao_fonte  date,                       -- IBGE: data de `modificacao` do periodo (base do incremental)
    http_status        smallint     NOT NULL,
    payload            jsonb        NOT NULL,      -- resposta original, inteira
    -- md5 calculado pelo proprio Postgres sobre o jsonb (forma canonica): sai igual
    -- nos dois cenarios, mesmo que Python e n8n serializem o JSON de jeitos diferentes
    payload_hash       text         GENERATED ALWAYS AS (md5(payload::text)) STORED,
    execucao_id        bigint       REFERENCES bronze.execucao (execucao_id),
    ingerido_em        timestamptz  NOT NULL DEFAULT now(),
    -- a mesma resposta nunca e gravada duas vezes pelo mesmo processo
    CONSTRAINT uq_api_resposta UNIQUE (origem_carga, recurso, lote, payload_hash)
);

CREATE INDEX IF NOT EXISTS ix_api_resposta_recurso_lote
    ON bronze.api_resposta (recurso, lote, ingerido_em DESC);

COMMENT ON TABLE bronze.api_resposta IS
    'Respostas das APIs do IBGE e do BCB exatamente como vieram. Somente INSERT.';

-- A bronze e o cofre: nem o proprio dono altera ou apaga respostas.
REVOKE UPDATE, DELETE, TRUNCATE ON bronze.api_resposta FROM etl_radar;
