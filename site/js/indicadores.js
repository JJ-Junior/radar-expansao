// Definição dos indicadores (abas do mapa e ficha) e dos critérios do ranking.
// Nenhum cálculo de nota acontece aqui: o site só lê as colunas da gold.

import { compacto, decimal, fracaoAoAno, inteiro, reais } from "./formato.js";

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

/** Abas do mapa. `escala`: "sequencial" (um tom) ou "divergente" (negativo x positivo). */
export const INDICADORES_MAPA = [
  {
    chave: "nota", rotulo: "Nota do ranking", titulo: "Nota final do ranking",
    valor: (m) => m.ranking?.nota_final ?? null, formato: (v) => decimal(v, 1), escala: "sequencial",
    explica: "Média ponderada das seis notas, de 0 a 100. Só municípios com 50 mil habitantes ou mais entram no ranking; os demais ficam em cinza.",
    semDado: "Fora do universo do ranking", destaques: "Maiores notas",
  },
  {
    chave: "populacao", rotulo: "População", titulo: "População estimada",
    valor: (m) => m.populacao, formato: compacto, escala: "sequencial",
    explica: "Estimativa mais recente do IBGE. Tamanho de mercado pesa 25% na nota.",
    semDado: "Sem dado", destaques: "Mais populosos",
  },
  {
    chave: "renda", rotulo: "Renda per capita", titulo: "Renda domiciliar per capita",
    valor: (m) => m.renda_dom_per_capita, formato: reais, escala: "sequencial",
    explica: "Rendimento médio mensal por morador, Censo 2022. Poder de compra pesa 25% na nota.",
    semDado: "Sem dado", destaques: "Maior renda",
  },
  {
    chave: "academias", rotulo: "Academias por 10 mil hab.", titulo: "Academias por 10 mil habitantes",
    valor: (m) => m.academias_por_10mil_hab, formato: (v) => decimal(v, 2), escala: "sequencial",
    explica: "Empresas de condicionamento físico (CNAE 93.13-1) por 10 mil habitantes. Mais escuro = mais concorrência; no ranking, menos academias dá nota maior (peso 20%).",
    semDado: "Sem dado", destaques: "Mais academias por habitante",
  },
  {
    chave: "crescimento", rotulo: "Crescimento", titulo: "Crescimento da população",
    valor: (m) => m.crescimento_pop_aa, formato: (v) => fracaoAoAno(v), escala: "divergente",
    explica: "Crescimento anual composto desde o Censo 2022. Vermelho perdeu população, azul ganhou. Pesa 15% na nota.",
    semDado: "Sem dado", destaques: "Que mais crescem",
    limites: [-0.01, -0.0025, 0.0025, 0.01, 0.02],
  },
];

/** Critérios na ordem do prd.md; o peso vem de ranking_criterio.json. */
export const CRITERIOS = [
  { criterio: "mercado", nome: "Tamanho de mercado", indicador: "populacao" },
  { criterio: "poder_compra", nome: "Poder de compra", indicador: "renda_dom_per_capita" },
  { criterio: "espaco_competitivo", nome: "Espaço competitivo", indicador: "academias_por_10mil_hab" },
  { criterio: "crescimento", nome: "Crescimento", indicador: "crescimento_pop_aa" },
  { criterio: "riqueza", nome: "Riqueza local", indicador: "pib_per_capita" },
  { criterio: "mercado_formal", nome: "Mercado formal", indicador: "salario_medio" },
];

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

const ICONES = {
  verde: '<path d="M5 12.5l4.2 4.2L19 7" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
  amarelo: '<path d="M12 5v9" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><circle cx="12" cy="19" r="1.8" fill="currentColor"/>',
  vermelho: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>',
};

/** Ícone redondo do semáforo: forma + cor, nunca só cor. */
export function iconeStatus(status, extraClasse = "") {
  return `<span class="icone-status icone-status--${status} ${extraClasse}" aria-hidden="true"><svg viewBox="0 0 24 24">${ICONES[status] ?? ""}</svg></span>`;
}
