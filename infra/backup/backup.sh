#!/usr/bin/env bash
# =============================================================================
# RADAR DE EXPANSAO - INFRA: backup diario das camadas bronze, silver e gold
# =============================================================================
#
# OBJETIVO: gerar um dump (formato custom do pg_dump) dos schemas bronze, silver
#           e gold e apagar os dumps mais antigos que a retencao.
# ENTRADA:  container do Postgres do Supabase (CONTAINER_DB)
# SAIDA:    <PASTA_BACKUP>/radar-AAAAMMDD-HHMM.dump (acrescenta; nao substitui)
#
# COMO RODAR:  ./backup.sh
# AGENDAR (crontab -e do usuario que roda o Docker; todo dia as 03:00):
#   0 3 * * * /caminho/para/backup.sh >> /caminho/para/backup.log 2>&1
#
# Papeis e permissoes nao entram no dump: sao recriados por infra/sql/00_schemas_roles.sql.
# ⏳ validar apos a instalacao: usuario do pg_dump dentro do container.
# =============================================================================
set -euo pipefail

# ============================== CONFIG ==============================
CONTAINER_DB="supabase-db"
BANCO="postgres"
USUARIO_DB="postgres"
PASTA_BACKUP="${HOME}/radar-backups"
RETENCAO_DIAS=14
SCHEMAS=(bronze silver gold)
# ====================================================================

mkdir -p "$PASTA_BACKUP"
ARQUIVO="${PASTA_BACKUP}/radar-$(date +%Y%m%d-%H%M).dump"

PARAMS_SCHEMAS=()
for s in "${SCHEMAS[@]}"; do PARAMS_SCHEMAS+=(-n "$s"); done

echo "[$(date '+%F %T')] gerando ${ARQUIVO}"
docker exec "$CONTAINER_DB" pg_dump -U "$USUARIO_DB" -d "$BANCO" -Fc "${PARAMS_SCHEMAS[@]}" > "$ARQUIVO"

# um dump vazio indica falha silenciosa: apaga e sai com erro
if [ ! -s "$ARQUIVO" ]; then
    echo "[$(date '+%F %T')] ERRO: dump vazio" >&2
    rm -f "$ARQUIVO"
    exit 1
fi
chmod 600 "$ARQUIVO"

# retencao: apaga dumps com mais de RETENCAO_DIAS dias
find "$PASTA_BACKUP" -name 'radar-*.dump' -type f -mtime +"$RETENCAO_DIAS" -delete

echo "[$(date '+%F %T')] ok: $(du -h "$ARQUIVO" | cut -f1)"
