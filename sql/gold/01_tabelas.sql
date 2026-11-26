-- =============================================================================
-- RADAR DE EXPANSAO - ETAPA 5: CAMADA GOLD · 01_tabelas.sql
-- =============================================================================
-- Tabelas de consumo. Cada uma responde a perguntas do prd.md (P1 a P8),
-- anotadas no comentario da tabela. A gold e recalculada inteira por
-- gold.atualizar() (02_atualizar_gold.sql).
-- Rodar como etl_radar (python -m src.transformacao.criar_estrutura). Idempotente.
-- =============================================================================

-- P1, P3, P4: uma linha por municipio com os indicadores do "fator onde" -------
CREATE TABLE IF NOT EXISTS gold.indicadores_municipio (
    municipio_id              integer       PRIMARY KEY,
    municipio_nome            text          NOT NULL,
    uf_sigla                  char(2)       NOT NULL,
    regiao_sigla              char(2)       NOT NULL,
    regiao_imediata_id        integer,
    regiao_imediata_nome      text,
    populacao                 integer,          -- estimativa mais recente (IBGE 6579)
    populacao_ano             smallint,
    populacao_censo_2022      integer,          -- IBGE 4714
    crescimento_pop_aa        numeric(7,4),     -- CAGR Censo 2022 -> populacao_ano (fracao: 0.0123 = 1,23% a.a.)
    pib_mil_reais             numeric,          -- PIB do ultimo ano disponivel (IBGE 5938)
    pib_ano                   smallint,
    pib_per_capita            numeric(12,2),    -- R$ por habitante no pib_ano
    pib_per_capita_tendencia  numeric(7,4),     -- CAGR do PIB per capita: 1o -> ultimo ano da janela de 5 anos
    tendencia_ano_inicial     smallint,         -- 1o ano da janela (ex.: 2019)
    renda_dom_per_capita      numeric(10,2),    -- R$/mes, Censo 2022 (IBGE 10295)
    renda_ano                 smallint,
    academias_qtd             integer,          -- empresas CNAE 93.13-1 (IBGE 9418); "-" da fonte = 0
    academias_ano             smallint,
    academias_por_10mil_hab   numeric(8,3),     -- academias / populacao do mesmo ano x 10.000
    salario_medio             numeric(10,2),    -- R$/mes (IBGE 9509)
    salario_ano               smallint,
    atualizado_em             timestamptz   NOT NULL DEFAULT now()
);
COMMENT ON TABLE gold.indicadores_municipio IS
    'P1, P3, P4: indicadores de cada municipio (populacao, crescimento, PIB, PIB per capita, renda, academias, salario).';

-- P8: criterios, pesos, sentido e fonte (metodologia do ranking) ----------------
CREATE TABLE IF NOT EXISTS gold.ranking_criterio (
    criterio      text          PRIMARY KEY,   -- a nota fica em ranking_expansao.nota_<criterio>
    grupo         text          NOT NULL,      -- criterio do prd (riqueza agrupa nivel + tendencia)
    descricao     text          NOT NULL,
    fonte         text          NOT NULL,
    peso          numeric(4,3)  NOT NULL CHECK (peso > 0 AND peso <= 1),
    sentido       text          NOT NULL CHECK (sentido IN ('maior_melhor', 'menor_melhor')),
    ordem         smallint      NOT NULL,
    versao_pesos  text          NOT NULL
);
COMMENT ON TABLE gold.ranking_criterio IS
    'P8: criterios e pesos do ranking (prd.md, secao 4), para explicar o calculo no dashboard.';

INSERT INTO gold.ranking_criterio (criterio, grupo, descricao, fonte, peso, sentido, ordem, versao_pesos) VALUES
    ('mercado', 'mercado', 'Tamanho de mercado: populacao estimada mais recente',
     'IBGE 6579', 0.250, 'maior_melhor', 1, 'prd-v0.3'),
    ('poder_compra', 'poder_compra', 'Poder de compra: renda domiciliar per capita media (Censo 2022)',
     'IBGE 10295', 0.250, 'maior_melhor', 2, 'prd-v0.3'),
    ('espaco_competitivo', 'espaco_competitivo',
     'Espaco competitivo: academias (CNAE 93.13-1) por 10 mil habitantes, limitado aos percentis 5% e 95%',
     'IBGE 9418 / 6579', 0.200, 'menor_melhor', 3, 'prd-v0.3'),
    ('crescimento', 'crescimento', 'Crescimento: taxa anual da populacao desde o Censo 2022',
     'IBGE 4714 / 6579', 0.150, 'maior_melhor', 4, 'prd-v0.3'),
    ('riqueza_nivel', 'riqueza', 'Riqueza local (nivel): PIB per capita do ultimo ano',
     'IBGE 5938 / 6579', 0.050, 'maior_melhor', 5, 'prd-v0.3'),
    ('riqueza_tendencia', 'riqueza', 'Riqueza local (tendencia): taxa media anual (CAGR) do PIB per capita em 5 anos',
     'IBGE 5938 / 6579', 0.050, 'maior_melhor', 6, 'prd-v0.3'),
    ('mercado_formal', 'mercado_formal', 'Mercado formal: salario medio mensal',
     'IBGE 9509', 0.050, 'maior_melhor', 7, 'prd-v0.3')
ON CONFLICT (criterio) DO UPDATE SET
    grupo = EXCLUDED.grupo, descricao = EXCLUDED.descricao, fonte = EXCLUDED.fonte, peso = EXCLUDED.peso,
    sentido = EXCLUDED.sentido, ordem = EXCLUDED.ordem, versao_pesos = EXCLUDED.versao_pesos;

-- P2, P5, P8: ranking do cliente ----------------------------------------------
CREATE TABLE IF NOT EXISTS gold.ranking_expansao (
    municipio_id              integer       PRIMARY KEY,
    municipio_nome            text          NOT NULL,
    uf_sigla                  char(2)       NOT NULL,
    regiao_sigla              char(2)       NOT NULL,
    regiao_imediata_id        integer       NOT NULL,
    regiao_imediata_nome      text          NOT NULL,
    populacao                 integer       NOT NULL,
    nota_mercado              numeric(5,2),
    nota_poder_compra         numeric(5,2),
    nota_espaco_competitivo   numeric(5,2),
    nota_crescimento          numeric(5,2),
    nota_riqueza_nivel        numeric(5,2),
    nota_riqueza_tendencia    numeric(5,2),
    nota_riqueza              numeric(5,2),     -- media ponderada de nivel e tendencia (visao do criterio do prd)
    nota_mercado_formal       numeric(5,2),
    nota_final                numeric(5,2)  NOT NULL,
    posicao_brasil            integer       NOT NULL,
    posicao_regiao            integer       NOT NULL,
    posicao_uf                integer       NOT NULL,
    dados_incompletos         boolean       NOT NULL DEFAULT false,  -- faltou criterio: peso redistribuido
    criterios_ausentes        text[],
    peso_considerado          numeric(4,3)  NOT NULL,                -- soma dos pesos disponiveis (1.000 = completo)
    verificar_concorrencia    boolean       NOT NULL DEFAULT false,  -- zero academias registradas: checar no local
    recomendado_top5          boolean       NOT NULL DEFAULT false,  -- lista das 5 unidades recomendadas (P8)
    ordem_recomendacao        smallint,                              -- 1 a 5
    versao_pesos              text          NOT NULL,
    calculado_em              timestamptz   NOT NULL DEFAULT now()
);
COMMENT ON TABLE gold.ranking_expansao IS
    'P2, P5, P8: ranking dos municipios com 50 mil habitantes ou mais, notas por criterio, nota final e as 5 recomendadas.';

-- P6: evolucao mensal do cenario economico ------------------------------------
CREATE TABLE IF NOT EXISTS gold.contexto_macro (
    mes                date          PRIMARY KEY,  -- 1o dia do mes
    mes_parcial        boolean       NOT NULL DEFAULT false,  -- mes corrente, ainda em andamento
    selic_meta         numeric(6,2),               -- % a.a., meta vigente no ultimo dia com dado no mes (BCB 432)
    selic_var_12m_pp   numeric(6,2),               -- pontos percentuais contra 12 meses antes
    dolar_medio        numeric(8,4),               -- R$, media dos dias uteis do mes (BCB 10813)
    dolar_var_12m_pct  numeric(7,2),               -- % contra 12 meses antes
    ipca_mensal        numeric(6,2),               -- % (IBGE 7060/63)
    ipca_12m           numeric(6,2),               -- % (IBGE 7060/2265)
    atualizado_em      timestamptz   NOT NULL DEFAULT now()
);
COMMENT ON TABLE gold.contexto_macro IS
    'P6: Selic, dolar e IPCA mes a mes, com variacoes em 12 meses.';

-- P7: "fator quando" (uma linha por mes com os tres sinais) --------------------
CREATE TABLE IF NOT EXISTS gold.momento_expansao (
    mes             date          PRIMARY KEY,
    sinal_juros     text          NOT NULL CHECK (sinal_juros IN ('verde', 'amarelo', 'vermelho')),
    sinal_inflacao  text          NOT NULL CHECK (sinal_inflacao IN ('verde', 'amarelo', 'vermelho')),
    sinal_cambio    text          NOT NULL CHECK (sinal_cambio IN ('verde', 'amarelo', 'vermelho')),
    pontuacao       smallint      NOT NULL,       -- verde = +1, amarelo = 0, vermelho = -1
    recomendacao    text          NOT NULL CHECK (recomendacao IN ('Expandir agora', 'Expandir com cautela', 'Esperar')),
    justificativa   text          NOT NULL,       -- frase pronta para o dashboard
    atualizado_em   timestamptz   NOT NULL DEFAULT now()
);
COMMENT ON TABLE gold.momento_expansao IS
    'P7: semaforo de juros, inflacao e cambio e a recomendacao expandir agora / com cautela / esperar.';
