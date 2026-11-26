# Site de apoio — Radar de Expansão

Vitrine de expansão para o diretor da rede de academias, numa página só, contada como um pitch:

1. **Hero:** o radar varre o Brasil e acende as cidades avaliadas; KPIs e busca de cidade.
2. **Letreiro** com os números do momento (Selic, IPCA, dólar, cidades no radar, 1ª do ranking, as recomendadas).
3. **Quando:** semáforo econômico, histórico mês a mês e as três séries.
4. **Onde:** mapa por regiões do IBGE que se aproxima com o scroll — Brasil → região → estado → região intermediária → região imediata —, e depois fica livre para explorar.
5. **As 5 recomendadas:** cards com o gráfico-radar das notas, num trilho horizontal, e o motivo de quem ficou de fora (trava de renda ou região imediata repetida); também o ranking geral por região.
6. **Ficha da cidade**, com endereço próprio (`?municipio=<código IBGE>`).
7. **Critérios:** o perfil que o Radar procura (cada setor = peso).
8. **Método:** fórmula, regras, semáforo e limitações.
9. **Dados:** as camadas do Lakehouse.
10. **Chamada** para o dashboard e o repositório.

**Não é o dashboard oficial** (esse é o Streamlit em `src/app/`): é a porta de entrada pública do projeto.

## Stack (sem etapa de build)

| Parte | Como é feito |
|---|---|
| Página | `index.html` + `css/estilo.css`, escritos à mão |
| Lógica | JavaScript puro em ES modules (`js/*.js`), sem framework |
| Mapas e gráficos | [D3](https://d3js.org/) 7.9.0 e [topojson-client](https://github.com/topojson/topojson-client) 3.1.0 |
| Animação de scroll | [GSAP](https://gsap.com/) 3.12.5 + ScrollTrigger (seções presas, trilho horizontal, entradas) |
| Scroll suave | [Lenis](https://github.com/darkroomengineering/lenis) 1.1.13 |
| Fontes | Big Shoulders Display (títulos), Archivo (texto) e JetBrains Mono (rótulos), pelo Google Fonts |
| Dados | JSONs estáticos em `dados/`, exportados da camada gold — contrato em [`dados/README.md`](dados/README.md) |
| Hospedagem | GitHub Pages, publicado pelo workflow `.github/workflows/site.yml` |

Todas as bibliotecas vêm por CDN, com versão fixa. Não há foto nem vídeo: o visual é feito de tipografia, cor e arte com os próprios dados (canvas e SVG).
O navegador nunca fala com o banco, então nenhuma credencial vai para o site.

## Estrutura

```
site/
├── index.html            página única, uma <section> por bloco do pitch
├── css/estilo.css        tokens de cor (marca × dado × estado), tema escuro (padrão) e claro
├── js/
│   ├── main.js           ponto de entrada: dados, seções, KPIs, letreiro, endereço ?municipio=
│   ├── dados.js          leitura dos JSONs colunares e das malhas
│   ├── movimento.js      Lenis + GSAP/ScrollTrigger, entradas e contadores (desligáveis)
│   ├── hero-radar.js     radar animado do topo (canvas)
│   ├── macro.js          semáforo, histórico e gráficos de Selic, IPCA e dólar
│   ├── mapa-regioes.js   mapa por regiões do IBGE: história guiada pelo scroll + exploração livre
│   ├── geo.js            utilidades das malhas TopoJSON
│   ├── cards.js          as recomendadas e o ranking geral em trilho horizontal
│   ├── recomendacao.js   explica a lista de recomendadas (trava de renda, uma por região imediata)
│   ├── grafico-radar.js  gráfico-radar das 6 notas (SVG)
│   ├── ficha.js          ficha da cidade: notas, percentis, cidades parecidas
│   ├── metodologia.js    painel dos critérios, fórmula e camadas do Lakehouse
│   ├── busca.js          busca de cidade (combobox acessível)
│   ├── indicadores.js    rótulos, critérios, indicadores da ficha, ícones do semáforo
│   └── formato.js        números e datas em pt-BR
├── dados/                gerado por src/exportacao/ (ver dados/README.md)
└── img/radar.svg         ícone
```

## Abrir localmente

Os módulos JavaScript e o `fetch` dos JSONs **não funcionam abrindo o `index.html` direto** (`file://`).
Use um servidor estático simples, a partir da raiz do repositório:

```powershell
python -m http.server 8000 --directory site
```

Depois abra http://localhost:8000. Para abrir a ficha de uma cidade direto: http://localhost:8000/?municipio=3550308
(código IBGE de 7 dígitos).

## Atualizar os dados

```powershell
# com o ambiente virtual ativo, na raiz do repositório
python src/exportacao/baixar_territorio.py   # só quando o IBGE mudar a divisão territorial
python src/exportacao/exportar_site.py       # regenera site/dados/*.json
```

O `exportar_site.py` lê as tabelas `gold.*` com as credenciais do `.env` (o mesmo banco dos scripts de transformação).
Ele também conta as linhas de cada camada para a seção "Dados" e confere a soma dos pesos, as notas entre 0 e 100 e a
quantidade de cidades recomendadas antes de gravar. O site não calcula nota nem escolhe as recomendadas: só lê a gold.

## Publicar no GitHub Pages

O workflow [`.github/workflows/site.yml`](../.github/workflows/site.yml) confere os arquivos de dados e publica a pasta `site/`.
Ele roda a cada push na branch `junior` que altere o site, ou manualmente em **Actions → Site de apoio (GitHub Pages) → Run workflow**.

O site está no ar em **https://jj-junior.github.io/radar-expansao/**.

Se o passo "Publica" falhar com *"No artifacts named github-pages were found"* (corrida logo após o upload; o workflow
já espera 10 s para evitar), **não use "Re-run"**: ele duplica o artefato e falha de novo. Dispare uma execução nova:

```powershell
gh workflow run site.yml --ref junior
```

Configuração do repositório (já feita; registrada para quem montar um repositório novo):

1. **Settings → Pages → Build and deployment → Source:** escolher **GitHub Actions**.
2. **Settings → Environments → `github-pages` → Deployment branches and tags:** adicionar a regra para a branch **`junior`**.
   - Por padrão o ambiente só aceita deploy da branch principal, e o workflow falha com *"Branch junior is not allowed to deploy to github-pages due to environment protection rules"*.
   - O ambiente `github-pages` aparece depois do passo 1; se não aparecer, rode o workflow uma vez.

Endereço depois do deploy: `https://jj-junior.github.io/radar-expansao/`.

Quando o trabalho for para a `main`, basta trocar `branches: [junior]` por `branches: [main]` no workflow
(a `main` já é aceita pelo ambiente).

## Movimento, acessibilidade e desempenho

- **Reduzir movimento:** com a opção "reduzir movimento" do sistema, ou se as bibliotecas de animação não carregarem, a página fica estática e completa:
  - sem scroll suave, sem seções presas e sem animações;
  - o radar do topo para num quadro fixo;
  - o letreiro fica parado.
- **Celular:** o trilho de cards vira um carrossel nativo com *snap*. O mapa fica fixo no topo e os passos da história passam por baixo dele.
- **Desempenho:**
  - o radar do topo só anima quando está visível e a aba está ativa;
  - as malhas mais pesadas carregam depois do resto da página;
  - não há vídeo nem imagem grande.
- **Cores:** marca (verde-limão), dado (escala azul e laranja das cidades) e estado (semáforo) vêm de tokens separados. O semáforo sempre usa ícone + texto, nunca só a cor.
- **Teclado:** filtros, busca (setas, Enter, Esc), trilha do mapa, cards e listas funcionam pelo teclado.
- **Tudo também em texto:** o que o mapa mostra também está no painel "Explore", na ficha e na busca.
- **Tema:** escuro é o padrão da marca; o botão no topo troca para o claro e lembra a escolha.
