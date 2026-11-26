-- =============================================================================
-- RADAR DE EXPANSAO - ETAPA 4: CAMADA SILVER · 03_funcoes_apoio.sql
-- =============================================================================
-- Funcoes pequenas usadas pela transformacao bronze -> silver:
--   valor_numerico / flag_valor : texto da API -> numero + flag dos simbolos
--   bronze_vigente              : resposta mais recente de cada (recurso, lote)
-- Rodar como etl_radar. Idempotente.
-- =============================================================================

-- Texto da API -> numero. Simbolos ("-", "...", "X", "..") viram nulo.
CREATE OR REPLACE FUNCTION silver.valor_numerico(p_texto text)
RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN p_texto ~ '^-?[0-9]+(\.[0-9]+)?$' THEN p_texto::numeric END
$$;

-- Texto da API -> flag que explica o valor nulo.
--   "-" = zero absoluto · "..." = nao disponivel · "X" = sigilo · ".." = nao se aplica
CREATE OR REPLACE FUNCTION silver.flag_valor(p_texto text)
RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN p_texto ~ '^-?[0-9]+(\.[0-9]+)?$'  THEN 'ok'
        WHEN p_texto = '-'                      THEN 'zero_absoluto'
        WHEN p_texto IS NULL OR p_texto IN ('...', '') THEN 'nao_disponivel'
        WHEN p_texto = 'X'                      THEN 'sigilo'
        WHEN p_texto = '..'                     THEN 'nao_se_aplica'
        ELSE 'invalido'
    END
$$;

-- Resposta mais recente de cada (recurso, lote) da bronze.
-- p_origem: 'python', 'n8n' ou 'qualquer' (padrao) - permite comparar os cenarios A e B.
CREATE OR REPLACE FUNCTION silver.bronze_vigente(p_origem text DEFAULT 'qualquer')
RETURNS TABLE (resposta_id bigint, recurso text, lote text, parametros jsonb,
               payload jsonb, ingerido_em timestamptz)
LANGUAGE sql STABLE AS $$
    SELECT DISTINCT ON (r.recurso, r.lote)
           r.resposta_id, r.recurso, r.lote, r.parametros, r.payload, r.ingerido_em
    FROM bronze.api_resposta AS r
    WHERE p_origem = 'qualquer' OR r.origem_carga = p_origem
    ORDER BY r.recurso, r.lote, r.ingerido_em DESC
$$;

-- Numero no formato brasileiro para textos prontos (ex.: 13.75 -> '13,75').
-- Usada nas justificativas do semaforo da gold; fica fora do schema exposto pela API.
CREATE OR REPLACE FUNCTION silver.numero_br(p_valor numeric, p_casas integer DEFAULT 2)
RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT replace(to_char(round(p_valor, p_casas),
                           'FM999999990' || CASE WHEN p_casas > 0 THEN '.' || repeat('0', p_casas) ELSE '' END),
                   '.', ',')
$$;
