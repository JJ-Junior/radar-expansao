// Formatação de números e datas no padrão brasileiro.
// Todas as funções aceitam null/undefined e devolvem "—" nesses casos.

const formatadores = new Map();
function nf(min, max) {
  const chave = `${min}-${max}`;
  if (!formatadores.has(chave)) {
    formatadores.set(chave, new Intl.NumberFormat("pt-BR", { minimumFractionDigits: min, maximumFractionDigits: max }));
  }
  return formatadores.get(chave);
}

const vazio = (v) => v === null || v === undefined || Number.isNaN(v);
export const TRACO = "—";

export const inteiro = (v) => (vazio(v) ? TRACO : nf(0, 0).format(v));
export const decimal = (v, casas = 1) => (vazio(v) ? TRACO : nf(casas, casas).format(v));
export const reais = (v) => (vazio(v) ? TRACO : `R$ ${nf(0, 0).format(v)}`);
export const reaisCentavos = (v, casas = 2) => (vazio(v) ? TRACO : `R$ ${nf(casas, casas).format(v)}`);

/** Valor já em % (ex.: 4.63) -> "4,63%". */
export const porcento = (v, casas = 1, sinal = false) =>
  vazio(v) ? TRACO : `${sinal && v > 0 ? "+" : ""}${nf(casas, casas).format(v)}%`.replace("-", "−");

/** Fração (ex.: 0.0123) -> "+1,23% a.a.". */
export const fracaoAoAno = (v, casas = 2) =>
  vazio(v) ? TRACO : `${porcento(v * 100, casas, true)} a.a.`;

/** 1234567 -> "1,23 mi"; 85400 -> "85,4 mil". */
export function compacto(v) {
  if (vazio(v)) return TRACO;
  const a = Math.abs(v);
  if (a >= 1e9) return `${nf(1, 1).format(v / 1e9)} bi`;
  if (a >= 1e6) return `${nf(2, 2).format(v / 1e6)} mi`;
  if (a >= 1e4) return `${nf(1, 1).format(v / 1e3)} mil`;
  return inteiro(v);
}

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
  "agosto", "setembro", "outubro", "novembro", "dezembro"];

/** "2026-10-01" -> Date local (sem deslocamento de fuso). */
export function paraData(texto) {
  const [a, m, d] = texto.slice(0, 10).split("-").map(Number);
  return new Date(a, m - 1, d || 1);
}
export const mesPorExtenso = (d) => `${MESES[d.getMonth()]} de ${d.getFullYear()}`;
export const mesCurto = (d) => `${MESES[d.getMonth()].slice(0, 3)}/${String(d.getFullYear()).slice(2)}`;
export const dataCurta = (iso) => {
  // data sem hora ("2026-11-26") é dia do calendário: não passa por fuso (new Date leria meia-noite UTC = dia anterior aqui)
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso ?? "")) return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? TRACO : d.toLocaleDateString("pt-BR");
};

/** Texto sem acento e em minúsculas, para a busca. */
export const normalizar = (t) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

/** Ordinal curto: 1 -> "1º". */
export const ordinal = (n) => (vazio(n) ? TRACO : `${inteiro(n)}º`);
