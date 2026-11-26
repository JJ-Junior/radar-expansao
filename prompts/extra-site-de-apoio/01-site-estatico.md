# Extra · Site de apoio (documentação + vitrine de dados)

- **Data:** 26/11/2026
- **Responsável:** _(a preencher)_
- **Arquivos afetados:** `site/`, `src/exportacao/`, `.github/workflows/site.yml`, `spec.md` (seção 9.2)

## Objetivo
Criar uma porta de entrada pública do projeto — mapa dos municípios, ficha de cada cidade, ranking, momento econômico,
metodologia e arquitetura — sem servidor e sem nenhuma credencial no navegador.

## Contexto fornecido
- `prd.md` (perguntas de negócio, critérios e pesos) e `spec.md` (tabelas da gold, regras 5.1 a 5.3).
- Restrições: hospedagem gratuita, nada de etapa de build, nenhum acesso do navegador ao banco.

## Entrada (prompt)
> Tarefa: construir um site estático que leia arquivos JSON exportados da camada gold, um por tabela, com os mesmos nomes
> de colunas do `spec.md`; publicar no GitHub Pages por GitHub Actions.
> Restrições: HTML, CSS e JavaScript puro (ES modules), bibliotecas por CDN com versão fixa, tema claro e escuro, acessível;
> o site não calcula notas, só lê a gold. Enquanto a gold não existir, gerar uma prévia com as mesmas regras direto das APIs,
> marcada como prévia na tela.
> Formato: `site/` + scripts de exportação em `src/exportacao/` com o cabeçalho padrão e bloco `CONFIG`.

## Saída esperada
Site publicado que abre em qualquer navegador, com um contrato de dados documentado que o exportador da gold possa seguir.

## O que a IA entregou
- `site/` estático com mapa coroplético, ficha do município, ranking filtrável, semáforo do momento econômico e metodologia.
- Contrato dos dados em `site/dados/README.md` (formato colunar `{colunas, linhas}`, um arquivo por tabela da gold).
- `src/exportacao/exportar_site.py` com dois modos (`"gold"` oficial e `"api"` prévia), `previa_api.py` e `baixar_malha.py`.
- Workflow de publicação no GitHub Pages.

## O que foi ajustado
- A prévia direto das APIs foi conferida contra o `prd.md`: 687 municípios no universo de 50 mil habitantes ou mais.
- O site mostra o aviso de prévia enquanto os dados não vierem da gold, para não ser confundido com o resultado oficial.
- O mesmo snapshot JSON passou a servir de plano B do dashboard quando a API do banco não responder (`spec.md`, seção 9.1).
- Pendente para o squad: liberar a publicação a partir da branch de desenvolvimento nas configurações do GitHub Pages.

## Lições
Um contrato de dados escrito antes (mesmas colunas da gold) deixou o site independente do banco e reaproveitável como fallback.
