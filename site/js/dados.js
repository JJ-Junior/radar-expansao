// Carrega os JSONs de site/dados/ (contrato em site/dados/README.md)
// e monta o "estado" que todas as seções usam.

const PASTA = "dados";

async function buscarJson(caminho) {
  const resposta = await fetch(`${PASTA}/${caminho}`);
  if (!resposta.ok) throw new Error(`Não foi possível carregar ${caminho} (HTTP ${resposta.status})`);
  return resposta.json();
}

/** Formato colunar {colunas, linhas} -> lista de objetos. */
export function paraObjetos(tabela) {
  const { colunas, linhas } = tabela;
  return linhas.map((linha) => Object.fromEntries(colunas.map((c, j) => [c, linha[j]])));
}

/** Tabelas pequenas, necessárias para o topo da página. */
export async function carregarDados() {
  const [meta, indicadores, ranking, criterios, macro, momento] = await Promise.all([
    buscarJson("meta.json"),
    buscarJson("indicadores_municipio.json").then(paraObjetos),
    buscarJson("ranking_expansao.json").then(paraObjetos),
    buscarJson("ranking_criterio.json").then(paraObjetos),
    buscarJson("contexto_macro.json").then(paraObjetos),
    buscarJson("momento_expansao.json").then(paraObjetos),
  ]);

  // Um registro por município, com a linha do ranking anexada quando ele está no universo
  const porId = new Map();
  for (const m of indicadores) porId.set(m.municipio_id, { ...m, ranking: null });
  for (const r of ranking) {
    const m = porId.get(r.municipio_id);
    if (m) m.ranking = r;
  }

  const ufs = [...new Set(indicadores.map((m) => m.uf_sigla))].sort();
  return { meta, indicadores, ranking, criterios, macro, momento, porId, ufs };
}

/** A malha é o arquivo mais pesado: carrega à parte, sem travar o resto. */
export const carregarMalha = () => buscarJson("malha/municipios.topo.json");
