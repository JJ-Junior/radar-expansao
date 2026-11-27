// Rótulos de regiões e UFs, critérios do ranking, indicadores da ficha e rótulos do semáforo.
// Nenhum cálculo de nota acontece aqui: o site só lê as colunas da gold.

import { decimal, fracaoAoAno, inteiro, reais } from "./formato.js";

export const REGIOES = [
  { sigla: "N", nome: "Norte" },
  { sigla: "NE", nome: "Nordeste" },
  { sigla: "SE", nome: "Sudeste" },
  { sigla: "S", nome: "Sul" },
  { sigla: "CO", nome: "Centro-Oeste" },
];

export const NOMES_UF = {
  AC: "Acre", AL: "Alagoas", AM: "Amazonas", AP: "Amapá", BA: "Bahia", CE: "Ceará", DF: "Distrito Federal",
  ES: "Espírito Santo", GO: "Goiás", MA: "Maranhão", MG: "Minas Gerais", MS: "Mato Grosso do Sul",
  MT: "Mato Grosso", PA: "Pará", PB: "Paraíba", PE: "Pernambuco", PI: "Piauí", PR: "Paraná",
  RJ: "Rio de Janeiro", RN: "Rio Grande do Norte", RO: "Rondônia", RR: "Roraima", RS: "Rio Grande do Sul",
  SC: "Santa Catarina", SE: "Sergipe", SP: "São Paulo", TO: "Tocantins",
};

/** Critérios na ordem do prd.md; o peso vem de ranking_criterio.json. */
export const CRITERIOS = [
  { criterio: "mercado", nome: "Tamanho de mercado", indicador: "populacao" },
  { criterio: "poder_compra", nome: "Poder de compra", indicador: "renda_dom_per_capita" },
  { criterio: "espaco_competitivo", nome: "Espaço competitivo", indicador: "academias_por_10mil_hab" },
  { criterio: "crescimento", nome: "Crescimento", indicador: "crescimento_pop_aa" },
  { criterio: "riqueza", nome: "Riqueza local", indicador: "pib_per_capita" },
  { criterio: "mercado_formal", nome: "Mercado formal", indicador: "salario_medio" },
];

/**
 * O que compõe a nota, em linguagem simples (um texto por critério do prd; a riqueza local junta nível e tendência).
 * `curto` vai no cartão de notas; `mede`, `fonte` e `porque` no bloco "O que compõe a nota" do método.
 * Indicador, fonte e sentido conferidos em sql/gold/02_atualizar_gold.sql e no spec.md; os anos vêm de meta.json.
 * O mesmo texto é usado na página "Como o ranking é calculado" do dashboard.
 */
export function textosCriterios(meta) {
  const p = meta?.periodos ?? {};
  const ano = (v, alt) => v ?? alt;
  return {
    mercado: {
      curto: "População: mais moradores, mais clientes possíveis",
      mede: "Quantas pessoas moram na cidade (população estimada mais recente).",
      fonte: `IBGE, estimativa de população (tabela 6579), ${ano(p.populacao, "último ano")}.`,
      porque: "Mais moradores querem dizer mais clientes possíveis para uma unidade.",
      sentido: "maior é melhor",
    },
    poder_compra: {
      curto: "Renda por pessoa: quem pode pagar mensalidade",
      mede: "Renda média por pessoa das famílias, em R$ por mês.",
      fonte: `IBGE, Censo ${ano(p.censo, 2022)} (tabela 10295).`,
      porque: "Mostra se os moradores conseguem pagar a mensalidade. Também é a trava das recomendadas.",
      sentido: "maior é melhor",
    },
    espaco_competitivo: {
      curto: "Menos academias por habitante dá nota maior",
      mede: "Academias formais (CNAE 93.13-1, condicionamento físico) para cada 10 mil habitantes.",
      fonte: `IBGE, Cadastro Central de Empresas (tabela 9418), ${ano(p.academias, "último ano")}, dividido pela população.`,
      porque: "Menos academias por habitante deixa mais espaço para uma nova. A escala é invertida e os extremos são limitados aos percentis 5% e 95%.",
      sentido: "menor é melhor",
    },
    crescimento: {
      curto: "Quanto a população cresce por ano",
      mede: `Crescimento anual da população desde o Censo ${ano(p.censo, 2022)}.`,
      fonte: `IBGE, Censo ${ano(p.censo, 2022)} (tabela 4714) e estimativa de população (tabela 6579).`,
      porque: "Cidade que cresce traz clientes novos nos próximos anos.",
      sentido: "maior é melhor",
    },
    riqueza: {
      curto: "PIB por habitante: nível e tendência",
      mede: "PIB por habitante: o valor do último ano (metade do peso) e o crescimento médio anual em 5 anos (a outra metade).",
      fonte: `IBGE, PIB dos Municípios (tabela 5938), até ${ano(p.pib, "o último ano")}, dividido pela população.`,
      porque: "Uma economia local forte e em alta sustenta o consumo.",
      sentido: "maior é melhor",
    },
    mercado_formal: {
      curto: "Salário médio dos empregos formais",
      mede: "Salário médio mensal dos empregos formais, em R$.",
      fonte: `IBGE, Cadastro Central de Empresas (tabela 9509), ${ano(p.salario, "último ano")}.`,
      porque: "Emprego formal dá renda estável para um gasto que se repete todo mês.",
      sentido: "maior é melhor",
    },
  };
}
export const FRASE_PERCENTIL = "Cada nota vai de 0 a 100 e é o percentil da cidade entre as que têm 50 mil habitantes ou mais: " +
  "nota 80 quer dizer que ela está à frente de 80% delas naquele critério. A nota final é a média ponderada pelos pesos.";

/**
 * Componentes da nota como estão em ranking_criterio.json (7 linhas: a riqueza local tem nível e tendência).
 * Nome e descrição com acento para exibir; peso, fonte, sentido e ordem vêm sempre da gold.
 */
export const COMPONENTES = {
  mercado: { nome: "Tamanho de mercado", descricao: "População estimada mais recente." },
  poder_compra: { nome: "Poder de compra", descricao: "Renda domiciliar per capita média (Censo 2022)." },
  espaco_competitivo: { nome: "Espaço competitivo", descricao: "Academias (CNAE 93.13-1) por 10 mil habitantes, limitado aos percentis 5% e 95% do universo." },
  crescimento: { nome: "Crescimento", descricao: "Taxa anual de crescimento da população desde o Censo 2022." },
  riqueza_nivel: { nome: "Riqueza · nível", descricao: "PIB per capita do último ano disponível." },
  riqueza_tendencia: { nome: "Riqueza · tendência", descricao: "Taxa média anual do PIB per capita em 5 anos." },
  mercado_formal: { nome: "Mercado formal", descricao: "Salário médio mensal dos empregos formais." },
};
export const nomeComponente = (c) => COMPONENTES[c.criterio]?.nome ?? c.criterio;

/** Peso de um critério do radar (soma dos componentes do mesmo grupo: riqueza = nível + tendência). */
export function pesoDoCriterio(criterios, criterio) {
  const linhas = criterios.filter((x) => (x.grupo ?? x.criterio) === criterio);
  return linhas.length ? linhas.reduce((s, x) => s + Number(x.peso), 0) : null;
}

/** Parâmetro de gold.parametro_ranking (ou o padrão, se o arquivo não existir). */
export function parametro(estado, nome, padrao) {
  const linha = estado.parametros?.find((p) => p.parametro === nome);
  return linha ? Number(linha.valor) : padrao;
}

/** Indicadores da ficha. `comparacao` vira a frase do percentil. */
export const INDICADORES_FICHA = [
  { coluna: "populacao", rotulo: "População", formato: inteiro, comparacao: "maior que" },
  { coluna: "renda_dom_per_capita", rotulo: "Renda domiciliar per capita", formato: reais, comparacao: "maior que" },
  { coluna: "academias_qtd", rotulo: "Academias (CNAE 93.13-1)", formato: inteiro, comparacao: null },
  { coluna: "academias_por_10mil_hab", rotulo: "Academias por 10 mil hab.", formato: (v) => decimal(v, 2), comparacao: "mais academias por habitante que" },
  { coluna: "crescimento_pop_aa", rotulo: "Crescimento desde 2022", formato: (v) => fracaoAoAno(v), comparacao: "cresce mais que" },
  { coluna: "pib_per_capita", rotulo: "PIB per capita", formato: reais, comparacao: "maior que" },
  { coluna: "pib_per_capita_tendencia", rotulo: "Tendência do PIB per capita", formato: (v) => fracaoAoAno(v), comparacao: "cresce mais que" },
  { coluna: "salario_medio", rotulo: "Salário médio formal", formato: reais, comparacao: "maior que" },
];

/** Cor da recomendação do semáforo (estado, não dado). */
export const STATUS_RECOMENDACAO = {
  "Expandir agora": "verde",
  "Expandir com cautela": "amarelo",
  "Esperar": "vermelho",
};
export const ROTULO_SINAL = { verde: "favorável", amarelo: "neutro", vermelho: "desfavorável" };
