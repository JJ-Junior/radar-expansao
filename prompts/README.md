# prompts/ — Registro do processo com IA

Esta pasta registra os principais pedidos feitos ao assistente de IA em cada etapa do projeto: o que foi pedido, o que a IA entregou
e o que o squad precisou revisar ou corrigir. O objetivo é mostrar um processo auditável, não guardar conversas inteiras.

## Organização

```
prompts/
├── README.md                      (este arquivo: modelo + índice)
├── etapa-1-planejamento/
├── etapa-2-exploracao-apis/
├── etapa-3-bronze/
├── etapa-4-silver/
├── etapa-5-gold/
├── etapa-6-n8n/
├── etapa-7-streamlit/
├── etapa-8-github-readme/
└── extra-site-de-apoio/
```

Cada registro é um arquivo `NN-assunto-curto.md` dentro da pasta da etapa (ex.: `etapa-3-bronze/02-lotes-ibge.md`).
As pastas das próximas etapas são criadas quando a etapa começar.

## Modelo de registro

Copie o bloco abaixo para um novo arquivo e preencha.

```markdown
# <Etapa> · <Assunto>

- **Data:** dd/mm/aaaa
- **Responsável:** <membro do squad>
- **Arquivos afetados:** <caminhos>

## Objetivo
O que se queria obter com o pedido, em uma ou duas frases.

## Contexto fornecido
Quais documentos e informações a IA recebeu (ex.: prd.md, spec.md seção X, resposta de exemplo da API).

## Entrada (prompt)
O pedido, escrito de forma estruturada: tarefa, restrições, formato de saída.
Sem credenciais, sem dados pessoais.

## Saída esperada
Como seria uma boa resposta (critério de aceite).

## O que a IA entregou
Resumo do que veio: arquivos, decisões, trechos relevantes.

## O que foi ajustado
O que o squad revisou, corrigiu ou rejeitou — e por quê. Esta é a parte mais importante.

## Lições
O que muda no próximo pedido (e, se for regra, o que entrou no agents.md).
```

## Índice

| Etapa | Registro | Assunto |
|---|---|---|
| 1 | [01-rascunho-prd.md](etapa-1-planejamento/01-rascunho-prd.md) | Rascunho do prd.md para a rede de academias |
| 1 | [02-validacao-cnae-academias.md](etapa-1-planejamento/02-validacao-cnae-academias.md) | Validação do código CNAE 93.13-1 na API do IBGE |
| 1 | [03-infraestrutura-e-cenarios-de-ingestao.md](etapa-1-planejamento/03-infraestrutura-e-cenarios-de-ingestao.md) | Supabase e n8n autohospedados, acesso à gold e cenários de ingestão |
| 3 | [01-ingestao-python.md](etapa-3-bronze/01-ingestao-python.md) | Camada bronze e ingestão em Python (cenário A) |
| extra | [01-site-estatico.md](extra-site-de-apoio/01-site-estatico.md) | Site de apoio estático no GitHub Pages |
