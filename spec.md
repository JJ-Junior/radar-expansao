# spec.md — Especificação Técnica do Radar de Expansão

> **RASCUNHO v0.13 (26/11/2026)** — itens marcados com ⏳ dependem de decisão do squad.
> v0.14: dashboard com 6 páginas (simulador de região, simulador de pesos, dólar parcial e último fechamento, semáforo de `momento_atual`) — seção 9.1.
> v0.13: semáforo com janela móvel de 30 dias até o último fechamento (câmbio e juros), alerta de alta de curto prazo no câmbio,
> `gold.momento_atual` com datas de referência, último fechamento em `contexto_macro`, limiares em `parametro_ranking` (seção 5.1).
> v0.12: dashboard Streamlit implementado (seção 9.1): 5 páginas, camada de dados única com cache de 10 minutos e cópia de contingência.
> v0.11: simulador de região (P9): centroides dos municípios (API de Malhas v4), coordenadas na silver e na gold, estimativas de
> população projetada e lacuna de academias (seções 2.1, 3.2, 3.3, 5.4 e 9.4).
> v0.10: site publicado só no servidor autohospedado, atualizado a partir da branch `junior` a cada 10 minutos.
> v0.9: acesso público só ao site e à API de leitura (sem proxy de acesso); site servido do servidor autohospedado.
> v0.8: trava de renda mínima nas 5 recomendadas (`gold.parametro_ranking`, coluna `elegivel_recomendacao`, teste 14).
> v0.7: gold implementada (seção 3.3 reflete `sql/gold/`; posição na região; nota de riqueza agregada; `mes_parcial`).
> v0.6: regras da gold alinhadas ao prd v0.3 (redistribuição de peso, uma cidade por região imediata no top 5, limites P5/P95 no espaço competitivo, CAGR da tendência).
> v0.5: silver implementada (seções 3.2 e 4); `dim_indicador` com agregado/variável/série; `dim_municipio` com regiões imediata e intermediária.
> v0.4: bronze implementada (seção 3.1 reflete o DDL de `sql/bronze/`); lote do IPCA por ano; app envia a chave anônima + token de leitura.
> v0.3: container de ETL disparado pelo n8n (cenário A); trava contra execução simultânea; fuso America/Sao_Paulo;
> dashboard lendo a gold pela API REST do Supabase com fallback em snapshot; conexão com `DB_SSLMODE` configurável; stack do site definida.
> v0.2: Supabase e n8n autohospedados via Docker; ingestão descrita em dois cenários (Python e n8n) com o mesmo contrato da bronze.
> Fonte da verdade técnica do projeto: toda mudança de modelo, endpoint ou regra é registrada aqui **antes** de ir para o código.

---

## 1. Visão geral

O Radar de Expansão é um Lakehouse em três camadas (bronze → silver → gold) num único banco Postgres (Supabase),
alimentado pelas APIs públicas do IBGE e do Banco Central, atualizado semanalmente pelo n8n e consumido por um dashboard Streamlit.
**Supabase e n8n são autohospedados via Docker** (Supabase num perfil enxuto: Postgres, API REST e Studio).
Todos os horários seguem o fuso **America/Sao_Paulo**.

A ingestão está especificada em **dois cenários**, construídos e comparados antes de o squad escolher um (seção 8):
**A — Python** (um container de ETL com os scripts do repositório chama as APIs; o n8n agenda e dispara por HTTP interno) e
**B — n8n** (o próprio workflow chama as APIs e grava o JSON bruto pelo nó Postgres).
Os dois gravam no **mesmo contrato da bronze**, marcando a origem em `origem_carga`; a transformação silver/gold é **um único caminho de código**.

O dashboard lê a gold pela **API REST do Supabase** (só o schema `gold`, papel somente leitura, RLS ligado) e, se a API não responder,
usa um **snapshot da gold versionado no repositório** (seção 9).

```mermaid
flowchart LR
    subgraph Fontes
        L["IBGE Localidades<br/>/api/v1/localidades"]
        A["IBGE Agregados<br/>/api/v3/agregados"]
        S["BCB SGS<br/>bcdata.sgs.codigo"]
    end

    subgraph Ingestao["Ingestão (dois cenários)"]
        PY["Cenário A · container de ETL<br/>src/ingestao (Python + requests)"]
        WF["Cenário B · n8n<br/>HTTP Request + Postgres"]
    end

    subgraph Docker["Supabase autohospedado (Docker) · Postgres"]
        B[("bronze<br/>api_resposta · jsonb<br/>como veio + origem_carga")]
        SV[("silver<br/>dimensões + fatos<br/>modelo estrela")]
        G[("gold<br/>indicadores_municipio<br/>ranking_expansao<br/>contexto_macro<br/>momento_expansao")]
        API["API REST<br/>só schema gold · leitura"]
    end

    N8N["n8n autohospedado (Docker)<br/>agenda semanal · America/Sao_Paulo"] -.->|"A: HTTP interno"| PY
    N8N -.->|"B: executa"| WF
    Fontes --> PY
    Fontes --> WF
    PY -->|"origem_carga = 'python'"| B
    WF -->|"origem_carga = 'n8n'"| B
    B -->|"transformação única<br/>sql/silver"| SV
    SV -->|sql/gold| G
    G --> API
    API --> APP["Streamlit Cloud<br/>src/app"]
    G -.->|"snapshot JSON<br/>src/exportacao"| SNAP["site/dados/"]
    SNAP -.->|fallback| APP
    SNAP --> SITE["Site de apoio<br/>servidor autohospedado"]
```

**Princípios**
1. **A bronze é o cofre:** guarda o JSON exatamente como a API devolveu. Nenhuma transformação na ingestão.
   As respostas (`bronze.api_resposta`) só recebem `INSERT`; apenas as tabelas de controle (`bronze.execucao`, `bronze.trava_carga`) são atualizadas.
2. **Rastreabilidade:** toda linha da silver guarda `bronze_id`; toda tabela da gold é recalculada a partir da silver. Dá para ir de um número do dashboard até a resposta original da API.
3. **Idempotência:** rodar a mesma carga duas vezes não duplica dado (hash na bronze, `UPSERT` na silver, recálculo completo na gold).
4. **Parâmetros no topo:** todo script tem um bloco `CONFIG` no início; credenciais só no `.env`.
5. **Fuso único:** colunas de controle em `timestamptz`; containers, banco e agenda do n8n em `America/Sao_Paulo`
   (datas das fontes, como `modificacao` do IBGE e `data` do BCB, já vêm no horário de Brasília).

---

## 2. Fontes e endpoints

### 2.1 IBGE — Localidades (`https://servicodados.ibge.gov.br/api/v1/localidades`)

| Recurso | Endpoint | Uso |
|---|---|---|
| Regiões | `/regioes` | `silver.dim_regiao` (5 linhas) |
| Estados | `/estados` | `silver.dim_uf` (27 linhas) |
| Municípios | `/municipios?view=nivelado` | `silver.dim_municipio` (5.571 linhas). JSON plano, sem aninhamento |
| Centroides | `https://servicodados.ibge.gov.br/api/v4/malhas/paises/BR/metadados?intrarregiao=municipio` | `latitude`/`longitude` da `dim_municipio`: 5.571 municípios numa chamada (~1,7 MB, < 1 s), `centroide` em graus decimais (número) |

Armadilha conhecida: Boa Esperança do Norte-MT (`5101837`, município recente) vem com `microrregiao` nulo e não aparece em séries anteriores à sua criação.

Validação da malha (chamada real em 26/11/2026): a **v3** (`/api/v3/malhas/paises/BR/metadados?intrarregiao=municipio`) devolve 5.570
municípios e não tem o 5101837; os parâmetros de período dão HTTP 500. A **v4** devolve os 5.571, todos com `centroide`;
192 centroides diferem da v3 (malha mais recente). Por isso a ingestão usa a v4 (recurso `ibge_malha_municipios`, lote `snapshot`).

### 2.2 IBGE — Agregados v3 (`https://servicodados.ibge.gov.br/api/v3/agregados`)

Padrão: `/{agregado}/periodos/{periodos}/variaveis/{variaveis}?localidades={nivel}[{ids}]&classificacao={cls}[{cats}]`

| Agregado | Indicador | Variáveis | Classificação | Períodos disponíveis | Nível |
|---|---|---|---|---|---|
| **6579** | População residente estimada (pessoas) | `9324` | — | 2001–2006, 2008, 2009, 2011–2021, 2024–2026 | N6 |
| **4714** | Censo 2022: população, área, densidade | `93`, `6318`, `614` | — | 2022 | N6 |
| **5938** | PIB dos Municípios a preços correntes (mil R$) | `37` | — | 2002–2023 | N6 |
| **7060** | IPCA (%) | `63` mensal, `2265` acumulado 12 meses | `315[7169]` (índice geral) | 202001–202610 | N1 |
| **10295** | Censo 2022: rendimento domiciliar per capita (R$) | `13431` média | `2[6794]\|86[95251]\|58[95253]` (totais) | 2022 | N6 |
| **9418** | Cadastro Central de Empresas por CNAE | `2585` nº de empresas | `12762[117856]` (CNAE 93.13-1) | 2022–2024 | N6 |
| **9509** | Cadastro Central de Empresas — total | `10143` salário médio mensal (R$) | — | 2022–2024 | N6 |

Endpoints auxiliares:
- `/{agregado}/metadados` — nomes, unidades, classificações e níveis territoriais.
- `/{agregado}/periodos` — lista de períodos com a data de `modificacao` → **base da carga incremental** (seção 6).

Armadilhas que o código precisa tratar:
- Valores chegam **sempre como texto**; o nome do município varia entre tabelas → usar só o código.
- População estimada **não tem 2007, 2010, 2022 e 2023**. 2022 vem do Censo (4714). 2023 é interpolado na gold (seção 5.2).
- PIB municipal sai com ~2 anos de atraso (último ano hoje: 2023) e o IBGE **revisa anos antigos** → a carga incremental precisa olhar `modificacao`, não só períodos novos.
- `periodos/all` devolve HTTP 500 → sempre listar os períodos explicitamente.
- Símbolos no lugar de número: `"-"` (zero absoluto), `"..."` (não disponível), `"X"` (sigilo estatístico), `".."` (não se aplica).

### 2.3 Validação do código CNAE das academias (chamada real em 26/11/2026)

Objetivo: confirmar o código da categoria **CNAE 93.13-1 — Atividades de condicionamento físico** na classificação 12762 do agregado 9418 e se há dado por município.

| Verificação | Chamada | Resultado |
|---|---|---|
| Categoria | `GET /api/v3/agregados/9418/metadados` | Classificação `12762` (CNAE 2.0, 1.067 categorias). **`117856` = "93.13-1 Atividades de condicionamento físico"** (nível 4 — classe). Grupo pai `117853` = "93.1 Atividades esportivas" |
| Níveis territoriais | idem | `N1`, `N2`, `N3`, **`N6` (município)** |
| Períodos | `GET /api/v3/agregados/9418/periodos` | `2022` (mod. 20/06/2024), `2023` (mod. 13/11/2025), `2024` (mod. 25/06/2026) |
| Dado por município | `GET .../9418/periodos/{ano}/variaveis/2585\|707?localidades=N6[all]&classificacao=12762[117856]` | HTTP 200 nos 3 anos, **5.570 municípios** por ano, ~1,3 MB, 11–22 s por chamada |

Conteúdo da resposta (variável 2585 — número de empresas):

| Ano | Municípios com número | Municípios com `"-"` (zero) | Total Brasil | São Paulo | Belo Horizonte | Brasília |
|---|---|---|---|---|---|---|
| 2022 | 4.417 | 1.153 | 53.711 | 3.746 | 834 | 1.181 |
| 2023 | 4.654 | 916 | 59.366 | 4.095 | 896 | 1.286 |
| 2024 | 4.816 | 754 | 65.346 | 4.500 | 1.008 | 1.329 |

**Conclusão:** o critério de concorrência é viável por município. Usar a **variável `2585` (empresas)**, que não tem sigilo.
A variável `707` (pessoal ocupado) **não serve** como critério: em 2024, 2.518 municípios vêm com `"X"` (sigilo).
Na silver, `"-"` vira nulo com flag `zero_absoluto`; na gold é lido como **0 academias**.

### 2.4 Banco Central — SGS (`https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados`)

Parâmetros: `formato=json&dataInicial=dd/MM/aaaa[&dataFinal=dd/MM/aaaa]`. Resposta: `[{"data": "dd/MM/aaaa", "valor": "11.75"}]`.

| Série | Indicador | Periodicidade | Obrigatória |
|---|---|---|---|
| **432** | Meta da Selic (% a.a.) | diária | sim |
| **10813** | Dólar comercial — venda (R$) | dias úteis | sim |
| 433 | IPCA mensal (%) — conferência contra o IBGE 7060 | mensal | não (opcional) |

Armadilhas:
- Séries diárias: **datas obrigatórias** (sem datas → HTTP 406) e **janela máxima de 10 anos** por chamada.
- Data em formato ISO → HTTP 400. Período sem dado → **HTTP 404 = "nada novo"**, não é erro.
- A série 432 traz **datas futuras** (a meta vale até o próximo Copom).
- Código inexistente pode devolver HTTP 200 com HTML depois de ~30 s → validar `content-type: application/json` e usar timeout.
- Evitar `/ultimos/N` (limite de 20, ordem inconsistente entre séries).
- Para algumas URLs exatas o SGS devolve **HTTP 304 vazio**, mesmo sem cabeçalho condicional (visto na série 432 com
  `dataInicial=01/01/2025`). O código pede a mesma janela com a data final 1, 2 ou 3 dias depois; a silver descarta datas futuras.

---

## 3. Modelo de dados

Convenções (detalhe em `agents.md`): `snake_case`, português sem acento, chaves `*_id`, datas de controle `*_em` (`timestamptz`), dimensões `dim_*`, fatos `fato_*`.

### 3.1 Bronze — dado bruto

DDL implementado em `sql/bronze/` (rodar como `etl_radar` com `python -m src.transformacao.criar_estrutura`; idempotente):

| Arquivo | Objeto | Para quê |
|---|---|---|
| `01_execucao.sql` | `bronze.execucao` | log de cada carga: uma linha por recurso processado numa rodada |
| `02_api_resposta.sql` | `bronze.api_resposta` | o "cofre": uma linha por chamada bem-sucedida, JSON como veio; **só `INSERT`** (`UPDATE`, `DELETE` e `TRUNCATE` revogados até do dono) |
| `03_trava_carga.sql` | `bronze.trava_carga` | linha única que impede duas cargas ao mesmo tempo (seção 8.3) |
| `04_vw_ultimo_periodo.sql` | `bronze.vw_ultimo_periodo` | último período (IBGE) ou última data (BCB) salvos — base do incremental |

```sql
-- Uma linha por chamada bem-sucedida à API. Contrato único para os dois cenários (seção 8).
CREATE TABLE bronze.api_resposta (
    resposta_id        bigserial    PRIMARY KEY,
    origem_carga       text         NOT NULL CHECK (origem_carga IN ('python', 'n8n')),
    fonte              text         NOT NULL CHECK (fonte IN ('IBGE', 'BCB')),
    recurso            text         NOT NULL,      -- 'ibge_agregado_6579', 'ibge_municipios', 'bcb_sgs_432'...
    endpoint           text         NOT NULL,      -- caminho chamado, sem o host
    parametros         jsonb        NOT NULL,      -- períodos, variáveis, localidades, datas
    url                text         NOT NULL,      -- URL completa, para reproduzir a chamada
    lote               text         NOT NULL,      -- ano, ano-UF, janela de datas ou 'snapshot'
    modificacao_fonte  date,                       -- IBGE: `modificacao` do período (base do incremental)
    http_status        smallint     NOT NULL,
    payload            jsonb        NOT NULL,      -- resposta original, inteira
    -- md5 calculado pelo Postgres sobre o jsonb (forma canônica): igual nos dois cenários
    payload_hash       text         GENERATED ALWAYS AS (md5(payload::text)) STORED,
    execucao_id        bigint       REFERENCES bronze.execucao (execucao_id),
    ingerido_em        timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT uq_api_resposta UNIQUE (origem_carga, recurso, lote, payload_hash)
);

-- Log de cada carga: uma linha por recurso processado numa rodada.
CREATE TABLE bronze.execucao (
    execucao_id      bigserial    PRIMARY KEY,
    rodada_id        uuid         NOT NULL,      -- agrupa os recursos de uma mesma carga
    origem_carga     text         NOT NULL CHECK (origem_carga IN ('python', 'n8n')),
    disparado_por    text         NOT NULL,      -- 'manual' | 'agenda_n8n'
    modo             text         NOT NULL CHECK (modo IN ('inicial', 'incremental')),
    recurso          text         NOT NULL,      -- 'rodada' = registro de rodada ignorada pela trava
    iniciado_em      timestamptz  NOT NULL DEFAULT now(),
    finalizado_em    timestamptz,
    status           text         NOT NULL DEFAULT 'em_andamento',
                     -- 'em_andamento' | 'sucesso' | 'sem_novidade' | 'erro' | 'ignorada_trava'
    chamadas_ok      integer      NOT NULL DEFAULT 0,   -- inclui o 404 "nada novo" do BCB
    chamadas_erro    integer      NOT NULL DEFAULT 0,   -- falharam depois de todas as tentativas
    respostas_novas  integer      NOT NULL DEFAULT 0,   -- gravadas (repetidas não contam)
    mensagem         text
);

-- Último período salvo por processo, recurso e lote.
CREATE VIEW bronze.vw_ultimo_periodo AS
SELECT origem_carga, recurso, lote,
       max(modificacao_fonte) AS modificacao_fonte,                 -- IBGE
       max(CASE WHEN fonte = 'BCB' THEN (SELECT max(to_date(e ->> 'data', 'DD/MM/YYYY'))
                                         FROM jsonb_array_elements(payload) e) END) AS ultima_data,  -- BCB
       max(ingerido_em) AS ingerido_em, count(*) AS respostas
FROM bronze.api_resposta
GROUP BY origem_carga, recurso, lote;
```

Regras de gravação: status da execução = `sucesso` se gravou ao menos uma resposta nova, `sem_novidade` se todas as respostas
já existiam (mesmo hash) ou a fonte respondeu "nada novo", `erro` se alguma chamada falhou depois das tentativas.
Cada cenário filtra a própria `origem_carga` na view, para um não "esconder" o período novo do outro.

### 3.2 Silver — modelo estrela

DDL implementado em `sql/silver/` (rodar como `etl_radar` com `python -m src.transformacao.criar_estrutura`; idempotente):

| Arquivo | Conteúdo |
|---|---|
| `01_dimensoes.sql` | `dim_regiao`, `dim_uf`, `dim_municipio`, `dim_calendario` (gerada, 2000–2030) e `dim_indicador` (catálogo com a origem de cada indicador) |
| `02_fatos.sql` | `fato_indicador_municipal` e `fato_indicador_macro` |
| `03_funcoes_apoio.sql` | `silver.valor_numerico()`, `silver.flag_valor()` e `silver.bronze_vigente(origem)` |
| `04_atualizar_silver.sql` | `silver.atualizar(origem)`: a transformação bronze → silver (seção 4) |
| `05_testes_qualidade.sql` | `silver.vw_testes_qualidade`: testes do "pronto quando" (esperado × obtido) |

```mermaid
erDiagram
    dim_regiao ||--o{ dim_uf : contem
    dim_uf ||--o{ dim_municipio : contem
    dim_municipio ||--o{ fato_indicador_municipal : mede
    dim_indicador ||--o{ fato_indicador_municipal : descreve
    dim_indicador ||--o{ fato_indicador_macro : descreve
    dim_calendario ||--o{ fato_indicador_macro : data
```

```sql
CREATE TABLE silver.dim_regiao (
    regiao_id smallint PRIMARY KEY, regiao_sigla char(2) NOT NULL UNIQUE, regiao_nome text NOT NULL,
    bronze_id bigint NOT NULL, atualizado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE silver.dim_uf (
    uf_id smallint PRIMARY KEY, uf_sigla char(2) NOT NULL UNIQUE, uf_nome text NOT NULL,
    regiao_id smallint NOT NULL REFERENCES silver.dim_regiao,
    bronze_id bigint NOT NULL, atualizado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE silver.dim_municipio (
    municipio_id              integer  PRIMARY KEY,          -- 7 dígitos (código IBGE)
    municipio_nome            text     NOT NULL,
    uf_id                     smallint NOT NULL REFERENCES silver.dim_uf,
    regiao_id                 smallint NOT NULL REFERENCES silver.dim_regiao,
    regiao_intermediaria_id   integer,  regiao_intermediaria_nome text,
    regiao_imediata_id        integer,  regiao_imediata_nome      text,   -- usada pelo prd
    mesorregiao_id            integer,  mesorregiao_nome          text,
    microrregiao_id           integer,  microrregiao_nome         text,   -- pode ser nulo
    latitude                  numeric(9,6), longitude numeric(9,6),          -- centroide (API de Malhas v4)
    coordenada_bronze_id      bigint,                                        -- resposta da malha na bronze
    bronze_id                 bigint   NOT NULL,
    atualizado_em             timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE silver.dim_calendario (
    data date PRIMARY KEY, ano smallint NOT NULL, trimestre smallint NOT NULL, mes smallint NOT NULL,
    ano_mes integer NOT NULL, nome_mes text NOT NULL, dia_semana smallint NOT NULL, eh_fim_de_semana boolean NOT NULL
);

CREATE TABLE silver.dim_indicador (
    indicador_id   text PRIMARY KEY,      -- 'populacao_estimada', 'pib', 'academias_qtd', 'selic_meta'...
    indicador_nome text NOT NULL,
    fonte          text NOT NULL,         -- 'IBGE' | 'BCB'
    agregado       integer,               -- IBGE: tabela    } a transformação usa estas três
    variavel       integer,               -- IBGE: variável  } colunas para ligar a resposta
    serie_bcb      integer,               -- BCB: série SGS  } da bronze ao indicador
    codigo_origem  text NOT NULL,         -- forma legível: '9418/2585 · 12762[117856]'
    unidade        text NOT NULL,         -- 'pessoas', 'mil R$', 'R$', '%', '% a.a.', 'unidades'
    periodicidade  text NOT NULL,         -- 'anual' | 'decenal' | 'mensal' | 'diaria'
    nivel          text NOT NULL,         -- 'municipal' | 'macro'
    descricao      text,
    UNIQUE (agregado, variavel), UNIQUE (serie_bcb)
);

CREATE TABLE silver.fato_indicador_municipal (
    municipio_id  integer  NOT NULL REFERENCES silver.dim_municipio,
    indicador_id  text     NOT NULL REFERENCES silver.dim_indicador,
    ano           smallint NOT NULL,
    valor         numeric,                -- nulo quando a fonte mandou símbolo
    flag_valor    text     NOT NULL,      -- 'ok' | 'zero_absoluto' | 'nao_disponivel' | 'sigilo' | 'nao_se_aplica' | 'invalido'
    bronze_id     bigint   NOT NULL,
    atualizado_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (municipio_id, indicador_id, ano)
);

CREATE TABLE silver.fato_indicador_macro (
    indicador_id  text NOT NULL REFERENCES silver.dim_indicador,
    data          date NOT NULL REFERENCES silver.dim_calendario,   -- mensal: 1º dia do mês
    valor         numeric,
    flag_valor    text NOT NULL,
    bronze_id     bigint NOT NULL,
    atualizado_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (indicador_id, data)
);
```

`bronze_id` existe em toda linha que vem da bronze (regiões, UFs, municípios e fatos). `dim_calendario` e `dim_indicador`
são geradas pelo próprio DDL e não têm origem na bronze.

Indicadores em `dim_indicador`:

| indicador_id | Origem | Nível | Unidade |
|---|---|---|---|
| `populacao_estimada` | IBGE 6579/9324 | municipal | pessoas |
| `populacao_censo`, `area_km2`, `densidade_demografica` | IBGE 4714/93, 6318, 614 | municipal | pessoas, km², hab/km² |
| `pib` | IBGE 5938/37 | municipal | mil R$ |
| `vab_total`, `vab_agropecuaria`, `vab_industria`, `vab_servicos`, `vab_administracao_publica`, `impostos_liquidos` | IBGE 5938/498, 513, 517, 6575, 525, 543 (até 2021) | municipal | mil R$ |
| `renda_dom_per_capita` | IBGE 10295/13431 | municipal | R$ |
| `academias_qtd` | IBGE 9418/2585 · CNAE 93.13-1 | municipal | unidades |
| `salario_medio` | IBGE 9509/10143 | municipal | R$ |
| `ipca_mensal`, `ipca_12m` | IBGE 7060/63 e 2265 · 315[7169] | macro | % |
| `selic_meta` | BCB SGS 432 | macro | % a.a. |
| `dolar_venda` | BCB SGS 10813 | macro | R$ |
| `ipca_mensal_bcb` | BCB SGS 433 (conferência do IPCA do IBGE) | macro | % |

### 3.3 Gold — tabelas de consumo

Implementada em `sql/gold/` (rodar como `etl_radar` com `python -m src.transformacao.criar_estrutura`; idempotente).
Cada tabela responde a perguntas do `prd.md`, anotadas no comentário da tabela no banco.

| Arquivo | Conteúdo |
|---|---|
| `01_tabelas.sql` | as tabelas abaixo + os pesos de `ranking_criterio` e os parâmetros de `parametro_ranking` |
| `02_atualizar_gold.sql` | `gold.atualizar(populacao_minima)`: recalcula a gold inteira a partir da silver (seção 5) |
| `03_testes_qualidade.sql` | `gold.vw_testes_qualidade` (14 testes) e `gold.vw_rastreio_exemplo` (um número da gold até a bronze) |
| `04_permissoes.sql` | `web_leitor` só com `SELECT` nas tabelas de consumo, RLS, views e função fora da API, recarga do schema da API |

| Tabela | Pergunta | Grão | Colunas principais |
|---|---|---|---|
| `gold.indicadores_municipio` | P1, P3, P4, P9 | 1 linha por município (5.571) | `latitude`, `longitude`, `faixa_renda`, `populacao_projetada`/`ano_projecao`, `densidade_referencia`, `lacuna_academias`, `estimativa` (aviso), `populacao`/`populacao_ano`, `populacao_censo_2022`, `crescimento_pop_aa`, `pib_mil_reais`/`pib_ano`, `pib_per_capita`, `pib_per_capita_tendencia`/`tendencia_ano_inicial`, `renda_dom_per_capita`/`renda_ano`, `academias_qtd`/`academias_ano`, `academias_por_10mil_hab`, `salario_medio`/`salario_ano`, `regiao_imediata_id`/`_nome` |
| `gold.ranking_expansao` | P2, P5, P8 | 1 linha por município do universo (≥ 50 mil hab.; 687) | `nota_mercado`, `nota_poder_compra`, `nota_espaco_competitivo`, `nota_crescimento`, `nota_riqueza_nivel`, `nota_riqueza_tendencia`, `nota_riqueza` (média ponderada das duas), `nota_mercado_formal`, `nota_final`, `posicao_brasil`, `posicao_regiao`, `posicao_uf`, `dados_incompletos`, `criterios_ausentes`, `peso_considerado`, `verificar_concorrencia`, `elegivel_recomendacao`, `recomendado_top5`, `ordem_recomendacao`, `regiao_imediata_id`/`_nome`, `latitude`, `longitude`, `versao_pesos` |
| `gold.ranking_criterio` | P8 | 1 linha por componente (7) | `criterio` (a nota fica em `nota_<criterio>`), `grupo` (critério do prd: `riqueza` agrupa nível e tendência), `descricao`, `fonte`, `peso`, `sentido`, `ordem`, `versao_pesos` |
| `gold.parametro_ranking` | P7, P8, P9 | 1 linha por parâmetro | `unidades_recomendadas` (5), `nota_minima_poder_compra` (50), `ano_projecao_populacao` (2028), `faixas_renda_referencia` (5) e os do semáforo: `semaforo_janela_dias` (30), `semaforo_alerta_cambio_30d_pct` (5), `semaforo_limiar_selic_pp` (0,5), `semaforo_teto_ipca_pct` (4,5), `semaforo_limiar_dolar_12m_pct` (10), `semaforo_meses_tendencia_ipca` (3) |
| `gold.contexto_macro` | P6 | 1 linha por mês | `mes`, `mes_parcial`, `selic_meta`/`selic_ultima_data`, `selic_var_12m_pp`, `dolar_medio` (média do mês, parcial no mês corrente), `dolar_ultimo`/`dolar_ultimo_data` (último fechamento do mês), `dolar_var_12m_pct`, `dolar_var_1m_pct`, `ipca_mensal`, `ipca_12m` |
| `gold.momento_expansao` | P7 | 1 linha por mês fechado com os três sinais + o mês corrente (parcial) | `sinal_juros`, `sinal_inflacao`, `sinal_cambio` (`verde`/`amarelo`/`vermelho`), `pontuacao`, `recomendacao`, `justificativa`, `mes_parcial`, `ref_juros`, `ref_cambio`, `ref_inflacao` |
| `gold.momento_atual` | P7 | 1 linha | `ref_juros`, `ref_cambio`, `ref_inflacao`, `janela_dias`, `selic_meta`/`_12m_antes`/`selic_var_12m_pp`, `dolar_ultimo`, `dolar_media_janela`/`_12m_antes`/`dolar_var_12m_pct`, `dolar_media_janela_anterior`/`dolar_var_janela_pct`, `alerta_cambio_curto_prazo`, `ipca_12m`/`ipca_12m_meses_antes`/`ipca_desacelerando`, sinais, `pontuacao`, `recomendacao`, `justificativa` (com as datas) |

```sql
-- Trecho do DDL (completo em sql/gold/01_tabelas.sql)
CREATE TABLE gold.ranking_expansao (
    municipio_id              integer       PRIMARY KEY,
    municipio_nome            text          NOT NULL,
    uf_sigla                  char(2)       NOT NULL,
    regiao_sigla              char(2)       NOT NULL,
    regiao_imediata_id        integer       NOT NULL,
    regiao_imediata_nome      text          NOT NULL,
    populacao                 integer       NOT NULL,
    nota_mercado              numeric(5,2),  -- ... uma coluna por componente (0 a 100)
    nota_final                numeric(5,2)  NOT NULL,
    posicao_brasil            integer       NOT NULL,
    posicao_regiao            integer       NOT NULL,
    posicao_uf                integer       NOT NULL,
    dados_incompletos         boolean       NOT NULL DEFAULT false,  -- faltou critério: peso redistribuído
    criterios_ausentes        text[],
    peso_considerado          numeric(4,3)  NOT NULL,                -- 1.000 = completo
    verificar_concorrencia    boolean       NOT NULL DEFAULT false,  -- zero academias registradas
    recomendado_top5          boolean       NOT NULL DEFAULT false,  -- lista das 5 unidades (P8)
    ordem_recomendacao        smallint,
    versao_pesos              text          NOT NULL,
    calculado_em              timestamptz   NOT NULL DEFAULT now()
);
```

Relacionamentos lógicos: `gold.*.municipio_id` → `silver.dim_municipio`; `gold.contexto_macro.mes` → `silver.dim_calendario`.
A função `gold.atualizar()` e as views de teste e de rastreio ficam **fora da API REST** (sem permissão para `web_leitor`).

### 3.4 Papéis e permissões

| Papel | Uso | Permissões |
|---|---|---|
| `etl_radar` | scripts de ingestão/transformação e credencial Postgres do n8n | `LOGIN`; leitura e escrita em `bronze`, `silver` e `gold`; sem superusuário. Na bronze, só `INSERT` e `SELECT` |
| `web_leitor` | API REST lida pelo dashboard | `NOLOGIN`; `USAGE` no schema `gold` e `SELECT` nas tabelas da gold; nada em `bronze` e `silver` |
| `anon` | acesso anônimo da API | nenhum acesso à gold |

```sql
CREATE ROLE web_leitor NOLOGIN;
GRANT USAGE ON SCHEMA gold TO web_leitor;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO web_leitor;
ALTER DEFAULT PRIVILEGES FOR ROLE etl_radar IN SCHEMA gold GRANT SELECT ON TABLES TO web_leitor;
GRANT web_leitor TO authenticator;          -- papel que a API REST assume ao validar o token

-- RLS como defesa extra (repetir para cada tabela da gold)
ALTER TABLE gold.ranking_expansao ENABLE ROW LEVEL SECURITY;
CREATE POLICY leitura_web ON gold.ranking_expansao FOR SELECT TO web_leitor USING (true);
```

A API REST expõe **somente** o schema `gold`; `bronze`, `silver` e `public` não aparecem nela.
Script completo e idempotente (schemas, papéis, permissões e RLS em todas as tabelas da gold): `infra/sql/00_schemas_roles.sql`.

---

## 4. Regras bronze → silver

1. **Fonte única por lote:** para cada `(recurso, lote)` usa-se só a resposta mais recente da bronze (`DISTINCT ON ... ORDER BY ingerido_em DESC`).
   O parâmetro `ORIGEM_CARGA_SILVER` (`'python'`, `'n8n'` ou `'qualquer'`, padrão `'qualquer'`) restringe a leitura a um cenário,
   para comparar as duas ingestões; silver e gold não mudam de estrutura conforme o cenário.
2. **Achatar o JSON do IBGE:** `payload[] → resultados[] → classificacoes / series[] → serie{periodo: valor}`. Cada linha da silver = localidade + período + variável (+ categoria) + valor.
3. **Períodos:** `"2024"` → `ano = 2024`; `"202610"` → `data = 2026-10-01`. BCB: `"dd/MM/aaaa"` → `date`.
4. **Tipos:** texto → `numeric` (o IBGE e o BCB usam ponto decimal). Códigos de localidade → `integer`.
5. **Ausentes:** `"-"` → nulo + `zero_absoluto`; `"..."` → nulo + `nao_disponivel`; `"X"` → nulo + `sigilo`; `".."` → nulo + `nao_se_aplica`.
6. **Códigos padronizados:** `municipio_id` com 7 dígitos; `uf_id = municipio_id / 100000`; `regiao_id = uf_id / 10`. Todo fato precisa casar com `dim_municipio` (checagem de integridade ao fim da carga).
7. **Duplicados:** chave primária + `INSERT ... ON CONFLICT DO UPDATE` → a versão mais nova vence (o IBGE revisa o PIB de anos anteriores).
8. **Selic com datas futuras:** a silver guarda só `data <= current_date`; o futuro continua na bronze.
9. **Unidades preservadas:** PIB fica em mil R$ na silver (unidade em `dim_indicador`); conversões acontecem na gold.
10. **Rastreio:** toda linha leva `bronze_id`.

**Implementação (um único caminho para os cenários A e B).** As regras acima estão na função `silver.atualizar(origem)`
(`sql/silver/04_atualizar_silver.sql`). O cenário A a chama por `python -m src.transformacao.executar`; o cenário B chama
o mesmo job ou faz `SELECT * FROM silver.atualizar()` pelo nó Postgres. A função:

- materializa a resposta vigente de cada `(recurso, lote)` (`silver.bronze_vigente`);
- liga cada variável do IBGE ao indicador por `parametros->>'agregado'` + `id` da variável, e cada série do BCB por
  `parametros->>'serie'` — **por isso os dois cenários gravam esses campos em `parametros`**;
- usa `jsonb_array_elements` / `jsonb_each_text` para achatar o JSON; `DISTINCT ON` + `ON CONFLICT DO UPDATE` para não
  duplicar; só reescreve uma linha quando valor, flag ou `bronze_id` mudaram (rodar de novo sem bronze nova grava 0 linhas);
- devolve as linhas gravadas por tabela.

**Testes de qualidade** (`silver.vw_testes_qualidade`, rodados pelo `executar.py`, que termina com erro se algum falhar):
5 regiões · 27 UFs · 5.571 municípios · nenhum município sem região imediata · nenhum município citado na bronze sem par
na `dim_municipio` · todo indicador com linhas · nenhum valor com formato inválido · coerência entre valor nulo e flag ·
toda linha rastreável até a bronze · nenhuma data futura nos fatos macro · IPCA do IBGE igual ao do BCB em todos os meses.

## 5. Regras silver → gold

### 5.1 `gold.contexto_macro`, `gold.momento_expansao` e `gold.momento_atual`
- Selic do mês = meta vigente no último dia com dado no mês (`selic_ultima_data`); dólar do mês = média dos dias úteis
  (parcial no mês corrente) e último fechamento do mês (`dolar_ultimo`, `dolar_ultimo_data`); IPCA = variáveis 63 e 2265 do IBGE.
- Variações de 12 meses: Selic em pontos percentuais; dólar em %. `dolar_var_1m_pct` = média do mês contra a do mês anterior.
- Semáforo (limiares e janela em `gold.parametro_ranking`; regras em funções pequenas `gold.sinal_juros/_inflacao/_cambio`):

| Sinal | Verde (+1) | Amarelo (0) | Vermelho (−1) |
|---|---|---|---|
| Juros | Selic caiu ≥ 0,5 p.p. em 12 meses | variação entre −0,5 e +0,5 p.p. | Selic subiu > 0,5 p.p. |
| Inflação | IPCA 12m ≤ 4,5% e desacelerando (vs. 3 meses antes) | só uma das duas condições | IPCA 12m > 4,5% e acelerando |
| Câmbio | dólar ≤ 12 meses antes | alta de até 10% | alta > 10% |

  Pontuação = soma dos três sinais: **≥ +2 → "Expandir agora"**, **0 a +1 → "Expandir com cautela"**, **≤ −1 → "Esperar"**.
- "Desacelerando" = IPCA 12m menor que o de 3 meses antes.
- **Alerta de alta de curto prazo no câmbio:** média do dólar nos últimos 30 dias > 5% acima da média dos 30 dias anteriores.
  Com alerta, o câmbio não pode ser verde: amarelo, ou vermelho se a variação em 12 meses for de alta. Escolhemos **média contra
  média** (e não fechamento contra fechamento de 30 dias antes) porque um único dia atípico não dispara o alerta.
- **`gold.momento_atual` (o semáforo exibido):** câmbio = média dos 30 dias corridos até o último fechamento (`ref_cambio`)
  contra a mesma janela 12 meses antes e contra os 30 dias anteriores; juros = meta da Selic no último dia disponível
  (`ref_juros`) contra a vigente 12 meses antes; inflação = último IPCA publicado (`ref_inflacao`). A justificativa traz as datas.
- **`gold.momento_expansao` (histórico):** meses fechados com IPCA, pela média/meta do mês; o alerta usa `dolar_var_1m_pct`.
  O mês do momento atual entra no histórico como **parcial** (`mes_parcial = true`), com os mesmos sinais.
- **Exemplo (26/11/2026):** dólar médio de R$ 5,63 nos 30 dias até 26/11 (último fechamento R$ 5,744), +5,4% em 12 meses e
  +10,4% sobre os 30 dias anteriores → alerta → câmbio vermelho; Selic 13,75% (−1,25 p.p.) → verde; IPCA 4,63% até 10/2026,
  acima do teto e sem desacelerar → vermelho. Pontuação −1 → **"Esperar"**. (A regra anterior, só com outubro fechado, dava câmbio verde.)
- Testes da gold 20 a 25: uma linha no momento atual; datas de referência iguais ao último fechamento do dólar, à última meta da
  Selic e ao último IPCA da silver; nenhum câmbio verde com alerta de curto prazo; nenhum mês parcial fora do mês corrente.

### 5.2 `gold.indicadores_municipio`
- **População:** estimativa mais recente do 6579. População de 2022 = Censo (4714). População de 2023 (inexistente na fonte) = interpolação geométrica `√(pop2022 × pop2024)`, usada só para o PIB per capita de 2023.
- **Crescimento:** `(pop_último_ano / pop_censo_2022)^(1/(último_ano − 2022)) − 1`.
  Não usar 2021 como base: as estimativas até 2021 eram projetadas a partir do Censo 2010 e ficaram acima do Censo 2022
  (Brasil: 213,3 mi estimados em 2021 × 203,1 mi recenseados em 2022), o que distorceria o crescimento.
- **PIB per capita** = `pib_mil_reais × 1000 / populacao` do mesmo ano.
- **Tendência** = CAGR do PIB per capita entre o 1º e o último ano de uma janela de 5 anos do PIB (hoje 2019 → 2023):
  `(pib_pc_último / pib_pc_primeiro)^(1/4) − 1`. A janela atravessa a pandemia (2020); a taxa média do período não é distorcida
  pela queda e pela retomada de anos isolados, por isso não se usa a variação ano a ano. Sem PIB em algum dos dois anos → nulo.
  Como o ranking usa percentil, deflacionar pelo IPCA não muda a ordem (a inflação é a mesma para todos os municípios).
- **Academias por 10 mil hab.** = `academias_qtd / populacao_do_mesmo_ano × 10000`; `zero_absoluto` = 0 academias.

### 5.3 `gold.ranking_expansao`
- **Universo:** municípios com população estimada ≥ 50 mil (687 municípios na estimativa de 2026). Limite no `CONFIG`.
- **Componentes e pesos** (`gold.ranking_criterio`, iguais ao `prd.md`): mercado 0,25 · poder de compra 0,25 · espaço competitivo 0,20 ·
  crescimento 0,15 · riqueza (nível) 0,05 · riqueza (tendência) 0,05 · mercado formal 0,05.
- **Nota de cada componente:** percentil no universo × 100, com empates recebendo o percentil da **posição média** do empate:
  `nota = 100 × (posição_média − 1) / (n − 1)`, onde `posição_média = rank() + (tamanho_do_empate − 1) / 2` em ordem crescente.
  Quando "menor é melhor", `nota = 100 − nota`. Componentes sem dado ficam fora do cálculo (não entram em `n`).
- **Espaço competitivo:** antes da nota, `academias_por_10mil_hab` é limitado aos percentis 5% e 95% do universo
  (`percentile_cont(0.05)` e `(0.95)`; abaixo do P5 vira P5, acima do P95 vira P95). Todas as cidades no limite inferior empatam
  e recebem a mesma nota — a "nota do limite", menor que 100. Cidade com 0 academias recebe essa nota e `verificar_concorrencia = true`.
- **Dado faltante:** o peso do componente sem dado é redistribuído proporcionalmente:
  `nota_final = Σ(peso × nota dos disponíveis) / Σ(pesos disponíveis)`; `peso_considerado` guarda o denominador,
  `criterios_ausentes` lista o que faltou e `dados_incompletos = true`.
- **Posições:** `posicao_brasil` e `posicao_uf` por `nota_final` decrescente (desempate pela maior população).
- **5 unidades recomendadas (P8):** primeiro marca `elegivel_recomendacao = nota_poder_compra >= nota_minima_poder_compra`
  (trava de renda; valor em `gold.parametro_ranking`, hoje 50 = percentil 50 do universo). Depois percorre só as elegíveis em
  ordem de `posicao_brasil` e escolhe a cidade se a sua `regiao_imediata_id` ainda não foi escolhida, até completar
  `unidades_recomendadas` (`recomendado_top5`, `ordem_recomendacao`). O ranking completo não é filtrado nem reordenado.
- **Testes da gold:** soma dos pesos = 1; `peso_considerado` entre 0 e 1; notas entre 0 e 100; todos os municípios do universo
  com nota; exatamente 5 recomendados, em 5 regiões imediatas diferentes e nenhum abaixo da trava de renda.
- A gold é **recalculada inteira** a cada execução (são poucos milhares de linhas; leva cerca de 2 s).
- **Execução:** `python -m src.transformacao.executar` roda silver e gold em sequência, cada uma com seus testes;
  `--camadas gold` roda só a gold. No cenário B, o n8n aciona o mesmo job (ou `SELECT * FROM gold.atualizar()`).

---

### 5.4 Estimativas do simulador (P9) — em `gold.indicadores_municipio`, para todos os municípios

- **Faixa de renda:** cortes nos quintis (`percentile_cont` 0,2/0,4/0,6/0,8) da renda domiciliar per capita do **universo**;
  cada município (de qualquer porte) recebe a faixa 1 a 5 por `width_bucket`. Número de faixas em `parametro_ranking`.
- **Densidade de referência:** mediana das academias por 10 mil hab. das cidades **do universo** na mesma faixa, com a densidade
  limitada a P5–P95 (os mesmos limites do espaço competitivo).
- **Lacuna de academias:** `round((densidade_referencia − densidade_atual_limitada_P5_P95) × populacao / 10000)`.
  Positiva = espaço estimado para novas academias; negativa = saturada.
- **População projetada:** `round(populacao × (1 + crescimento_pop_aa) ^ (ano_projecao − populacao_ano))`; ano em `parametro_ranking`.
- **Aviso:** a coluna `estimativa` leva o texto "Estimativa simples, não é previsão garantida…" em toda linha com estimativa.
- Sem renda (município criado depois do Censo 2022) → sem faixa, referência e lacuna; sem crescimento → sem projeção.
- Testes 15 a 19 da gold: 5.571 municípios com coordenada, nenhuma fora do retângulo do Brasil (lat −34 a 6; lon −74,5 a −28),
  as 5 faixas com referência, nenhum município com dados completos sem lacuna, ranking inteiro com coordenada.

## 6. Limite da API do IBGE e estratégia de lotes

O IBGE não documenta o limite, mas nos testes ele fica em **≈ 100 mil valores por chamada**
(valores = períodos × variáveis × localidades × categorias). Acima disso a API devolve HTTP 500 genérico.

Regra do código (`CONFIG: LIMITE_VALORES_POR_CHAMADA = 50_000`, metade do limite como margem):
1. Estimar o tamanho da chamada antes de fazer.
2. Se passar do limite: dividir **por ano**; se um ano ainda passar, dividir **por UF** (`N6[N3[uf]]`).
3. Cada lote é uma linha na bronze (`lote = '2024'` ou `lote = '2024-MG'`).
4. **No cenário B (n8n)** os agregados municipais são pedidos **sempre por ano × UF** (`N6[N3[uf]]`, 27 chamadas por ano):
   respostas menores evitam estourar a memória do n8n, que segura os itens em RAM. O JSON é gravado inteiro, sem ser "explodido" em itens.

| Agregado | Lote padrão | Valores por chamada |
|---|---|---|
| 6579 população | 1 ano × N6[all] | ≈ 5.570 |
| 5938 PIB | 1 ano × N6[all] | ≈ 5.570 |
| 9418 CNAE 93.13-1 | 1 ano × N6[all] × 1 categoria | ≈ 5.570 (11–22 s) |
| 9509 salário médio | 1 ano × N6[all] | ≈ 5.570 |
| 4714 / 10295 Censo | carga única × N6[all] | ≤ 16.710 |
| 7060 IPCA | todos os meses × N1 | < 200 |

Boas práticas de chamada: timeout de 60 s (120 s para o 9418), 3 tentativas com espera crescente (2 s, 4 s, 8 s),
validar `content-type: application/json`, `User-Agent` próprio do projeto e `try/except` com registro em `bronze.execucao`.

## 7. Carga de dados novos (incremental)

| Fonte | Carga inicial | Carga incremental (semanal) |
|---|---|---|
| Localidades | 1 chamada por recurso | recarga completa (barata); a silver atualiza por `UPSERT` |
| Agregados anuais (6579, 5938, 9418, 9509) | 1 chamada por ano | `GET /{agregado}/periodos` → compara `id` e `modificacao` com `bronze.vw_ultimo_periodo` (filtrada pela própria `origem_carga`) → baixa só período **novo** ou **modificado** |
| Censo (4714, 10295) | carga única | só se `/periodos` mostrar `modificacao` mais nova |
| IPCA (7060) | um lote por ano (meses AAAAMM agrupados) | mesma regra dos anuais: o lote do ano é baixado de novo quando um mês dele é novo ou modificado (maior `modificacao` dos meses) |
| BCB diárias (432, 10813) | janelas de até 10 anos desde `DATA_INICIO` (CONFIG, proposta: 01/01/2015) | `dataInicial = última data salva − 30 dias`, sem `dataFinal`; HTTP 404 = nada novo |

Depois de gravar na bronze, a execução roda `silver` → `gold` só se houve resposta nova; senão registra `status = 'sem_novidade'`.
As regras desta seção e da seção 6 (lotes, limites, janelas, retry) valem **igualmente para os dois cenários** da seção 8.

## 8. Ingestão e automação: dois cenários

O n8n roda **autohospedado via Docker** e agenda a atualização semanal no fuso **America/Sao_Paulo**.
A diferença entre os cenários é **quem chama as APIs e grava na bronze**. Os dois são construídos na trilha de desenvolvimento e
comparados; o squad escolhe um para a entrega (⏳).

**O que é comum aos dois**
- Mesmo contrato da bronze: `bronze.api_resposta` + `bronze.execucao`, com `origem_carga = 'python'` ou `'n8n'` (seção 3.1).
- Mesmas regras de lote, limite do IBGE, janelas do BCB, retry e carga incremental (seções 6 e 7).
- **Transformação num único caminho de código:** as regras da silver e da gold ficam em SQL versionado (`sql/silver/`, `sql/gold/`)
  e são executadas sempre pelo mesmo programa, `src/transformacao/executar.py`. Nos dois cenários o n8n o aciona pelo job
  `transformar` do container de ETL (seção 8.1). Não existe uma segunda versão das regras dentro do n8n.
- **Trava contra execução simultânea** (seção 8.3) e agendas em horários diferentes.

### 8.1 Cenário A — container de ETL em Python (o n8n agenda e dispara)

Um container de ETL (imagem Python fixa, com o `requirements.txt` instalado e o código deste repositório montado só para leitura)
fica na mesma rede Docker interna do n8n e do banco. Ele **não publica porta** nem fica exposto fora do servidor.
Um disparador HTTP interno (`infra/radar-etl/disparador.py`) executa apenas **jobs fixos** — nenhum comando livre vem da requisição:

| Chamada | Executa |
|---|---|
| `POST /rodar/cenario-a` | `python -m src.ingestao.carga_incremental --disparado-por agenda_n8n` e, se der certo, `python -m src.transformacao.executar` (com a trava do banco pega de novo) |
| `POST /rodar/transformar` | só `python -m src.transformacao.executar`; usado pelo cenário B e só aceito com a trava em `em_uso_por = 'n8n'` (senão 409 `sem_trava`) |
| `GET /saude` | `livre` ou `ocupado` (um job por vez no container) |

Os `POST` exigem o header `X-Radar-Token`, guardado no n8n como credencial *Header Auth*. A resposta é síncrona (JSON com
`status`, etapas e código de saída de cada script, resumo de `bronze.execucao`, duração e commit): **200** sucesso,
**409** ocupado ou trava, **500** erro, **401** token.

Workflow **Radar · Cenário A** (`n8n/radar-expansao-cenario-a.json`):

```mermaid
flowchart LR
    T["Schedule Trigger<br/>segunda 06:00"] --> S["GET /saude"]
    S -- livre --> P["POST /rodar/cenario-a<br/>timeout 15 min"]
    P -- 200 --> OK["Resumo do sucesso"]
    P -- "409 / erro" --> R["Postgres: registra em<br/>bronze.execucao"]
    S -- "ocupado / fora" --> R
    R -- 409 --> F["Fim sem rodar"]
    R -- erro --> E["Stop and Error"]
    P -.-> B[("bronze · origem_carga = 'python'<br/>→ silver → gold")]
```

- `src/ingestao/` faz as chamadas com `requests` (timeout, 3 tentativas, validação de `content-type`) e grava na bronze.
- Carga inicial (milhares de municípios, chamadas de até 22 s): roda à mão no container, fora do disparo síncrono do n8n.
  A incremental semanal cabe no disparo (timeout do nó HTTP de ~15 min).
- No servidor o container usa `TZ=America/Sao_Paulo` e o papel `etl_radar`.

### 8.2 Cenário B — ingestão no próprio n8n

Workflow **Radar · Cenário B** (`n8n/radar-expansao-cenario-b.json`) + sub-workflow **Radar · Cenário B · grava resposta** +
error workflow **Radar · Cenário B · erro**:

```mermaid
flowchart LR
    T["Manual ou Schedule<br/>segunda 07:00 (inativo)"] --> CF["Code: Config"]
    CF --> K["Postgres: pega a trava<br/>em_uso_por = 'n8n'"]
    K -- "não pegou" --> IG["Postgres: registra<br/>ignorada_trava"]
    K -- pegou --> U["Postgres: vw_ultimo_periodo<br/>(origem n8n)"]
    U --> P["HTTP: IBGE /periodos<br/>(7 agregados)"]
    P --> M["Code: monta as chamadas<br/>lotes novos ou modificados"]
    M --> AB["Postgres: abre<br/>bronze.execucao"]
    AB --> G["Sub-workflow por chamada:<br/>GET com retry → INSERT jsonb"]
    G --> FE["Postgres: fecha<br/>bronze.execucao"]
    FE -- "houve nova" --> TR["POST /rodar/transformar"]
    FE -- "nada novo" --> SO
    TR --> SO["Postgres: solta a trava"]
    SO --> FIM{"tudo certo?"}
```

- **Mesmo contrato da bronze:** `bronze.api_resposta` (JSON inteiro em `jsonb`, sem transformar, uma linha por chamada,
  `ON CONFLICT DO NOTHING`) e `bronze.execucao` (uma linha por recurso, mesma regra de status da seção 3.1), com `origem_carga = 'n8n'`.
- **Mesmos recursos e regras de incremental** do cenário A (seção 7), lidos de `bronze.vw_ultimo_periodo` filtrada por `'n8n'`.
  Agregados municipais sempre por ano × UF (seção 6, item 4) e só a partir de `ANO_INICIO` (padrão 2022, nó *Config*):
  o histórico longo fica com o cenário A. A primeira execução faz ~370 chamadas; as semanais, só as dos períodos novos.
- **Memória:** cada chamada roda num sub-workflow que devolve só um resumo (nova, já existia, nada novo, erro) e não salva
  execução bem-sucedida; o JSON não fica acumulado na execução principal.
- **Retry:** nó *HTTP Request* com 3 tentativas e espera de 4 s; 404 do BCB = "nada novo"; resposta que não é JSON = erro.
- **Trava:** pega no início e solta no fim, inclusive quando chamadas falham (o fluxo segue e marca erro só depois de soltar).
  Se o workflow quebrar no meio, o error workflow solta a trava e fecha as execuções abertas; numa execução manual, a trava
  expira sozinha em 2 horas.
- **Transformação:** só se houve resposta nova, pelo `POST /rodar/transformar` do container (seção 8.1) — a mesma regra SQL do A.
- Credenciais do n8n: Postgres com o papel `etl_radar` e *Header Auth* do token; nenhuma vai nos arquivos exportados.

### 8.3 Convivência dos cenários: trava e agenda

- **Agendas diferentes:** cenário A na segunda às 06:00 (ativo); cenário B na segunda às 07:00, desligado por padrão (roda manual, para demonstração e comparação).
- **Trava de carga:** toda execução, nos dois cenários, começa tentando pegar a trava e só segue se conseguir. Se não conseguir,
  registra `status = 'ignorada_trava'` em `bronze.execucao` e termina sem chamar as APIs. A trava vale entre processos e
  conexões diferentes (Python e nó Postgres do n8n) e expira sozinha se um processo morrer no meio.

```sql
CREATE TABLE bronze.trava_carga (
    trava_id      smallint PRIMARY KEY DEFAULT 1 CHECK (trava_id = 1),  -- uma única linha
    em_uso_por    text,                                                 -- 'python' | 'n8n' | nulo = livre
    rodada_id     uuid,
    desde         timestamptz
);
INSERT INTO bronze.trava_carga (trava_id) VALUES (1);

-- Pegar a trava (devolve 1 linha se conseguiu; 0 se outro processo está rodando)
UPDATE bronze.trava_carga
SET em_uso_por = :origem_carga, rodada_id = :rodada_id, desde = now()
WHERE trava_id = 1
  AND (em_uso_por IS NULL OR desde < now() - interval '2 hours')   -- expira trava esquecida
RETURNING trava_id;

-- Soltar a trava (no fim, inclusive no caminho de erro)
UPDATE bronze.trava_carga SET em_uso_por = NULL, rodada_id = NULL, desde = NULL
WHERE trava_id = 1 AND rodada_id = :rodada_id;
```

### 8.4 Prós e contras

| | Cenário A — container de ETL em Python | Cenário B — n8n |
|---|---|---|
| **Onde fica a lógica** | Código Python versionado em `src/ingestao/`, com bloco `CONFIG` | Nós do workflow, exportados em `n8n/*.json` |
| **Prós** | Fácil de revisar em PR e de testar localmente · reaproveita o que o curso ensinou (`requests`, `pandas`) · carga inicial pesada sem limite de memória do n8n · uma só implementação para carga inicial e incremental · imagem oficial do n8n intacta | Automação inteira visível num só fluxo (bom para demonstrar e para o print da execução) · retry e agendamento nativos · qualquer membro acompanha a execução pela interface · um container a menos na ingestão |
| **Contras** | Um container a mais para manter (build quando mudar o `requirements.txt`) · logs em dois lugares (n8n e script) · o n8n vira só agendador | Lógica de lotes e URLs espalhada em nós e JavaScript · revisão de PR difícil (JSON exportado) · lotes por UF multiplicam as chamadas (27 por ano) · memória do n8n exige cuidado · atenção redobrada para não exportar credenciais |
| **Risco principal** | Dependências do Python no servidor | Workflow grande e frágil de manter |

### 8.5 Como comparar os dois

Os lotes não são iguais (A pede por ano; B, por ano × UF), então a comparação é feita **depois da silver**, que é igual para os dois:

1. Rodar os dois cenários sobre os mesmos recursos e períodos.
2. Gerar a silver com `ORIGEM_CARGA_SILVER = 'python'` e guardar um resumo de controle por indicador e ano
   (quantidade de linhas, soma de `valor`, quantidade de cada `flag_valor`).
3. Repetir com `ORIGEM_CARGA_SILVER = 'n8n'` e comparar os resumos — devem ser idênticos, e o ranking da gold também.
4. **Operação:** comparar em `bronze.execucao` a duração (`finalizado_em − iniciado_em`), chamadas com erro e execuções `sem_novidade`.

```sql
-- Resumo de controle da silver (rodar após cada geração e comparar os resultados)
SELECT indicador_id, ano, count(*) AS linhas, sum(valor) AS soma_valor,
       count(*) FILTER (WHERE flag_valor <> 'ok') AS valores_especiais
FROM silver.fato_indicador_municipal
GROUP BY indicador_id, ano
ORDER BY indicador_id, ano;
```

Onde os lotes coincidem (localidades, IPCA, séries do BCB), também dá para comparar direto os `payload_hash` da bronze,
calculados pelo Postgres (diferenças de serialização entre Python e n8n não interferem).

Workflows exportados (sempre **sem credenciais**) e passo a passo de importação em [`n8n/README.md`](n8n/README.md).

## 9. Dashboard (Streamlit) e site de apoio

### 9.1 Dashboard

Implementado em `src/app/` e publicado no Streamlit Cloud em **https://radar-expansao.streamlit.app** (repositório `JJ-Junior/radar-expansao`,
branch `junior`, arquivo `src/app/app.py`), lendo a gold ao vivo pela API REST. O app **só lê e apresenta**: ranking, notas, lista recomendada e semáforo vêm prontos da gold.

| Arquivo | Conteúdo |
|---|---|
| `app.py` | ponto de entrada: `st.set_page_config` (aba "RADAR DE EXPANSÃO · SQUAD DROP DATABASE"), menu no topo (`st.navigation`) com as 6 páginas, cabeçalho da marca e o aviso de contingência |
| `dados.py` | camada de dados única: lê as 6 tabelas da gold pela API (ou a cópia), acerta tipos e guarda em cache |
| `formato.py` | rótulos dos critérios, cores do tema e números no padrão brasileiro |
| `paginas/visao_geral.py` | semáforo + justificativa, 5 recomendadas em cards (nota, posição, população, 2 pontos fortes), motivo das cidades bem colocadas que ficaram fora, mapa do universo e números de contexto (P7, P8) |
| `paginas/ranking.py` | filtros por região, UF, faixa de população, nome e elegibilidade; top 10 do recorte; tabela com notas por critério; CSV (`;` e vírgula decimal); **simulador de pesos** opcional: sliders dos 6 critérios refazem só a média ponderada das notas da gold (mesma regra de peso redistribuído), com aviso de simulação e "Voltar ao oficial" — não muda o ranking oficial nem as recomendadas (P2, P4, P5) |
| `paginas/simulador.py` | **simulador de região (P9, seção 9.4):** cidade central (qualquer dos 5.571) e raio de 10 a 300 km (padrão 100); distância haversine no app; mapa com o círculo do raio e as divisas das UFs; ranking local (posição no raio e no Brasil, distância, notas, população projetada, lacuna) com opção de incluir cidades com menos de 50 mil habitantes (sem nota); resumo da região (população, população projetada, renda média ponderada, academias, densidade, soma das lacunas positivas); aviso das estimativas com as premissas de `parametro_ranking`; CSV |
| `paginas/municipio.py` | nota, posições, nota e peso por componente, indicadores com percentil no universo e medianas do universo e da UF, alertas (P1, P3, P8) |
| `paginas/contexto_macro.py` | Selic, IPCA mensal e 12 meses (teto de `parametro_ranking`) e dólar por período; o dólar mostra a **média do mês** ("parcial, até dd/mm" no mês corrente) e o **último fechamento com a data** (`dolar_ultimo`/`dolar_ultimo_data`; na cópia antiga, `meta.json`); legenda das datas de referência do semáforo + faixa mês a mês com o mês parcial marcado (P6, P7) |
| `paginas/metodologia.py` | critérios, pesos, sentido e fontes de `gold.ranking_criterio`, travas de `gold.parametro_ranking`, regras do semáforo e fluxo bronze → silver → gold com a contagem de linhas da última exportação (P8) |

- **Fonte principal: API REST do Supabase**, lida com `requests`:
  `GET {SUPABASE_URL}/rest/v1/{tabela}?select=*&order=<coluna>.asc&limit=1000&offset=<n>` com os headers `apikey: <chave anônima>`
  (o gateway exige uma chave de consumidor), `Authorization: Bearer <token do papel web_leitor>` e `Accept-Profile: gold`.
  Sem o token de leitura, a chave anônima sozinha recebe 401.
  - A API expõe **só o schema `gold`**, com papel somente leitura e RLS (seção 3.4).
  - Segredos lidos de `st.secrets` (Streamlit Cloud) ou, fora dele, das mesmas variáveis no `.env`; só existem no servidor do
    Streamlit e nunca chegam ao navegador do visitante. Valor com marcador `<...>` conta como ausente.
  - Paginação de 1000 em 1000 linhas (limite da API; `indicadores_municipio` tem 5.571), timeout de 10 s e 2 tentativas por chamada.
  - Cache com `st.cache_data(ttl=600)`: a gold é lida no máximo a cada 10 minutos; trocar de página não chama a API.
- **Fallback: snapshot da gold no repositório.** Se faltar segredo ou qualquer tabela falhar (timeout, erro HTTP, resposta vazia),
  o app lê **todas** as tabelas dos JSON da gold em `site/dados/` (os mesmos do site, formato colunar `{colunas, linhas}`,
  contrato em `site/dados/README.md`) e mostra no topo de toda página o aviso **"Dados de <data>"** (campo `gerado_em` de
  `site/dados/meta.json`) com o motivo. A mensagem nunca exibe o endereço da API.
- **Semáforo exibido:** `gold.momento_atual` (uma linha, com as datas de referência e o alerta de câmbio). Se a tabela não
  existir na fonte lida (cópia antiga), o app mostra o último mês fechado de `gold.momento_expansao` e diz isso na tela.
  `momento_atual` é **opcional** na leitura: a falta dela não derruba a API nem a cópia. Cada selo de sinal mostra a data do
  dado usado (`ref_juros`, `ref_cambio`, `ref_inflacao`); na linha do tempo, a data vai no texto de cada célula e o mês em
  andamento aparece como parcial. O cartão da Selic do mês corrente traz `selic_ultima_data`. Colunas novas ausentes na cópia
  antiga são só omitidas da tela.
- **Mapa:** pontos nas coordenadas da gold (`latitude`/`longitude` de `gold.ranking_expansao`; na cópia antiga, `site/dados/territorio.json`)
  sobre as divisas das UFs desenhadas a partir da malha do IBGE (`site/dados/malha/ufs.topo.json`), sem servidor de mapas externo.
- **Tema** em `.streamlit/config.toml`: fundo escuro, verde-limão (`#c4f03b`) só como cor de marca (botões, links, item ativo,
  selo "Recomendada"), escala azul como cor de dado nos gráficos e tabelas, laranja para destacar as recomendadas no mapa e
  verde/amarelo/vermelho só para o semáforo.
- **Rodar:** `streamlit run src/app/app.py` a partir da raiz do repositório.

### 9.2 Segurança do acesso público

Só duas coisas têm endereço público: o **site de apoio** (estático, sem credencial nenhuma) e a **API REST de leitura da gold**.
Não há proxy de acesso na frente da API; a proteção fica em camadas no próprio Supabase:

| Camada | Como |
|---|---|
| Caminho publicado | só `/rest/v1/` do gateway; qualquer outro caminho (Studio, autenticação, armazenamento) não é publicado |
| Chave de consumidor | o gateway exige `apikey` (chave anônima); sem ela, 401 |
| Papel de leitura | o token `web_leitor` só tem `SELECT` nas tabelas de consumo da gold; a chave anônima sozinha não lê nada (401) |
| Schemas | a API expõe só `gold`; pedir `bronze` ou `silver` devolve erro |
| RLS | ligado em todas as tabelas da gold, com política só de leitura para `web_leitor` |
| Escrita | `POST`/`PATCH`/`DELETE` com o token de leitura → 403 |
| Abuso | limite de requisições (rate limit) no endereço da API |
| Segredos | `apikey` e token ficam em `st.secrets` no servidor do Streamlit; nunca chegam ao navegador do visitante |

**Studio e n8n não têm endereço público**: a administração é feita só por túnel SSH. O endereço da API fica apenas no `.env` e
nos *Secrets* do Streamlit, nunca no repositório.

### 9.3 Site de apoio

- **Stack:** HTML, CSS e JavaScript estáticos (ES modules), **sem etapa de build**; bibliotecas de mapa e gráficos por CDN
  com versão fixa; malha municipal do IBGE.
- **Publicação:** servido pelo servidor autohospedado em https://radar-expansao.lovelearning.com.br, que atualiza os arquivos a partir da
  branch `junior` do repositório a cada 10 minutos. É o único endereço do site.
- **Dados:** JSON exportados da gold por `src/exportacao/exportar_site.py`, um arquivo por tabela, com os mesmos nomes de colunas.
- Para abrir localmente: `python -m http.server 8000 --directory site`.

### 9.4 Simulador de região (P9)

- **Entrada do usuário:** uma cidade de referência e um raio em km.
- **Cálculo da distância no app e no site**, a partir das coordenadas da gold (`latitude`, `longitude`), pela fórmula de
  **haversine** (raio da Terra = 6.371 km):
  `d = 2 · 6371 · asin( √( sen²(Δφ/2) + cos φ₁ · cos φ₂ · sen²(Δλ/2) ) )`, com φ = latitude e λ = longitude em radianos.
  A gold **não** guarda pares de distância (seriam ~15,5 milhões de pares para 5.571 municípios).
- **Saída:** cidades do ranking (`gold.ranking_expansao`) dentro do raio, ordenadas por `nota_final`, com `lacuna_academias`,
  `populacao_projetada` e o aviso de `estimativa` (de `gold.indicadores_municipio`); opcionalmente, a soma das lacunas
  positivas de todos os municípios do raio, incluindo os menores que 50 mil habitantes.
- Distância em linha reta entre centroides: serve para comparar regiões, não para estimar tempo de deslocamento.

## 10. Stack e como rodar

| Camada | Ferramenta |
|---|---|
| Linguagem | Python 3.11+ localmente; Python 3.12 (versão fixa) no container de ETL — `requests`, `pandas`, `SQLAlchemy`, `psycopg2-binary`, `python-dotenv` |
| Banco | Supabase (Postgres + API REST + Studio) **autohospedado via Docker**, com schemas `bronze`, `silver`, `gold` |
| Automação | n8n **autohospedado via Docker** |
| Ingestão | Cenário A: container de ETL em Python · Cenário B: nós do n8n |
| Dashboard | Streamlit + Plotly, publicado no Streamlit Cloud, lendo a gold pela API REST |
| Site de apoio | HTML/CSS/JS estático, servido pelo servidor autohospedado |
| Versionamento | Git + GitHub (repositório público) |

**Conexões**

| Quem | Como chega aos dados | Configuração |
|---|---|---|
| Scripts no computador do desenvolvedor | Postgres por um túnel autenticado que expõe o banco em `localhost:5432`; o banco **não** é publicado na internet | `.env` (bloco do banco) |
| Container de ETL e n8n no servidor | Rede Docker interna, sem sair do servidor; SSL desligado (`DB_SSLMODE=disable`) | `.env` do servidor e credencial do n8n |
| Dashboard (Streamlit Cloud) | Só a API REST da gold; **não** conecta direto no Postgres | `st.secrets` (bloco do app) |

Variáveis (modelo em `.env.example` e `.streamlit/secrets.toml.example`):

| Variável | Conteúdo |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME` | endereço, porta e banco do Postgres (no computador do dev: `localhost`, `5432`, `postgres`) |
| `DB_USER`, `DB_PASSWORD` | papel `etl_radar` e sua senha (só no `.env`, nunca no repositório) |
| `DB_SSLMODE` | modo SSL do driver: `prefer` (padrão), `require` ou `disable` — **configurável, não fixo no código** |
| `SUPABASE_URL` | endereço da API REST do Supabase |
| `SUPABASE_ANON_KEY` | chave anônima do Supabase (exigida pelo gateway; sozinha não lê nada) |
| `SUPABASE_CHAVE_LEITURA` | token do papel `web_leitor` (somente leitura na gold) |

Endereços, nomes e detalhes do servidor **não** entram no repositório — a única exceção é o endereço público do site
(https://radar-expansao.lovelearning.com.br).

**Instalação e operação da infraestrutura:** guia em [`docs/instalacao.md`](docs/instalacao.md) e modelos em `infra/`
(override do Supabase em perfil enxuto, compose do n8n, `infra/sql/00_schemas_roles.sql` com schemas, papéis e RLS, e
`infra/backup/backup.sh` com dump diário das três camadas e retenção de 14 dias).

Roteiro previsto (nomes dos scripts podem mudar; este arquivo será atualizado junto):

```powershell
# 0. Infraestrutura no ar (docs/instalacao.md) e túnel SSH aberto: banco em localhost:5432

# 1. Ambiente local
git clone https://github.com/JJ-Junior/radar-expansao.git
cd radar-expansao
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env                                      # bloco do banco
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml  # bloco do app

# 2. Criar schemas, tabelas e papéis (ou colar os arquivos no SQL Editor do Supabase Studio)
python -m src.transformacao.criar_estrutura

# 3. Carga inicial na bronze (em lotes) — cenário A; no cenário B, rodar o workflow do n8n com gatilho manual
python -m src.ingestao.carga_inicial

# 4. Bronze → silver → gold
python -m src.transformacao.executar

# 5. Dashboard
streamlit run src/app/app.py
```

## 11. Pendências deste rascunho

- ✅ Supabase e n8n autohospedados via Docker (seções 1 e 10).
- ✅ Conexões e variáveis de ambiente (seção 10) e leitura da gold pela API REST com fallback (seção 9.1).
- ✅ Disparo do Python pelo n8n: container de ETL com jobs fixos por HTTP interno (seção 8.1).
- ✅ Stack, hospedagem e segurança do acesso público (seções 9.2 e 9.3).
- ⏳ Cenário de ingestão da entrega: A (Python) ou B (n8n), após a comparação (seção 8.5).
- ⏳ Limiares do semáforo macro (seção 5.1).
- ⏳ Data de início do histórico do BCB (proposta: 01/01/2015).

## 12. Bairros sob demanda (experimental, só na branch `bairros`)

Estudo exploratório que desce o ranking da cidade ao bairro. Fica **fora** das camadas bronze/silver/gold oficiais e pode
ser removido inteiro (`DROP SCHEMA bairros CASCADE`, as views `gold.bairro_*` e a função `gold.pedir_bairros`).

| Peça | Onde | O que faz |
|---|---|---|
| Base nacional de academias | `src/bairros/base_cnpj.py` → `bairros.academia` | Mensal: CNPJ da Receita (10 zips de Estabelecimentos, ~5,5 GB em fluxo), só ativas com CNAE 93.13-1 (principal ou secundária) ou 85.91-1, endereço fiscal e código IBGE. Sem nome, telefone, e-mail ou sócios |
| Pipeline por município | `python -m src.bairros.processar --municipio <código>` | Baixa do IBGE os setores 2022 (WFS), o CNEFE do município e os agregados por setor (população, 20 a 59 anos, renda do responsável); geocodifica as academias pelo CNEFE; calcula 2 escalas (bairros do IBGE e "bairros populares" = localidade do CNEFE, com rateio da população por endereço residencial) e grava `bairros.ranking`, `bairros.setor`, `bairros.academia_ponto` e `bairros.resumo` numa transação |
| Fila | `bairros.pedido` + `gold.pedir_bairros(cod)` | A API (papel `web_leitor`) só lê as views `gold.bairro_*` e chama a função, que valida o código, não duplica pedido, limita a 20 pendentes e 30 pedidos por hora; o container `radar-bairros` atende um pedido por vez |
| DDL | `sql/bairros/01_estrutura.sql`, `02_gold_api.sql` | Idempotente, roda como `etl_radar` |
| Testes | `python -m src.bairros.testes [--bauru]` | Regras (pesos, percentis, número "quadra-casa") e Bauru de ponta a ponta: 379.146 hab. e top 3 conhecidos |

Ranking de bairros (mesma lógica de percentis do ranking de cidades; só unidades com 5 mil hab. ou mais): público de 20 a
59 anos 30 % · renda média do responsável 25 % · academias (93.13-1 principal) por 10 mil hab. num raio de 1,5 km, menor é
melhor, 30 % · massa de renda por km² 15 %. Sem a base de academias, o ranking sai marcado `concorrencia = 'pendente'`,
com os outros pesos reescalonados para somar 100 %.

Escala mostrada por padrão (`bairros.resumo.escala_padrao`, exposta em `gold.bairro_resumo`): a escala oficial do IBGE só é o padrão quando é de bairros de verdade. Ela cai para os bairros populares, com uma frase em `aviso_escala` para a tela, quando: (a) metade ou mais dos nomes começa por bacia, região, zona ou similar (Bauru cadastrou no Censo 2022 12 bacias hidrográficas como "bairros", com 16 mil a 72 mil hab.); (b) há menos unidades do IBGE que 10 % das localidades do CNEFE; (c) o município não tem bairro e a escala usa distritos ou subdistritos (São Paulo); (d) não há escala oficial (Santana de Parnaíba). `escala_ibge_tipo` = `bairro`, `regiao`, `distrito`, `subdistrito` ou nulo. Parâmetros no CONFIG de `src/bairros/indicadores.py`.
