-- =============================================================================
-- RADAR DE EXPANSAO - ETAPA 4: CAMADA SILVER · 04_atualizar_silver.sql
-- =============================================================================
-- Transformacao bronze -> silver num UNICO caminho de codigo, usado pelos dois
-- cenarios de ingestao (A: python -m src.transformacao.executar; B: o n8n chama
-- o mesmo job ou faz SELECT * FROM silver.atualizar()).
--
-- O que faz (spec.md, secao 4):
--   1. le a resposta mais recente de cada (recurso, lote) da bronze;
--   2. carrega regioes, UFs e municipios (JSON de localidades);
--   3. "achata" o JSON dos agregados do IBGE: localidade + periodo + valor;
--   4. le as series do BCB (data + valor), sem datas futuras;
--   5. converte tipos, troca simbolos por nulo + flag, padroniza codigos;
--   6. grava com UPSERT (a versao mais nova vence; sem duplicatas) e bronze_id.
-- Devolve uma linha por tabela com a quantidade de linhas inseridas/alteradas.
-- Rodar como etl_radar. Idempotente.
-- =============================================================================

CREATE OR REPLACE FUNCTION silver.atualizar(p_origem text DEFAULT 'qualquer')
RETURNS TABLE (tabela text, linhas_gravadas bigint)
LANGUAGE plpgsql AS $$
DECLARE
    v_linhas bigint;
BEGIN
    IF p_origem NOT IN ('qualquer', 'python', 'n8n') THEN
        RAISE EXCEPTION 'p_origem invalida: % (use qualquer, python ou n8n)', p_origem;
    END IF;

    -- resposta vigente de cada (recurso, lote), materializada uma vez
    CREATE TEMP TABLE IF NOT EXISTS tmp_vigente ON COMMIT DROP AS
        SELECT * FROM silver.bronze_vigente(p_origem);

    -- 1. Regioes ------------------------------------------------------------
    INSERT INTO silver.dim_regiao AS d (regiao_id, regiao_sigla, regiao_nome, bronze_id)
    SELECT (e ->> 'id')::smallint, e ->> 'sigla', e ->> 'nome', v.resposta_id
    FROM tmp_vigente AS v, jsonb_array_elements(v.payload) AS e
    WHERE v.recurso = 'ibge_regioes'
    ON CONFLICT (regiao_id) DO UPDATE
        SET regiao_sigla = EXCLUDED.regiao_sigla, regiao_nome = EXCLUDED.regiao_nome,
            bronze_id = EXCLUDED.bronze_id, atualizado_em = now()
        WHERE (d.regiao_sigla, d.regiao_nome, d.bronze_id)
              IS DISTINCT FROM (EXCLUDED.regiao_sigla, EXCLUDED.regiao_nome, EXCLUDED.bronze_id);
    GET DIAGNOSTICS v_linhas = ROW_COUNT;
    tabela := 'silver.dim_regiao'; linhas_gravadas := v_linhas; RETURN NEXT;

    -- 2. UFs ----------------------------------------------------------------
    INSERT INTO silver.dim_uf AS d (uf_id, uf_sigla, uf_nome, regiao_id, bronze_id)
    SELECT (e ->> 'id')::smallint, e ->> 'sigla', e ->> 'nome',
           (e -> 'regiao' ->> 'id')::smallint, v.resposta_id
    FROM tmp_vigente AS v, jsonb_array_elements(v.payload) AS e
    WHERE v.recurso = 'ibge_estados'
    ON CONFLICT (uf_id) DO UPDATE
        SET uf_sigla = EXCLUDED.uf_sigla, uf_nome = EXCLUDED.uf_nome,
            regiao_id = EXCLUDED.regiao_id, bronze_id = EXCLUDED.bronze_id, atualizado_em = now()
        WHERE (d.uf_sigla, d.uf_nome, d.regiao_id, d.bronze_id)
              IS DISTINCT FROM (EXCLUDED.uf_sigla, EXCLUDED.uf_nome, EXCLUDED.regiao_id, EXCLUDED.bronze_id);
    GET DIAGNOSTICS v_linhas = ROW_COUNT;
    tabela := 'silver.dim_uf'; linhas_gravadas := v_linhas; RETURN NEXT;

    -- 3. Municipios (JSON "nivelado": um objeto plano por municipio) ----------
    INSERT INTO silver.dim_municipio AS d
        (municipio_id, municipio_nome, uf_id, regiao_id,
         regiao_intermediaria_id, regiao_intermediaria_nome, regiao_imediata_id, regiao_imediata_nome,
         mesorregiao_id, mesorregiao_nome, microrregiao_id, microrregiao_nome, bronze_id)
    SELECT (e ->> 'municipio-id')::integer, e ->> 'municipio-nome',
           (e ->> 'UF-id')::smallint, (e ->> 'regiao-id')::smallint,
           (e ->> 'regiao-intermediaria-id')::integer, e ->> 'regiao-intermediaria-nome',
           (e ->> 'regiao-imediata-id')::integer, e ->> 'regiao-imediata-nome',
           (e ->> 'mesorregiao-id')::integer, e ->> 'mesorregiao-nome',
           (e ->> 'microrregiao-id')::integer, e ->> 'microrregiao-nome',
           v.resposta_id
    FROM tmp_vigente AS v, jsonb_array_elements(v.payload) AS e
    WHERE v.recurso = 'ibge_municipios'
    ON CONFLICT (municipio_id) DO UPDATE
        SET municipio_nome = EXCLUDED.municipio_nome, uf_id = EXCLUDED.uf_id,
            regiao_id = EXCLUDED.regiao_id,
            regiao_intermediaria_id = EXCLUDED.regiao_intermediaria_id,
            regiao_intermediaria_nome = EXCLUDED.regiao_intermediaria_nome,
            regiao_imediata_id = EXCLUDED.regiao_imediata_id,
            regiao_imediata_nome = EXCLUDED.regiao_imediata_nome,
            mesorregiao_id = EXCLUDED.mesorregiao_id, mesorregiao_nome = EXCLUDED.mesorregiao_nome,
            microrregiao_id = EXCLUDED.microrregiao_id, microrregiao_nome = EXCLUDED.microrregiao_nome,
            bronze_id = EXCLUDED.bronze_id, atualizado_em = now()
        WHERE (d.municipio_nome, d.uf_id, d.regiao_imediata_id, d.regiao_intermediaria_id,
               d.microrregiao_id, d.bronze_id)
              IS DISTINCT FROM (EXCLUDED.municipio_nome, EXCLUDED.uf_id, EXCLUDED.regiao_imediata_id,
               EXCLUDED.regiao_intermediaria_id, EXCLUDED.microrregiao_id, EXCLUDED.bronze_id);
    GET DIAGNOSTICS v_linhas = ROW_COUNT;
    tabela := 'silver.dim_municipio'; linhas_gravadas := v_linhas; RETURN NEXT;

    -- 4. Fatos municipais: achata variavel -> resultados -> series -> serie{periodo: valor}
    INSERT INTO silver.fato_indicador_municipal AS f
        (municipio_id, indicador_id, ano, valor, flag_valor, bronze_id)
    SELECT DISTINCT ON (l.municipio_id, l.indicador_id, l.ano)
           l.municipio_id, l.indicador_id, l.ano,
           silver.valor_numerico(l.valor_texto), silver.flag_valor(l.valor_texto), l.resposta_id
    FROM (
        SELECT (s -> 'localidade' ->> 'id')::integer AS municipio_id,
               i.indicador_id,
               p.periodo::smallint                   AS ano,
               p.valor_texto,
               v.resposta_id,
               v.ingerido_em
        FROM tmp_vigente AS v
        CROSS JOIN LATERAL jsonb_array_elements(v.payload) AS var
        JOIN silver.dim_indicador AS i
          ON i.agregado = (v.parametros ->> 'agregado')::integer
         AND i.variavel = (var ->> 'id')::integer
         AND i.nivel = 'municipal'
        CROSS JOIN LATERAL jsonb_array_elements(var -> 'resultados') AS r
        CROSS JOIN LATERAL jsonb_array_elements(r -> 'series') AS s
        CROSS JOIN LATERAL jsonb_each_text(s -> 'serie') AS p (periodo, valor_texto)
        WHERE v.recurso LIKE 'ibge_agregado_%'
          AND s -> 'localidade' -> 'nivel' ->> 'id' = 'N6'
    ) AS l
    JOIN silver.dim_municipio AS m ON m.municipio_id = l.municipio_id
    ORDER BY l.municipio_id, l.indicador_id, l.ano, l.ingerido_em DESC
    ON CONFLICT (municipio_id, indicador_id, ano) DO UPDATE
        SET valor = EXCLUDED.valor, flag_valor = EXCLUDED.flag_valor,
            bronze_id = EXCLUDED.bronze_id, atualizado_em = now()
        WHERE (f.valor, f.flag_valor, f.bronze_id)
              IS DISTINCT FROM (EXCLUDED.valor, EXCLUDED.flag_valor, EXCLUDED.bronze_id);
    GET DIAGNOSTICS v_linhas = ROW_COUNT;
    tabela := 'silver.fato_indicador_municipal'; linhas_gravadas := v_linhas; RETURN NEXT;

    -- 5. Fatos macro: IPCA do IBGE (AAAAMM, nivel Brasil) + series do BCB (dd/MM/aaaa)
    INSERT INTO silver.fato_indicador_macro AS f
        (indicador_id, data, valor, flag_valor, bronze_id)
    SELECT DISTINCT ON (l.indicador_id, l.data)
           l.indicador_id, l.data,
           silver.valor_numerico(l.valor_texto), silver.flag_valor(l.valor_texto), l.resposta_id
    FROM (
        SELECT i.indicador_id,
               to_date(p.periodo, 'YYYYMM') AS data,
               p.valor_texto, v.resposta_id, v.ingerido_em
        FROM tmp_vigente AS v
        CROSS JOIN LATERAL jsonb_array_elements(v.payload) AS var
        JOIN silver.dim_indicador AS i
          ON i.agregado = (v.parametros ->> 'agregado')::integer
         AND i.variavel = (var ->> 'id')::integer
         AND i.nivel = 'macro'
        CROSS JOIN LATERAL jsonb_array_elements(var -> 'resultados') AS r
        CROSS JOIN LATERAL jsonb_array_elements(r -> 'series') AS s
        CROSS JOIN LATERAL jsonb_each_text(s -> 'serie') AS p (periodo, valor_texto)
        WHERE v.recurso LIKE 'ibge_agregado_%'

        UNION ALL

        SELECT i.indicador_id,
               to_date(e ->> 'data', 'DD/MM/YYYY') AS data,
               e ->> 'valor', v.resposta_id, v.ingerido_em
        FROM tmp_vigente AS v
        JOIN silver.dim_indicador AS i ON i.serie_bcb = (v.parametros ->> 'serie')::integer
        CROSS JOIN LATERAL jsonb_array_elements(v.payload) AS e
        WHERE v.recurso LIKE 'bcb_sgs_%'
    ) AS l
    WHERE l.data <= current_date          -- Selic meta traz datas futuras: ficam so na bronze
    ORDER BY l.indicador_id, l.data, l.ingerido_em DESC
    ON CONFLICT (indicador_id, data) DO UPDATE
        SET valor = EXCLUDED.valor, flag_valor = EXCLUDED.flag_valor,
            bronze_id = EXCLUDED.bronze_id, atualizado_em = now()
        WHERE (f.valor, f.flag_valor, f.bronze_id)
              IS DISTINCT FROM (EXCLUDED.valor, EXCLUDED.flag_valor, EXCLUDED.bronze_id);
    GET DIAGNOSTICS v_linhas = ROW_COUNT;
    tabela := 'silver.fato_indicador_macro'; linhas_gravadas := v_linhas; RETURN NEXT;

    DROP TABLE IF EXISTS tmp_vigente;
END
$$;
