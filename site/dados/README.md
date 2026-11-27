# Contrato dos dados do site (`site/dados/`)

O site de apoio não conecta no banco: ele lê arquivos JSON estáticos desta pasta. Os arquivos são gerados por
[`src/exportacao/exportar_site.py`](../../src/exportacao/exportar_site.py); as malhas e o território por
[`src/exportacao/baixar_territorio.py`](../../src/exportacao/baixar_territorio.py).

Cada arquivo de dados espelha **uma tabela da camada gold** do [`spec.md`](../../spec.md) (seção 3.3), com os
**mesmos nomes de colunas**. Assim, quem conhece a gold entende o site, e o site não tem regra de cálculo própria:
percentis, médias por UF e "municípios parecidos" são só leituras dessas tabelas, feitas no navegador.

## De onde vem

Tudo sai da **camada gold** do Supabase autohospedado (conexão pelo `.env`, nunca pelo site), inclusive o último
fechamento diário do dólar e as datas de referência do semáforo (prd v0.6). O script também conta as
linhas de cada tabela de `bronze`, `silver` e `gold` para a seção "Dados" do site. Não existe mais modo de prévia: a gold
é a única fonte das notas, do ranking, da lista de recomendadas e do semáforo.

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
| `indicadores_municipio.json` | `gold.indicadores_municipio` | todos os municípios (~5.571) | P1, P3, P4, P9 |
| `ranking_expansao.json` | `gold.ranking_expansao` | universo do ranking (~687) | P2, P5, P8 |
| `ranking_criterio.json` | `gold.ranking_criterio` | 7 componentes | P8 |
| `parametro_ranking.json` | `gold.parametro_ranking` | 10 parâmetros | P7, P8, P9 |
| `contexto_macro.json` | `gold.contexto_macro` | 1 por mês | P6 |
| `momento_expansao.json` | `gold.momento_expansao` | 1 por mês com os 3 sinais (+ o mês corrente, parcial) | P7 |
| `momento_atual.json` | `gold.momento_atual` | 1 linha: o semáforo de hoje | P7 |
| `territorio.json` | IBGE Localidades + Malhas (referência, não é tabela da gold) | todos os municípios (~5.571) | mapa por regiões |
| `malha/regioes.topo.json` | API de Malhas v3 do IBGE | 5 polígonos | mapa |
| `malha/ufs.topo.json` | idem | 27 polígonos | mapa e radar do topo |
| `malha/intermediarias.topo.json` | idem | 133 polígonos | mapa |
| `malha/imediatas.topo.json` | idem | 510 polígonos | mapa |

### `meta.json`

| Campo | Tipo | Descrição |
|---|---|---|
| `gerado_em` | texto (data e hora) | Quando o script rodou |
| `fonte` | `"gold"` | De onde vieram os dados |
| `eh_previa` | booleano | Sempre `false` (o site ainda sabe exibir um aviso de prévia se um dia vier `true`) |
| `versao_pesos` | texto | Versão dos pesos usada no ranking (ex.: `"prd-v0.3"`) |
| `populacao_minima_universo` | inteiro | Corte do universo do ranking (50.000) |
| `periodos` | objeto | Último período de cada fonte: `populacao`, `censo`, `pib`, `academias`, `salario`, `macro_ate` (`"AAAA-MM"`) |
| `camadas` | objeto | `{"bronze": [...], "silver": [...], "gold": [...]}` com `{"tabela": texto, "linhas": inteiro}`; cada camada é `null` se não tiver tabelas |
| `exportado` | objeto | Linhas gravadas em cada arquivo desta pasta (`{"ranking_expansao": 687, ...}`) |
| `aviso_estimativa` | texto \| null | O texto da coluna `estimativa` da gold, guardado uma vez só (em `indicadores_municipio.json` a coluna vira verdadeiro/falso) |

Exemplo:

```json
{
  "gerado_em": "2026-11-26T15:04:12-03:00",
  "fonte": "gold",
  "eh_previa": false,
  "versao_pesos": "prd-v0.3",
  "populacao_minima_universo": 50000,
  "periodos": {"populacao": 2026, "censo": 2022, "pib": 2023, "academias": 2024, "salario": 2024, "macro_ate": "2026-11"},
  "camadas": {"bronze": [{"tabela": "bronze.api_resposta", "linhas": 71}, ...],
              "silver": [{"tabela": "silver.dim_municipio", "linhas": 5571}, ...],
              "gold": [{"tabela": "gold.ranking_expansao", "linhas": 687}, ...]},
  "exportado": {"indicadores_municipio": 5571, "ranking_expansao": 687, "ranking_criterio": 7,
                "parametro_ranking": 10, "contexto_macro": 143, "momento_expansao": 69, "momento_atual": 1}
}
```

### `indicadores_municipio.json` — `gold.indicadores_municipio`

| Coluna | Tipo | Descrição |
|---|---|---|
| `municipio_id` | inteiro | Código IBGE de 7 dígitos (chave; casa com `territorio.json`) |
| `municipio_nome` | texto | Nome oficial |
| `uf_sigla` | texto (2) | Sigla da UF |
| `regiao_sigla` | texto (1–2) | `N`, `NE`, `SE`, `S`, `CO` |
| `regiao_imediata_id`, `regiao_imediata_nome` | inteiro, texto | Região geográfica imediata do IBGE |
| `populacao` | inteiro \| null | Estimativa mais recente (IBGE 6579) |
| `populacao_ano` | inteiro \| null | Ano da estimativa |
| `populacao_censo_2022` | inteiro \| null | Censo 2022 (IBGE 4714) |
| `crescimento_pop_aa` | número \| null | Crescimento anual desde o Censo 2022, em fração (`0.0123` = 1,23% a.a.) |
| `pib_mil_reais` | número \| null | PIB do último ano, em mil R$ (IBGE 5938) |
| `pib_ano` | inteiro \| null | Ano do PIB |
| `pib_per_capita` | número \| null | R$ por habitante no ano do PIB |
| `pib_per_capita_tendencia` | número \| null | Crescimento anual do PIB per capita entre `tendencia_ano_inicial` e `pib_ano`, em fração |
| `tendencia_ano_inicial` | inteiro \| null | 1º ano da janela de 5 anos do PIB |
| `renda_dom_per_capita` | número \| null | R$/mês, Censo 2022 (IBGE 10295) |
| `renda_ano` | inteiro \| null | Ano da renda (2022) |
| `academias_qtd` | inteiro \| null | Empresas da CNAE 93.13-1 (IBGE 9418); `"-"` da fonte vira `0` |
| `academias_ano` | inteiro \| null | Ano do cadastro |
| `academias_por_10mil_hab` | número \| null | Academias ÷ população do mesmo ano × 10.000 |
| `salario_medio` | número \| null | Salário médio mensal formal, R$ (IBGE 9509) |
| `salario_ano` | inteiro \| null | Ano do salário médio |
| `latitude`, `longitude` | número | Centroide oficial do município (IBGE, API de Malhas v4), usado no simulador de região |
| `faixa_renda` | inteiro 1–5 \| null | Quintil da renda domiciliar per capita do universo |
| `populacao_projetada`, `ano_projecao` | inteiro \| null | Estimativa: população × (1 + crescimento anual) ^ (ano − ano da população) |
| `densidade_referencia` | número \| null | Estimativa: mediana de academias por 10 mil hab. do universo na mesma faixa de renda (limitada a P5–P95) |
| `lacuna_academias` | inteiro \| null | Estimativa: (densidade de referência − densidade atual) × população ÷ 10 mil. Positiva = espaço; negativa = saturada |
| `estimativa` | booleano | A linha tem estimativa (o texto do aviso está em `meta.json → aviso_estimativa`) |
| `atualizado_em` | texto (data e hora) | Quando a linha foi calculada |

### `ranking_expansao.json` — `gold.ranking_expansao`

| Coluna | Tipo | Descrição |
|---|---|---|
| `municipio_id`, `municipio_nome`, `uf_sigla`, `regiao_sigla` | | Como acima |
| `regiao_imediata_id`, `regiao_imediata_nome` | inteiro, texto | Região imediata (a lista de recomendadas tem no máximo uma por região) |
| `populacao` | inteiro | População usada para entrar no universo (≥ 50 mil) |
| `nota_mercado` | número 0–100 \| null | Percentil da população |
| `nota_poder_compra` | número 0–100 \| null | Percentil da renda domiciliar per capita |
| `nota_espaco_competitivo` | número 0–100 \| null | Percentil **invertido** de academias por 10 mil hab., limitado aos percentis 5% e 95% |
| `nota_crescimento` | número 0–100 \| null | Percentil do crescimento anual desde 2022 |
| `nota_riqueza_nivel`, `nota_riqueza_tendencia` | número 0–100 \| null | Percentis do PIB per capita (nível) e da tendência |
| `nota_riqueza` | número 0–100 \| null | Média ponderada de nível e tendência (o critério "riqueza local" do prd) |
| `nota_mercado_formal` | número 0–100 \| null | Percentil do salário médio formal |
| `nota_final` | número 0–100 | Média ponderada das notas disponíveis (peso de critério sem dado é redistribuído) |
| `posicao_brasil`, `posicao_regiao`, `posicao_uf` | inteiro | 1 = melhor do Brasil / da região / da UF |
| `dados_incompletos` | booleano | Algum critério sem dado |
| `criterios_ausentes` | lista de texto \| null | Componentes sem dado (ex.: `["mercado_formal"]`) |
| `peso_considerado` | número | Soma dos pesos com dado (`1.0` = completo) |
| `verificar_concorrencia` | booleano | Nenhuma academia formal registrada: conferir no local |
| `elegivel_recomendacao` | booleano | Passa na trava de renda (`nota_poder_compra` ≥ `nota_minima_poder_compra`) |
| `recomendado_top5` | booleano | Está na lista das unidades recomendadas |
| `ordem_recomendacao` | número \| null | 1 a 5, ordem na lista de recomendadas |
| `latitude`, `longitude` | número | Centroide do município (o mesmo de `indicadores_municipio`) |
| `versao_pesos` | texto | Versão dos pesos |
| `calculado_em` | texto (data e hora) | Quando o ranking foi calculado |

### `ranking_criterio.json` — `gold.ranking_criterio`

| Coluna | Tipo | Descrição |
|---|---|---|
| `criterio` | texto | `mercado`, `poder_compra`, `espaco_competitivo`, `crescimento`, `riqueza_nivel`, `riqueza_tendencia`, `mercado_formal` (a nota fica em `nota_<criterio>`) |
| `grupo` | texto | Critério do prd que o componente compõe (`riqueza` agrupa nível e tendência) |
| `descricao` | texto | O que o componente mede (o site usa um texto próprio, com acentos, e cai neste se faltar) |
| `fonte` | texto | Tabela do IBGE de origem |
| `peso` | número | Fração; a soma dos 7 é `1.000` |
| `sentido` | texto | `maior_melhor` \| `menor_melhor` |
| `ordem` | inteiro | Ordem de exibição |
| `versao_pesos` | texto | Versão dos pesos |

### `parametro_ranking.json` — `gold.parametro_ranking`

| Coluna | Tipo | Descrição |
|---|---|---|
| `parametro` | texto | `unidades_recomendadas`, `nota_minima_poder_compra` (trava de renda), `ano_projecao_populacao` e `faixas_renda_referencia` (premissas do simulador); do semáforo: `semaforo_janela_dias`, `semaforo_alerta_cambio_30d_pct`, `semaforo_limiar_selic_pp`, `semaforo_teto_ipca_pct`, `semaforo_limiar_dolar_12m_pct` e `semaforo_meses_tendencia_ipca` |
| `valor` | número | Valor do parâmetro (hoje 5, 50, 2028, 5, 30, 5, 0,5, 4,5, 10 e 3) |
| `descricao` | texto | Explicação do parâmetro |
| `versao_pesos` | texto | Versão |

O site lê esses valores para explicar a lista de recomendadas; se o arquivo faltar, usa 5 e 50.

### `contexto_macro.json` — `gold.contexto_macro`

| Coluna | Tipo | Descrição |
|---|---|---|
| `mes` | texto `AAAA-MM-01` | Primeiro dia do mês |
| `mes_parcial` | booleano | Mês corrente, ainda em andamento |
| `selic_meta` | número \| null | % a.a., meta vigente no último dia com dado no mês (BCB 432) |
| `selic_ultima_data` | texto `AAAA-MM-DD` \| null | Dia da meta usada |
| `selic_var_12m_pp` | número \| null | Variação em pontos percentuais contra 12 meses antes |
| `dolar_medio` | número \| null | R$, média dos dias úteis do mês (BCB 10813); parcial no mês corrente |
| `dolar_var_12m_pct` | número \| null | Variação % contra 12 meses antes |
| `dolar_ultimo`, `dolar_ultimo_data` | número, texto `AAAA-MM-DD` \| null | Último fechamento do dólar no mês e o dia |
| `dolar_var_1m_pct` | número \| null | Média do mês contra a do mês anterior (%) |
| `ipca_mensal` | número \| null | % no mês (IBGE 7060/63) |
| `ipca_12m` | número \| null | % acumulado em 12 meses (IBGE 7060/2265) |
| `atualizado_em` | texto (data e hora) | |

O mês corrente pode aparecer com Selic e dólar parciais e IPCA `null` (o IPCA sai no mês seguinte).

### `momento_expansao.json` — `gold.momento_expansao`

| Coluna | Tipo | Descrição |
|---|---|---|
| `mes` | texto `AAAA-MM-01` | Mês avaliado (meses com os 3 sinais + o mês corrente) |
| `mes_parcial` | booleano | Mês corrente: sinais iguais aos de `momento_atual` |
| `ref_juros`, `ref_cambio`, `ref_inflacao` | texto `AAAA-MM-DD` | Dia da meta da Selic, último fechamento do dólar e mês do IPCA usados |
| `sinal_juros`, `sinal_inflacao`, `sinal_cambio` | `"verde"` \| `"amarelo"` \| `"vermelho"` | Regras do `spec.md` 5.1 |
| `pontuacao` | inteiro −3 a +3 | verde = +1, amarelo = 0, vermelho = −1 |
| `recomendacao` | texto | `Expandir agora` (≥ +2) \| `Expandir com cautela` (0 a +1) \| `Esperar` (≤ −1) |
| `justificativa` | texto | Frase pronta para exibir |
| `atualizado_em` | texto (data e hora) | |

O site usa estas linhas no histórico mês a mês. O semáforo exibido vem de `momento_atual.json` (se ele faltar, da última linha).

### `momento_atual.json` — `gold.momento_atual`

Uma linha: o semáforo de hoje. Câmbio e juros pela janela móvel até o último fechamento; inflação pelo último IPCA publicado.

| Coluna | Tipo | Descrição |
|---|---|---|
| `mes` | texto `AAAA-MM-01` | Mês do último fechamento do dólar |
| `janela_dias` | inteiro | Tamanho da janela móvel (30) |
| `ref_juros`, `ref_cambio`, `ref_inflacao` | texto `AAAA-MM-DD` | Data de referência de cada sinal (o site mostra "dólar até 26/11", "IPCA até out/26") |
| `selic_meta`, `selic_meta_12m_antes`, `selic_var_12m_pp` | número | Meta da Selic em `ref_juros`, 12 meses antes e a diferença (p.p.) |
| `dolar_ultimo` | número | Último fechamento (R$) |
| `dolar_media_janela`, `dolar_media_janela_12m_antes`, `dolar_var_12m_pct` | número | Média dos 30 dias até `ref_cambio`, a mesma janela 12 meses antes e a variação (%) |
| `dolar_media_janela_anterior`, `dolar_var_janela_pct` | número | Média dos 30 dias anteriores e a variação de curto prazo (%) |
| `alerta_cambio_curto_prazo` | booleano | Alta de curto prazo acima do limite: o câmbio não pode ser verde |
| `ipca_12m`, `ipca_12m_meses_antes`, `ipca_desacelerando` | número, número, booleano | IPCA de 12 meses em `ref_inflacao`, o de 3 meses antes e se está caindo |
| `sinal_juros`, `sinal_inflacao`, `sinal_cambio` | `"verde"` \| `"amarelo"` \| `"vermelho"` | Regras do `spec.md` 5.1 |
| `pontuacao`, `recomendacao`, `justificativa` | inteiro, texto, texto | Como em `momento_expansao`; a justificativa traz as datas |
| `atualizado_em` | texto (data e hora) | |

### `territorio.json` — hierarquia do IBGE e ponto de cada município

Mesmo formato colunar (`"tabela": "ibge.territorio"`). Não vem da gold: é referência territorial do IBGE, igual para
qualquer versão do ranking. Serve para agrupar as cidades por região intermediária e imediata e para pôr cada uma no mapa (o radar do topo, o mapa por regiões e a vista "Mapa" do Explorar usam a `longitude`/`latitude` daqui).

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

A malha do Brasil inteiro por município é baixada só em memória, para calcular os pontos do `territorio.json`.

### `malha/municipios/<codigo_uf>.topo.json` — contorno dos municípios, um arquivo por UF

Usada no mapa do simulador de região (dashboard e site), que carrega só as UFs que o raio toca.
Vem de `/api/v3/malhas/estados/<codigo_uf>?formato=application/json&qualidade=minima&intrarregiao=municipio`,
com dois ajustes:

- o objeto se chama sempre **`municipios`** (o IBGE usa `UF<codigo>MU`);
- cada geometria tem **`id`** = código IBGE do município com 7 dígitos (**inteiro**, igual a `municipio_id`),
  além do `properties.codarea` (texto) que veio do IBGE.

| Item | Valor |
|---|---|
| Arquivos | 27, nomeados pelo código da UF com 2 dígitos (`11.topo.json` … `53.topo.json`; SP = `35`) |
| Geometrias | 5.570 `Polygon`/`MultiPolygon` (todos os municípios da gold menos Boa Esperança do Norte-MT, `5101837`, criado depois da malha; ele aparece só como ponto, pelo `territorio.json`) |
| Tamanho | 1,4 MB no total (de 1 KB no DF a 207 KB em MG) |
| Coordenadas | quantizadas: aplique `transform` (`scale`, `translate`) para obter longitude/latitude (WGS84) |

No navegador (d3 + topojson-client):

```js
const topo = await d3.json(`dados/malha/municipios/${codigoUf}.topo.json`);
const municipios = topojson.feature(topo, topo.objects.municipios); // feature.id = municipio_id
const divisas = topojson.mesh(topo, topo.objects.municipios, (a, b) => a !== b);
```

As malhas mudam raramente: rode `baixar_territorio.py` só quando o IBGE publicar uma nova divisão territorial
(`--so-municipios` refaz só a pasta `malha/municipios/`).

## Como gerar

```powershell
# na raiz do repositório, com o ambiente virtual ativo
python src/exportacao/baixar_territorio.py # uma vez (malhas, malha municipal por UF e territorio.json)
python src/exportacao/exportar_site.py     # a cada atualização da gold
```

Depois, faça commit da pasta `site/dados/`: o deploy do site publica o que estiver no repositório.
