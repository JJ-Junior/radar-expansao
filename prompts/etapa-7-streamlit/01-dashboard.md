# Etapa 7 · Dashboard Streamlit lendo a camada gold

- **Data:** 26/11/2026
- **Responsável:** José Martins (Junior)
- **Arquivos afetados:** `src/app/` (`app.py`, `dados.py`, `formato.py`, `paginas/*.py`), `.streamlit/config.toml`,
  `.streamlit/secrets.toml.example`, `README.md` (seção 5), `spec.md` (v0.12, seção 9.1)

## Objetivo
Entregar o dashboard da etapa 7: em 30 segundos, o diretor de expansão vê quais cidades priorizar, por quê, e se o momento
econômico favorece abrir agora.

## Contexto fornecido
- `prd.md` (perguntas P1 a P8, critérios, pesos, trava de renda e uma cidade por região imediata), `spec.md` (seção 3.3, a gold;
  seção 9, dashboard e segurança) e `agents.md` (cabeçalho padrão, bloco CONFIG, commits).
- Contrato dos JSON exportados da gold em `site/dados/README.md` (formato colunar `{colunas, linhas}`).
- Forma de acesso à API REST da gold (headers e papel somente leitura), sem nenhum valor de chave.

## Entrada (prompt)
> Tarefa: construir em `src/app/` um app Streamlit multipágina com (1) visão geral: semáforo com a justificativa, as 5 unidades
> recomendadas em cards com 2 pontos fortes, mapa do universo e KPIs; (2) ranking filtrável por região, UF, faixa de população
> e nome, com notas por critério e CSV; (3) ficha do município com posições, critérios com peso e nota, indicadores com
> percentil e alertas; (4) contexto macro (Selic, IPCA mensal e 12 meses, dólar) e linha do tempo do semáforo; (5) metodologia
> lida de `ranking_criterio` e `parametro_ranking`, com o fluxo bronze → silver → gold.
> Restrições: uma camada de dados única com `requests` e `st.cache_data(ttl=600)`; se a API falhar ou faltar segredo, usar os
> JSON de `site/dados/` com aviso "dados de <data>"; segredos só em `st.secrets`/`.env`; o app não recalcula o ranking; tema
> alinhado ao site (escuro, verde-limão de marca, cor de dado separada); cabeçalho padrão e CONFIG em todo arquivo.

## Saída esperada
As 5 páginas abrindo sem erro com a cópia da gold e com a API; mesma lista de recomendadas e mesmo semáforo do site; nenhuma
chave ou endereço da API no repositório.

## O que a IA entregou
- `dados.py` com leitura paginada (1000 linhas por chamada, limite da API), 2 tentativas, timeout de 10 s e queda para a cópia
  da gold em qualquer falha, informando o motivo sem mostrar o endereço da API.
- Cinco páginas em `src/app/paginas/` com menu no topo; frases de "por que não está na lista" lidas das marcas da gold
  (`elegivel_recomendacao`, região imediata), sem refazer a regra.
- Tema próprio em `.streamlit/config.toml` e números no padrão brasileiro (`formato.py`).
- Testes: cada página rodada pela API de agente do Streamlit (status "ready", sem exceção), botões e filtros exercitados, e um
  servidor falso local imitando a API REST para conferir paginação, headers e a queda para a cópia (401 e servidor fora do ar).

## O que foi ajustado
- **Mapa:** a primeira versão usava fundo de mapa da internet (`Scattermap`); o Plotly embutido no Streamlit não carregou o
  estilo e o mapa saiu vazio. Trocado por divisas das UFs desenhadas da malha do IBGE já versionada — funciona sem rede externa.
- **Rótulos sobrepostos** no mapa (Rio de Janeiro e Santana de Parnaíba): o nome passa para a esquerda quando há outra
  recomendada perto, a leste.
- **Cores:** barras de progresso das tabelas vinham na cor de marca (limão); passaram à escala azul de dado. Separador decimal
  dos gráficos trocado para vírgula.
- **Coordenadas na gold:** durante a etapa a gold ganhou `latitude`/`longitude`; o app passou a usar as da gold e só completa
  pelo `territorio.json` quando a cópia ainda não as tem.

## Lições
- Pedir o teste de cada página no app rodando (não só a leitura do código): o mapa vazio só apareceu na tela.
- Em app público, a mensagem de erro da fonte de dados não pode repetir a URL da API — vale para qualquer tela futura.
