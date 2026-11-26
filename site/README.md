# Site de apoio — Radar de Expansão

Documentação e vitrine de dados do projeto, numa página só: mapa dos municípios, ficha de cada cidade,
ranking por região e estado, momento econômico, metodologia e arquitetura.

**Não é o dashboard oficial** (esse é o Streamlit em `src/app/`): é a porta de entrada pública do projeto.

## Stack (sem etapa de build)

| Parte | Como é feito |
|---|---|
| Página | `index.html` + `css/estilo.css` escritos à mão |
| Lógica | JavaScript puro em ES modules (`js/*.js`), sem framework |
| Mapa e gráficos | [D3](https://d3js.org/) 7.9.0 e [topojson-client](https://github.com/topojson/topojson-client) 3.1.0, por CDN com versão fixa |
| Fonte | Archivo (Google Fonts), com largura variável para os títulos condensados |
| Dados | JSONs estáticos em `dados/`, exportados da camada gold — contrato em [`dados/README.md`](dados/README.md) |
| Hospedagem | GitHub Pages, publicado pelo workflow `.github/workflows/site.yml` |

O navegador nunca fala com o banco: nenhuma credencial vai para o site.

## Estrutura

```
site/
├── index.html            página única, uma <section> por bloco
├── css/estilo.css        tokens de cor (marca × dado × estado), tema claro e escuro
├── js/
│   ├── main.js           ponto de entrada: carrega dados, liga as seções, endereço ?municipio=
│   ├── dados.js          leitura dos JSONs colunares
│   ├── indicadores.js    abas do mapa, critérios, rótulos (nenhum cálculo de nota)
│   ├── mapa.js           mapa coroplético em <canvas> com a malha do IBGE
│   ├── ficha.js          ficha do município: notas, percentis, municípios parecidos
│   ├── ranking.js        tabela filtrável e grade por UF
│   ├── macro.js          semáforo, histórico e gráficos de Selic, IPCA e dólar
│   ├── metodologia.js    pesos, critérios e camadas do Lakehouse
│   ├── busca.js          busca de município (combobox acessível)
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

Depois abra http://localhost:8000. Para abrir a ficha de um município direto: http://localhost:8000/?municipio=3550308
(código IBGE de 7 dígitos).

## Atualizar os dados

```powershell
# com o ambiente virtual ativo, na raiz do repositório
python src/exportacao/baixar_malha.py      # só quando o IBGE mudar a malha
python src/exportacao/exportar_site.py     # regenera site/dados/*.json
```

No `CONFIG` do `exportar_site.py`, `FONTE = "api"` gera a **prévia** direto das APIs (o site mostra o aviso
"Prévia — ranking calculado após a camada gold"). Quando a camada gold existir no Supabase, troque para
`FONTE = "gold"`: o script lê as tabelas `gold.*` com as credenciais do `.env`, conta as linhas de cada camada
para a seção "Arquitetura" e o aviso de prévia some sozinho.

## Publicar no GitHub Pages

O workflow [`.github/workflows/site.yml`](../.github/workflows/site.yml) publica a pasta `site/` a cada push na
branch `junior` que altere o site (ou manualmente, em **Actions → Site de apoio (GitHub Pages) → Run workflow**).

Antes do primeiro deploy, quem administra o repositório precisa liberar duas coisas (uma vez só):

1. **Settings → Pages → Build and deployment → Source:** escolher **GitHub Actions**.
2. **Settings → Environments → `github-pages` → Deployment branches and tags:** adicionar a regra para a branch
   **`junior`**. Por padrão o ambiente só aceita deploy da branch principal, e o workflow falha com
   *"Branch junior is not allowed to deploy to github-pages due to environment protection rules"*.
   (O ambiente `github-pages` aparece depois do passo 1; se não aparecer, rode o workflow uma vez.)

Endereço depois do deploy: `https://jj-junior.github.io/radar-expansao/`.

Quando o trabalho for para a `main`, basta trocar `branches: [junior]` por `branches: [main]` no workflow
(a `main` já é aceita pelo ambiente).

## Acessibilidade e decisões de visual

- Tema claro e escuro (segue o sistema; o botão no topo troca e lembra a escolha).
- Cores de **dado** (escala azul sequencial; vermelho–cinza–azul para crescimento), de **marca** (verde-limão) e de
  **estado** (semáforo) vêm de tokens separados no CSS. O semáforo sempre usa ícone + texto, nunca só a cor.
- "Sem dado" no mapa é hachurado, para não se confundir com a faixa do meio da escala.
- Tudo que o mapa mostra também está em texto: lista de destaques ao lado, busca, tabela do ranking e ficha.
- Abas e filtros funcionam pelo teclado (setas, Home, End); a busca é um combobox com setas, Enter e Esc.
