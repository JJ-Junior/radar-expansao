# Etapa 5 · Camada gold: ranking, recomendação das 5 unidades e semáforo

- **Data:** 26/11/2026
- **Responsável:** _(a preencher)_
- **Arquivos afetados:** `sql/gold/`, `src/transformacao/executar.py`, `spec.md` (seções 3.3 e 5), `README.md`

## Objetivo
Transformar a silver nas tabelas que respondem às perguntas P1 a P8 do `prd.md`: indicadores por município, ranking de
expansão com as 5 unidades recomendadas, critérios e pesos, contexto macroeconômico e o semáforo "expandir agora ou esperar".

## Contexto fornecido
- `prd.md` v0.3 (critérios, pesos e as regras de dado faltante, região imediata, limites P5/P95 e tendência por CAGR).
- `spec.md` seções 3.3 e 5 (colunas e fórmulas) e o contrato de colunas já usado pelo site de apoio.
- Silver carregada e testada; mesma exigência de caminho único para os cenários A e B.

## Entrada (prompt)
> Tarefa: escrever as tabelas da gold e a transformação silver → gold.
> Restrições: cada tabela anotada com a pergunta do prd que responde; notas 0–100 por percentil; peso do critério sem dado
> redistribuído; espaço competitivo limitado aos percentis 5% e 95%, com marca para cidades sem academia; no máximo uma
> cidade por região imediata nas 5 recomendadas; semáforo de juros, inflação e câmbio com justificativa em texto; papel de
> leitura da API só com `SELECT` na gold; testes de qualidade e um exemplo de rastreio até a bronze.
> Formato: `sql/gold/NN_*.sql` idempotentes, função SQL chamada pelo mesmo executor da silver.

## Saída esperada
Gold recalculável em segundos, com todos os testes passando e resultados que façam sentido para o diretor de expansão.

## O que a IA entregou
- `gold.atualizar()` com as regras do prd, o laço que escolhe as 5 recomendadas pulando regiões imediatas repetidas e o texto
  pronto da justificativa do semáforo.
- 13 testes de qualidade e a view de rastreio (academias do 1º colocado: gold → silver → `bronze_id` → valor no JSON original).
- Permissões: `web_leitor` lê só as cinco tabelas; testes, rastreio e a função ficam fora da API.

## O que foi ajustado
- **Compatibilidade com o site:** além das notas separadas de nível e tendência da riqueza, a gold mantém `nota_riqueza`
  (média ponderada das duas), que o site já usava.
- **Regras sem caso real hoje:** nenhum município do universo tem dado faltante e a regra da região imediata não pula ninguém
  no top 5 atual. As duas foram testadas à parte: a redistribuição numa transação desfeita no fim (Recife sem renda →
  peso 0,75 e nota igual à conta manual) e a região imediata simulando 10 vagas (Osasco seria pulada por estar na mesma região
  de Santana de Parnaíba).
- **Acentos no terminal:** a saída do executor passou a ser forçada em UTF-8, porque nomes como "Cuiabá" apareciam trocados
  no terminal do Windows.
- **Conferência externa:** o 1º colocado (Recife) e o semáforo de outubro/2026 ("Expandir com cautela": juros verde,
  inflação vermelho, câmbio verde) batem com a prévia calculada direto das APIs pelo site de apoio.

## Lições
Regra de negócio que não aparece nos dados de hoje precisa de teste com caso construído; senão um erro só apareceria quando
os dados mudassem.
