# Etapa 3 · Camada bronze com ingestão em Python (cenário A)

- **Data:** 26/11/2026
- **Responsável:** _(a preencher)_
- **Arquivos afetados:** `sql/bronze/`, `src/ingestao/`, `src/transformacao/criar_estrutura.py`, `spec.md` (seções 3.1, 7, 8.1, 9.1 e 10), `README.md`

## Objetivo
Construir a camada bronze: tabelas que guardam as respostas das APIs exatamente como vieram e scripts Python que
fazem a carga inicial e a incremental, em lotes, sem duplicar dados.

## Contexto fornecido
- `spec.md` (contrato da bronze, limites da API do IBGE, janelas do BCB, regras da carga incremental).
- `agents.md` (cabeçalho padrão, bloco `CONFIG`, nada de credencial no código, bronze só recebe `INSERT`).
- Banco já criado com os schemas e o papel de carga; credenciais só no `.env`.

## Entrada (prompt)
> Tarefa: escrever o DDL da bronze (respostas, log de execução, trava de carga e uma view com o último período salvo)
> e os scripts de ingestão: funções comuns, localidades do IBGE, agregados do IBGE em lotes por ano, séries do BCB em
> janelas de até 10 anos, e dois orquestradores (carga inicial e incremental).
> Restrições: JSON gravado sem transformação; idempotência pelo hash da resposta; timeout, 3 tentativas com espera
> crescente e validação do tipo de conteúdo; 404 do BCB = "sem novidade"; incremental do IBGE pelo `/periodos`
> (id + data de modificação); cabeçalho padrão e `CONFIG` em todo script.
> Formato: arquivos `sql/bronze/NN_*.sql` idempotentes e módulos executáveis com `python -m`.

## Saída esperada
Rodar a carga inicial preenche a bronze; rodar a incremental logo depois termina como "sem novidade" e não grava nada.

## O que a IA entregou
- DDL em quatro arquivos, com o hash calculado pelo próprio Postgres e `UPDATE`/`DELETE` revogados na tabela de respostas.
- `comum.py` com conexão, GET com tentativas, gravação com `ON CONFLICT DO NOTHING`, log por recurso e trava de carga.
- Scripts por fonte e orquestradores com `--fonte` (os jobs que o n8n dispara no cenário A).
- Teste ponta a ponta num Postgres descartável antes de usar o banco do projeto.

## O que foi ajustado
- **Log de execução:** o rascunho do spec tinha uma linha por carga; passou a ser uma linha **por recurso**, agrupada por
  `rodada_id`, para mostrar tempo e resultado de cada fonte separadamente.
- **IPCA:** a regra "últimos 3 meses" do spec foi trocada por lote anual com a mesma lógica de modificação dos outros
  agregados — um só jeito de decidir o que baixar.
- **Última data do BCB:** em vez de uma tabela de controle, a view calcula a maior data presente nas respostas.
- **Selic meta:** a série traz datas futuras; o incremental parte de `min(última data, hoje)` menos 30 dias.
- **HTTP 304 vazio do BCB:** o teste revelou que o SGS devolve 304 sem conteúdo para certas URLs exatas (uma das janelas
  da Selic). O script agora repete a janela com a data final 1 a 3 dias depois, e a carga passou.
- **Chave do dashboard:** a validação da infraestrutura mostrou que o gateway exige a chave anônima além do token de leitura;
  o spec e os modelos de segredos ganharam `SUPABASE_ANON_KEY`.

## Lições
Testar o DDL e a carga num banco descartável antes do banco do projeto encontra erros sem sujar a bronze, que não aceita
`DELETE`.
