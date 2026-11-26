// As 5 unidades recomendadas (gold.ranking_expansao.recomendado_top5) e o motivo de uma cidade bem colocada ficar fora.
// A regra é da gold (spec.md 5.3): trava de renda + no máximo uma cidade por região imediata. Aqui só se explica.

import { decimal } from "./formato.js";
import { parametro } from "./indicadores.js";

export const travaDeRenda = (estado) => parametro(estado, "nota_minima_poder_compra", 50);
export const quantidadeRecomendada = (estado) => parametro(estado, "unidades_recomendadas", 5);

const elegivel = (estado, r) =>
  r.elegivel_recomendacao ?? (r.nota_poder_compra !== null && r.nota_poder_compra >= travaDeRenda(estado));

/** Frase curta com o motivo de uma cidade do ranking não estar entre as recomendadas. */
export function motivoFora(estado, r) {
  if (r.recomendado_top5) return null;
  if (!elegivel(estado, r)) {
    return `poder de compra ${decimal(r.nota_poder_compra, 0)}, abaixo da trava de renda (${decimal(travaDeRenda(estado), 0)})`;
  }
  const mesmaRegiao = estado.recomendadas.find((x) => x.regiao_imediata_id === r.regiao_imediata_id);
  if (mesmaRegiao) return `mesma região imediata de ${mesmaRegiao.municipio_nome}, que já está na lista`;
  return `vem depois da ${estado.recomendadas.length}ª recomendada no ranking`;
}

/** Cidades à frente da última recomendada que ficaram fora da lista, com o motivo. */
export function foraDaLista(estado) {
  const ultima = estado.recomendadas.at(-1);
  if (!ultima) return [];
  return estado.ranking
    .filter((r) => !r.recomendado_top5 && r.posicao_brasil < ultima.posicao_brasil)
    .map((r) => ({ r, motivo: motivoFora(estado, r) }));
}
