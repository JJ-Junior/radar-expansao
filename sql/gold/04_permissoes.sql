-- =============================================================================
-- RADAR DE EXPANSAO - ETAPA 5: CAMADA GOLD · 04_permissoes.sql
-- =============================================================================
-- O dashboard le a gold pela API REST com o papel web_leitor: so SELECT nas
-- tabelas da gold, com RLS. Views internas e a funcao de carga ficam fora da API.
-- Rodar como etl_radar, depois das tabelas e views. Idempotente.
-- =============================================================================

-- Leitura das tabelas de consumo
GRANT USAGE ON SCHEMA gold TO web_leitor;
GRANT SELECT ON gold.indicadores_municipio, gold.ranking_expansao, gold.ranking_criterio,
                gold.parametro_ranking, gold.contexto_macro, gold.momento_expansao
   TO web_leitor;

-- RLS como defesa extra: leitura so para web_leitor (o servidor ja aplica isso
-- automaticamente a tabelas novas da gold; aqui fica explicito e reproduzivel)
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['indicadores_municipio', 'ranking_expansao', 'ranking_criterio',
                             'parametro_ranking', 'contexto_macro', 'momento_expansao'] LOOP
        EXECUTE format('ALTER TABLE gold.%I ENABLE ROW LEVEL SECURITY', t);
        IF NOT EXISTS (SELECT 1 FROM pg_policies
                        WHERE schemaname = 'gold' AND tablename = t AND 'web_leitor' = ANY (roles)) THEN
            EXECUTE format('CREATE POLICY leitura_web_leitor ON gold.%I FOR SELECT TO web_leitor USING (true)', t);
        END IF;
    END LOOP;
END
$$;

-- Fora da API: testes, rastreio e a funcao que recalcula a gold
REVOKE ALL ON gold.vw_testes_qualidade, gold.vw_rastreio_exemplo FROM PUBLIC, web_leitor;
REVOKE EXECUTE ON FUNCTION gold.atualizar(integer) FROM PUBLIC;

-- Avisa a API REST para recarregar o cache de schema (sem efeito onde ela nao existe)
NOTIFY pgrst, 'reload schema';
