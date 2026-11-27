-- =============================================================================
-- RADAR DE EXPANSAO - BAIRROS SOB DEMANDA · 01_estrutura.sql
-- =============================================================================
-- Schema NOVO "bairros", isolado das camadas bronze/silver/gold (nada existente
-- e alterado). Guarda a base nacional de academias (CNPJ), a fila de pedidos e
-- o resultado por municipio (ranking de bairros, setores do mapa, academias).
-- Rodar como etl_radar. Idempotente. Remover: DROP SCHEMA bairros CASCADE.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS bairros;
COMMENT ON SCHEMA bairros IS 'Bairros sob demanda (estudo exploratorio): base de academias, fila e resultados por municipio.';

-- Base nacional de academias ativas (CNPJ da Receita, carga mensal) -----------
-- LGPD: sem razao social, nome fantasia, telefone, e-mail ou socios.
CREATE TABLE IF NOT EXISTS bairros.academia (
    cnpj                  char(14)     PRIMARY KEY,
    cnae_principal        char(7)      NOT NULL,
    academia_principal    boolean      NOT NULL,   -- 93.13-1 como atividade principal (entra no ranking)
    academia_secundaria   boolean      NOT NULL,   -- 93.13-1 so como secundaria
    ensino_esportes_8591  boolean      NOT NULL,   -- 85.91-1 sem 93.13-1 (fora da contagem)
    situacao              char(2)      NOT NULL,   -- 02 = ativa
    data_inicio           varchar(8),              -- AAAAMMDD, como vem da Receita
    tipo_logradouro       text,
    logradouro            text,
    numero                text,
    bairro                text,                    -- texto livre do cadastro
    cep                   varchar(8),
    uf                    char(2)      NOT NULL,
    municipio_receita     varchar(4)   NOT NULL,   -- codigo da Receita
    cod_municipio         integer,                 -- codigo IBGE (de-para pelo nome; nulo se nao casou)
    data_referencia       varchar(7)   NOT NULL    -- mes da base da Receita (AAAA-MM)
);
CREATE INDEX IF NOT EXISTS academia_cod_municipio_idx ON bairros.academia (cod_municipio);
COMMENT ON TABLE bairros.academia IS 'Academias ativas do Brasil (CNPJ, CNAE 93.13-1 e 85.91-1), endereco fiscal, sem dado pessoal.';

-- Fila de pedidos (escrita so pela funcao gold.pedir_bairros e pelo worker) ---
CREATE TABLE IF NOT EXISTS bairros.pedido (
    id             bigserial     PRIMARY KEY,
    cod_municipio  integer       NOT NULL,
    status         text          NOT NULL DEFAULT 'pendente'
                                 CHECK (status IN ('pendente', 'processando', 'pronto', 'erro')),
    pedido_em      timestamptz   NOT NULL DEFAULT now(),
    inicio         timestamptz,
    fim            timestamptz,
    duracao_s      numeric(8,1),
    erro_resumo    text
);
-- no maximo um pedido aberto por municipio (evita duplicar na fila)
CREATE UNIQUE INDEX IF NOT EXISTS pedido_aberto_por_municipio
    ON bairros.pedido (cod_municipio) WHERE status IN ('pendente', 'processando');
CREATE INDEX IF NOT EXISTS pedido_status_idx ON bairros.pedido (status, pedido_em);

-- Resumo de cada municipio processado (1 linha; substituida a cada execucao) --
CREATE TABLE IF NOT EXISTS bairros.resumo (
    cod_municipio             integer      PRIMARY KEY,
    municipio_nome            text         NOT NULL,
    uf_sigla                  char(2)      NOT NULL,
    processado_em             timestamptz  NOT NULL DEFAULT now(),
    duracao_s                 numeric(8,1),
    pop_oficial               integer,              -- Censo 2022 (SIDRA 4714)
    pop_setores               integer,              -- soma dos setores (deve ser igual)
    pop_rateada               integer,              -- soma dos bairros populares
    concorrencia              text         NOT NULL CHECK (concorrencia IN ('ok', 'pendente')),
    data_base_cnpj            varchar(7),
    academias_base            integer,              -- ativas 93.13-1 principal no municipio
    academias_geocodificadas  integer,
    niveis_geocod             jsonb,
    consultas_api_cep         integer,
    centro_lat                double precision,
    centro_lon                double precision,
    centro_origem             text,
    bairros_ibge              integer,
    bairros_ibge_ranking      integer,
    bairros_populares         integer,
    bairros_populares_ranking integer,
    pesos                     jsonb,
    parametros                jsonb                 -- raio, populacao minima, versao
);

-- Ranking por municipio x escala x unidade ------------------------------------
CREATE TABLE IF NOT EXISTS bairros.ranking (
    cod_municipio      integer           NOT NULL,
    escala             text              NOT NULL CHECK (escala IN ('ibge', 'popular')),
    unidade_id         text              NOT NULL,   -- codigo do bairro IBGE ou nome normalizado da localidade
    unidade_nome       text              NOT NULL,
    elegivel           boolean           NOT NULL,   -- populacao >= minimo e nao e area rural/sem localidade
    posicao            smallint,                     -- so para elegiveis
    setores            integer,
    populacao          numeric(12,1),
    pop_20_59          numeric(12,1),
    dom_ocupados       numeric(12,1),
    renda_media_resp   numeric(10,2),
    area_km2           numeric(12,4),
    densidade_hab_km2  numeric(12,2),
    massa_renda_km2    numeric(16,2),
    acad_unidade       integer,
    pop_raio           integer,
    acad_raio          integer,
    acad_raio_10k      numeric(8,3),
    dist_centro_km     numeric(8,3),
    nota_mercado       numeric(5,1),
    nota_renda         numeric(5,1),
    nota_espaco        numeric(5,1),
    nota_densidade     numeric(5,1),
    nota_final         numeric(5,1),
    frase              text,
    concorrencia       text              NOT NULL CHECK (concorrencia IN ('ok', 'pendente')),
    lat                double precision,
    lon                double precision,
    geojson            jsonb,                        -- contorno simplificado (bairros IBGE); nulo nos populares
    processado_em      timestamptz       NOT NULL DEFAULT now(),
    PRIMARY KEY (cod_municipio, escala, unidade_id)
);

-- Setores do municipio para o mapa (renda e populacao) -------------------------
CREATE TABLE IF NOT EXISTS bairros.setor (
    cod_municipio     integer       NOT NULL,
    cd_setor          varchar(15)   PRIMARY KEY,
    bairro_ibge       text,
    urbano            boolean       NOT NULL,
    populacao         integer,
    pop_20_59         integer,
    renda_media_resp  numeric(10,2),
    renda_imputada    boolean       NOT NULL,
    geojson           jsonb                         -- contorno simplificado
);
CREATE INDEX IF NOT EXISTS setor_cod_municipio_idx ON bairros.setor (cod_municipio);

-- Academias geocodificadas do municipio (pontos do mapa) -----------------------
CREATE TABLE IF NOT EXISTS bairros.academia_ponto (
    cod_municipio     integer           NOT NULL,
    cnpj              char(14)          NOT NULL,
    lat               double precision  NOT NULL,
    lon               double precision  NOT NULL,
    nivel_geocod      text              NOT NULL,
    cd_setor          varchar(15),
    localidade        text,
    PRIMARY KEY (cod_municipio, cnpj)
);

-- RLS ligado sem politica: so o dono (etl_radar) le e escreve; a API so ve as views da gold
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['academia', 'pedido', 'resumo', 'ranking', 'setor', 'academia_ponto'] LOOP
        EXECUTE format('ALTER TABLE bairros.%I ENABLE ROW LEVEL SECURITY', t);
    END LOOP;
END
$$;
REVOKE ALL ON SCHEMA bairros FROM PUBLIC;
