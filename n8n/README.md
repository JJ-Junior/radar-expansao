# n8n/ — workflows exportados (sem credenciais)

Automação da etapa 6. Os dois cenários de ingestão do [`spec.md`](../spec.md) (seção 8) gravam na mesma bronze, com a
mesma trava (`bronze.trava_carga`) e a mesma transformação (`src/transformacao/executar.py`, rodada pelo container de ETL).

| Arquivo | Workflow | O que faz |
|---|---|---|
| `radar-expansao-cenario-a.json` | **Radar · Cenário A** | Segunda às 06:00: `GET /saude` do container de ETL → `POST /rodar/cenario-a` (carga incremental em Python + silver/gold). 200 = sucesso; 409 (trava ou container ocupado) e erros ficam registrados em `bronze.execucao`, e só o erro marca a execução como falha |
| `radar-expansao-cenario-b.json` | **Radar · Cenário B** | O próprio n8n chama o IBGE e o BCB: pega a trava (`em_uso_por = 'n8n'`), lê o último período salvo, monta as chamadas (ano × UF), grava cada JSON com `origem_carga = 'n8n'`, fecha `bronze.execucao`, chama `POST /rodar/transformar` se houve resposta nova e solta a trava. Agenda de segunda 07:00, **desligada** (workflow inativo) |
| `radar-expansao-cenario-b-grava-resposta.json` | **Radar · Cenário B · grava resposta** | Sub-workflow: um GET com 3 tentativas, validação do JSON e `INSERT` em `bronze.api_resposta` (`ON CONFLICT DO NOTHING`). Não salva as execuções bem-sucedidas, para não guardar os JSON |
| `radar-expansao-cenario-b-erro.json` | **Radar · Cenário B · erro** | *Error workflow* do cenário B: se a execução agendada quebrar no meio, solta a trava e fecha as execuções abertas com `status = 'erro'` |

## Pré-requisitos

- n8n autohospedado na rede Docker `radar`, a mesma do banco e do container de ETL ([`docs/instalacao.md`](../docs/instalacao.md), seções 3 e 4.1).
- Duas credenciais criadas no n8n **com estes nomes**:

| Nome da credencial | Tipo | Campos |
|---|---|---|
| `Radar · Postgres etl_radar` | Postgres | host do banco na rede Docker, porta 5432, banco `postgres`, usuário `etl_radar`, senha do `etl_radar`, SSL desligado (rede interna) |
| `Radar · X-Radar-Token` | Header Auth | Name `X-Radar-Token`, Value = `RADAR_ETL_TOKEN` do `.env` do container de ETL |

## Importar

1. **Workflows → Import from File**, nesta ordem: `…-cenario-b-grava-resposta.json`, `…-cenario-b-erro.json`,
   `…-cenario-a.json` e `…-cenario-b.json`.
2. Em cada nó Postgres e nos nós HTTP que chamam o container (`Dispara cenário A`, `Transforma (radar-etl)`), escolha a
   credencial correspondente (os arquivos trazem só o nome, nunca o segredo).
3. No **Radar · Cenário B**:
   - nó **Grava cada resposta** → escolha o workflow **Radar · Cenário B · grava resposta** (no arquivo está o marcador
     `ID_DO_SUBWORKFLOW_GRAVAR`);
   - **Settings → Error workflow** → **Radar · Cenário B · erro** (marcador `ID_DO_WORKFLOW_DE_ERRO`).
4. Ative o **Radar · Cenário A** (agenda de segunda 06:00, fuso `America/Sao_Paulo`). Deixe o **Radar · Cenário B** inativo e
   rode-o pelo botão *Execute workflow*; para agendá-lo, basta ativá-lo (segunda 07:00, uma hora depois do A).

## Parâmetros do cenário B (nó **Config**)

| Parâmetro | Padrão | Para quê |
|---|---|---|
| `MODO` | `incremental` | `inicial` ignora o que já foi salvo e baixa tudo de novo (sem duplicar: o hash barra respostas iguais) |
| `ANO_INICIO` | `2022` | agregados municipais só deste ano em diante; o histórico completo é do cenário A |
| `DATA_INICIO_BCB` | `2015-01-01` | início do histórico do BCB quando a série ainda não tem nada salvo pelo n8n |
| `AGREGADOS`, `SERIES_BCB`, `LOCALIDADES`, `UFS` | iguais aos de `src/ingestao/` | mesmos recursos do cenário A |

## Exportar de novo sem credenciais

Depois de mudar um workflow no n8n, exporte (*Download*) e, antes de commitar, troque o `id` de cada credencial por
`CREDENCIAL_POSTGRES` / `CREDENCIAL_TOKEN`, os IDs do sub-workflow e do error workflow pelos marcadores acima e apague os
campos `id`, `versionId`, `meta.instanceId`, `active`, `shared` e `tags` da raiz. Nenhum arquivo daqui pode ter senha, token,
IP ou endereço interno.
