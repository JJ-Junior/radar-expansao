-- =============================================================================
-- RADAR DE EXPANSAO - ETAPA 4: CAMADA SILVER · 01_dimensoes.sql
-- =============================================================================
-- Dimensoes do modelo estrela: regiao, UF, municipio, calendario e o catalogo
-- de indicadores (que liga cada fato a sua origem na API).
-- Rodar como etl_radar (python -m src.transformacao.criar_estrutura). Idempotente.
-- =============================================================================

CREATE TABLE IF NOT EXISTS silver.dim_regiao (
    regiao_id      smallint     PRIMARY KEY,          -- 1 a 5 (codigo IBGE)
    regiao_sigla   char(2)      NOT NULL UNIQUE,      -- N, NE, SE, S, CO
    regiao_nome    text         NOT NULL,
    bronze_id      bigint       NOT NULL,             -- bronze.api_resposta.resposta_id
    atualizado_em  timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS silver.dim_uf (
    uf_id          smallint     PRIMARY KEY,          -- 11 a 53 (codigo IBGE)
    uf_sigla       char(2)      NOT NULL UNIQUE,
    uf_nome        text         NOT NULL,
    regiao_id      smallint     NOT NULL REFERENCES silver.dim_regiao,
    bronze_id      bigint       NOT NULL,
    atualizado_em  timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS silver.dim_municipio (
    municipio_id               integer      PRIMARY KEY,   -- 7 digitos (codigo IBGE)
    municipio_nome             text         NOT NULL,
    uf_id                      smallint     NOT NULL REFERENCES silver.dim_uf,
    regiao_id                  smallint     NOT NULL REFERENCES silver.dim_regiao,
    regiao_intermediaria_id    integer,
    regiao_intermediaria_nome  text,
    regiao_imediata_id         integer,                    -- usada pelo prd (mercado de influencia)
    regiao_imediata_nome       text,
    mesorregiao_id             integer,
    mesorregiao_nome           text,
    microrregiao_id            integer,                    -- pode ser nulo (municipios recentes)
    microrregiao_nome          text,
    bronze_id                  bigint       NOT NULL,
    atualizado_em              timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_dim_municipio_uf ON silver.dim_municipio (uf_id);
CREATE INDEX IF NOT EXISTS ix_dim_municipio_imediata ON silver.dim_municipio (regiao_imediata_id);

-- Centroide do municipio (API de Malhas v4 do IBGE), base do simulador de regiao.
-- Colunas acrescentadas depois da primeira versao da tabela (bancos ja existentes).
ALTER TABLE silver.dim_municipio
    ADD COLUMN IF NOT EXISTS latitude              numeric(9,6),   -- graus decimais (sul negativo)
    ADD COLUMN IF NOT EXISTS longitude             numeric(9,6),   -- graus decimais (oeste negativo)
    ADD COLUMN IF NOT EXISTS coordenada_bronze_id  bigint;         -- resposta da malha na bronze

-- Calendario gerado (nao vem da bronze): 2000-01-01 a 2030-12-31
CREATE TABLE IF NOT EXISTS silver.dim_calendario (
    data              date      PRIMARY KEY,
    ano               smallint  NOT NULL,
    trimestre         smallint  NOT NULL,
    mes               smallint  NOT NULL,
    ano_mes           integer   NOT NULL,             -- 202610
    nome_mes          text      NOT NULL,
    dia_semana        smallint  NOT NULL,             -- 1 = segunda ... 7 = domingo
    eh_fim_de_semana  boolean   NOT NULL
);

INSERT INTO silver.dim_calendario
SELECT d::date,
       extract(year FROM d)::smallint,
       extract(quarter FROM d)::smallint,
       extract(month FROM d)::smallint,
       (extract(year FROM d) * 100 + extract(month FROM d))::integer,
       (ARRAY['janeiro','fevereiro','marco','abril','maio','junho','julho',
              'agosto','setembro','outubro','novembro','dezembro'])[extract(month FROM d)::int],
       extract(isodow FROM d)::smallint,
       extract(isodow FROM d) IN (6, 7)
FROM generate_series(date '2000-01-01', date '2030-12-31', interval '1 day') AS d
ON CONFLICT (data) DO NOTHING;

-- Catalogo dos indicadores (nao vem da bronze): liga cada fato a sua origem na API
CREATE TABLE IF NOT EXISTS silver.dim_indicador (
    indicador_id    text      PRIMARY KEY,
    indicador_nome  text      NOT NULL,
    fonte           text      NOT NULL CHECK (fonte IN ('IBGE', 'BCB')),
    agregado        integer,                          -- IBGE: tabela do SIDRA
    variavel        integer,                          -- IBGE: variavel
    serie_bcb       integer,                          -- BCB: codigo da serie no SGS
    codigo_origem   text      NOT NULL,               -- forma legivel, ex.: '9418/2585 · 12762[117856]'
    unidade         text      NOT NULL,
    periodicidade   text      NOT NULL CHECK (periodicidade IN ('anual', 'decenal', 'mensal', 'diaria')),
    nivel           text      NOT NULL CHECK (nivel IN ('municipal', 'macro')),
    descricao       text,
    UNIQUE (agregado, variavel),
    UNIQUE (serie_bcb)
);

INSERT INTO silver.dim_indicador
    (indicador_id, indicador_nome, fonte, agregado, variavel, serie_bcb, codigo_origem,
     unidade, periodicidade, nivel, descricao)
VALUES
    ('populacao_estimada', 'Populacao residente estimada', 'IBGE', 6579, 9324, NULL, '6579/9324',
     'pessoas', 'anual', 'municipal', 'Estimativa anual da populacao (sem 2007, 2010, 2022 e 2023)'),
    ('populacao_censo', 'Populacao residente (Censo 2022)', 'IBGE', 4714, 93, NULL, '4714/93',
     'pessoas', 'decenal', 'municipal', 'Populacao recenseada em 2022'),
    ('area_km2', 'Area territorial', 'IBGE', 4714, 6318, NULL, '4714/6318',
     'km2', 'decenal', 'municipal', 'Area da unidade territorial (Censo 2022)'),
    ('densidade_demografica', 'Densidade demografica', 'IBGE', 4714, 614, NULL, '4714/614',
     'hab/km2', 'decenal', 'municipal', 'Habitantes por km2 (Censo 2022)'),
    ('pib', 'PIB a precos correntes', 'IBGE', 5938, 37, NULL, '5938/37',
     'mil R$', 'anual', 'municipal', 'Produto Interno Bruto dos Municipios'),
    ('vab_total', 'Valor adicionado bruto total', 'IBGE', 5938, 498, NULL, '5938/498',
     'mil R$', 'anual', 'municipal', 'Componente do PIB; disponivel ate 2021'),
    ('vab_agropecuaria', 'Valor adicionado bruto da agropecuaria', 'IBGE', 5938, 513, NULL, '5938/513',
     'mil R$', 'anual', 'municipal', 'Componente do PIB; disponivel ate 2021'),
    ('vab_industria', 'Valor adicionado bruto da industria', 'IBGE', 5938, 517, NULL, '5938/517',
     'mil R$', 'anual', 'municipal', 'Componente do PIB; disponivel ate 2021'),
    ('vab_servicos', 'Valor adicionado bruto dos servicos (exceto administracao publica)', 'IBGE', 5938, 6575, NULL, '5938/6575',
     'mil R$', 'anual', 'municipal', 'Componente do PIB; disponivel ate 2021'),
    ('vab_administracao_publica', 'Valor adicionado bruto da administracao publica', 'IBGE', 5938, 525, NULL, '5938/525',
     'mil R$', 'anual', 'municipal', 'Componente do PIB; disponivel ate 2021'),
    ('impostos_liquidos', 'Impostos liquidos de subsidios sobre produtos', 'IBGE', 5938, 543, NULL, '5938/543',
     'mil R$', 'anual', 'municipal', 'Componente do PIB; disponivel ate 2021'),
    ('renda_dom_per_capita', 'Rendimento domiciliar per capita medio', 'IBGE', 10295, 13431, NULL,
     '10295/13431 · 2[6794]|86[95251]|58[95253]', 'R$', 'decenal', 'municipal', 'Censo 2022, totais de sexo, cor/raca e idade'),
    ('academias_qtd', 'Empresas de condicionamento fisico (CNAE 93.13-1)', 'IBGE', 9418, 2585, NULL,
     '9418/2585 · 12762[117856]', 'unidades', 'anual', 'municipal', 'Cadastro Central de Empresas'),
    ('salario_medio', 'Salario medio mensal', 'IBGE', 9509, 10143, NULL, '9509/10143',
     'R$', 'anual', 'municipal', 'Cadastro Central de Empresas'),
    ('ipca_mensal', 'IPCA - variacao mensal', 'IBGE', 7060, 63, NULL, '7060/63 · 315[7169]',
     '%', 'mensal', 'macro', 'Indice geral'),
    ('ipca_12m', 'IPCA - acumulado em 12 meses', 'IBGE', 7060, 2265, NULL, '7060/2265 · 315[7169]',
     '%', 'mensal', 'macro', 'Indice geral'),
    ('selic_meta', 'Meta da taxa Selic', 'BCB', NULL, NULL, 432, 'SGS 432',
     '% a.a.', 'diaria', 'macro', 'Datas futuras (ate o proximo Copom) ficam so na bronze'),
    ('dolar_venda', 'Dolar comercial - venda', 'BCB', NULL, NULL, 10813, 'SGS 10813',
     'R$', 'diaria', 'macro', 'Dias uteis'),
    ('ipca_mensal_bcb', 'IPCA - variacao mensal (BCB)', 'BCB', NULL, NULL, 433, 'SGS 433',
     '%', 'mensal', 'macro', 'Conferencia contra o IPCA do IBGE (7060/63)')
ON CONFLICT (indicador_id) DO UPDATE SET
    indicador_nome = EXCLUDED.indicador_nome, fonte = EXCLUDED.fonte,
    agregado = EXCLUDED.agregado, variavel = EXCLUDED.variavel, serie_bcb = EXCLUDED.serie_bcb,
    codigo_origem = EXCLUDED.codigo_origem, unidade = EXCLUDED.unidade,
    periodicidade = EXCLUDED.periodicidade, nivel = EXCLUDED.nivel, descricao = EXCLUDED.descricao;
