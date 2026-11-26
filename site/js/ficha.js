// Ficha da cidade, em três camadas de leitura:
// 1) cabeçalho: nome, onde fica, selo, nota final e posições (Brasil / região / UF);
// 2) uma frase-resumo gerada das notas;
// 3) corpo: "por que esta cidade" (barras dos 6 critérios) e os 8 indicadores com o percentil no Brasil.
// Percentis e "parecidas" são leituras das colunas da gold feitas no navegador.

import { COMPONENTES, CRITERIOS, INDICADORES_FICHA, NOMES_UF, REGIOES, pesoDoCriterio } from "./indicadores.js";
import { decimal, inteiro, ordinal } from "./formato.js";
import { motivoFora } from "./recomendacao.js";

// Perfil usado para achar cidades parecidas (log suaviza população e PIB)
const PERFIL = [
  (m) => (m.populacao > 0 ? Math.log10(m.populacao) : null),
  (m) => m.renda_dom_per_capita,
  (m) => m.academias_por_10mil_hab,
  (m) => m.crescimento_pop_aa,
  (m) => (m.pib_per_capita > 0 ? Math.log10(m.pib_per_capita) : null),
  (m) => m.salario_medio,
];

// Como cada critério aparece na frase-resumo quando é ponto forte ou ponto de atenção
const FRASE = {
  mercado: { forte: "tamanho de mercado", fraco: "mercado pequeno para o universo" },
  poder_compra: { forte: "poder de compra", fraco: "renda abaixo da média" },
  espaco_competitivo: { forte: "pouca concorrência", fraco: "concorrência acima da média" },
  crescimento: { forte: "crescimento da população", fraco: "crescimento lento" },
  riqueza: { forte: "riqueza local", fraco: "PIB per capita abaixo da média" },
  mercado_formal: { forte: "mercado formal", fraco: "salário formal abaixo da média" },
};
const FORTE = 75, FRACO = 35;

export function criarFicha({ estado, aoSelecionar }) {
  const d3 = window.d3;
  const el = (id) => document.getElementById(id);

  // valores ordenados de cada indicador, para o percentil por busca binária
  const ordenados = {};
  for (const { coluna } of INDICADORES_FICHA) {
    ordenados[coluna] = estado.indicadores.map((m) => m[coluna]).filter((v) => v !== null).sort(d3.ascending);
  }
  const percentil = (coluna, v) => {
    const lista = ordenados[coluna];
    return lista.length ? (d3.bisectLeft(lista, v) / lista.length) * 100 : null;
  };

  // perfil padronizado (z-score) de cada cidade com todos os dados
  const colunas = PERFIL.map((f) => estado.indicadores.map(f));
  const medias = colunas.map((c) => d3.mean(c));
  const desvios = colunas.map((c) => d3.deviation(c) || 1);
  const perfis = [];
  estado.indicadores.forEach((m, i) => {
    const vetor = colunas.map((c, j) => (c[i] === null || c[i] === undefined ? null : (c[i] - medias[j]) / desvios[j]));
    if (vetor.every((v) => v !== null)) perfis.push({ id: m.municipio_id, vetor, noUniverso: !!estado.porId.get(m.municipio_id).ranking });
  });
  const perfilPorId = new Map(perfis.map((p) => [p.id, p]));
  function parecidas(id, quantas = 6) {
    const alvo = perfilPorId.get(id);
    if (!alvo) return [];
    return perfis.filter((p) => p.id !== id && p.noUniverso === alvo.noUniverso)
      .map((p) => ({ id: p.id, d: Math.hypot(...p.vetor.map((v, j) => v - alvo.vetor[j])) }))
      .sort((a, b) => a.d - b.d).slice(0, quantas);
  }

  const totalUf = d3.rollup(estado.ranking, (v) => v.length, (r) => r.uf_sigla);
  const totalRegiao = d3.rollup(estado.ranking, (v) => v.length, (r) => r.regiao_sigla);

  /** "Destaque em poder de compra e mercado formal; ponto de atenção: concorrência acima da média." */
  function resumo(r) {
    const notas = CRITERIOS.map((c) => ({ c: c.criterio, v: r[`nota_${c.criterio}`] })).filter((n) => n.v !== null);
    const fortes = notas.filter((n) => n.v >= FORTE).sort((a, b) => b.v - a.v).slice(0, 2).map((n) => FRASE[n.c].forte);
    const fracos = notas.filter((n) => n.v <= FRACO).sort((a, b) => a.v - b.v).slice(0, 2).map((n) => FRASE[n.c].fraco);
    const juntar = (l) => l.join(" e ");
    if (!fortes.length && !fracos.length) return "Notas equilibradas: nenhum critério muito acima ou muito abaixo do universo.";
    const partes = [];
    if (fortes.length) partes.push(`Destaque em ${juntar(fortes)}`);
    if (fracos.length) partes.push(`ponto de atenção: ${juntar(fracos)}`);
    const frase = partes.join("; ");
    return `${frase.charAt(0).toUpperCase()}${frase.slice(1)}.`;
  }

  /** Frase curta do percentil: "Top 3% do Brasil" ou "Maior que 62% das cidades". */
  function frasePercentil(p, comparacao) {
    const pct = Math.round(p);
    if (comparacao === "maior que" && pct >= 90) return `Top ${Math.max(1, 100 - pct)}% do Brasil`;
    const texto = `${comparacao} ${pct}% das cidades`;
    return texto.charAt(0).toUpperCase() + texto.slice(1);
  }

  function mostrar(id, { exemplo = false } = {}) {
    const m = estado.porId.get(id);
    if (!m) return;
    const r = m.ranking;
    const regiao = REGIOES.find((x) => x.sigla === m.regiao_sigla)?.nome ?? m.regiao_sigla;

    el("ficha-sobre").innerHTML = `<span class="rotulo__num">05</span> ${exemplo ? "Ficha da cidade · exemplo: a 1ª recomendada" : "Ficha da cidade"}`;
    el("ficha-nome").textContent = m.municipio_nome;
    el("ficha-onde").textContent = [NOMES_UF[m.uf_sigla] ?? m.uf_sigla, regiao, m.regiao_imediata_nome && `região imediata de ${m.regiao_imediata_nome}`].filter(Boolean).join(" · ");

    // selo e posições
    let selo = "";
    if (r?.recomendado_top5) selo = `<span class="selo selo--recomendada">Recomendada nº ${r.ordem_recomendacao}</span>`;
    else if (r && estado.recomendadas.length) selo = `<span class="selo selo--fora">Fora da lista de recomendadas</span>`;
    else if (!r) selo = `<span class="selo selo--fora">Fora do universo do ranking</span>`;
    el("ficha-selos").innerHTML = selo;
    el("ficha-posicoes").innerHTML = r ? [
      ["Brasil", `${ordinal(r.posicao_brasil)} de ${inteiro(estado.ranking.length)}`],
      r.posicao_regiao ? [regiao, `${ordinal(r.posicao_regiao)} de ${inteiro(totalRegiao.get(m.regiao_sigla))}`] : null,
      [m.uf_sigla, `${ordinal(r.posicao_uf)} de ${inteiro(totalUf.get(m.uf_sigla))}`],
    ].filter(Boolean).map(([rotulo, valor]) => `<li><span>${rotulo}</span><b>${valor}</b></li>`).join("") : "";

    el("ficha-nota").textContent = r ? decimal(r.nota_final, 1) : "—";
    el("ficha-nota-escala").textContent = r ? "nota final, de 0 a 100" : "sem nota: menos de 50 mil habitantes";

    // frase-resumo + avisos curtos (motivo de estar fora da lista, concorrência, dado faltante)
    el("ficha-resumo").textContent = r ? resumo(r)
      : `Com ${inteiro(m.populacao)} habitantes, fica fora do universo do ranking (50 mil ou mais); os indicadores estão abaixo.`;
    const avisos = [];
    if (r && !r.recomendado_top5 && estado.recomendadas.length) avisos.push(["", `Fora da lista: ${motivoFora(estado, r)}.`]);
    if (r?.verificar_concorrencia) avisos.push(["atencao", "Nenhuma academia formal registrada (CNAE 93.13-1): verificar a concorrência no local."]);
    if (r?.dados_incompletos) {
      const nomes = (r.criterios_ausentes ?? []).map((c) => COMPONENTES[c]?.nome ?? c).join(", ");
      avisos.push(["atencao", `Dados incompletos: ${nomes || "algum critério"} sem dado; o peso foi dividido entre os demais.`]);
    }
    el("ficha-avisos").innerHTML = avisos.map(([tipo, texto]) => `<li class="${tipo ? `aviso--${tipo}` : ""}">${texto}</li>`).join("");
    el("ficha-corpo").hidden = false;

    // por que esta cidade: barras dos critérios
    el("ficha-porque").hidden = !r;
    el("ficha-criterios").innerHTML = r ? CRITERIOS.map((c) => {
      const v = r[`nota_${c.criterio}`];
      const peso = pesoDoCriterio(estado.criterios, c.criterio);
      return `<li class="barra-criterio">
        <span class="barra-criterio__nome">${c.nome}</span>
        <span class="barra-criterio__peso">peso ${peso === null ? "—" : `${Math.round(peso * 100)}%`}</span>
        <span class="barra-criterio__num">${v === null ? "—" : decimal(v, 0)}</span>
        <span class="barra-criterio__trilho" role="img" aria-label="${c.nome}: ${v === null ? "sem dado" : `${decimal(v, 0)} de 100`}"><span class="barra-criterio__valor" style="width:${v ?? 0}%"></span></span>
      </li>`;
    }).join("") : "";

    // indicadores: valor grande + uma frase + barra de percentil 0–100
    el("ficha-indicadores").innerHTML = INDICADORES_FICHA.map(({ coluna, rotulo, formato, comparacao }) => {
      const v = m[coluna];
      const p = v === null || v === undefined || !comparacao ? null : percentil(coluna, v);
      const extra = p === null
        ? `<dd class="indicador__frase discreto">${coluna === "academias_qtd" ? "empresas formais de condicionamento físico" : "sem comparação"}</dd>`
        : `<dd class="indicador__frase">${frasePercentil(p, comparacao)}</dd>
           <dd class="percentil" role="img" aria-label="percentil ${Math.round(p)} de 100"><span class="percentil__trilho"><i style="width:${p}%"></i></span><span class="percentil__escala"><span>0</span><span>50</span><span>100</span></span></dd>`;
      return `<div class="indicador"><dt>${rotulo}</dt><dd class="indicador__valor">${formato(v)}</dd>${extra}</div>`;
    }).join("");

    const lista = parecidas(id);
    el("ficha-parecidos").innerHTML = lista.length ? lista.map(({ id: pid }) => {
      const p = estado.porId.get(pid);
      return `<li><button type="button" data-id="${pid}">${p.municipio_nome}<small>${p.uf_sigla}${p.ranking ? ` · ${p.ranking.posicao_brasil}º` : ""}</small></button></li>`;
    }).join("") : `<li class="discreto">Sem dados suficientes para comparar.</li>`;
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
      botao.textContent = "Copie o endereço da barra";
    }
    setTimeout(() => { botao.textContent = "Copiar link da ficha"; }, 2500);
  });

  return { mostrar };
}
