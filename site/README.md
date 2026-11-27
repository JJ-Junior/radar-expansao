# Site de apoio — Radar de Expansão

Vitrine de expansão para o diretor da rede de academias, numa página só, contada como um pitch:

1. **Hero:** o radar varre o Brasil e acende as cidades avaliadas; KPIs e busca de cidade.
   **Pitch em vídeo:** botão de play no centro do radar do topo abre um modal com o vídeo legendado (4 min 33 s,
   `video/pitch-radar-expansao.mp4`, pôster `img/pitch-poster.jpg`); o vídeo só carrega ao abrir, sem botão nem menu de download. O endereço `#pitch` abre o modal.
2. **Letreiro** com os números do momento (Selic, IPCA, dólar, cidades no radar, 1ª do ranking, as recomendadas).
3. **Quando:** semáforo econômico, histórico mês a mês e as três séries.
4. **Onde:** mapa por regiões do IBGE que se aproxima com o scroll — Brasil → região → estado → região intermediária → região imediata —, e depois fica livre para explorar.
5. **As 5 recomendadas:** cards com o gráfico-radar das notas, num trilho horizontal, e o motivo de quem ficou de fora (trava de renda ou região imediata repetida); também o ranking geral por região.
6. **Explorar as 687 cidades:** um ponto por cidade num canvas; cinco vistas (mapa, renda × concorrência, crescimento × renda, ranking e por região) reorganizam os mesmos pontos com animação, com tooltip, busca e alternativa em tabela.
7. **Ficha da cidade**, com endereço próprio (`?municipio=<código IBGE>`).
8. **Critérios:** o perfil que o Radar procura (cada setor = peso).
9. **Método:** fórmula, regras, semáforo e limitações.
10. **Dados:** as camadas do Lakehouse.
11. **Chamada** para o dashboard publicado (https://radar-expansao.streamlit.app) e o repositório; o link do dashboard também fica no topo, no simulador e no rodapé.

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
| Hospedagem | Servidor autohospedado do projeto (nginx em Docker, exposto por túnel), que atualiza a partir da branch `junior` |

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
│   ├── cards.js          as recomendadas e o ranking geral (grade; carrossel no celular)
│   ├── explorar.js       as 687 cidades como pontos em canvas, cinco vistas com transição
│   ├── simulador.js      simule sua região: cidade central + raio (?centro=&raio=), mapa com o contorno dos municípios e ranking local
│   ├── dica.js           tooltip único do site (hover, foco, toque; Esc fecha)
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

A **imagem de prévia do link** (`img/previa.jpg`, 1200 × 630, usada pelas tags `og:image` e `twitter:image`) é gerada por
`src/exportacao/gerar_previa.py` a partir dos próprios dados (momento econômico e as recomendadas), com o Edge/Chrome sem janela;
o `exportar_site.py` a refaz no fim de cada exportação.

O `exportar_site.py` lê as tabelas `gold.*` com as credenciais do `.env` (o mesmo banco dos scripts de transformação).
Ele também conta as linhas de cada camada para a seção "Dados" e confere a soma dos pesos, as notas entre 0 e 100 e a
quantidade de cidades recomendadas antes de gravar. O site não calcula nota nem escolhe as recomendadas: só lê a gold.

## Publicação

O site está no ar em **https://radar-expansao.lovelearning.com.br**.

Ele é servido pelo servidor autohospedado do projeto: um nginx em Docker, exposto à internet por um túnel, que serve a
pasta `site/` direto de um clone do repositório. Esse clone faz `git pull` da branch `junior` **a cada 10 minutos**,
então não há passo de build nem de deploy:

1. rode `exportar_site.py` (se os dados mudaram) e confira o site localmente;
2. faça commit e push em `site/` na branch `junior`;
3. em até 10 minutos a versão nova está no ar (confira, por exemplo, o `gerado_em` de `dados/meta.json`).

**Cache:** o `index.html` tem o marcador `__VERSAO__` (meta `radar-versao`, `?v=` no CSS, no `main.js` e no *import map*
de todos os módulos; os JSONs de `dados/` também levam `?v=`). No servidor, o `atualizar.sh` troca o marcador pelo hash do
commit depois do `git pull`, e o `index.html` vai com `Cache-Control: no-cache`; assim cada commit gera URLs novas e o
navegador e o Cloudflare não seguram versão velha. **Módulo novo em `js/` precisa entrar no import map do `index.html`.**
Localmente o marcador fica literal e o site funciona igual.

Como os caminhos do site são todos relativos (`css/`, `js/`, `dados/`), a mesma pasta funciona na raiz do domínio,
numa subpasta ou no servidor local de teste.

## Movimento, acessibilidade e desempenho

- **Reduzir movimento:** com a opção "reduzir movimento" do sistema, ou se as bibliotecas de animação não carregarem, a página fica estática e completa:
  - sem scroll suave, sem seções presas e sem animações;
  - o radar do topo para num quadro fixo;
  - o letreiro fica parado.
- **Celular:** o trilho de cards vira um carrossel nativo com *snap*. O mapa fica fixo no topo e os passos da história passam por baixo dele.
- **Desempenho:**
  - o radar do topo só anima quando está visível e a aba está ativa;
  - as malhas mais pesadas carregam depois do resto da página;
  - o simulador baixa a malha municipal só das UFs que o mapa mostra (e guarda para as próximas simulações); enquanto ela não chega, ou se falhar, as cidades aparecem como pontos;
  - não há vídeo nem imagem grande.
- **Cores:** marca (verde-limão), dado (escala azul e laranja das cidades) e estado (semáforo) vêm de tokens separados. O semáforo sempre usa ícone + texto, nunca só a cor.
- **Teclado:** filtros, busca (setas, Enter, Esc), trilha do mapa, cards e listas funcionam pelo teclado.
- **Tudo também em texto:** o que o mapa mostra também está no painel "Explore", na ficha e na busca.
- **Tema:** escuro é o padrão da marca; o botão no topo troca para o claro e lembra a escolha.
