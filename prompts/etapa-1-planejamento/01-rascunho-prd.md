# Etapa 1 · Rascunho do prd.md (rede de academias)

- **Data:** 26/11/2026
- **Responsável:** _(a preencher)_
- **Arquivos afetados:** `prd.md`

## Objetivo
Gerar a primeira versão do documento de requisitos para o cliente "rede de academias", com perguntas de negócio,
critérios e pesos do ranking justificados, escopo e critérios de sucesso.

## Contexto fornecido
- Enunciado do desafio (cenário, perguntas guia, entregáveis e critérios de avaliação).
- Análise de negócio do squad: "fator onde" (população, crescimento, PIB, PIB per capita) e "fator quando" (Selic, IPCA, câmbio).
- Lista de indicadores do IBGE e do BCB já testados nas APIs, com códigos e anos disponíveis.

## Entrada (prompt)
> Tarefa: escrever o `prd.md` do Radar de Expansão para uma rede de academias.
> Restrições: usar só indicadores que existem por município nas APIs do IBGE e do BCB; cada critério com fonte, sentido
> (maior/menor é melhor) e peso somando 100%; justificar cada peso pelo modelo de negócio de uma academia; separar
> o momento econômico do ranking de municípios; incluir o que está fora do escopo e como medir sucesso.
> Formato: Markdown, seções numeradas, tabelas para perguntas e critérios.

## Saída esperada
Documento específico do cliente (não serviria para uma farmácia), com perguntas numeradas ligadas às tabelas da gold.

## O que a IA entregou
- Oito perguntas de negócio (P1–P8), cada uma ligada a uma tabela da gold.
- Seis critérios com pesos 25/25/20/15/10/5 e justificativa.
- Semáforo "expandir agora / com cautela / esperar" fora da nota do município.

## O que foi ajustado
- **Base do crescimento populacional:** a primeira versão usava 2021 como ano inicial. Ao checar a API, a estimativa de 2021
  (213,3 milhões no Brasil) ficou acima do Censo 2022 (203,1 milhões), porque as estimativas antigas eram projetadas do Censo 2010.
  A base passou a ser o Censo 2022.
- **Universo do ranking:** o número de municípios com 50 mil habitantes ou mais foi conferido na estimativa de 2026 (687).
- Cliente confirmado pelo squad (rede de academias). Ainda **a revisar pelo squad:** pesos dos critérios, perfil da rede e limiares do semáforo.

## Lições
Toda afirmação numérica do prd.md precisa vir de uma chamada real à API, não da memória do assistente.
