-- =============================================================================
-- RADAR DE EXPANSAO - INFRA: schemas, papeis, permissoes e RLS
-- =============================================================================
--
-- OBJETIVO: preparar o banco do Supabase autohospedado para o Lakehouse:
--           schemas bronze/silver/gold, papel de carga (etl_radar), papel de
--           leitura da API (web_leitor), permissoes e RLS na gold.
-- ENTRADA:  banco "postgres" recem-criado pelo Supabase.
-- SAIDA:    schemas e papeis criados. Idempotente: pode rodar de novo.
--
-- COMO RODAR (no servidor; a senha vai como variavel do psql, nunca no arquivo):
--   docker exec -i supabase-db psql -U postgres -d postgres \
--     -v ON_ERROR_STOP=1 -v senha_etl='<senha-do-etl_radar>' < 00_schemas_roles.sql
--
-- Rodar DE NOVO depois de criar as tabelas da gold (secao 5 aplica o RLS nelas).
-- ⏳ validar apos a instalacao: permissoes do usuario "postgres" na versao
--    do Supabase escolhida (criar papeis e conceder ao "authenticator").
-- =============================================================================

-- 1. Schemas das camadas ------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- Fuso padrao do banco (datas de controle e calendario)
ALTER DATABASE postgres SET timezone TO 'America/Sao_Paulo';

-- 2. Papel de carga: scripts Python, container de ETL e credencial do n8n -----
SELECT format('CREATE ROLE etl_radar LOGIN PASSWORD %L', :'senha_etl')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'etl_radar')
\gexec

ALTER ROLE etl_radar SET timezone TO 'America/Sao_Paulo';
GRANT CONNECT ON DATABASE postgres TO etl_radar;
GRANT USAGE, CREATE ON SCHEMA bronze, silver, gold TO etl_radar;
-- etl_radar cria (e e dono de) todas as tabelas das tres camadas.
-- A regra "respostas da bronze so recebem INSERT" e reforcada depois da DDL:
--   REVOKE UPDATE, DELETE, TRUNCATE ON bronze.api_resposta FROM etl_radar;

-- 3. Papel de leitura da API REST: so SELECT na gold --------------------------
SELECT 'CREATE ROLE web_leitor NOLOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'web_leitor')
\gexec

GRANT USAGE ON SCHEMA gold TO web_leitor;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO web_leitor;
-- tabelas que o etl_radar criar no futuro tambem ficam legiveis pela API
ALTER DEFAULT PRIVILEGES FOR ROLE etl_radar IN SCHEMA gold GRANT SELECT ON TABLES TO web_leitor;
-- a API REST assume o papel indicado no token; ela precisa poder "virar" web_leitor
GRANT web_leitor TO authenticator;

-- 4. Ninguem mais le as camadas pela API ---------------------------------------
REVOKE ALL ON SCHEMA bronze, silver, gold FROM PUBLIC;
REVOKE ALL ON SCHEMA bronze, silver, gold FROM anon, authenticated;
REVOKE ALL ON ALL TABLES IN SCHEMA gold FROM anon, authenticated;

-- 5. RLS na gold (defesa extra): leitura so para web_leitor ---------------------
DO $$
DECLARE
    t record;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'gold' LOOP
        EXECUTE format('ALTER TABLE gold.%I ENABLE ROW LEVEL SECURITY', t.tablename);
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = 'gold' AND tablename = t.tablename AND policyname = 'leitura_web'
        ) THEN
            EXECUTE format(
                'CREATE POLICY leitura_web ON gold.%I FOR SELECT TO web_leitor USING (true)',
                t.tablename);
        END IF;
    END LOOP;
END
$$;

-- 6. Avisa a API REST para recarregar o cache de schema -------------------------
NOTIFY pgrst, 'reload schema';
