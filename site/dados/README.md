# Contrato dos dados do site (`site/dados/`)

O site de apoio não conecta no banco: ele lê arquivos JSON estáticos desta pasta. Os arquivos são gerados por
[`src/exportacao/exportar_site.py`](../../src/exportacao/exportar_site.py); as malhas e o território por
[`src/exportacao/baixar_territorio.py`](../../src/exportacao/baixar_territorio.py).

Cada arquivo de dados espelha **uma tabela da camada gold** do [`spec.md`](../../spec.md) (seção 3.3), com os
**mesmos nomes de colunas**. Assim, quem conhece a gold entende o site, e o site não tem regra de cálculo própria:
percentis, médias por UF e "municípios parecidos" são só leituras dessas tabelas, feitas no navegador.

## Dois modos de geração

| `FONTE` no `CONFIG` | De onde vem | `meta.json → eh_previa` | Quando usar |
|---|---|---|---|
| `"gold"` | Tabelas `gold.*` do Supabase (conexão pelo `.env`) | `false` | Depois que a camada gold existir — é o modo oficial |
| `"api"` | Chamadas diretas às APIs do IBGE e do BCB, com as regras do `spec.md` (5.1 a 5.3) refeitas em Python | `true` | Enquanto a gold não existe. O site mostra o aviso **"Prévia — ranking calculado após a camada gold"** |

No modo `"api"` todos os números são **reais** (vêm das APIs oficiais), mas o ranking e o semáforo são uma prévia:
a versão que vale é a calculada na gold. A camada bronze/silver não é usada nesse modo, por isso a contagem de linhas
das camadas fica `null`.

## Formato comum das tabelas

Para manter os arquivos pequenos, as tabelas usam formato **colunar** (nomes uma vez, depois só valores):

```json
{
  "tabela": "gold.ranking_expansao",
  "gerado_em": "2026-11-26T15:04:12-03:00",
  "colunas": ["municipio_id", "municipio_nome", "uf_sigla", "nota_final"],
  "linhas": [
    [3550308, "São Paulo", "SP", 71.42],
    [3106200, "Belo Horizonte", "MG", 69.80]
  ]
}
```

Regras:
- `linhas[i][j]` é o valor da coluna `colunas[j]`. A ordem das colunas pode mudar; o site sempre procura pelo **nome**.
- Valor ausente é `null` (nunca `"-"`, `"..."`, `"X"` ou `NaN`).
- Números são números JSON com ponto decimal; frações ficam como fração (`0.0123` = 1,23%), percentuais como no `spec.md`.
- Datas: `"AAAA-MM-DD"`; data e hora: ISO 8601 com fuso.
- Codificação UTF-8, nomes de municípios com acento, exatamente como na API de Localidades do IBGE.

Para ler em JavaScript: `linhas.map(l => Object.fromEntries(colunas.map((c, j) => [c, l[j]])))` (feito em `site/js/dados.js`).

## Arquivos

| Arquivo | Tabela de origem | Linhas | Responde (prd.md) |
|---|---|---|---|
| `meta.json` | — (metadados da exportação) | 1 objeto | — |
| `indicadores_municipio.json` | `gold.indicadores_municipio` | todos os municípios (~5.571) | P1, P3, P4 |
| `ranking_expansao.json` | `gold.ranking_expansao` | universo do ranking (~687) | P2, P5, P8 |
| `ranking_criterio.json` | `gold.ranking_criterio` | 6 critérios | P8 |
| `contexto_macro.json` | `gold.contexto_macro` | 1 por mês | P6 |
| `momento_expansao.json` | `gold.momento_expansao` | 1 por mês com os 3 sinais | P7 |
| `territorio.json` | IBGE Localidades + Malhas (referência, não é tabela da gold) | todos os municípios (~5.571) | mapa por regiões |
| `malha/regioes.topo.json` | API de Malhas v3 do IBGE | 5 polígonos | mapa |
| `malha/ufs.topo.json` | idem | 27 polígonos | mapa e radar do topo |
| `malha/intermediarias.topo.json` | idem | 133 polígonos | mapa |
| `malha/imediatas.topo.json` | idem | 510 polígonos | mapa |

### `meta.json`

| Campo | Tipo | Descrição |
|---|---|---|
| `gerado_em` | texto (data e hora) | Quando o script rodou |
| `fonte` | `"gold"` \| `"api"` | Modo de geração (tabela acima) |
| `eh_previa` | booleano | `true` no modo `"api"`: o site exibe o aviso de prévia |
| `versao_pesos` | texto | Versão dos pesos usada no ranking (ex.: `"prd-v0.2"`) |
| `populacao_minima_universo` | inteiro | Corte do universo do ranking (50.000) |
| `periodos` | objeto | Último período de cada fonte: `populacao`, `censo`, `pib`, `academias`, `salario`, `macro_ate` (`"AAAA-MM"`) |
| `camadas` | objeto | `{"bronze": [...], "silver": [...], "gold": [...]}` com `{"tabela": texto, "linhas": inteiro}`; cada camada é `null` quando não foi lida (modo `"api"`) |
| `exportado` | objeto | Linhas gravadas em cada arquivo desta pasta (`{"ranking_expansao": 687, ...}`) |

Exemplo:

```json
{
  "gerado_em": "2026-11-26T15:04:12-03:00",
  "fonte": "api",
  "eh_previa": true,
  "versao_pesos": "prd-v0.2",
  "populacao_minima_universo": 50000,
  "periodos": {"populacao": 2026, "censo": 2022, "pib": 2023, "academias": 2024, "salario": 2024, "macro_ate": "2026-11"},
  "camadas": {"bronze": null, "silver": null, "gold": null},
  "exportado": {"indicadores_municipio": 5571, "ranking_expansao": 687, "ranking_criterio": 6,
                "contexto_macro": 143, "momento_expansao": 70}
}
```

### `indicadores_municipio.json` — `gold.indicadores_municipio`

| Coluna | Tipo | Descrição |
|---|---|---|
| `municipio_id` | inteiro | Código IBGE de 7 dígitos (chave; casa com `territorio.json`) |
| `municipio_nome` | texto | Nome oficial |
| `uf_sigla` | texto (2) | Sigla da UF |
| `regiao_sigla` | texto (1–2) | `N`, `NE`, `SE`, `S`, `CO` |
| `populacao` | inteiro \| null | Estimativa mais recente (IBGE 6579) |
| `populacao_ano` | inteiro \| null | Ano da estimativa |
| `populacao_censo_2022` | inteiro \| null | Censo 2022 (IBGE 4714) |
| `crescimento_pop_aa` | número \| null | Crescimento anual desde o Censo 2022, em fração (`0.0123` = 1,23% a.a.) |
| `pib_mil_reais` | número \| null | PIB do último ano, em mil R$ (IBGE 5938) |
| `pib_ano` | inteiro \| null | Ano do PIB |
| `pib_per_capita` | número \| null | R$ por habitante no ano do PIB |
| `pib_per_capita_tendencia` | número \| null | Crescimento anual do PIB per capita nos 5 anos até `pib_ano`, em fração |
| `renda_dom_per_capita` | número \| null | R$/mês, Censo 2022 (IBGE 10295) |
| `academias_qtd` | inteiro \| null | Empresas da CNAE 93.13-1 (IBGE 9418); `"-"` da fonte vira `0` |
| `academias_ano` | inteiro \| null | Ano do cadastro |
| `academias_por_10mil_hab` | número \| null | Academias ÷ população do mesmo ano × 10.000 |
| `salario_medio` | número \| null | Salário médio mensal formal, R$ (IBGE 9509) |
| `atualizado_em` | texto (data e hora) | Quando a linha foi calculada |

Exemplo de uma linha (valores ilustrativos do formato):

```json
[3106200, "Belo Horizonte", "MG", "SE", 2416339, 2026, 2315560, 0.0107, 120000000, 2023, 51800.5, 0.021,
 2600.10, 1008, 2024, 4.27, 4100.25, "2026-11-26T15:04:12-03:00"]
```

### `ranking_expansao.json` — `gold.ranking_expansao`

| Coluna | Tipo | Descrição |
|---|---|---|
| `municipio_id`, `municipio_nome`, `uf_sigla`, `regiao_sigla` | | Como acima |
| `populacao` | inteiro | População usada para entrar no universo (≥ 50 mil) |
| `nota_mercado` | número 0–100 | Percentil da população |
| `nota_poder_compra` | número 0–100 | Percentil da renda domiciliar per capita |
| `nota_espaco_competitivo` | número 0–100 | Percentil **invertido** de academias por 10 mil hab. (menos academias = nota maior) |
| `nota_crescimento` | número 0–100 | Percentil do crescimento anual desde 2022 |
| `nota_riqueza` | número 0–100 | Média dos percentis do PIB per capita (nível) e da tendência |
| `nota_mercado_formal` | número 0–100 | Percentil do salário médio formal |
| `nota_final` | número 0–100 | Soma ponderada das notas pelos pesos de `ranking_criterio` |
| `posicao_brasil` | inteiro | 1 = melhor do Brasil |
| `posicao_uf` | inteiro | 1 = melhor da UF |
| `dados_incompletos` | booleano | Algum critério recebeu nota neutra 50 por falta de dado |
| `versao_pesos` | texto | Versão dos pesos |
| `calculado_em` | texto (data e hora) | Quando o ranking foi calculado |

### `ranking_criterio.json` — `gold.ranking_criterio`

| Coluna | Tipo | Descrição |
|---|---|---|
| `criterio` | texto | `mercado`, `poder_compra`, `espaco_competitivo`, `crescimento`, `riqueza`, `mercado_formal` (a nota fica em `nota_<criterio>`) |
| `descricao` | texto | O que o critério mede |
| `fonte` | texto | Tabela do IBGE de origem |
| `peso` | número | Fração; a soma dos 6 é `1.000` |
| `sentido` | texto | `maior_melhor` \| `menor_melhor` |
| `versao_pesos` | texto | Versão dos pesos |

### `contexto_macro.json` — `gold.contexto_macro`

| Coluna | Tipo | Descrição |
|---|---|---|
| `mes` | texto `AAAA-MM-01` | Primeiro dia do mês |
| `selic_meta` | número \| null | % a.a., meta vigente no último dia do mês (BCB 432) |
| `selic_var_12m_pp` | número \| null | Variação em pontos percentuais contra 12 meses antes |
| `dolar_medio` | número \| null | R$, média dos dias úteis do mês (BCB 10813) |
| `dolar_var_12m_pct` | número \| null | Variação % contra 12 meses antes |
| `ipca_mensal` | número \| null | % no mês (IBGE 7060/63) |
| `ipca_12m` | número \| null | % acumulado em 12 meses (IBGE 7060/2265) |
| `atualizado_em` | texto (data e hora) | |

O mês corrente pode aparecer com Selic e dólar parciais e IPCA `null` (o IPCA sai no mês seguinte).

### `momento_expansao.json` — `gold.momento_expansao`

| Coluna | Tipo | Descrição |
|---|---|---|
| `mes` | texto `AAAA-MM-01` | Mês avaliado (só meses com os 3 sinais) |
| `sinal_juros`, `sinal_inflacao`, `sinal_cambio` | `"verde"` \| `"amarelo"` \| `"vermelho"` | Regras do `spec.md` 5.1 |
| `pontuacao` | inteiro −3 a +3 | verde = +1, amarelo = 0, vermelho = −1 |
| `recomendacao` | texto | `Expandir agora` (≥ +2) \| `Expandir com cautela` (0 a +1) \| `Esperar` (≤ −1) |
| `justificativa` | texto | Frase pronta para exibir |
| `atualizado_em` | texto (data e hora) | |

O site usa a **última linha** como semáforo atual e as anteriores como histórico.

### `territorio.json` — hierarquia do IBGE e ponto de cada município

Mesmo formato colunar (`"tabela": "ibge.territorio"`). Não vem da gold: é referência territorial do IBGE, igual para
qualquer versão do ranking. Serve para agrupar as cidades por região intermediária e imediata e para pôr cada uma no mapa.

| Coluna | Tipo | Descrição |
|---|---|---|
| `municipio_id` | inteiro | Código IBGE de 7 dígitos |
| `regiao_imediata_id`, `regiao_imediata_nome` | inteiro, texto | Região geográfica imediata (510 no país) |
| `regiao_intermediaria_id`, `regiao_intermediaria_nome` | inteiro, texto | Região geográfica intermediária (133 no país) |
| `longitude`, `latitude` | número \| null | Centro do município (centroide do polígono, ponderado pela área), 4 casas. `null` para município sem polígono na malha (ex.: criado depois dela) |

UF e região saem do próprio código: `uf_id = municipio_id ÷ 100000`, `regiao_id = municipio_id ÷ 1000000` (divisão inteira).

### `malha/*.topo.json` — malhas do IBGE

TopoJSON baixado da [API de Malhas v3 do IBGE](https://servicodados.ibge.gov.br/api/docs/malhas?versao=3)
(`/api/v3/malhas/paises/BR?formato=application/json&qualidade=minima&intrarregiao=<camada>`), salvo como veio.

| Arquivo | `intrarregiao` | Objeto | `codarea` |
|---|---|---|---|
| `regioes.topo.json` | `regiao` | `BRGR` | 1 dígito (1 = Norte … 5 = Centro-Oeste) |
| `ufs.topo.json` | `UF` | `BRUF` | 2 dígitos (código da UF) |
| `intermediarias.topo.json` | `regiao-intermediaria` | `BRIN` | 4 dígitos (`regiao_intermediaria_id`) |
| `imediatas.topo.json` | `regiao-imediata` | `BRIM` | 6 dígitos (`regiao_imediata_id`) |

A malha de municípios (1,4 MB) é baixada só em memória, para calcular os pontos do `territorio.json`; o site não a usa.
As malhas mudam raramente: rode `baixar_territorio.py` só quando o IBGE publicar uma nova divisão territorial.

## Como gerar

```powershell
# na raiz do repositório, com o ambiente virtual ativo
python src/exportacao/baixar_territorio.py # uma vez (malhas + territorio.json)
python src/exportacao/exportar_site.py     # a cada atualização da gold (ou da prévia)
```

Depois, faça commit da pasta `site/dados/`: o deploy do site publica o que estiver no repositório.
