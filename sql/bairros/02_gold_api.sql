-- =============================================================================
-- RADAR DE EXPANSAO - BAIRROS SOB DEMANDA · 02_gold_api.sql
-- =============================================================================
-- O que a API REST (papel web_leitor) enxerga dos bairros: views SO LEITURA em
-- gold e UMA funcao de escrita, gold.pedir_bairros, que poe a cidade na fila
-- com validacao e limites. Nada de CNPJ, endereco ou erro interno na API.
-- Rodar como etl_radar, depois de 01_estrutura.sql. Idempotente.
-- Remover: DROP VIEW gold.bairro_ranking, gold.bairro_resumo, gold.bairro_setor,
--          gold.bairro_academia, gold.bairro_pedido;
--          DROP FUNCTION gold.pedir_bairros(integer);
-- =============================================================================

-- Parametros da fila (mudar aqui e rodar de novo) ------------------------------
--   max_pendentes      = 20   pedidos aguardando ao mesmo tempo
--   max_pedidos_hora   = 30   pedidos novos por hora (todas as cidades)
--   validade_dias      = 35   resultado pronto vale ate a proxima base mensal do CNPJ
--   tempo_padrao_s     = 180  estimativa por pedido enquanto nao ha historico

CREATE OR REPLACE VIEW gold.bairro_ranking AS
SELECT cod_municipio, escala, unidade_id, unidade_nome, elegivel, posicao, setores,
       populacao, pop_20_59, renda_media_resp, area_km2, densidade_hab_km2, massa_renda_km2,
       acad_unidade, pop_raio, acad_raio, acad_raio_10k, dist_centro_km,
       nota_mercado, nota_renda, nota_espaco, nota_densidade, nota_final, frase, concorrencia,
       lat, lon, geojson, processado_em
  FROM bairros.ranking;
COMMENT ON VIEW gold.bairro_ranking IS 'Ranking de bairros por municipio nas escalas ibge e popular (so leitura).';

CREATE OR REPLACE VIEW gold.bairro_resumo AS
SELECT cod_municipio, municipio_nome, uf_sigla, processado_em, duracao_s, pop_oficial, pop_setores, pop_rateada,
       concorrencia, data_base_cnpj, academias_base, academias_geocodificadas, niveis_geocod,
       centro_lat, centro_lon, centro_origem, bairros_ibge, bairros_ibge_ranking,
       bairros_populares, bairros_populares_ranking, pesos, parametros
  FROM bairros.resumo;
COMMENT ON VIEW gold.bairro_resumo IS 'Resumo e conferencias de cada municipio processado (so leitura).';

CREATE OR REPLACE VIEW gold.bairro_setor AS
SELECT cod_municipio, cd_setor, bairro_ibge, urbano, populacao, pop_20_59, renda_media_resp, renda_imputada, geojson
  FROM bairros.setor;
COMMENT ON VIEW gold.bairro_setor IS 'Setores censitarios do municipio para o mapa (renda e populacao; so leitura).';

-- pontos sem CNPJ (o mapa so precisa da posicao)
CREATE OR REPLACE VIEW gold.bairro_academia AS
SELECT cod_municipio, round(lat::numeric, 5)::double precision AS lat, round(lon::numeric, 5)::double precision AS lon,
       nivel_geocod, localidade
  FROM bairros.academia_ponto;
COMMENT ON VIEW gold.bairro_academia IS 'Academias geocodificadas (CNAE 93.13-1 principal), sem CNPJ (so leitura).';

-- fila: ultimo pedido de cada municipio, com posicao e estimativa (sem erro interno)
CREATE OR REPLACE VIEW gold.bairro_pedido AS
WITH media AS (
    SELECT coalesce(avg(duracao_s), 180) AS seg
      FROM (SELECT duracao_s FROM bairros.pedido WHERE status = 'pronto' ORDER BY fim DESC LIMIT 20) u
), fila AS (
    SELECT id, row_number() OVER (ORDER BY pedido_em, id) AS posicao
      FROM bairros.pedido WHERE status = 'pendente'
), ultimo AS (
    SELECT DISTINCT ON (cod_municipio) *
      FROM bairros.pedido ORDER BY cod_municipio, pedido_em DESC, id DESC
)
SELECT u.id, u.cod_municipio, u.status, u.pedido_em, u.inicio, u.fim, u.duracao_s,
       f.posicao AS posicao_fila,
       CASE WHEN u.status = 'pendente'
            THEN round((f.posicao + (SELECT count(*) FROM bairros.pedido WHERE status = 'processando')) * m.seg)
            WHEN u.status = 'processando'
            THEN greatest(round(m.seg - extract(epoch FROM now() - u.inicio)), 10)
       END::integer AS estimativa_s
  FROM ultimo u
  LEFT JOIN fila f ON f.id = u.id
  CROSS JOIN media m;
COMMENT ON VIEW gold.bairro_pedido IS 'Situacao do ultimo pedido de cada municipio, posicao na fila e tempo estimado (so leitura).';

-- Unica escrita exposta pela API ----------------------------------------------
-- Devolve: status = pronto | pendente | processando | invalido | fila_cheia | limite_hora
CREATE OR REPLACE FUNCTION gold.pedir_bairros(cod_municipio integer)
RETURNS TABLE (status text, pedido_id bigint, posicao_fila integer, estimativa_s integer, mensagem text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
#variable_conflict use_column
DECLARE
    max_pendentes    constant integer  := 20;
    max_pedidos_hora constant integer  := 30;
    validade         constant interval := interval '35 days';
    v_cod            integer := pedir_bairros.cod_municipio;
    v_id             bigint;
BEGIN
    IF v_cod IS NULL OR NOT EXISTS (SELECT 1 FROM silver.dim_municipio d WHERE d.municipio_id = v_cod) THEN
        RETURN QUERY SELECT 'invalido'::text, NULL::bigint, NULL::integer, NULL::integer,
                            'codigo de municipio inexistente'::text;
        RETURN;
    END IF;

    -- ja calculado, dentro da validade e com a base de academias vigente: nao entra na fila
    -- (resultado "pendente" feito antes da carga do CNPJ, ou com base de outro mes, pode ser pedido de novo)
    IF EXISTS (SELECT 1 FROM bairros.resumo r
                WHERE r.cod_municipio = v_cod AND r.processado_em > now() - validade
                  AND coalesce(r.data_base_cnpj, '') = coalesce((SELECT max(a.data_referencia) FROM bairros.academia a), '')) THEN
        RETURN QUERY SELECT 'pronto'::text, NULL::bigint, NULL::integer, 0, 'resultado disponivel'::text;
        RETURN;
    END IF;

    -- ja esta na fila: devolve o pedido existente
    IF EXISTS (SELECT 1 FROM bairros.pedido p WHERE p.cod_municipio = v_cod AND p.status IN ('pendente', 'processando')) THEN
        RETURN QUERY SELECT g.status, g.id, g.posicao_fila::integer, g.estimativa_s, 'pedido ja estava na fila'::text
                       FROM gold.bairro_pedido g WHERE g.cod_municipio = v_cod;
        RETURN;
    END IF;

    IF (SELECT count(*) FROM bairros.pedido p WHERE p.status = 'pendente') >= max_pendentes THEN
        RETURN QUERY SELECT 'fila_cheia'::text, NULL::bigint, NULL::integer, NULL::integer,
                            'fila cheia; tente mais tarde'::text;
        RETURN;
    END IF;
    IF (SELECT count(*) FROM bairros.pedido p WHERE p.pedido_em > now() - interval '1 hour') >= max_pedidos_hora THEN
        RETURN QUERY SELECT 'limite_hora'::text, NULL::bigint, NULL::integer, NULL::integer,
                            'limite de pedidos por hora atingido; tente mais tarde'::text;
        RETURN;
    END IF;

    INSERT INTO bairros.pedido AS p (cod_municipio) VALUES (v_cod)
        ON CONFLICT (cod_municipio) WHERE status IN ('pendente', 'processando') DO NOTHING
        RETURNING p.id INTO v_id;
    RETURN QUERY SELECT g.status, g.id, g.posicao_fila::integer, g.estimativa_s,
                        CASE WHEN v_id IS NULL THEN 'pedido ja estava na fila' ELSE 'pedido registrado' END
                   FROM gold.bairro_pedido g WHERE g.cod_municipio = v_cod;
END
$$;
COMMENT ON FUNCTION gold.pedir_bairros(integer) IS
    'Poe o municipio na fila de bairros (valida o codigo, nao duplica, limita fila e pedidos por hora).';

-- Permissoes -------------------------------------------------------------------
GRANT USAGE ON SCHEMA gold TO web_leitor;
GRANT SELECT ON gold.bairro_ranking, gold.bairro_resumo, gold.bairro_setor, gold.bairro_academia, gold.bairro_pedido
   TO web_leitor;
REVOKE ALL ON FUNCTION gold.pedir_bairros(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION gold.pedir_bairros(integer) TO web_leitor;

-- Avisa a API REST para recarregar o cache de schema (sem efeito onde ela nao existe)
NOTIFY pgrst, 'reload schema';
