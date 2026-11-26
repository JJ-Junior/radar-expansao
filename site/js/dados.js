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

/** Tabelas da gold + território do IBGE. */
export async function carregarDados() {
  const [meta, indicadores, ranking, criteriosBrutos, parametros, macro, momento, territorio] = await Promise.all([
    buscarJson("meta.json"),
    buscarJson("indicadores_municipio.json").then(paraObjetos),
    buscarJson("ranking_expansao.json").then(paraObjetos),
    buscarJson("ranking_criterio.json").then(paraObjetos),
    buscarJson("parametro_ranking.json").then(paraObjetos).catch(() => []),   // opcional
    buscarJson("contexto_macro.json").then(paraObjetos),
    buscarJson("momento_expansao.json").then(paraObjetos),
    buscarJson("territorio.json").then(paraObjetos),
  ]);
  const criterios = [...criteriosBrutos].sort((a, b) => (a.ordem ?? 0) - (b.ordem ?? 0));
  // as 5 unidades recomendadas, na ordem da recomendação
  const recomendadas = ranking.filter((r) => r.recomendado_top5).sort((a, b) => a.ordem_recomendacao - b.ordem_recomendacao);

  // Um registro por município: indicadores + território + linha do ranking (quando está no universo)
  const porId = new Map();
  const territorioPorId = new Map(territorio.map((t) => [t.municipio_id, t]));
  for (const m of indicadores) {
    const t = territorioPorId.get(m.municipio_id) ?? {};
    porId.set(m.municipio_id, {
      ...m,
      uf_id: Math.floor(m.municipio_id / 100000),
      regiao_id: Math.floor(m.municipio_id / 1000000),
      regiao_intermediaria_id: t.regiao_intermediaria_id ?? null,
      regiao_intermediaria_nome: t.regiao_intermediaria_nome ?? null,
      regiao_imediata_id: t.regiao_imediata_id ?? null,
      regiao_imediata_nome: t.regiao_imediata_nome ?? null,
      longitude: t.longitude ?? null,
      latitude: t.latitude ?? null,
      ranking: null,
    });
  }
  for (const r of ranking) {
    const m = porId.get(r.municipio_id);
    if (m) m.ranking = r;
  }

  const ufs = [...new Set(indicadores.map((m) => m.uf_sigla))].sort();
  // cidades do universo, já na ordem do ranking
  const universo = ranking.map((r) => porId.get(r.municipio_id)).filter(Boolean);
  return { meta, indicadores, ranking, criterios, parametros, recomendadas, macro, momento, porId, ufs, universo };
}

/** Malhas do IBGE (TopoJSON): carregadas à parte, sem travar o resto da página. */
export async function carregarMalhas(camadas = ["regioes", "ufs", "intermediarias", "imediatas"]) {
  const topos = await Promise.all(camadas.map((c) => buscarJson(`malha/${c}.topo.json`)));
  return Object.fromEntries(camadas.map((c, i) => [c, topos[i]]));
}
