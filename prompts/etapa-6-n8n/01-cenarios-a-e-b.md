# Etapa 6 · Workflows do n8n para os cenários A e B

- **Data:** 27/11/2026
- **Responsável:** José Martins (Junior)
- **Arquivos afetados:** `n8n/*.json`, `n8n/README.md`, `README.md` (seções 3, 6 e 6.1), `spec.md` (seções 8.1, 8.2, 8.3 e 9.1)

## Objetivo
Automatizar a atualização semanal da bronze com o n8n nos dois cenários do enunciado e deixar os dois comparáveis:
A (o n8n agenda e dispara o Python do container de ETL) e B (o próprio n8n chama as APIs e grava na bronze).

## Contexto fornecido
- `spec.md` seções 3.1 (contrato da bronze), 6 (lotes e limite do IBGE), 7 (incremental) e 8 (cenários e trava).
- Código da ingestão em Python (`src/ingestao/`), para o cenário B repetir os mesmos recursos, lotes e regras.
- Contrato do disparador HTTP do container de ETL (`/saude`, `/rodar/cenario-a`, `/rodar/transformar`, códigos 200/409/500/401).
- Restrições do n8n autohospedado: limite de memória do container e acesso só por túnel SSH.

## Entrada (prompt)
> Tarefa: montar dois workflows do n8n. (A) agenda de segunda 06:00 em America/Sao_Paulo → verifica se o container está livre →
> dispara a carga incremental + transformação com o token em credencial *Header Auth* → registra 409 e erros.
> (B) pega a trava do banco com `em_uso_por = 'n8n'`, compara os períodos do IBGE com o último período salvo pelo n8n, chama
> IBGE e BCB por *HTTP Request* e grava cada resposta inteira na bronze com `origem_carga = 'n8n'`, no mesmo contrato do A;
> depois chama só a transformação e solta a trava, inclusive em caso de erro. Agenda do B desligada.
> Restrições: nenhuma credencial nos arquivos exportados; nó *Code* só para montar URLs e parâmetros; nada de transformar dado na
> ingestão; não "explodir" o JSON em itens; respeitar o limite de memória do n8n.

## Saída esperada
Workflows importáveis, uma execução real do A, uma execução de teste do B gravando na bronze e a mesma silver/gold.

## O que a IA entregou
- Cenário A com ramo de sucesso, ramo de 409 (registrado em `bronze.execucao`, sem falhar a execução) e ramo de erro
  (registrado e marcado como falha).
- Cenário B em três peças: o fluxo principal, um sub-workflow que faz uma chamada e grava uma resposta (a memória de cada JSON
  é liberada logo depois) e um *error workflow* que solta a trava se a execução quebrar no meio.
- Os workflows foram gerados por um script, o que deixou os nós e as ligações padronizados; a lógica de lotes e janelas foi
  conferida contra as APIs reais antes de importar no n8n.

## O que foi ajustado
- **Alcance do B:** a primeira proposta baixava todo o histórico por ano × UF (milhares de chamadas). Ficou um `ANO_INICIO`
  no nó *Config*: o B cuida dos anos recentes e o histórico continua com o A.
- **Memória:** em vez de um *Loop* no fluxo principal, que guardaria todos os JSON na execução, cada chamada virou um
  sub-workflow que não salva execução bem-sucedida.
- **Respostas do BCB:** 404 é "nada novo", não erro; e resposta que não é JSON (HTML com status 200) vira erro, igual ao A.
- **Lotes com a silver:** conferido que os lotes por UF do B e por ano do A não duplicam fatos na silver (chave
  município + indicador + ano).

## Lições
- No n8n, uma resposta JSON em lista vira vários itens: para manter "uma chamada = uma linha na bronze", o nó HTTP devolve a
  resposta completa (corpo, status e headers) num item só.
- Execução manual não aciona *error workflow*: a expiração da trava em 2 horas continua sendo a rede de segurança.
