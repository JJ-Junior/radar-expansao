// Ficha do município: posição, notas por critério, percentis e municípios parecidos.
// Percentis e "parecidos" são leituras das colunas da gold feitas no navegador.

import { CRITERIOS, INDICADORES_FICHA, NOMES_UF, REGIOES } from "./indicadores.js";
import { decimal, inteiro, ordinal } from "./formato.js";

// Variáveis do perfil para achar municípios parecidos (log suaviza população e PIB)
const PERFIL = [
  (m) => (m.populacao > 0 ? Math.log10(m.populacao) : null),
  (m) => m.renda_dom_per_capita,
  (m) => m.academias_por_10mil_hab,
  (m) => m.crescimento_pop_aa,
  (m) => (m.pib_per_capita > 0 ? Math.log10(m.pib_per_capita) : null),
  (m) => m.salario_medio,
];

export function criarFicha({ estado, aoSelecionar }) {
  const d3 = window.d3;
  const el = (id) => document.getElementById(id);

  // Valores ordenados de cada indicador, para o percentil por busca binária
  const ordenados = {};
  for (const { coluna } of INDICADORES_FICHA) {
    ordenados[coluna] = estado.indicadores.map((m) => m[coluna]).filter((v) => v !== null).sort(d3.ascending);
  }
  const percentil = (coluna, v) => {
    const lista = ordenados[coluna];
    return lista.length ? (d3.bisectLeft(lista, v) / lista.length) * 100 : null;
  };

  // Perfil padronizado (z-score) de cada município com todos os dados
  const perfis = [];
  const colunasPerfil = PERFIL.map((f) => estado.indicadores.map(f));
  const medias = colunasPerfil.map((c) => d3.mean(c));
  const desvios = colunasPerfil.map((c) => d3.deviation(c) || 1);
  estado.indicadores.forEach((m, i) => {
    const vetor = colunasPerfil.map((c, j) => (c[i] === null || c[i] === undefined ? null : (c[i] - medias[j]) / desvios[j]));
    if (vetor.every((v) => v !== null)) perfis.push({ id: m.municipio_id, vetor, noUniverso: !!estado.porId.get(m.municipio_id).ranking });
  });
  const perfilPorId = new Map(perfis.map((p) => [p.id, p]));

  function parecidos(id, quantos = 6) {
    const alvo = perfilPorId.get(id);
    if (!alvo) return [];
    return perfis
      .filter((p) => p.id !== id && p.noUniverso === alvo.noUniverso)
      .map((p) => ({ id: p.id, d: Math.hypot(...p.vetor.map((v, j) => v - alvo.vetor[j])) }))
      .sort((a, b) => a.d - b.d)
      .slice(0, quantos);
  }

  const peso = (criterio) => estado.criterios.find((c) => c.criterio === criterio)?.peso ?? null;
  const totalUf = d3.rollup(estado.ranking, (v) => v.length, (r) => r.uf_sigla);

  function resumo(r) {
    const notas = CRITERIOS.map((c) => ({ nome: c.nome.toLowerCase(), v: r[`nota_${c.criterio}`] })).sort((a, b) => b.v - a.v);
    const fortes = notas.filter((n) => n.v >= 75).slice(0, 2).map((n) => n.nome);
    const fracos = notas.filter((n) => n.v <= 30).slice(-2).map((n) => n.nome);
    const juntar = (l) => l.join(" e ");
    if (!fortes.length && !fracos.length) return "Notas equilibradas, sem ponto muito forte nem muito fraco.";
    return [fortes.length && `Destaque em ${juntar(fortes)}.`, fracos.length && `Ponto de atenção: ${juntar(fracos)}.`].filter(Boolean).join(" ");
  }

  function mostrar(id, { exemplo = false } = {}) {
    const m = estado.porId.get(id);
    if (!m) return;
    const r = m.ranking;
    const regiao = REGIOES.find((x) => x.sigla === m.regiao_sigla)?.nome ?? m.regiao_sigla;

    el("ficha-sobre").textContent = exemplo ? "Ficha do município · exemplo: o 1º do ranking" : "Ficha do município";
    el("ficha-nome").textContent = `${m.municipio_nome} (${m.uf_sigla})`;
    el("ficha-resumo").textContent = r
      ? `${NOMES_UF[m.uf_sigla] ?? m.uf_sigla}, ${regiao}. ${resumo(r)}`
      : `${NOMES_UF[m.uf_sigla] ?? m.uf_sigla}, ${regiao}. Com ${inteiro(m.populacao)} habitantes, fica fora do universo do ranking (50 mil ou mais), mas os indicadores estão abaixo.`;
    el("ficha-corpo").hidden = false;

    // placar
    el("ficha-nota").textContent = r ? decimal(r.nota_final, 1) : "sem nota";
    el("ficha-nota").classList.toggle("ficha__nota-valor--sem", !r);
    el("ficha-posicoes").innerHTML = r
      ? `<li><span>No Brasil</span><b>${ordinal(r.posicao_brasil)} de ${inteiro(estado.ranking.length)}</b></li>
         <li><span>Em ${m.uf_sigla}</span><b>${ordinal(r.posicao_uf)} de ${inteiro(totalUf.get(m.uf_sigla))}</b></li>
         ${r.dados_incompletos ? '<li><span>⚠ Dados incompletos</span><b>nota neutra em algum critério</b></li>' : ""}`
      : `<li class="ficha__fora">Fora do universo do ranking: menos de 50 mil habitantes.</li>`;

    // notas por critério
    el("ficha-criterios").innerHTML = r
      ? CRITERIOS.map((c) => {
        const v = r[`nota_${c.criterio}`];
        const p = peso(c.criterio);
        return `<li class="barra-criterio">
            <span class="barra-criterio__nome">${c.nome}<small>peso ${p === null ? "—" : `${Math.round(p * 100)}%`}</small></span>
            <span class="barra-criterio__trilho" role="img" aria-label="${c.nome}: ${decimal(v, 0)} de 100"><span class="barra-criterio__valor" style="display:block;width:${v}%"></span></span>
            <span class="barra-criterio__num">${decimal(v, 0)}</span>
          </li>`;
      }).join("")
      : `<li class="discreto">Sem nota: o município não entra no universo do ranking.</li>`;

    // indicadores com percentil
    el("ficha-indicadores").innerHTML = INDICADORES_FICHA.map(({ coluna, rotulo, formato, comparacao }) => {
      const v = m[coluna];
      const p = v === null || v === undefined || !comparacao ? null : percentil(coluna, v);
      const frase = p === null ? "" : `<span class="marcador-pct" aria-hidden="true"><i style="left:${p}%"></i></span><span class="indicador__pct">${comparacao} ${decimal(p, 0)}% dos municípios</span>`;
      return `<div class="indicador"><dt>${rotulo}</dt><dd class="indicador__valor">${formato(v)}</dd><dd>${frase}</dd></div>`;
    }).join("");

    // parecidos
    const lista = parecidos(id);
    el("ficha-parecidos").innerHTML = lista.length
      ? lista.map(({ id: pid }) => {
        const p = estado.porId.get(pid);
        const extra = p.ranking ? ` · ${ordinal(p.ranking.posicao_brasil)}` : "";
        return `<li><button type="button" data-id="${pid}">${p.municipio_nome}<small>${p.uf_sigla}${extra}</small></button></li>`;
      }).join("")
      : `<li class="discreto">Sem dados suficientes para comparar.</li>`;
  }

  el("ficha-parecidos").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-id]");
    if (b) aoSelecionar(Number(b.dataset.id));
  });
  el("ficha-copiar").addEventListener("click", async (e) => {
    const botao = e.currentTarget;
    try {
      await navigator.clipboard.writeText(location.href);
      botao.textContent = "Link copiado";
    } catch {
      botao.textContent = "Copie o endereço da barra do navegador";
    }
    setTimeout(() => { botao.textContent = "Copiar link desta ficha"; }, 2500);
  });

  return { mostrar };
}
