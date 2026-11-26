# prd.md — Radar de Expansão · Rede de academias

> ⚠️ **RASCUNHO**
> Versão 0.4 (26/11/2026). Cliente confirmado pelo squad: rede de academias. Critérios e pesos ainda em revisão; qualquer mudança é registrada aqui antes de ir para o código.
> v0.4: trava de renda mínima na lista das 5 unidades recomendadas (nota de poder de compra ≥ 50).
> v0.3: dado faltante com redistribuição de peso; recomendação com no máximo uma cidade por região imediata; espaço competitivo
> com limites nos percentis 5% e 95%; tendência do PIB per capita como taxa média anual (CAGR).

---

## 1. O cliente

**Vertical:** rede de academias de ginástica e musculação (cliente da consultoria Bússola Pública).

**Perfil proposto:** rede de padrão intermediário a alto — mensalidade acima das redes de baixo custo, equipamentos de musculação e
esteiras em boa parte importados, unidades de médio porte. Quer abrir **5 novas unidades no próximo ano** e precisa decidir **onde** e **quando**.

**Quem usa o Radar:** o diretor de expansão. Ele decide com base em visitas e intuição e precisa, em 30 segundos, ver quais cidades priorizar e por quê.

## 2. O problema hoje

- A escolha da cidade é feita no "feeling": "a cidade está crescendo", "o concorrente abriu lá".
- Olhar só o tamanho ou o crescimento da população engana: uma cidade pode encher de gente sem renda para pagar a mensalidade.
- Academia é **gasto que o cliente corta primeiro** quando o orçamento aperta. Renda e momento econômico pesam mais do que para um varejo de necessidade básica.
- Abrir uma unidade é caro e difícil de desfazer (contrato de locação longo, obra, equipamento). Uma unidade ruim consome o lucro de várias boas.
- O momento também importa: juros altos alongam o retorno do investimento, inflação aperta a renda do aluno e os custos,
  e o dólar alto encarece os equipamentos importados.

## 3. Perguntas de negócio

| # | Pergunta | Onde é respondida |
|---|---|---|
| P1 | Quais são a população, o PIB, o PIB per capita e o crescimento de cada município candidato? | `gold.indicadores_municipio` · ficha do município |
| P2 | Quais os 10 municípios com maior potencial para uma nova academia em cada estado e região? | `gold.ranking_expansao` · filtros por UF e região |
| P3 | Quais municípios mais cresceram em população desde o Censo 2022? | `gold.indicadores_municipio` |
| P4 | Quais cidades médias (100 a 500 mil habitantes) têm renda e PIB per capita acima da média do seu estado? | `gold.indicadores_municipio` |
| P5 | Onde há **poucas academias por habitante** em cidades com bom poder de compra (espaço para entrar)? | `gold.ranking_expansao` · nota de espaço competitivo |
| P6 | A Selic subiu ou caiu nos últimos 12 meses? A inflação (IPCA) está acelerando? O dólar subiu? | `gold.contexto_macro` |
| P7 | **Fator quando:** o momento econômico favorece **expandir agora, com cautela ou esperar**? | `gold.momento_expansao` · semáforo no topo do dashboard |
| P8 | Se a rede abrir 5 unidades no próximo ano, quais municípios são os melhores candidatos (renda acima da mediana do universo e no máximo um por região imediata) — e por quê? | `gold.ranking_expansao` + `gold.ranking_criterio` · página "Como o ranking é calculado" |

## 4. Critérios do ranking ("fator onde")

**Universo:** municípios com **50 mil habitantes ou mais** (687 municípios na estimativa de 2026). Abaixo disso, o público
pagante de uma unidade de médio porte é pequeno demais.

**Como cada critério vira nota:** percentil do município dentro do universo, de 0 a 100 (municípios empatados recebem o mesmo
percentil, o da posição média do empate). A nota final é a média ponderada pelos pesos abaixo.

| Critério | O que mede | Fonte (IBGE) | Sentido | Peso |
|---|---|---|---|---|
| **Tamanho de mercado** | População estimada mais recente | Estimativas de população (6579) | maior é melhor | **25%** |
| **Poder de compra** | Renda domiciliar per capita média | Censo 2022 (10295) | maior é melhor | **25%** |
| **Espaço competitivo** | Academias (CNAE 93.13-1) por 10 mil habitantes | Cadastro Central de Empresas (9418) | **menor é melhor** | **20%** |
| **Crescimento** | Crescimento anual da população desde o Censo 2022 | Censo 2022 (4714) + estimativas (6579) | maior é melhor | **15%** |
| **Riqueza local** | PIB per capita: nível no último ano (5%) + tendência = taxa média anual (CAGR) na janela de 5 anos (5%) | PIB dos Municípios (5938) ÷ população | maior é melhor | **10%** |
| **Mercado formal** | Salário médio mensal dos empregos formais | Cadastro Central de Empresas (9509) | maior é melhor | **5%** |

**Por que esses pesos**
- **Mercado (25%) + poder de compra (25%)** são a base: a academia precisa de gente **e** de renda para pagar a mensalidade.
  Os dois com o mesmo peso evitam o erro clássico de olhar só volume ou só renda.
- **Espaço competitivo (20%)** diferencia o Radar de um "ranking de cidades grandes": uma capital pode ter muita gente e
  já estar saturada de academias. O dado vem do número de empresas da classe CNAE 93.13-1 (condicionamento físico), validado por município.
- **Crescimento (15%)** mostra demanda nova — famílias que chegam e ainda não têm academia. Nunca pesa sozinho: crescer sem renda é armadilha.
  A base é o Censo 2022 porque as estimativas anteriores foram projetadas do Censo 2010 e superestimavam a população.
- **Riqueza local (10%)** inclui a **tendência** do PIB per capita: se a população cresce mais que a economia, a cidade está empobrecendo.
  A tendência é o **crescimento médio anual composto (CAGR)** entre o primeiro e o último ano de uma janela de 5 anos do PIB
  (hoje 2019 → 2023). A janela atravessa a pandemia (2020), quando muitos municípios caíram e depois se recuperaram; por isso
  usamos a **taxa média do período**, que não é distorcida pelo tombo e pela retomada de anos isolados, e não a variação ano a ano.
- **Mercado formal (5%)** é um ajuste fino: salário formal mais alto indica renda mais estável para uma mensalidade recorrente.

### 4.1 Regras de cálculo

**Dado faltante — redistribuição do peso.** Se um município não tem dado para um critério, o peso desse critério é
**redistribuído proporcionalmente** entre os critérios que ele tem: a nota final é a soma de `peso × nota` dos critérios
disponíveis dividida pela soma dos pesos disponíveis. Exemplo: sem dado de salário médio (5%), os outros critérios passam a valer
95% e são reescalados para somar 100%. O município fica marcado como **"dados incompletos"** no dashboard, com a lista do que faltou.
Assim a falta de dado não ajuda nem prejudica artificialmente a cidade (uma nota neutra de 50 puxaria para o meio cidades
muito boas ou muito ruins).

**Espaço competitivo — limites nos percentis 5% e 95%.** Antes de calcular a nota inversa, academias por 10 mil habitantes são
**limitadas aos percentis 5% e 95% do universo** (*winsorização*): valores abaixo do P5 viram o P5 e acima do P95 viram o P95.
Isso evita que poucos valores extremos achatem a nota de todas as outras cidades.
Uma cidade do universo com **zero academias** recebe a nota do limite (a mesma de quem está no P5), **não 100 automático**, e
ganha a marca **"verificar concorrência"**: zero empresas na CNAE 93.13-1 pode ser falta de mercado, academias registradas em outra
atividade ou estúdios informais, e precisa de checagem local antes de virar recomendação.

### 4.2 Recomendação das 5 unidades (P8)

A lista **"5 unidades recomendadas"** segue a ordem da nota final, com duas regras a mais:

1. **Trava de renda mínima:** só entra na lista a cidade com **nota de poder de compra ≥ 50**, ou seja, renda domiciliar per
   capita na metade de cima do universo (percentil 50). É a resposta da pergunta de teste 1: cidade populosa com renda baixa é
   armadilha para uma academia de padrão intermediário a alto, mesmo que o tamanho de mercado e o espaço competitivo puxem
   a nota final para cima.
2. **No máximo uma cidade por região imediata do IBGE.** Regiões imediatas agrupam os municípios que dividem o mesmo polo de
   comércio e serviços; duas unidades na mesma região disputariam o mesmo público (canibalização).

Quando a próxima cidade do ranking não passa na trava ou cai numa região imediata já escolhida, ela é pulada e a lista segue
para a seguinte. O **ranking completo não muda** — as duas regras valem só para a lista das 5 recomendadas, e a cidade pulada
continua na sua posição (com a indicação de que não é elegível para a recomendação). Os dois valores (quantidade de cidades e
nota mínima de poder de compra) ficam num único lugar, a tabela de parâmetros do ranking, e aparecem na página de metodologia.

## 5. Momento econômico ("fator quando")

Fica **fora da nota do município** (vale igual para todas as cidades) e aparece como **semáforo** no topo do dashboard.

| Sinal | Por que importa para uma academia | Fonte |
|---|---|---|
| **Juros** (meta da Selic, variação em 12 meses) | Financiar a abertura fica mais caro; o retorno do investimento demora mais | BCB, série 432 |
| **Inflação** (IPCA acumulado em 12 meses e tendência) | Aperta a renda do aluno (a academia é o primeiro gasto cortado) e sobe aluguel, energia e folha | IBGE, agregado 7060 |
| **Câmbio** (dólar, variação em 12 meses) | Esteiras e aparelhos de musculação são, em boa parte, importados ou têm componentes importados | BCB, série 10813 |

Cada sinal fica verde, amarelo ou vermelho; a soma gera a recomendação **"Expandir agora"**, **"Expandir com cautela"** ou **"Esperar"**
(regras e limiares no `spec.md`, seção 5.1). **"Esperar" é uma resposta válida:** o Radar pode indicar a cidade certa e, ao mesmo tempo,
recomendar segurar o caixa até o cenário melhorar.

## 6. Perguntas de teste do modelo

O squad usa estas perguntas para checar se o ranking faz sentido para **este** cliente:

1. **Cidade populosa com renda baixa é oportunidade ou armadilha?** Para academia de padrão intermediário a alto, **armadilha**:
   por isso poder de compra pesa tanto quanto tamanho de mercado, e a lista das 5 recomendadas só aceita cidades com renda
   acima da mediana do universo (trava de renda, seção 4.2).
2. **Capital cheia de concorrentes ou cidade média crescendo sem chamar atenção?** O espaço competitivo e o crescimento favorecem
   a cidade média; o dashboard permite comparar as duas lado a lado.
3. **Como explicar o ranking a um diretor que decide no feeling?** Cada município mostra a nota de cada critério (0 a 100) e uma frase
   que resume os pontos fortes e fracos; a página de metodologia mostra pesos e fontes.
4. **Cidade grande sem nenhuma academia registrada é a melhor oportunidade?** Não automaticamente: recebe a nota do limite e a marca
   "verificar concorrência", para o diretor confirmar no local antes de decidir.
5. **As 5 recomendações podem ser cidades vizinhas?** Não: no máximo uma por região imediata, para as unidades não disputarem
   o mesmo público.

## 7. Escopo

**Dentro**
- Todos os municípios do Brasil nas camadas bronze e silver; ranking para os municípios com 50 mil habitantes ou mais.
- Indicadores do IBGE (população, Censo 2022, PIB, renda, academias por CNAE, salário médio, IPCA) e do BCB (Selic, dólar).
- Atualização semanal automática.
- Dashboard com ranking filtrável por região e estado, ficha do município, momento econômico e explicação do cálculo.

**Fora**
- Escolha do bairro ou do ponto comercial (o Radar indica a cidade, não o endereço).
- Preço de aluguel, fluxo de pessoas, dados de cartão ou de redes sociais.
- Concorrência por marca e academias informais (o dado conta empresas formais da CNAE 93.13-1; estúdios registrados em outra
  atividade não entram).
- Previsão econômica (o semáforo olha o passado recente, não projeta o futuro).
- Viabilidade financeira de cada unidade (payback, investimento por unidade).

## 8. Marcos e prazo

Fase 2 do projeto: início em 18/11/2026, **entrega em 20/12/2026**.

| Datas | Marco |
|---|---|
| 26–28/11 | Repositório criado · prd.md, spec.md e agents.md revisados · Supabase criado com os schemas bronze, silver e gold |
| 29/11–03/12 | Bronze: ingestão de localidades, população, PIB, IPCA, Censo 2022, Cadastro Central de Empresas, Selic e dólar |
| 04–08/12 | Silver: modelo estrela (dimensões de região, UF, município e calendário; fatos municipais e macroeconômicos) |
| a partir de 06/12 | Automação no n8n em paralelo: agenda semanal + checagem de período novo |
| 09–11/12 | Gold: indicadores por município, ranking de expansão, contexto macro e semáforo do momento |
| 12–14/12 | Dashboard Streamlit publicado no Streamlit Cloud |
| 15–17/12 | Site de apoio · README com prints · pasta `prompts/` revisada |
| 18–19/12 | Apresentação (até 6 slides) + ensaio + folga para imprevistos |
| **20/12** | **Entrega** |

## 9. Como saber que deu certo

- [ ] O pipeline roda do início ao fim, com as duas APIs, sem intervenção manual.
- [ ] O n8n atualiza os dados sozinho toda semana e registra cada execução.
- [ ] Qualquer número da gold pode ser rastreado até a resposta original da API na bronze.
- [ ] O dashboard publicado responde às perguntas P1 a P8.
- [ ] Em 30 segundos, o diretor de expansão identifica as 5 cidades candidatas e o motivo de cada uma.
- [ ] O semáforo mostra a recomendação do momento e explica o porquê.
- [ ] Checagens automáticas: soma dos pesos = 100% (também depois da redistribuição em cada município), todos os municípios do
      universo com nota, nenhuma nota fora de 0–100, as 5 recomendadas em regiões imediatas diferentes e todas com nota
      de poder de compra ≥ 50.
