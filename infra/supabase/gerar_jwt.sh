#!/usr/bin/env bash
# =============================================================================
# RADAR DE EXPANSAO - INFRA: gera um token JWT (HS256) para o Supabase autohospedado
# =============================================================================
#
# OBJETIVO: gerar ANON_KEY, SERVICE_ROLE_KEY e o token do papel web_leitor,
#           assinados com o JWT_SECRET do .env do Supabase.
# ENTRADA:  variavel de ambiente JWT_SECRET; argumentos <papel> [dias_de_validade]
# SAIDA:    o token impresso na tela (copie para o .env / Secrets; nao versione)
#
# COMO RODAR:
#   export JWT_SECRET='<o mesmo valor do .env do Supabase>'
#   ./gerar_jwt.sh anon 3650
#   ./gerar_jwt.sh service_role 3650
#   ./gerar_jwt.sh web_leitor 365
# =============================================================================
set -euo pipefail

PAPEL="${1:?informe o papel: anon | service_role | web_leitor}"
DIAS="${2:-3650}"
: "${JWT_SECRET:?defina JWT_SECRET no ambiente antes de rodar}"

# base64 "url-safe" sem padding, como o padrao JWT exige
b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }

AGORA=$(date +%s)
EXPIRA=$((AGORA + DIAS * 86400))

CABECALHO=$(printf '{"alg":"HS256","typ":"JWT"}' | b64url)
CORPO=$(printf '{"role":"%s","iss":"supabase","iat":%d,"exp":%d}' "$PAPEL" "$AGORA" "$EXPIRA" | b64url)
ASSINATURA=$(printf '%s.%s' "$CABECALHO" "$CORPO" | openssl dgst -sha256 -hmac "$JWT_SECRET" -binary | b64url)

echo "${CABECALHO}.${CORPO}.${ASSINATURA}"
