-- =============================================================================
-- RADAR DE EXPANSAO - ETAPA 4: CAMADA SILVER · 02_fatos.sql
-- =============================================================================
-- Fatos do modelo estrela: indicadores municipais (anuais) e macroeconomicos
-- (mensais e diarios). Uma linha = localidade/data + indicador + valor.
-- Rodar como etl_radar. Idempotente.
-- =============================================================================

CREATE TABLE IF NOT EXISTS silver.fato_indicador_municipal (
    municipio_id   integer      NOT NULL REFERENCES silver.dim_municipio,
    indicador_id   text         NOT NULL REFERENCES silver.dim_indicador,
    ano            smallint     NOT NULL,
    valor          numeric,                               -- nulo quando a fonte mandou simbolo
    flag_valor     text         NOT NULL DEFAULT 'ok'
                   CHECK (flag_valor IN ('ok', 'zero_absoluto', 'nao_disponivel', 'sigilo', 'nao_se_aplica', 'invalido')),
    bronze_id      bigint       NOT NULL,                 -- bronze.api_resposta.resposta_id
    atualizado_em  timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (municipio_id, indicador_id, ano)
);

CREATE INDEX IF NOT EXISTS ix_fato_municipal_indicador_ano
    ON silver.fato_indicador_municipal (indicador_id, ano);

CREATE TABLE IF NOT EXISTS silver.fato_indicador_macro (
    indicador_id   text         NOT NULL REFERENCES silver.dim_indicador,
    data           date         NOT NULL REFERENCES silver.dim_calendario,   -- mensal: 1o dia do mes
    valor          numeric,
    flag_valor     text         NOT NULL DEFAULT 'ok'
                   CHECK (flag_valor IN ('ok', 'zero_absoluto', 'nao_disponivel', 'sigilo', 'nao_se_aplica', 'invalido')),
    bronze_id      bigint       NOT NULL,
    atualizado_em  timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (indicador_id, data)
);
