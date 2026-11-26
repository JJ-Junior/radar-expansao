// Rótulos de regiões e UFs, critérios do ranking, indicadores da ficha e ícones do semáforo.
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
