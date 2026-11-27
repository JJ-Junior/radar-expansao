// Mapa por regiões do IBGE: Brasil -> região -> UF -> região intermediária -> região imediata.
// A história (passos à direita) escolhe os recortes líderes a partir dos dados; depois o usuário explora clicando.
// As áreas são pintadas pela nota média das cidades avaliadas no recorte; cada cidade é um ponto laranja.

import { NOMES_UF, REGIOES } from "./indicadores.js";
import { compacto, decimal, inteiro } from "./formato.js";
import { feicoes, objetoDe } from "./geo.js";
import { conteudoDica, esconderDica, mostrarDica } from "./dica.js";

const L = 1000, A = 960;                          // sistema de coordenadas do SVG
const NIVEIS = ["brasil", "regiao", "uf", "intermediaria", "imediata"];
const NOME_NIVEL = { brasil: "Brasil", regiao: "Região", uf: "Estado", intermediaria: "Região intermediária", imediata: "Região imediata" };
const LIMIARES = [40, 46, 52, 58, 64];            // nota média -> faixa de cor
const CORES = ["--seq-1", "--seq-2", "--seq-3", "--seq-4", "--seq-5", "--seq-6"];
const ROTULOS_POR_NIVEL = { brasil: 0, regiao: 3, uf: 5, intermediaria: 8, imediata: 12 };
const prefereMenos = window.matchMedia("(prefers-reduced-motion: reduce)");

export function criarMapaRegioes({ topos, estado, aoSelecionar, menu = null }) {
  const d3 = window.d3;
  const topojson = window.topojson;
  const svg = d3.select("#mapa-svg").attr("viewBox", `0 0 ${L} ${A}`);

  // ------------------------------------------------------------ geometria
  const geo = {
    regiao: feicoes(topos.regioes).features,
    uf: feicoes(topos.ufs).features,
    intermediaria: feicoes(topos.intermediarias).features,
    imediata: feicoes(topos.imediatas).features,
  };
  const projecao = d3.geoMercator().fitExtent([[40, 70], [L - 40, A - 30]], { type: "FeatureCollection", features: geo.uf });
  const caminho = d3.geoPath(projecao);

  // ------------------------------------------------------------ unidades e agregados
  const unidades = {};          // unidades[nivel] = Map(codigo -> unidade)
  const siglaUf = new Map();
  const imediataPai = new Map();
  for (const m of estado.porId.values()) {
    siglaUf.set(m.uf_id, m.uf_sigla);
    if (m.regiao_imediata_id) imediataPai.set(m.regiao_imediata_id, m.regiao_intermediaria_id);
  }
  const nomeIntermediaria = new Map(), nomeImediata = new Map();
  for (const m of estado.porId.values()) {
    nomeIntermediaria.set(m.regiao_intermediaria_id, m.regiao_intermediaria_nome);
    nomeImediata.set(m.regiao_imediata_id, m.regiao_imediata_nome);
  }
  const descreve = {
    regiao: (c) => ({ nome: REGIOES[c - 1]?.nome ?? `Região ${c}`, pai: null }),
    uf: (c) => ({ nome: NOMES_UF[siglaUf.get(c)] ?? String(c), sigla: siglaUf.get(c), pai: Math.floor(c / 10) }),
    intermediaria: (c) => ({ nome: nomeIntermediaria.get(c) ?? String(c), pai: Math.floor(c / 100) }),
    imediata: (c) => ({ nome: nomeImediata.get(c) ?? String(c), pai: imediataPai.get(c) ?? null }),
  };
  for (const nivel of ["regiao", "uf", "intermediaria", "imediata"]) {
    unidades[nivel] = new Map(geo[nivel].map((f) => {
      const codigo = Number(f.properties.codarea);
      return [codigo, { codigo, nivel, feicao: f, cidades: [], ...descreve[nivel](codigo) }];
    }));
  }
  const chaveCidade = { regiao: "regiao_id", uf: "uf_id", intermediaria: "regiao_intermediaria_id", imediata: "regiao_imediata_id" };
  for (const c of estado.universo) {
    for (const nivel of Object.keys(chaveCidade)) unidades[nivel].get(c[chaveCidade[nivel]])?.cidades.push(c);
  }
  for (const mapa of Object.values(unidades)) {
    for (const u of mapa.values()) {
      u.n = u.cidades.length;
      u.media = u.n ? d3.mean(u.cidades, (c) => c.ranking.nota_final) : null;
      u.lider = u.cidades[0] ?? null;              // universo já vem na ordem do ranking
      u.populacao = d3.sum(u.cidades, (c) => c.populacao);
    }
  }
  const brasil = { nivel: "brasil", codigo: null, nome: "Brasil", cidades: estado.universo, n: estado.universo.length,
    media: d3.mean(estado.universo, (c) => c.ranking.nota_final), lider: estado.universo[0],
    populacao: d3.sum(estado.universo, (c) => c.populacao), feicao: { type: "FeatureCollection", features: geo.uf } };
  const unidade = (nivel, codigo) => (nivel === "brasil" ? brasil : unidades[nivel].get(codigo));
  const filhosDe = (u) => {
    if (u.nivel === "brasil") return [...unidades.regiao.values()];
    if (u.nivel === "imediata") return [...unidades.imediata.values()].filter((x) => x.pai === u.pai);
    const proximo = NIVEIS[NIVEIS.indexOf(u.nivel) + 1];
    return [...unidades[proximo].values()].filter((x) => x.pai === u.codigo);
  };
  const cadeia = (u) => {                         // Brasil > região > UF > ... até u
    const lista = [u];
    let atual = u;
    while (atual.nivel !== "brasil") {
      const nivelPai = NIVEIS[NIVEIS.indexOf(atual.nivel) - 1];
      atual = nivelPai === "brasil" ? brasil : unidade(nivelPai, atual.pai);
      if (!atual) break;
      lista.unshift(atual);
    }
    return lista;
  };
  const contem = (u, c) => u.nivel === "brasil" || c[chaveCidade[u.nivel]] === u.codigo;

  // ------------------------------------------------------------ camadas do SVG
  const raiz = svg.append("g");
  const gContexto = raiz.append("g");
  const gAreas = raiz.append("g");
  const gDivisas = raiz.append("g");
  const gDestaque = raiz.append("g");
  const gCidades = raiz.append("g");
  const gRotulos = raiz.append("g");

  gContexto.selectAll("path").data(geo.uf).join("path").attr("class", "area area--contexto").attr("d", caminho);
  const objUf = objetoDe(topos.ufs);
  gDivisas.append("path").attr("class", "divisa").attr("d", caminho(topojson.mesh(topos.ufs, objUf, (a, b) => a !== b)));
  gDivisas.append("path").attr("class", "divisa").attr("d", caminho(topojson.mesh(topos.ufs, objUf, (a, b) => a === b)));

  const cidades = estado.universo.filter((c) => c.longitude !== null).map((c) => {
    const [x, y] = projecao([c.longitude, c.latitude]);
    return { c, x, y, r: 2.2 + Math.sqrt(c.populacao / 1e6) * 5 };
  });
  const pontos = gCidades.selectAll("circle").data(cidades).join("circle")
    .attr("class", (d) => `cidade${d.c.ranking.recomendado_top5 ? " cidade--recomendada" : ""}`)
    .attr("cx", (d) => d.x).attr("cy", (d) => d.y).attr("r", (d) => d.r)
    .on("click", (_, d) => aoSelecionar(d.c.municipio_id))
    .on("pointerenter", (e, d) => mostrarDica(e.currentTarget, dicaCidade(d.c)))
    .on("pointerleave", esconderDica);
  pontos.filter((d) => d.c.ranking.recomendado_top5).raise();   // recomendadas por cima das outras
  pontos.append("desc").text((d) => `${d.c.municipio_nome} (${d.c.uf_sigla}), nota ${decimal(d.c.ranking.nota_final, 1)}`);

  /** Tooltip de uma cidade. */
  function dicaCidade(c) {
    const r = c.ranking;
    return conteudoDica({
      titulo: `${c.municipio_nome} · ${c.uf_sigla}`,
      chip: r.recomendado_top5 ? { texto: `Recomendada nº ${r.ordem_recomendacao}`, estado: "verde" } : null,
      linhas: [
        { rotulo: "Nota final", valor: decimal(r.nota_final, 1), detalhe: `${r.posicao_brasil}º no Brasil` },
        { rotulo: "População", valor: compacto(c.populacao), detalhe: c.regiao_imediata_nome ?? "" },
      ],
      nota: `Clique para abrir a ficha${menu ? "; botão direito ou toque longo: mais opções" : ""}.`,
    });
  }

  /** Tooltip de uma área (região, UF, região intermediária ou imediata). */
  function dicaArea(d) {
    return conteudoDica({
      titulo: d.nome,
      chip: { texto: NOME_NIVEL[d.nivel] },
      linhas: d.n ? [
        { rotulo: "Cidades avaliadas", valor: inteiro(d.n) },
        { rotulo: "Nota média", valor: decimal(d.media, 1) },
        { rotulo: "Líder", valor: d.lider.municipio_nome, detalhe: `nota ${decimal(d.lider.ranking.nota_final, 1)}` },
      ] : [],
      nota: d.n ? (d.nivel === "imediata" ? "Enter ou clique para focar esta região." : "Enter ou clique para aproximar.") : "Nenhuma cidade com 50 mil habitantes ou mais.",
    });
  }

  // ------------------------------------------------------------ zoom animado
  let visao = [L / 2, A / 2, L];                  // [centro x, centro y, largura visível]
  let k = 1;
  function aplicarVisao(v) {
    visao = v;
    k = L / v[2];
    raiz.attr("transform", `translate(${L / 2 - v[0] * k},${A / 2 - v[1] * k}) scale(${k})`);
    pontos.attr("r", (d) => d.r / Math.sqrt(k));
    gRotulos.selectAll("text").style("font-size", `${17 / k}px`).style("stroke-width", `${4 / k}px`);
  }
  function enquadrar(u, animar = true) {
    const [[x0, y0], [x1, y1]] = caminho.bounds(u.feicao);
    const lado = Math.max(x1 - x0, (y1 - y0) * (L / A)) * 1.18;
    const destino = [(x0 + x1) / 2, (y0 + y1) / 2 + lado * 0.02, Math.max(lado, 60)];
    svg.interrupt();
    if (!animar || prefereMenos.matches) { aplicarVisao(destino); return; }
    const interp = d3.interpolateZoom(visao, destino);
    svg.transition().duration(Math.min(1400, Math.max(700, interp.duration * 0.6))).ease(d3.easeCubicInOut)
      .tween("zoom", () => (t) => aplicarVisao(interp(t)));
  }

  // ------------------------------------------------------------ desenho do recorte atual
  const corDe = (u) => (u.media === null ? "var(--mapa-fora)" : `var(${CORES[d3.bisectRight(LIMIARES, u.media)]})`);
  let atual = brasil;
  let foco = null;                                // região imediata escolhida (último nível)

  function mostrar(u, { animar = true } = {}) {
    atual = u.nivel === "imediata" ? unidade("intermediaria", u.pai) ?? u : u;
    foco = u.nivel === "imediata" ? u : null;
    const filhos = filhosDe(atual);

    gAreas.selectAll("path").data(filhos, (d) => `${d.nivel}-${d.codigo}`).join(
      (entra) => entra.append("path").attr("class", "area").attr("d", (d) => caminho(d.feicao)).style("opacity", 0),
    )
      .attr("tabindex", 0).attr("role", "button")
      .attr("aria-label", (d) => `${NOME_NIVEL[d.nivel]} ${d.nome}: ${d.n ? `${d.n} cidades avaliadas, nota média ${decimal(d.media, 1)}` : "nenhuma cidade avaliada"}`)
      .on("click", (_, d) => { esconderDica(); descer(d); })
      .on("keydown", (e, d) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); esconderDica(); descer(d); } })
      .on("pointermove", (e, d) => mostrarDica(e, dicaArea(d)))
      .on("pointerleave", esconderDica)
      .on("focus", (e, d) => mostrarDica(e.currentTarget, dicaArea(d), { alvo: e.currentTarget }))
      .on("blur", esconderDica)
      .style("fill", corDe)
      .style("opacity", (d) => (foco && d.codigo !== foco.codigo ? 0.55 : 1));

    const alvo = foco ?? atual;
    gDestaque.selectAll("path").data(alvo.nivel === "brasil" ? [] : [alvo]).join("path")
      .attr("class", "destaque-borda").attr("d", (d) => caminho(d.feicao));

    pontos.classed("cidade--fora", (d) => !contem(alvo, d.c));

    const nomes = cidades.filter((d) => contem(alvo, d.c)).slice(0, ROTULOS_POR_NIVEL[alvo.nivel]);
    gRotulos.selectAll("text").data(nomes, (d) => d.c.municipio_id).join("text")
      .attr("class", "rotulo-cidade").attr("x", (d) => d.x + d.r * 0.6 + 3).attr("y", (d) => d.y + 4)
      .text((d) => d.c.municipio_nome);

    gRotulos.selectAll("text").style("font-size", `${17 / k}px`).style("stroke-width", `${4 / k}px`);
    enquadrar(alvo, animar);
    desenharTrilha(alvo);
    desenharResumo(alvo);
  }

  function descer(u) {
    if (u.nivel === "imediata" && foco?.codigo === u.codigo) return;
    mostrar(u);
  }

  // ------------------------------------------------------------ trilha, legenda e resumo
  const trilha = document.getElementById("mapa-trilha");
  function desenharTrilha(u) {
    const lista = cadeia(u);
    trilha.innerHTML = lista.map((x, i) => `<button type="button" data-i="${i}" ${i === lista.length - 1 ? 'aria-current="true"' : ""}>${x.nivel === "uf" ? x.sigla : x.nome}</button>`).join("");
    trilha.onclick = (e) => { const b = e.target.closest("button"); if (b) mostrar(lista[Number(b.dataset.i)]); };
  }

  document.getElementById("mapa-legenda").innerHTML = `Nota média das cidades avaliadas
    <div class="escala">${CORES.map((c) => `<i style="background:var(${c})"></i>`).join("")}</div>
    <div style="display:flex;justify-content:space-between"><span>&lt; ${LIMIARES[0]}</span><span>${LIMIARES.at(-1)}+</span></div>
    <div style="margin-top:6px"><span class="ponto"></span>cidade avaliada (tamanho = população)</div>
    ${estado.recomendadas.length ? `<div><span class="ponto ponto--recomendada"></span>unidade recomendada</div>` : ""}`;



  const resumo = document.getElementById("explorar-resumo");
  const lista = document.getElementById("explorar-lista");
  function desenharResumo(u) {
    resumo.innerHTML = `<p class="nivel">${NOME_NIVEL[u.nivel]}</p><h4>${u.nome}</h4>
      <dl><div><dt>Cidades avaliadas</dt><dd>${inteiro(u.n)}</dd></div>
      <div><dt>Nota média</dt><dd>${u.n ? decimal(u.media, 1) : "—"}</dd></div>
      <div><dt>População</dt><dd>${u.n ? compacto(u.populacao) : "—"}</dd></div>
      <div><dt>Líder</dt><dd style="font-size:1.2rem">${u.lider ? u.lider.municipio_nome : "—"}</dd></div></dl>`;
    lista.innerHTML = u.cidades.slice(0, 10).map((c) => `<li><button type="button" data-id="${c.municipio_id}">
      <span class="nome">${c.municipio_nome}<small>${c.uf_sigla} · ${c.ranking.posicao_brasil}º</small></span>
      <span class="trilho"><i style="width:${c.ranking.nota_final}%"></i></span><span class="v">${decimal(c.ranking.nota_final, 1)}</span></button></li>`).join("")
      || `<li class="discreto">Nenhuma cidade com 50 mil habitantes ou mais neste recorte.</li>`;
  }
  lista.addEventListener("click", (e) => { const b = e.target.closest("button[data-id]"); if (b) aoSelecionar(Number(b.dataset.id)); });
  // botão direito / toque longo nas cidades do mapa e nos nomes da lista
  if (menu) {
    menu.ligar(gCidades.node(), (e) => { const d = e.target.__data__; if (d?.c) esconderDica(); return d?.c?.municipio_id ?? null; });
    menu.ligar(lista, (e) => Number(e.target.closest("[data-id]")?.dataset.id) || null);
  }

  // ------------------------------------------------------------ história guiada pelo scroll
  const melhor = (lista, minimo = 1) => {
    const validos = lista.filter((u) => u.n >= minimo);
    return d3.greatest(validos.length ? validos : lista.filter((u) => u.n), (u) => u.media);
  };
  const regiao = melhor([...unidades.regiao.values()]);
  const uf = melhor(filhosDe(regiao), 3);
  const inter = melhor(filhosDe(uf), 2);
  const imed = melhor(filhosDe(inter));
  const numeros = (u) => `<div class="numeros"><div><b>${inteiro(u.n)}</b><span>cidades</span></div>
    <div><b>${decimal(u.media, 1)}</b><span>nota média</span></div><div><b>${compacto(u.populacao)}</b><span>habitantes</span></div></div>`;
  const passos = [
    { u: brasil, nivel: "01 · Brasil", titulo: `${inteiro(brasil.n)} cidades no radar`,
      texto: `Todas as cidades com 50 mil habitantes ou mais, nas 5 regiões. A mais bem colocada é ${brasil.lider.municipio_nome} (${brasil.lider.uf_sigla})${estado.recomendadas.length ? `; os pontos verdes são as ${estado.recomendadas.length} unidades recomendadas` : ""}.` },
    { u: regiao, nivel: "02 · Região", titulo: `${regiao.nome} na frente`,
      texto: `É a região com a maior nota média entre as cidades avaliadas. Líder: ${regiao.lider.municipio_nome} (${regiao.lider.uf_sigla}).` },
    { u: uf, nivel: "03 · Estado", titulo: uf.nome,
      texto: `O estado com a maior nota média da região (entre os que têm 3 ou mais cidades avaliadas). Líder: ${uf.lider.municipio_nome}.` },
    { u: inter, nivel: "04 · Região intermediária", titulo: inter.nome,
      texto: `Dentro do estado, a região intermediária do IBGE com a maior nota média — o polo que organiza as cidades ao redor.` },
    { u: imed, nivel: "05 · Região imediata", titulo: imed.nome,
      texto: `O menor recorte do IBGE: as cidades que dividem o mesmo comércio e serviços do dia a dia. Líder: ${imed.lider.municipio_nome}.` },
  ];
  const container = document.getElementById("mapa-passos");
  const final = document.getElementById("explorar");
  for (const [i, p] of passos.entries()) {
    final.insertAdjacentHTML("beforebegin", `<div class="passo" data-passo="${i}"><div class="passo__cartao">
      <p class="passo__nivel">${p.nivel}</p><h3>${p.titulo}</h3><p>${p.texto}</p>${numeros(p.u)}</div></div>`);
  }
  const observador = new IntersectionObserver((entradas) => {
    for (const e of entradas) {
      if (!e.isIntersecting) continue;
      for (const x of container.querySelectorAll(".passo")) x.classList.toggle("ativo", x === e.target);
      const i = e.target.dataset.passo;
      if (i === "explorar") return;               // no passo final o usuário manda
      mostrar(passos[Number(i)].u);
    }
  }, { rootMargin: "-45% 0px -45% 0px" });
  for (const p of container.querySelectorAll(".passo")) observador.observe(p);

  document.getElementById("mapa-carregando").remove();
  mostrar(brasil, { animar: false });

  return {
    /** Mostra no mapa o recorte (região imediata) de uma cidade. */
    focarCidade(id) {
      const c = estado.porId.get(id);
      const u = c && unidades.imediata.get(c.regiao_imediata_id);
      if (u) mostrar(u);
    },
  };
}
