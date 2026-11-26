-- =============================================================================
-- RADAR DE EXPANSAO - ETAPA 5: CAMADA GOLD · 02_atualizar_gold.sql
-- =============================================================================
-- Transformacao silver -> gold no MESMO caminho unico dos cenarios A e B
-- (python -m src.transformacao.executar, ou SELECT * FROM gold.atualizar()).
-- Recalcula a gold inteira (poucos milhares de linhas). Regras: spec.md, secao 5;
-- criterios e pesos: prd.md, secao 4 (tabela gold.ranking_criterio).
-- Rodar como etl_radar. Idempotente.
-- =============================================================================

-- Regras do semaforo (prd.md, secao 5), reaproveitadas no historico e no momento atual.
-- Ficam fora da API REST (04_permissoes.sql revoga o EXECUTE).
CREATE OR REPLACE FUNCTION gold.sinal_juros(p_var_pp numeric, p_limiar numeric)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN p_var_pp <= -p_limiar THEN 'verde' WHEN p_var_pp > p_limiar THEN 'vermelho' ELSE 'amarelo' END
$$;

CREATE OR REPLACE FUNCTION gold.sinal_inflacao(p_ipca_12m numeric, p_desacelerando boolean, p_teto numeric)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN p_ipca_12m <= p_teto AND p_desacelerando THEN 'verde'
                WHEN p_ipca_12m >  p_teto AND NOT p_desacelerando THEN 'vermelho' ELSE 'amarelo' END
$$;

-- cambio: pela variacao em 12 meses; com alerta de alta de curto prazo nunca e verde
-- (amarelo; vermelho se a variacao em 12 meses tambem for de alta)
CREATE OR REPLACE FUNCTION gold.sinal_cambio(p_var_12m numeric, p_alerta boolean, p_limiar numeric)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN p_alerta AND p_var_12m > 0 THEN 'vermelho'
                WHEN p_alerta                    THEN 'amarelo'
                WHEN p_var_12m <= 0              THEN 'verde'
                WHEN p_var_12m >  p_limiar       THEN 'vermelho'
                ELSE 'amarelo' END
$$;

CREATE OR REPLACE FUNCTION gold.pontos_sinal(p_sinal text)
RETURNS smallint LANGUAGE sql IMMUTABLE AS $$
    SELECT (CASE p_sinal WHEN 'verde' THEN 1 WHEN 'vermelho' THEN -1 ELSE 0 END)::smallint
$$;

CREATE OR REPLACE FUNCTION gold.recomendacao(p_pontuacao integer)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN p_pontuacao >= 2 THEN 'Expandir agora'
                WHEN p_pontuacao >= 0 THEN 'Expandir com cautela'
                ELSE 'Esperar' END
$$;

CREATE OR REPLACE FUNCTION gold.atualizar(p_populacao_minima integer DEFAULT 50000)
RETURNS TABLE (tabela text, linhas_gravadas bigint)
LANGUAGE plpgsql AS $$
DECLARE
    -- ============================== CONFIG ==============================
    c_janela_tendencia_anos  constant integer := 5;     -- janela da tendencia do PIB per capita
    c_percentil_inferior     constant numeric := 0.05;  -- limites do espaco competitivo
    c_percentil_superior     constant numeric := 0.95;
    -- quantidade de recomendadas e trava de renda ficam em gold.parametro_ranking
    -- limiares e janela do semaforo tambem ficam em gold.parametro_ranking
    -- ====================================================================
    v_ano_pop      smallint;
    v_ano_pib      smallint;
    v_ano_ini      smallint;
    v_ano_acad     smallint;
    v_ano_sal      smallint;
    v_ano_renda    smallint;
    v_p_inf        numeric;
    v_p_sup        numeric;
    v_versao       text;
    v_linhas       bigint;
    v_escolhidas   integer := 0;
    v_qtd_recomendadas integer;
    v_renda_minima     numeric;
    v_ano_projecao     integer;
    v_faixas           integer;
    v_cortes_renda     numeric[];
    v_janela           integer;
    v_alerta_pct       numeric;
    v_selic_pp         numeric;
    v_teto_ipca        numeric;
    v_dolar_pct        numeric;
    v_meses_ipca       integer;
    v_ref_cambio       date;
    v_ref_juros        date;
    v_ref_inflacao     date;
    v_imediatas    integer[] := '{}';
    v_cand         record;
BEGIN
    -- Anos de referencia: ultimo ano com dado de cada indicador ---------------
    SELECT max(ano) FILTER (WHERE indicador_id = 'populacao_estimada'),
           max(ano) FILTER (WHERE indicador_id = 'pib'),
           max(ano) FILTER (WHERE indicador_id = 'academias_qtd'),
           max(ano) FILTER (WHERE indicador_id = 'salario_medio'),
           max(ano) FILTER (WHERE indicador_id = 'renda_dom_per_capita')
      INTO v_ano_pop, v_ano_pib, v_ano_acad, v_ano_sal, v_ano_renda
      FROM silver.fato_indicador_municipal
     WHERE flag_valor IN ('ok', 'zero_absoluto');
    v_ano_ini := v_ano_pib - (c_janela_tendencia_anos - 1);

    -- Populacao por municipio e ano: estimativas + Censo 2022 + 2023 interpolado ---
    -- (a estimativa do IBGE nao existe para 2022 e 2023; ver spec.md 5.2)
    DROP TABLE IF EXISTS tmp_pop;
    CREATE TEMP TABLE tmp_pop AS
        SELECT municipio_id, ano, valor AS pop
          FROM silver.fato_indicador_municipal
         WHERE indicador_id = 'populacao_estimada' AND valor > 0;
    INSERT INTO tmp_pop
        SELECT c.municipio_id, 2022::smallint, c.valor
          FROM silver.fato_indicador_municipal AS c
         WHERE c.indicador_id = 'populacao_censo' AND c.valor > 0
           AND NOT EXISTS (SELECT 1 FROM tmp_pop AS p WHERE p.municipio_id = c.municipio_id AND p.ano = 2022);
    INSERT INTO tmp_pop
        SELECT a.municipio_id, 2023::smallint, sqrt(a.pop * b.pop)
          FROM tmp_pop AS a JOIN tmp_pop AS b ON b.municipio_id = a.municipio_id AND b.ano = 2024
         WHERE a.ano = 2022
           AND NOT EXISTS (SELECT 1 FROM tmp_pop AS p WHERE p.municipio_id = a.municipio_id AND p.ano = 2023);
    CREATE INDEX ON tmp_pop (municipio_id, ano);

    -- 1. gold.indicadores_municipio (P1, P3, P4) --------------------------------
    TRUNCATE gold.indicadores_municipio;
    INSERT INTO gold.indicadores_municipio
        (municipio_id, municipio_nome, uf_sigla, regiao_sigla, regiao_imediata_id, regiao_imediata_nome,
         populacao, populacao_ano, populacao_censo_2022, crescimento_pop_aa,
         pib_mil_reais, pib_ano, pib_per_capita, pib_per_capita_tendencia, tendencia_ano_inicial,
         renda_dom_per_capita, renda_ano, academias_qtd, academias_ano, academias_por_10mil_hab,
         salario_medio, salario_ano, latitude, longitude)
    SELECT m.municipio_id, m.municipio_nome, u.uf_sigla, r.regiao_sigla,
           m.regiao_imediata_id, m.regiao_imediata_nome,
           round(pop_atual.pop)::integer, v_ano_pop, round(censo.valor)::integer,
           CASE WHEN censo.valor > 0 AND pop_atual.pop > 0 AND v_ano_pop > 2022
                THEN round(power(pop_atual.pop / censo.valor, 1.0 / (v_ano_pop - 2022)) - 1, 4) END,
           pib.valor, v_ano_pib,
           round(pib.valor * 1000 / pop_pib.pop, 2),
           CASE WHEN pib.valor > 0 AND pib_ini.valor > 0
                THEN round(power((pib.valor / pop_pib.pop) / (pib_ini.valor / pop_ini.pop),
                                 1.0 / (v_ano_pib - v_ano_ini)) - 1, 4) END,
           v_ano_ini,
           renda.valor, v_ano_renda,
           CASE WHEN acad.flag_valor = 'zero_absoluto' THEN 0 ELSE round(acad.valor)::integer END,
           v_ano_acad,
           round(CASE WHEN acad.flag_valor = 'zero_absoluto' THEN 0 ELSE acad.valor END
                 * 10000 / pop_acad.pop, 3),
           sal.valor, v_ano_sal,
           m.latitude, m.longitude
      FROM silver.dim_municipio AS m
      JOIN silver.dim_uf AS u ON u.uf_id = m.uf_id
      JOIN silver.dim_regiao AS r ON r.regiao_id = m.regiao_id
      LEFT JOIN tmp_pop AS pop_atual ON pop_atual.municipio_id = m.municipio_id AND pop_atual.ano = v_ano_pop
      LEFT JOIN tmp_pop AS pop_pib   ON pop_pib.municipio_id = m.municipio_id   AND pop_pib.ano = v_ano_pib
      LEFT JOIN tmp_pop AS pop_ini   ON pop_ini.municipio_id = m.municipio_id   AND pop_ini.ano = v_ano_ini
      LEFT JOIN tmp_pop AS pop_acad  ON pop_acad.municipio_id = m.municipio_id  AND pop_acad.ano = v_ano_acad
      LEFT JOIN silver.fato_indicador_municipal AS censo
             ON censo.municipio_id = m.municipio_id AND censo.indicador_id = 'populacao_censo' AND censo.ano = 2022
      LEFT JOIN silver.fato_indicador_municipal AS pib
             ON pib.municipio_id = m.municipio_id AND pib.indicador_id = 'pib' AND pib.ano = v_ano_pib
      LEFT JOIN silver.fato_indicador_municipal AS pib_ini
             ON pib_ini.municipio_id = m.municipio_id AND pib_ini.indicador_id = 'pib' AND pib_ini.ano = v_ano_ini
      LEFT JOIN silver.fato_indicador_municipal AS renda
             ON renda.municipio_id = m.municipio_id AND renda.indicador_id = 'renda_dom_per_capita' AND renda.ano = v_ano_renda
      LEFT JOIN silver.fato_indicador_municipal AS acad
             ON acad.municipio_id = m.municipio_id AND acad.indicador_id = 'academias_qtd' AND acad.ano = v_ano_acad
      LEFT JOIN silver.fato_indicador_municipal AS sal
             ON sal.municipio_id = m.municipio_id AND sal.indicador_id = 'salario_medio' AND sal.ano = v_ano_sal;
    GET DIAGNOSTICS v_linhas = ROW_COUNT;
    tabela := 'gold.indicadores_municipio'; linhas_gravadas := v_linhas; RETURN NEXT;

    -- 2. gold.ranking_expansao (P2, P5, P8) ------------------------------------
    SELECT max(versao_pesos) INTO v_versao FROM gold.ranking_criterio;

    DROP TABLE IF EXISTS tmp_universo;
    CREATE TEMP TABLE tmp_universo AS
        SELECT * FROM gold.indicadores_municipio
         WHERE populacao >= p_populacao_minima AND regiao_imediata_id IS NOT NULL;

    -- limites do espaco competitivo (winsorizacao nos percentis 5% e 95% do universo)
    SELECT percentile_cont(c_percentil_inferior) WITHIN GROUP (ORDER BY academias_por_10mil_hab),
           percentile_cont(c_percentil_superior) WITHIN GROUP (ORDER BY academias_por_10mil_hab)
      INTO v_p_inf, v_p_sup
      FROM tmp_universo WHERE academias_por_10mil_hab IS NOT NULL;

    -- Estimativas do simulador de regiao (P9), para TODOS os municipios ------------
    --   faixa de renda: quintis da renda domiciliar per capita do universo;
    --   densidade de referencia: mediana de academias/10 mil hab. (limitada a P5-P95)
    --   das cidades do universo da mesma faixa;
    --   lacuna = (referencia - densidade atual limitada a P5-P95) x populacao / 10 mil;
    --   populacao projetada = populacao atual x (1 + crescimento anual) ^ (ano - ano atual).
    SELECT max(valor) FILTER (WHERE parametro = 'ano_projecao_populacao'),
           max(valor) FILTER (WHERE parametro = 'faixas_renda_referencia')
      INTO v_ano_projecao, v_faixas
      FROM gold.parametro_ranking;
    v_ano_projecao := coalesce(v_ano_projecao, v_ano_pop + 2);
    v_faixas := coalesce(v_faixas, 5);

    SELECT percentile_cont(ARRAY(SELECT g::numeric / v_faixas FROM generate_series(1, v_faixas - 1) AS g))
           WITHIN GROUP (ORDER BY renda_dom_per_capita)
      INTO v_cortes_renda
      FROM tmp_universo WHERE renda_dom_per_capita IS NOT NULL;

    DROP TABLE IF EXISTS tmp_referencia;
    CREATE TEMP TABLE tmp_referencia AS
        SELECT width_bucket(renda_dom_per_capita, v_cortes_renda) + 1 AS faixa_renda,
               percentile_cont(0.5) WITHIN GROUP (
                   ORDER BY least(greatest(academias_por_10mil_hab, v_p_inf), v_p_sup)) AS densidade_referencia
          FROM tmp_universo
         WHERE renda_dom_per_capita IS NOT NULL AND academias_por_10mil_hab IS NOT NULL
         GROUP BY 1;

    UPDATE gold.indicadores_municipio AS i
       SET faixa_renda = f.faixa_renda,
           densidade_referencia = round(ref.densidade_referencia::numeric, 3),
           lacuna_academias = round((ref.densidade_referencia
                                     - least(greatest(i.academias_por_10mil_hab, v_p_inf), v_p_sup))
                                    * i.populacao / 10000.0),
           ano_projecao = v_ano_projecao,
           populacao_projetada = round(i.populacao * power(1 + i.crescimento_pop_aa, v_ano_projecao - i.populacao_ano)),
           estimativa = CASE WHEN i.crescimento_pop_aa IS NOT NULL OR i.academias_por_10mil_hab IS NOT NULL THEN
               'Estimativa simples, nao e previsao garantida: populacao projetada pela taxa anual desde o Censo 2022; '
               || 'lacuna = (densidade de referencia da faixa de renda - densidade atual) x populacao / 10 mil.' END
      FROM (SELECT municipio_id, width_bucket(renda_dom_per_capita, v_cortes_renda) + 1 AS faixa_renda
              FROM gold.indicadores_municipio WHERE renda_dom_per_capita IS NOT NULL) AS f
      LEFT JOIN tmp_referencia AS ref ON ref.faixa_renda = f.faixa_renda
     WHERE f.municipio_id = i.municipio_id;

    -- valor de cada componente por municipio (formato longo)
    DROP TABLE IF EXISTS tmp_valor;
    CREATE TEMP TABLE tmp_valor AS
              SELECT municipio_id, 'mercado'::text AS criterio, populacao::numeric AS valor FROM tmp_universo
    UNION ALL SELECT municipio_id, 'poder_compra', renda_dom_per_capita FROM tmp_universo
    UNION ALL SELECT municipio_id, 'espaco_competitivo',
                     least(greatest(academias_por_10mil_hab, v_p_inf), v_p_sup) FROM tmp_universo
    UNION ALL SELECT municipio_id, 'crescimento', crescimento_pop_aa FROM tmp_universo
    UNION ALL SELECT municipio_id, 'riqueza_nivel', pib_per_capita FROM tmp_universo
    UNION ALL SELECT municipio_id, 'riqueza_tendencia', pib_per_capita_tendencia FROM tmp_universo
    UNION ALL SELECT municipio_id, 'mercado_formal', salario_medio FROM tmp_universo;

    -- nota 0-100: percentil com empates na posicao media; invertida quando "menor e melhor"
    DROP TABLE IF EXISTS tmp_nota;
    CREATE TEMP TABLE tmp_nota AS
    SELECT p.municipio_id, p.criterio, c.peso, c.grupo,
           CASE WHEN c.sentido = 'menor_melhor' THEN 100 - p.percentil ELSE p.percentil END AS nota
      FROM (
            SELECT municipio_id, criterio,
                   CASE WHEN count(*) OVER w_criterio = 1 THEN 100
                        ELSE 100.0 * (rank() OVER w_ordem
                                      + (count(*) OVER w_empate - 1) / 2.0 - 1)
                             / (count(*) OVER w_criterio - 1)
                   END AS percentil
              FROM tmp_valor
             WHERE valor IS NOT NULL
            WINDOW w_criterio AS (PARTITION BY criterio),
                   w_ordem    AS (PARTITION BY criterio ORDER BY valor),
                   w_empate   AS (PARTITION BY criterio, valor)
           ) AS p
      JOIN gold.ranking_criterio AS c ON c.criterio = p.criterio;

    TRUNCATE gold.ranking_expansao;
    INSERT INTO gold.ranking_expansao
        (municipio_id, municipio_nome, uf_sigla, regiao_sigla, regiao_imediata_id, regiao_imediata_nome,
         latitude, longitude,
         populacao, nota_mercado, nota_poder_compra, nota_espaco_competitivo, nota_crescimento,
         nota_riqueza_nivel, nota_riqueza_tendencia, nota_riqueza, nota_mercado_formal,
         nota_final, posicao_brasil, posicao_regiao, posicao_uf,
         dados_incompletos, criterios_ausentes, peso_considerado, verificar_concorrencia, versao_pesos)
    SELECT u.municipio_id, u.municipio_nome, u.uf_sigla, u.regiao_sigla,
           u.regiao_imediata_id, u.regiao_imediata_nome, u.latitude, u.longitude, u.populacao,
           n.nota_mercado, n.nota_poder_compra, n.nota_espaco_competitivo, n.nota_crescimento,
           n.nota_riqueza_nivel, n.nota_riqueza_tendencia, n.nota_riqueza, n.nota_mercado_formal,
           n.nota_final,
           row_number() OVER (ORDER BY n.nota_final DESC, u.populacao DESC),
           row_number() OVER (PARTITION BY u.regiao_sigla ORDER BY n.nota_final DESC, u.populacao DESC),
           row_number() OVER (PARTITION BY u.uf_sigla ORDER BY n.nota_final DESC, u.populacao DESC),
           n.peso_considerado < 0.9995,
           NULLIF(ARRAY(SELECT c.criterio FROM gold.ranking_criterio AS c
                         WHERE NOT EXISTS (SELECT 1 FROM tmp_nota AS t
                                           WHERE t.municipio_id = u.municipio_id AND t.criterio = c.criterio)
                         ORDER BY c.ordem), '{}'),
           n.peso_considerado,
           coalesce(u.academias_qtd = 0, false),
           v_versao
      FROM tmp_universo AS u
      JOIN (
            SELECT municipio_id,
                   round(max(nota) FILTER (WHERE criterio = 'mercado'), 2)            AS nota_mercado,
                   round(max(nota) FILTER (WHERE criterio = 'poder_compra'), 2)       AS nota_poder_compra,
                   round(max(nota) FILTER (WHERE criterio = 'espaco_competitivo'), 2) AS nota_espaco_competitivo,
                   round(max(nota) FILTER (WHERE criterio = 'crescimento'), 2)        AS nota_crescimento,
                   round(max(nota) FILTER (WHERE criterio = 'riqueza_nivel'), 2)      AS nota_riqueza_nivel,
                   round(max(nota) FILTER (WHERE criterio = 'riqueza_tendencia'), 2)  AS nota_riqueza_tendencia,
                   round(sum(peso * nota) FILTER (WHERE grupo = 'riqueza')
                         / nullif(sum(peso) FILTER (WHERE grupo = 'riqueza'), 0), 2)  AS nota_riqueza,
                   round(max(nota) FILTER (WHERE criterio = 'mercado_formal'), 2)     AS nota_mercado_formal,
                   -- dado faltante: o peso do criterio ausente e redistribuido entre os disponiveis
                   round(sum(peso * nota) / sum(peso), 2)                             AS nota_final,
                   round(sum(peso), 3)                                                AS peso_considerado
              FROM tmp_nota
             GROUP BY municipio_id
           ) AS n ON n.municipio_id = u.municipio_id;
    GET DIAGNOSTICS v_linhas = ROW_COUNT;

    -- 5 unidades recomendadas (prd.md 4.2):
    --   trava de renda: so e elegivel quem tem nota de poder de compra >= parametro;
    --   no maximo uma por regiao imediata (evita canibalizacao). O ranking geral nao muda.
    SELECT max(valor) FILTER (WHERE parametro = 'unidades_recomendadas'),
           max(valor) FILTER (WHERE parametro = 'nota_minima_poder_compra')
      INTO v_qtd_recomendadas, v_renda_minima
      FROM gold.parametro_ranking;
    v_qtd_recomendadas := coalesce(v_qtd_recomendadas, 5);
    v_renda_minima := coalesce(v_renda_minima, 0);

    UPDATE gold.ranking_expansao
       SET elegivel_recomendacao = coalesce(nota_poder_compra >= v_renda_minima, false);

    FOR v_cand IN SELECT municipio_id, regiao_imediata_id FROM gold.ranking_expansao
                   WHERE elegivel_recomendacao ORDER BY posicao_brasil LOOP
        EXIT WHEN v_escolhidas >= v_qtd_recomendadas;
        CONTINUE WHEN v_cand.regiao_imediata_id = ANY (v_imediatas);
        v_escolhidas := v_escolhidas + 1;
        v_imediatas := v_imediatas || v_cand.regiao_imediata_id;
        UPDATE gold.ranking_expansao
           SET recomendado_top5 = true, ordem_recomendacao = v_escolhidas
         WHERE municipio_id = v_cand.municipio_id;
    END LOOP;
    tabela := 'gold.ranking_expansao'; linhas_gravadas := v_linhas; RETURN NEXT;

    -- 3. gold.contexto_macro (P6) ----------------------------------------------
    TRUNCATE gold.contexto_macro;
    INSERT INTO gold.contexto_macro
        (mes, mes_parcial, selic_meta, selic_ultima_data, selic_var_12m_pp,
         dolar_medio, dolar_ultimo, dolar_ultimo_data, dolar_var_12m_pct, dolar_var_1m_pct,
         ipca_mensal, ipca_12m)
    WITH macro AS (
        SELECT indicador_id, data, date_trunc('month', data)::date AS mes, valor
          FROM silver.fato_indicador_macro WHERE valor IS NOT NULL
    ),
    selic AS (   -- meta vigente no ultimo dia com dado no mes
        SELECT DISTINCT ON (mes) mes, data, valor FROM macro
         WHERE indicador_id = 'selic_meta' ORDER BY mes, data DESC
    ),
    dolar AS (SELECT mes, avg(valor) AS valor FROM macro WHERE indicador_id = 'dolar_venda' GROUP BY mes),
    dolar_ultimo AS (   -- ultimo fechamento do mes
        SELECT DISTINCT ON (mes) mes, data, valor FROM macro
         WHERE indicador_id = 'dolar_venda' ORDER BY mes, data DESC
    ),
    ipca AS (SELECT mes, valor FROM macro WHERE indicador_id = 'ipca_mensal'),
    ipca12 AS (SELECT mes, valor FROM macro WHERE indicador_id = 'ipca_12m'),
    meses AS (SELECT DISTINCT mes FROM macro WHERE indicador_id IN ('selic_meta', 'dolar_venda', 'ipca_mensal', 'ipca_12m'))
    SELECT m.mes,
           m.mes = date_trunc('month', current_date)::date,
           s.valor, s.data, s.valor - s12.valor,
           round(d.valor, 4), du.valor, du.data,
           round((d.valor / nullif(d12.valor, 0) - 1) * 100, 2),
           round((d.valor / nullif(d1.valor, 0) - 1) * 100, 2),
           i.valor, i12.valor
      FROM meses AS m
      LEFT JOIN selic        AS s   ON s.mes = m.mes
      LEFT JOIN selic        AS s12 ON s12.mes = (m.mes - interval '12 months')::date
      LEFT JOIN dolar        AS d   ON d.mes = m.mes
      LEFT JOIN dolar        AS d12 ON d12.mes = (m.mes - interval '12 months')::date
      LEFT JOIN dolar        AS d1  ON d1.mes = (m.mes - interval '1 month')::date
      LEFT JOIN dolar_ultimo AS du  ON du.mes = m.mes
      LEFT JOIN ipca         AS i   ON i.mes = m.mes
      LEFT JOIN ipca12       AS i12 ON i12.mes = m.mes;
    GET DIAGNOSTICS v_linhas = ROW_COUNT;
    tabela := 'gold.contexto_macro'; linhas_gravadas := v_linhas; RETURN NEXT;

    -- Parametros do semaforo (gold.parametro_ranking) ----------------------------
    SELECT max(valor) FILTER (WHERE parametro = 'semaforo_janela_dias'),
           max(valor) FILTER (WHERE parametro = 'semaforo_alerta_cambio_30d_pct'),
           max(valor) FILTER (WHERE parametro = 'semaforo_limiar_selic_pp'),
           max(valor) FILTER (WHERE parametro = 'semaforo_teto_ipca_pct'),
           max(valor) FILTER (WHERE parametro = 'semaforo_limiar_dolar_12m_pct'),
           max(valor) FILTER (WHERE parametro = 'semaforo_meses_tendencia_ipca')
      INTO v_janela, v_alerta_pct, v_selic_pp, v_teto_ipca, v_dolar_pct, v_meses_ipca
      FROM gold.parametro_ranking;
    v_janela := coalesce(v_janela, 30);
    v_alerta_pct := coalesce(v_alerta_pct, 5);
    v_selic_pp := coalesce(v_selic_pp, 0.5);
    v_teto_ipca := coalesce(v_teto_ipca, 4.5);
    v_dolar_pct := coalesce(v_dolar_pct, 10);
    v_meses_ipca := coalesce(v_meses_ipca, 3);

    -- 4. gold.momento_expansao (P7): historico mensal (meses fechados com IPCA) ----
    --    cambio e juros pela media/meta do mes; alerta de curto prazo pela media do
    --    mes contra a do mes anterior (mesma ideia da janela movel, em meses)
    TRUNCATE gold.momento_expansao;
    INSERT INTO gold.momento_expansao
        (mes, sinal_juros, sinal_inflacao, sinal_cambio, pontuacao, recomendacao, justificativa,
         mes_parcial, ref_juros, ref_cambio, ref_inflacao)
    WITH base AS (
        SELECT c.mes, c.selic_meta, c.selic_ultima_data, c.selic_var_12m_pp, c.dolar_medio, c.dolar_ultimo_data,
               c.dolar_var_12m_pct, coalesce(c.dolar_var_1m_pct > v_alerta_pct, false) AS alerta,
               c.ipca_12m, c.ipca_12m < a.ipca_12m AS desacelerando
          FROM gold.contexto_macro AS c
          JOIN gold.contexto_macro AS a
            ON a.mes = (c.mes - make_interval(months => v_meses_ipca))::date
         WHERE c.selic_var_12m_pp IS NOT NULL AND c.dolar_var_12m_pct IS NOT NULL
           AND c.ipca_12m IS NOT NULL AND a.ipca_12m IS NOT NULL
           AND NOT c.mes_parcial
    ),
    sinais AS (
        SELECT b.*,
               gold.sinal_juros(b.selic_var_12m_pp, v_selic_pp) AS s_juros,
               gold.sinal_inflacao(b.ipca_12m, b.desacelerando, v_teto_ipca) AS s_inflacao,
               gold.sinal_cambio(b.dolar_var_12m_pct, b.alerta, v_dolar_pct) AS s_cambio
          FROM base AS b
    ),
    pontos AS (
        SELECT s.*, gold.pontos_sinal(s.s_juros) + gold.pontos_sinal(s.s_inflacao)
                    + gold.pontos_sinal(s.s_cambio) AS pontuacao
          FROM sinais AS s
    )
    SELECT p.mes, p.s_juros, p.s_inflacao, p.s_cambio, p.pontuacao, gold.recomendacao(p.pontuacao),
           format('Juros: Selic em %s%% a.a., %s de %s p.p. em 12 meses (%s). '
                  'Inflação: IPCA de %s%% em 12 meses, %s do teto de %s%% e %s (%s). '
                  'Câmbio: dólar médio de R$ %s no mês, %s de %s%% em 12 meses%s (%s).',
                  silver.numero_br(p.selic_meta, 2),
                  CASE WHEN p.selic_var_12m_pp < 0 THEN 'queda' WHEN p.selic_var_12m_pp > 0 THEN 'alta' ELSE 'variação' END,
                  silver.numero_br(abs(p.selic_var_12m_pp), 2), p.s_juros,
                  silver.numero_br(p.ipca_12m, 2),
                  CASE WHEN p.ipca_12m > v_teto_ipca THEN 'acima' ELSE 'dentro' END,
                  silver.numero_br(v_teto_ipca, 1),
                  CASE WHEN p.desacelerando THEN 'desacelerando' ELSE 'sem desacelerar' END, p.s_inflacao,
                  silver.numero_br(p.dolar_medio, 2),
                  CASE WHEN p.dolar_var_12m_pct < 0 THEN 'queda' WHEN p.dolar_var_12m_pct > 0 THEN 'alta' ELSE 'variação' END,
                  silver.numero_br(abs(p.dolar_var_12m_pct), 1),
                  CASE WHEN p.alerta THEN format(' e alta de mais de %s%% sobre o mês anterior', silver.numero_br(v_alerta_pct, 0)) ELSE '' END,
                  p.s_cambio),
           false, p.selic_ultima_data, p.dolar_ultimo_data, p.mes
      FROM pontos AS p;

    -- 5. gold.momento_atual (P7): janela movel ate o ultimo fechamento ------------
    SELECT max(data) INTO v_ref_cambio
      FROM silver.fato_indicador_macro WHERE indicador_id = 'dolar_venda' AND valor IS NOT NULL;
    SELECT max(data) INTO v_ref_juros
      FROM silver.fato_indicador_macro WHERE indicador_id = 'selic_meta' AND valor IS NOT NULL;
    SELECT max(data) INTO v_ref_inflacao
      FROM silver.fato_indicador_macro WHERE indicador_id = 'ipca_12m' AND valor IS NOT NULL;

    TRUNCATE gold.momento_atual;
    INSERT INTO gold.momento_atual
        (mes, janela_dias, ref_juros, ref_cambio, ref_inflacao,
         selic_meta, selic_meta_12m_antes, selic_var_12m_pp,
         dolar_ultimo, dolar_media_janela, dolar_media_janela_12m_antes, dolar_var_12m_pct,
         dolar_media_janela_anterior, dolar_var_janela_pct, alerta_cambio_curto_prazo,
         ipca_12m, ipca_12m_meses_antes, ipca_desacelerando,
         sinal_juros, sinal_inflacao, sinal_cambio, pontuacao, recomendacao, justificativa)
    WITH dolar AS (
        SELECT data, valor FROM silver.fato_indicador_macro WHERE indicador_id = 'dolar_venda' AND valor IS NOT NULL
    ),
    valores AS (
        SELECT
            (SELECT valor FROM silver.fato_indicador_macro
              WHERE indicador_id = 'selic_meta' AND data = v_ref_juros)                       AS selic_meta,
            (SELECT valor FROM silver.fato_indicador_macro
              WHERE indicador_id = 'selic_meta' AND valor IS NOT NULL
                AND data <= (v_ref_juros - interval '1 year')::date
              ORDER BY data DESC LIMIT 1)                                                     AS selic_12m,
            (SELECT valor FROM dolar WHERE data = v_ref_cambio)                               AS dolar_ultimo,
            (SELECT avg(valor) FROM dolar
              WHERE data >  v_ref_cambio - v_janela
                AND data <= v_ref_cambio)                                                     AS media_janela,
            (SELECT avg(valor) FROM dolar
              WHERE data >  (v_ref_cambio - interval '1 year')::date - v_janela
                AND data <= (v_ref_cambio - interval '1 year')::date)                         AS media_12m,
            (SELECT avg(valor) FROM dolar
              WHERE data >  v_ref_cambio - 2 * v_janela
                AND data <= v_ref_cambio - v_janela)                                          AS media_anterior,
            (SELECT valor FROM silver.fato_indicador_macro
              WHERE indicador_id = 'ipca_12m' AND data = v_ref_inflacao)                      AS ipca_12m,
            (SELECT valor FROM silver.fato_indicador_macro
              WHERE indicador_id = 'ipca_12m'
                AND data = (v_ref_inflacao - make_interval(months => v_meses_ipca))::date)    AS ipca_antes
    ),
    calc AS (
        SELECT v.*,
               v.selic_meta - v.selic_12m                                         AS selic_var,
               round((v.media_janela / nullif(v.media_12m, 0) - 1) * 100, 2)      AS var_12m,
               round((v.media_janela / nullif(v.media_anterior, 0) - 1) * 100, 2) AS var_janela,
               v.ipca_12m < v.ipca_antes                                          AS desacelerando
          FROM valores AS v
    ),
    sinais AS (
        SELECT c.*,
               coalesce(c.var_janela > v_alerta_pct, false)                                     AS alerta,
               gold.sinal_juros(c.selic_var, v_selic_pp)                                        AS s_juros,
               gold.sinal_inflacao(c.ipca_12m, c.desacelerando, v_teto_ipca)                    AS s_inflacao,
               gold.sinal_cambio(c.var_12m, coalesce(c.var_janela > v_alerta_pct, false), v_dolar_pct) AS s_cambio
          FROM calc AS c
    )
    SELECT date_trunc('month', v_ref_cambio)::date, v_janela, v_ref_juros, v_ref_cambio, v_ref_inflacao,
           s.selic_meta, s.selic_12m, s.selic_var,
           s.dolar_ultimo, round(s.media_janela, 4), round(s.media_12m, 4), s.var_12m,
           round(s.media_anterior, 4), s.var_janela, s.alerta,
           s.ipca_12m, s.ipca_antes, s.desacelerando,
           s.s_juros, s.s_inflacao, s.s_cambio,
           gold.pontos_sinal(s.s_juros) + gold.pontos_sinal(s.s_inflacao) + gold.pontos_sinal(s.s_cambio),
           gold.recomendacao(gold.pontos_sinal(s.s_juros) + gold.pontos_sinal(s.s_inflacao) + gold.pontos_sinal(s.s_cambio)),
           format('Juros: meta da Selic de %s%% a.a. em %s, %s de %s p.p. em 12 meses (%s). '
                  'Inflação: IPCA de %s%% em 12 meses até %s, %s do teto de %s%% e %s (%s). '
                  'Câmbio: dólar médio de R$ %s nos %s dias até %s (último fechamento R$ %s), %s de %s%% em 12 meses '
                  'e %s de %s%% sobre os %s dias anteriores%s (%s).',
                  silver.numero_br(s.selic_meta, 2), to_char(v_ref_juros, 'DD/MM/YYYY'),
                  CASE WHEN s.selic_var < 0 THEN 'queda' WHEN s.selic_var > 0 THEN 'alta' ELSE 'variação' END,
                  silver.numero_br(abs(s.selic_var), 2), s.s_juros,
                  silver.numero_br(s.ipca_12m, 2), to_char(v_ref_inflacao, 'MM/YYYY'),
                  CASE WHEN s.ipca_12m > v_teto_ipca THEN 'acima' ELSE 'dentro' END,
                  silver.numero_br(v_teto_ipca, 1),
                  CASE WHEN s.desacelerando THEN 'desacelerando' ELSE 'sem desacelerar' END, s.s_inflacao,
                  silver.numero_br(s.media_janela, 2), v_janela, to_char(v_ref_cambio, 'DD/MM/YYYY'),
                  silver.numero_br(s.dolar_ultimo, 2),
                  CASE WHEN s.var_12m < 0 THEN 'queda' WHEN s.var_12m > 0 THEN 'alta' ELSE 'variação' END,
                  silver.numero_br(abs(s.var_12m), 1),
                  CASE WHEN s.var_janela < 0 THEN 'queda' WHEN s.var_janela > 0 THEN 'alta' ELSE 'variação' END,
                  silver.numero_br(abs(s.var_janela), 1), v_janela,
                  CASE WHEN s.alerta THEN ' — alerta de alta de curto prazo' ELSE '' END,
                  s.s_cambio)
      FROM sinais AS s;
    GET DIAGNOSTICS v_linhas = ROW_COUNT;
    tabela := 'gold.momento_atual'; linhas_gravadas := v_linhas; RETURN NEXT;

    -- o mes do momento atual entra no historico, marcado como parcial
    INSERT INTO gold.momento_expansao
        (mes, sinal_juros, sinal_inflacao, sinal_cambio, pontuacao, recomendacao, justificativa,
         mes_parcial, ref_juros, ref_cambio, ref_inflacao)
    SELECT a.mes, a.sinal_juros, a.sinal_inflacao, a.sinal_cambio, a.pontuacao, a.recomendacao, a.justificativa,
           a.mes = date_trunc('month', current_date)::date, a.ref_juros, a.ref_cambio, a.ref_inflacao
      FROM gold.momento_atual AS a
     WHERE NOT EXISTS (SELECT 1 FROM gold.momento_expansao AS m WHERE m.mes = a.mes);

    SELECT count(*) INTO v_linhas FROM gold.momento_expansao;
    tabela := 'gold.momento_expansao'; linhas_gravadas := v_linhas; RETURN NEXT;

    DROP TABLE IF EXISTS tmp_pop, tmp_universo, tmp_valor, tmp_nota, tmp_referencia;
END
$$;

COMMENT ON FUNCTION gold.atualizar(integer) IS
    'Recalcula a gold a partir da silver (caminho unico dos cenarios A e B).';
