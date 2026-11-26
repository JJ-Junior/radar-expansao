// Gráfico-radar das 6 notas de uma cidade (0 a 100), em SVG.
// É a assinatura visual do site: aparece nos cards e na ficha.

import { CRITERIOS } from "./indicadores.js";

const CURTOS = {
  mercado: "Mercado", poder_compra: "Renda", espaco_competitivo: "Espaço",
  crescimento: "Cresc.", riqueza: "Riqueza", mercado_formal: "Formal",
};

/** Devolve o HTML de um <svg> com o radar das notas de `ranking` (linha de ranking_expansao). */
export function graficoRadar(ranking, { tamanho = 220, rotulos = true, valores = false, titulo = "" } = {}) {
  const margem = rotulos ? 38 : 6;
  const raio = tamanho / 2 - margem;
  const centro = tamanho / 2;
  const n = CRITERIOS.length;
  const ponto = (i, valor) => {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / n;
    const r = (valor / 100) * raio;
    return [centro + Math.cos(a) * r, centro + Math.sin(a) * r];
  };
  const aneis = [25, 50, 75, 100].map((v) => {
    const pts = CRITERIOS.map((_, i) => ponto(i, v).join(",")).join(" ");
    return `<polygon class="anel ${v === 50 ? "anel--50" : ""}" points="${pts}"/>`;
  }).join("");
  const eixos = CRITERIOS.map((_, i) => { const [x, y] = ponto(i, 100); return `<line class="eixo" x1="${centro}" y1="${centro}" x2="${x}" y2="${y}"/>`; }).join("");
  const notas = CRITERIOS.map((c) => ranking[`nota_${c.criterio}`] ?? 50);
  const forma = notas.map((v, i) => ponto(i, Math.max(v, 3)).join(",")).join(" ");
  const vertices = notas.map((v, i) => { const [x, y] = ponto(i, Math.max(v, 3)); return `<circle class="vertice" cx="${x}" cy="${y}" r="${tamanho > 260 ? 3.5 : 2.5}"/>`; }).join("");
  const textos = rotulos ? CRITERIOS.map((c, i) => {
    const [x, y] = ponto(i, 100 + (tamanho > 260 ? 22 : 26));
    const ancora = Math.abs(x - centro) < 4 ? "middle" : x > centro ? "start" : "end";
    const nome = tamanho > 260 ? c.nome : CURTOS[c.criterio];
    const valor = valores ? `<tspan class="valor" x="${x}" dy="13">${Math.round(notas[i])}</tspan>` : "";
    return `<text x="${x}" y="${y}" text-anchor="${ancora}" dominant-baseline="middle">${nome}${valor}</text>`;
  }).join("") : "";
  const descricao = titulo || `Notas: ${CRITERIOS.map((c, i) => `${c.nome} ${Math.round(notas[i])}`).join(", ")}`;
  return `<svg class="radar-notas" viewBox="0 0 ${tamanho} ${tamanho}" role="img" aria-label="${descricao}">
    ${aneis}${eixos}<polygon class="forma" points="${forma}"/>${vertices}${textos}</svg>`;
}
