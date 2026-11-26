# agents.md — Regras da casa para o assistente de IA

> **RASCUNHO v0.1 (26/11/2026).** Este arquivo é o manual do assistente de IA que trabalha neste repositório.
> Vale para qualquer tarefa: código, SQL, documentação, workflow do n8n ou dashboard.

---

## 1. Antes de qualquer tarefa

1. Ler **`prd.md`** (o que o cliente quer) e **`spec.md`** (como construímos). Se a tarefa contradiz um dos dois, parar e perguntar.
2. Ler este arquivo inteiro.
3. Conferir em que etapa o projeto está (seção "Pendências" do `spec.md`) e trabalhar só no escopo pedido.

## 2. Estrutura de pastas

| Pasta / arquivo | O que vai ali | O que NÃO vai |
|---|---|---|
| `prd.md`, `spec.md`, `agents.md` | Planejamento: negócio, técnica, regras | — |
| `prompts/` | Registro dos principais prompts por etapa (modelo em `prompts/README.md`) | Conversas inteiras copiadas, dados pessoais |
| `sql/bronze/`, `sql/silver/`, `sql/gold/` | DDL e transformações SQL de cada camada, numeradas na ordem de execução (`01_...sql`) | Dados, senhas |
| `src/ingestao/` | Chamadas às APIs do IBGE e do BCB → bronze | Transformação de dado |
| `src/transformacao/` | Execução das regras bronze → silver → gold | Chamadas às APIs |
| `src/app/` | Dashboard Streamlit (lê só a gold) | Lógica de cálculo do ranking |
| `n8n/` | Workflow exportado em `.json` **sem credenciais** | Exportação com credenciais |
| `site/` | Site de apoio (documentação + vitrine de dados) | Build (`dist/`), `node_modules/` |
| `docs/img/` | Prints do dashboard e da execução do n8n | — |
| raiz | `README.md`, `requirements.txt`, `.env.example`, `.gitignore` | `.env`, `.venv/`, `__pycache__/`, dados locais |

## 3. Convenções de nomes

**Geral:** português, sem acento, `snake_case`. Nomes descritivos, sem abreviação obscura.

| Objeto | Padrão | Exemplo |
|---|---|---|
| Schemas | camada | `bronze`, `silver`, `gold` |
| Tabela da bronze | `api_resposta`, `execucao` | `bronze.api_resposta` |
| Dimensões / fatos | `dim_<entidade>` / `fato_<assunto>` | `silver.dim_municipio`, `silver.fato_indicador_macro` |
| Tabelas da gold | o que a tabela entrega | `gold.ranking_expansao` |
| Chaves | `<entidade>_id` | `municipio_id`, `uf_id` |
| Datas de controle | `<acao>_em` (`timestamptz`) | `ingerido_em`, `atualizado_em` |
| Flags booleanas | `eh_<algo>` ou adjetivo | `eh_fim_de_semana`, `dados_incompletos` |
| Notas do ranking | `nota_<criterio>` | `nota_poder_compra` |
| Arquivos Python | `snake_case.py` por responsabilidade | `ibge_agregados.py`, `bcb_sgs.py` |
| Arquivos SQL | `NN_<objeto>.sql` | `sql/silver/02_dim_municipio.sql` |
| Funções Python | verbo + objeto | `buscar_periodos()`, `gravar_bronze()` |
| Constantes do CONFIG | `MAIUSCULAS` | `LIMITE_VALORES_POR_CHAMADA` |

## 4. Padrão de todo script

### 4.1 Cabeçalho obrigatório

**Todo script Python começa com o cabeçalho abaixo** (em notebook, ele vai na **primeira célula**), logo seguido do bloco `CONFIG`.

Regras do cabeçalho:
- **ASCII puro, sem acentos**, para não quebrar em nenhum terminal ou codificação.
- O **banner "SQUAD 21001" é idêntico em todos os arquivos** — copiar sem alterar.
- As seções **JA APRENDIDO** e **NOVIDADES** são didáticas e **específicas de cada script**: dizem o que aquele arquivo usa
  que já foi visto no curso e o que é novo nele. Nada de texto genérico copiado de outro arquivo.
- `SAIDA` diz se o script **substitui** ou **acrescenta** dados na tabela de destino.
- Nenhuma menção a ferramenta de IA no cabeçalho.

```python
# +======================================================================================+
# |                                                                                      |
# |    ____    ___   _   _      _     ____      ____     _     ___    ___     _          |
# |   / ___|  / _ \ | | | |    / \   |  _ \     |___ \  / |   / _ \  / _ \   / |         |
# |   \___ \ | | | || | | |   / _ \  | | | |      __) | | |  | | | || | | |  | |         |
# |    ___) || |_| || |_| |  / ___ \ | |_| |     / __/  | |  | |_| || |_| |  | |         |
# |   |____/  \__\_\ \___/  /_/   \_\|____/     |_____| |_|   \___/  \___/   |_|         |
# |                                                                                      |
# +======================================================================================+
#
# =============================================================================
# RADAR DE EXPANSAO - ETAPA <N>: <NOME DA ETAPA>
# =============================================================================
#
# OBJETIVO: <o que o script faz, em 1-2 linhas>
# ENTRADA:  <API / schema.tabela que le>
# SAIDA:    <schema.tabela ou arquivo que grava; se substitui ou acrescenta>
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - <itens que o aluno ja domina>
#
# NOVIDADES:
#   1. <comando/conceito>  -> <explicacao curta>
#   2. ...
#
# INSTALACAO: pip install <pacotes>   (ou: pip install -r requirements.txt)
# COMO RODAR: python src/<pasta>/<arquivo>.py
#
# =============================================================================
```

### 4.2 Bloco CONFIG e corpo do script

Logo depois do cabeçalho (exemplo de um script de ingestão):

```python
# ============================== CONFIG ==============================
AGREGADO = 6579
VARIAVEIS = [9324]
LIMITE_VALORES_POR_CHAMADA = 50_000
TIMEOUT_SEGUNDOS = 60
# ====================================================================

import os
from dotenv import load_dotenv

load_dotenv()  # credenciais vêm do .env, nunca do código
```

- Todos os parâmetros ajustáveis ficam no bloco **`CONFIG` no topo** do arquivo, logo abaixo do cabeçalho.
- Credenciais só por variável de ambiente (`.env` local, `st.secrets` no Streamlit Cloud, credencial do n8n).
- Toda chamada de API: `timeout`, `try/except`, até 3 tentativas e registro em `bronze.execucao`.
- Funções pequenas, com docstring de uma linha. Comentários explicam o **porquê**, não o óbvio.

## 5. O assistente de IA SEMPRE deve

- Ler `prd.md` e `spec.md` antes de começar e citar a seção que está implementando.
- Abrir todo script Python (e a primeira célula de todo notebook) com o cabeçalho padrão da seção 4.1, seguido do bloco `CONFIG`.
- Testar a chamada de API de verdade (com volume pequeno) antes de escrever o código definitivo.
- Respeitar o limite do IBGE: estimar períodos × variáveis × localidades × categorias e dividir em lotes (`spec.md`, seção 6).
- Gravar na bronze o JSON **exatamente como veio**, com fonte, endpoint, parâmetros e data/hora.
- Manter rastreabilidade: toda linha da silver com `bronze_id`.
- Tratar `"-"`, `"..."`, `"X"` e `".."` como nulo + flag na silver.
- Atualizar o `spec.md` **no mesmo commit** quando mudar tabela, coluna, endpoint ou regra.
- Atualizar o `prd.md` quando mudar critério ou peso do ranking.
- Registrar em `prompts/` os prompts que geraram entregas relevantes (modelo em `prompts/README.md`).
- Mostrar o `git status` e a lista de arquivos antes de qualquer commit.
- Escrever em português do Brasil (código, comentários, mensagens e documentação).

## 6. O assistente de IA NUNCA deve

- Apagar, truncar ou atualizar as respostas da **bronze** (`bronze.api_resposta` só recebe `INSERT`; só as tabelas de controle são atualizadas).
- Transformar dado na ingestão.
- Colocar chave, senha, token ou string de conexão em código, notebook, SQL, workflow exportado ou documentação.
- Commitar `.env`, `.venv/`, `__pycache__/`, `.ipynb_checkpoints/`, dados locais ou configurações locais de ferramentas.
- Alterar o modelo de dados sem atualizar o `spec.md`.
- Mudar critério ou peso do ranking sem atualizar o `prd.md`.
- Criar tabela na gold que não responde a nenhuma pergunta do `prd.md`.
- Pedir ao IBGE todos os municípios, todos os anos e várias variáveis numa chamada só.
- Usar `periodos/all` no IBGE ou `/ultimos/N` no BCB.
- Fazer `push --force`, reescrever histórico ou commitar direto sem revisão do squad.
- Citar fontes que não sejam as oficiais (IBGE, BCB) e as ferramentas da stack.

## 7. Padrão de commit

Formato: `tipo(escopo): descrição no imperativo, em português, até 72 caracteres`

| Tipo | Quando | Exemplo |
|---|---|---|
| `feat` | nova funcionalidade | `feat(ingestao): busca população do IBGE em lotes por ano` |
| `fix` | correção | `fix(silver): trata "X" como sigilo no Cadastro de Empresas` |
| `docs` | documentação | `docs(spec): adiciona DDL da camada gold` |
| `refactor` | mudança sem alterar comportamento | `refactor(ingestao): extrai função de retry` |
| `chore` | configuração, dependências | `chore: adiciona .gitignore e .env.example` |
| `test` | testes e validações | `test(gold): confere soma dos pesos do ranking` |

Escopos: `ingestao`, `bronze`, `silver`, `gold`, `app`, `n8n`, `site`, `prd`, `spec`, `agents`, `prompts`.

Regras:
- Commits pequenos e frequentes, um assunto por commit.
- Antes de commitar: `git status` + `git diff --staged` revisados; nenhum arquivo da lista "NUNCA" no stage.
- Só membros do squad fazem commit, com o próprio nome e e-mail.
