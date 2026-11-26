# Etapa 4 · Camada silver (modelo estrela)

- **Data:** 26/11/2026
- **Responsável:** _(a preencher)_
- **Arquivos afetados:** `sql/silver/`, `src/transformacao/executar.py`, `spec.md` (seções 3.2 e 4), `README.md`

## Objetivo
Transformar as respostas brutas da bronze num modelo estrela que o negócio entende: dimensões de região, UF, município,
calendário e indicador; fatos municipais e macroeconômicos com tipos corretos, sem duplicatas e rastreáveis até a bronze.

## Contexto fornecido
- `spec.md` seção 4 (regras bronze → silver) e o "pronto quando" da frente F3 em `docs/responsabilidades.md`.
- Estrutura real dos JSON gravados na bronze (localidades "niveladas", agregados do IBGE, séries do BCB).
- Exigência de um único caminho de transformação para os cenários A (Python) e B (n8n).

## Entrada (prompt)
> Tarefa: escrever o DDL da silver e a transformação bronze → silver.
> Restrições: achatar o JSON do IBGE em localidade + período + valor; texto → número; `-`, `...`, `X` e `..` viram nulo
> com flag; códigos de município com 7 dígitos; sem duplicatas (a versão mais nova vence); `bronze_id` em toda linha;
> datas futuras da Selic fora da silver; a mesma lógica precisa servir ao script Python e ao n8n.
> Formato: arquivos `sql/silver/NN_*.sql` idempotentes, testes de qualidade consultáveis e um executor em Python.

## Saída esperada
Rodar a transformação preenche as tabelas; rodar de novo sem bronze nova não altera nada; todos os testes do
"pronto quando" passam.

## O que a IA entregou
- Transformação como **função SQL** (`silver.atualizar`): o Python e o n8n só a chamam, então não há duas versões da regra.
- `dim_indicador` com `agregado`, `variavel` e `serie_bcb`, que ligam cada resposta da bronze ao indicador sem
  "adivinhar" pelo nome.
- `dim_municipio` com regiões imediata e intermediária (e meso/microrregião), lidas do JSON "nivelado" do IBGE.
- 12 testes de qualidade numa view, incluindo a conferência cruzada do IPCA do IBGE com o do BCB.

## O que foi ajustado
- **Ambiente de teste:** a primeira tentativa no banco do projeto bateu num Postgres local que ocupava a porta padrão do
  computador; o acesso ao banco passou a usar outra porta local, e a silver foi desenvolvida e testada antes num banco
  descartável com a bronze carregada das APIs. A segunda execução da transformação gravou 0 linhas (idempotente).
- **Teste de "100% dos fatos casando com municípios":** a chave estrangeira já garante isso dentro da silver; o teste útil
  é outro — nenhum município citado na bronze pode ficar sem par na dimensão. Foi esse que entrou.
- **Conferência de números:** população 2024 (212.583.750), Censo 2022 (203.080.756) e academias 2024 (65.346) batem com
  as chamadas feitas direto na API na etapa de exploração.

## Lições
Guardar na bronze os parâmetros de cada chamada (agregado, série) foi o que permitiu ligar resposta e indicador sem
regras frágeis na silver.
