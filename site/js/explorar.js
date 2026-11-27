// Explorar as cidades: um ponto por cidade do universo, num <canvas>, e cinco vistas que
// reorganizam OS MESMOS pontos (mapa, dois cruzamentos de indicadores, ranking e regiões).
// Cada vista calcula o alvo (x, y, r, alfa) de todos os pontos; a troca interpola do estado atual
// até o alvo (850 ms, cúbica in-out). Trocar no meio parte da posição atual, sem pulo.
// Sem "reduzir movimento": a troca é imediata.

import { REGIOES } from "./indicadores.js";
import { compacto, decimal, fracaoAoAno, inteiro, normalizar, reais } from "./formato.js";
import { conteudoDica, esconderDica, mostrarDica } from "./dica.js";
import { feicoes, objetoDe } from "./geo.js";

const DURACAO = 850;
// escala própria para pontos: um tom só, sem o degrau que some no fundo (tokens --pt-* do CSS, por tema)
const LIMIARES = [45, 52, 59, 66];
const CORES = ["--pt-1", "--pt-2", "--pt-3", "--pt-4", "--pt-5"];
const ORDEM_REGIOES = ["N", "NE", "CO", "SE", "S"];
const prefereMenos = window.matchMedia("(prefers-reduced-motion: reduce)");
const cor = (nome) => getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
const facilitar = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);  // cúbica in-out

const VISTAS = [
  { chave: "mapa", rotulo: "Mapa" },
  { chave: "oportunidade", rotulo: "Renda × concorrência" },
  { chave: "armadilha", rotulo: "Crescimento × renda" },
  { chave: "ranking", rotulo: "Ranking" },
  { chave: "regioes", rotulo: "Por região" },
];

/** Beeswarm determinístico: para cada ponto (na ordem do eixo), o menor deslocamento que não encosta nos já colocados. */
function enxame(itens, folga = 0.6) {
  // itens: [{ eixo, r }]; devolve o deslocamento perpendicular de cada item (mesma ordem)
  const ordem = itens.map((it, i) => i).sort((a, b) => itens[a].eixo - itens[b].eixo);
  const colocados = [];
  const desloc = new Float32Array(itens.length);
  for (const i of ordem) {
    const { eixo, r } = itens[i];
    const bloqueios = [];
    for (let k = colocados.length - 1; k >= 0; k--) {
      const j = colocados[k];
      const dx = eixo - itens[j].eixo;
      const alcance = r + itens[j].r + folga;
      if (dx > alcance) break;                     // ordenados pelo eixo: os anteriores estão ainda mais longe
      const dy = Math.sqrt(Math.max(0, alcance * alcance - dx * dx));
      bloqueios.push([desloc[j] - dy, desloc[j] + dy]);
    }
    const livre = (y) => bloqueios.every(([a, b]) => y <= a || y >= b);
    let melhor = 0;
    if (!livre(0)) {
      const candidatos = bloqueios.flatMap(([a, b]) => [a - 0.01, b + 0.01]).sort((p, q) => Math.abs(p) - Math.abs(q));
      melhor = candidatos.find(livre) ?? 0;
    }
    desloc[i] = melhor;
    colocados.push(i);
  }
  return desloc;
}

const quantil = (valores, p) => window.d3.quantileSorted(valores, p);

export function criarExplorar({ estado, topoUfs, aoSelecionar, menu = null }) {
  const d3 = window.d3;
  const topojson = window.topojson;
  const palco = document.getElementById("explorar-palco");
  const canvas = document.getElementById("explorar-canvas");
  const ctx = canvas.getContext("2d");
  const svg = d3.select("#explorar-eixos");
  const abas = document.getElementById("explorar-abas");
  const frase = document.getElementById("explorar-frase");
  const busca = document.getElementById("explorar-busca");

  // ------------------------------------------------------------ dados de cada ponto
  const cidades = estado.universo;                 // já na ordem do ranking
  const n = cidades.length;
  const brasil = feicoes(topoUfs);
  const divisas = topojson.mesh(topoUfs, objetoDe(topoUfs), (a, b) => a !== b);
  const contorno = topojson.mesh(topoUfs, objetoDe(topoUfs), (a, b) => a === b);
  const ordenado = (f) => cidades.map(f).filter((v) => v !== null && v !== undefined).sort(d3.ascending);
  const academias = ordenado((c) => c.academias_por_10mil_hab);
  const lim = [quantil(academias, 0.05), quantil(academias, 0.95)];          // limite 5–95% (o mesmo da gold)
  const acadLimitada = (c) => (c.academias_por_10mil_hab === null ? null : Math.min(Math.max(c.academias_por_10mil_hab, lim[0]), lim[1]));
  const rendas = ordenado((c) => c.renda_dom_per_capita);
  const crescimentos = ordenado((c) => c.crescimento_pop_aa);
  const mediana = {
    renda: quantil(rendas, 0.5),
    academias: quantil(ordenado(acadLimitada), 0.5),
    crescimento: quantil(crescimentos, 0.5),
  };
  const recomendada = (c) => !!c.ranking.recomendado_top5;

  // estado da animação: posições atuais, de onde saiu e para onde vai
  const atual = { x: new Float32Array(n), y: new Float32Array(n), r: new Float32Array(n), a: new Float32Array(n) };
  const origem = { x: new Float32Array(n), y: new Float32Array(n), r: new Float32Array(n), a: new Float32Array(n) };
  let alvo = null;
  let vista = VISTAS[0].chave;
  let inicio = 0;
  let quadro = null;
  let largura = 0, altura = 0, dpr = 1;
  let layouts = {};
  let sobMouse = -1;
  let fixada = -1;                                   // cidade escolhida na busca: etiqueta fixa

  // ------------------------------------------------------------ layouts (em pixels; refeitos a cada tamanho)
  function calcularLayouts() {
    const m = { topo: 24, dir: 24, base: 48, esq: largura < 600 ? 48 : 72 };
    const rMax = Math.max(7, Math.min(16, largura / 70));
    const raio = d3.scaleSqrt().domain([0, d3.max(cidades, (c) => c.populacao)]).range([0, rMax]);
    const r = cidades.map((c) => Math.max(1.8, raio(c.populacao)));
    const L = {};
    const vazio = () => ({ x: new Float32Array(n), y: new Float32Array(n), r: Float32Array.from(r), a: new Float32Array(n).fill(1) });

    // 1. mapa: centro do município, projeção igual à do mapa do site
    {
      const p = vazio();
      const proj = d3.geoMercator().fitExtent([[m.esq / 2, 16], [largura - 16, altura - 16]], brasil);
      cidades.forEach((c, i) => {
        if (c.longitude === null) { p.a[i] = 0; return; }
        [p.x[i], p.y[i]] = proj([c.longitude, c.latitude]);
        p.r[i] = r[i] * 0.8;
      });
      p.caminho = d3.geoPath(proj);
      L.mapa = p;
    }
    const x0 = m.esq, x1 = largura - m.dir, y0 = altura - m.base, y1 = m.topo;
    // renda em escala log, do percentil 0,5% ao máximo (poucas cidades muito pobres não achatam o resto)
    const yRenda = d3.scaleLog().domain([quantil(rendas, 0.005), rendas.at(-1)]).range([y0, y1]).clamp(true);

    // 2. renda × concorrência (x = academias por 10 mil, limitado a 5–95%)
    {
      const p = vazio();
      const x = d3.scaleLinear().domain(lim).range([x0, x1]).nice();
      cidades.forEach((c, i) => {
        const v = acadLimitada(c);
        if (v === null || c.renda_dom_per_capita === null) { p.a[i] = 0; p.x[i] = x(mediana.academias); p.y[i] = y0; return; }
        p.x[i] = x(v); p.y[i] = yRenda(c.renda_dom_per_capita);
      });
      p.escalas = { x, y: yRenda };
      L.oportunidade = p;
    }
    // 3. crescimento × renda
    {
      const p = vazio();
      const x = d3.scaleLinear().domain([quantil(crescimentos, 0.01), quantil(crescimentos, 0.99)]).range([x0, x1]).nice().clamp(true);
      cidades.forEach((c, i) => {
        if (c.crescimento_pop_aa === null || c.renda_dom_per_capita === null) { p.a[i] = 0; p.x[i] = x(mediana.crescimento); p.y[i] = y0; return; }
        p.x[i] = x(c.crescimento_pop_aa); p.y[i] = yRenda(c.renda_dom_per_capita);
      });
      p.escalas = { x, y: yRenda };
      L.armadilha = p;
    }
    // 4. ranking: enxame horizontal pela nota final
    {
      const p = vazio();
      const x = d3.scaleLinear().domain([0, 100]).range([x0, x1]);
      const rr = r.map((v) => Math.max(3, v * 1.1));
      const desloc = enxame(cidades.map((c, i) => ({ eixo: x(c.ranking.nota_final), r: rr[i] })));
      const meio = (y0 + y1) / 2;
      const maior = d3.max(desloc, Math.abs) || 1;
      const fator = Math.min(1, ((y0 - y1) / 2 - 8) / maior);  // se não couber, aperta um pouco
      cidades.forEach((c, i) => { p.x[i] = x(c.ranking.nota_final); p.y[i] = meio + desloc[i] * fator; p.r[i] = rr[i]; });
      p.escalas = { x };
      L.ranking = p;
    }
    // 5. por região: cinco colunas, enxame vertical pela nota
    {
      const p = vazio();
      const colunas = d3.scaleBand().domain(ORDEM_REGIOES).range([x0, x1]).padding(0.08);
      const y = d3.scaleLinear().domain([0, 100]).range([y0, y1]);
      const rr = r.map((v) => v * 0.6);
      for (const sigla of ORDEM_REGIOES) {
        const idx = cidades.map((c, i) => (c.regiao_sigla === sigla ? i : -1)).filter((i) => i >= 0);
        const desloc = enxame(idx.map((i) => ({ eixo: y(cidades[i].ranking.nota_final), r: rr[i] })));
        const maior = d3.max(desloc, Math.abs) || 1;
        const fator = Math.min(1, (colunas.bandwidth() / 2 - 4) / maior);
        const centro = colunas(sigla) + colunas.bandwidth() / 2;
        idx.forEach((i, k) => { p.x[i] = centro + desloc[k] * fator; p.y[i] = y(cidades[i].ranking.nota_final); p.r[i] = rr[i]; });
      }
      p.escalas = { colunas, y };
      L.regioes = p;
    }
    L.margens = m;
    return L;
  }

  // ------------------------------------------------------------ eixos e legendas (SVG por cima, com crossfade)
  function desenharEixos() {
    const L = layouts;
    const m = L.margens;
    svg.attr("viewBox", `0 0 ${largura} ${altura}`).selectAll("*").remove();
    const grupo = (chave) => svg.append("g").attr("class", "explorar__camada").attr("data-vista", chave).classed("ativa", chave === vista);
    const y0 = altura - m.base, y1 = m.topo, x0 = m.esq, x1 = largura - m.dir;

    // mapa: divisas das UFs
    const gm = grupo("mapa");
    gm.append("path").attr("class", "explorar__divisa").attr("d", L.mapa.caminho(divisas));
    gm.append("path").attr("class", "explorar__contorno").attr("d", L.mapa.caminho(contorno));

    // cruzamentos: eixos, medianas e o quadrante em destaque
    const cruzamento = (chave, rotuloX, formatoX, medianaX, quadrante) => {
      const { x, y } = L[chave].escalas;
      const g = grupo(chave);
      g.append("g").attr("class", "explorar__eixo").attr("transform", `translate(0,${y0})`)
        .call(d3.axisBottom(x).ticks(largura < 600 ? 4 : 7).tickFormat(formatoX).tickSize(-(y0 - y1)).tickPadding(8));
      g.append("g").attr("class", "explorar__eixo").attr("transform", `translate(${x0},0)`)
        .call(d3.axisLeft(y).tickValues([300, 500, 1000, 2000, 4000, 8000].filter((v) => v >= y.domain()[0] && v <= y.domain()[1]))
          .tickFormat((v) => `R$ ${inteiro(v)}`).tickSize(-(x1 - x0)).tickPadding(8));
      const mx = x(medianaX), my = y(mediana.renda);
      g.append("line").attr("class", "explorar__mediana").attr("x1", mx).attr("x2", mx).attr("y1", y1).attr("y2", y0);
      g.append("line").attr("class", "explorar__mediana").attr("x1", x0).attr("x2", x1).attr("y1", my).attr("y2", my);
      const [qx0, qx1] = quadrante.lado === "esquerda" ? [x0, mx] : [mx, x1];
      const [qy0, qy1] = quadrante.alto ? [y1, my] : [my, y0];
      g.insert("rect", ":first-child").attr("class", "explorar__quadrante").attr("x", qx0).attr("y", qy0).attr("width", qx1 - qx0).attr("height", qy1 - qy0);
      g.append("text").attr("class", "explorar__rotulo-quadrante").attr("x", quadrante.lado === "esquerda" ? qx0 + 12 : qx1 - 12)
        .attr("y", quadrante.alto ? qy0 + 24 : qy1 - 12).attr("text-anchor", quadrante.lado === "esquerda" ? "start" : "end").text(quadrante.texto);
      g.append("text").attr("class", "explorar__titulo-eixo").attr("x", x1).attr("y", altura - 8).attr("text-anchor", "end").text(rotuloX);
      g.append("text").attr("class", "explorar__titulo-eixo").attr("x", 4).attr("y", 14).text("Renda per capita (escala log)");
    };
    cruzamento("oportunidade", "Academias por 10 mil hab. (limitado aos percentis 5–95%) →", (v) => decimal(v, 1), mediana.academias,
      { lado: "esquerda", alto: true, texto: "Oportunidade" });
    cruzamento("armadilha", "Crescimento da população desde 2022 (% a.a.) →", (v) => decimal(v * 100, 1), mediana.crescimento,
      { lado: "direita", alto: false, texto: "Armadilha" });

    // ranking
    {
      const { x } = L.ranking.escalas;
      const g = grupo("ranking");
      g.append("g").attr("class", "explorar__eixo").attr("transform", `translate(0,${y0})`)
        .call(d3.axisBottom(x).ticks(10).tickSize(-(y0 - y1)).tickPadding(8));
      g.append("text").attr("class", "explorar__titulo-eixo").attr("x", x1).attr("y", altura - 8).attr("text-anchor", "end").text("Nota final (0 a 100) →");
    }
    // regiões
    {
      const { colunas, y } = L.regioes.escalas;
      const g = grupo("regioes");
      g.append("g").attr("class", "explorar__eixo").attr("transform", `translate(${x0},0)`)
        .call(d3.axisLeft(y).ticks(5).tickSize(-(x1 - x0)).tickPadding(8));
      g.append("g").selectAll("text").data(ORDEM_REGIOES).join("text").attr("class", "explorar__titulo-coluna")
        .attr("x", (s) => colunas(s) + colunas.bandwidth() / 2).attr("y", altura - 16).attr("text-anchor", "middle")
        .text((s) => (largura < 600 ? s : REGIOES.find((r) => r.sigla === s)?.nome ?? s));
    }
  }

  // ------------------------------------------------------------ frase de cada vista (números reais)
  function fraseDa(chave) {
    const total = inteiro(n);
    if (chave === "mapa") {
      const porRegiao = d3.rollup(cidades, (v) => v.length, (c) => c.regiao_sigla);
      const maior = d3.greatest(porRegiao, ([, v]) => v);
      const nome = REGIOES.find((r) => r.sigla === maior[0])?.nome;
      return `${total} cidades com 50 mil habitantes ou mais. O ${nome} concentra ${inteiro(maior[1])} delas; a cor é a nota final e o tamanho, a população.`;
    }
    if (chave === "oportunidade") {
      const q = cidades.filter((c) => c.renda_dom_per_capita > mediana.renda && acadLimitada(c) !== null && acadLimitada(c) < mediana.academias).length;
      return `${inteiro(q)} das ${total} cidades estão no quadrante de oportunidade: renda acima da mediana e menos academias por habitante que a mediana.`;
    }
    if (chave === "armadilha") {
      const noQuadrante = cidades.filter((c) => c.crescimento_pop_aa > mediana.crescimento && c.renda_dom_per_capita !== null && c.renda_dom_per_capita < mediana.renda);
      const destaque = noQuadrante.find((c) => !c.ranking.recomendado_top5 && c.ranking.elegivel_recomendacao === false);
      return `${inteiro(noQuadrante.length)} cidades crescem acima da mediana com renda abaixo dela — o quadrante armadilha.` +
        (destaque ? ` ${destaque.municipio_nome} (${destaque.ranking.posicao_brasil}º no ranking) está aqui: por isso ficou fora da lista, pela trava de renda.` : "");
    }
    if (chave === "ranking") {
      const notas = cidades.map((c) => c.ranking.nota_final).sort(d3.ascending);
      const ultimaRec = d3.max(estado.recomendadas, (r) => r.posicao_brasil);
      return `A nota final vai de ${decimal(notas[0], 1)} a ${decimal(notas.at(-1), 1)}; metade das cidades fica entre ${decimal(quantil(notas, 0.25), 1)} e ${decimal(quantil(notas, 0.75), 1)}.` +
        (ultimaRec ? ` As ${estado.recomendadas.length} recomendadas estão entre as ${ultimaRec} primeiras.` : "");
    }
    const medianas = ORDEM_REGIOES.map((s) => {
      const v = cidades.filter((c) => c.regiao_sigla === s).map((c) => c.ranking.nota_final).sort(d3.ascending);
      return `${s} ${decimal(quantil(v, 0.5), 1)}`;
    });
    return `Nota mediana por região: ${medianas.join(" · ")}.`;
  }

  // ------------------------------------------------------------ desenho do canvas
  let paleta = {};
  let corPorPonto = [];
  function lerCores() {
    paleta = Object.fromEntries(CORES.map((c) => [c, cor(c)]));
    paleta.limao = cor("--limao-texto");
    paleta.tinta = cor("--tinta");
    paleta.halo = cor("--halo");
    paleta.fonte = `600 12px ${cor("--mono") || "monospace"}`;
    corPorPonto = cidades.map((c) => paleta[CORES[d3.bisectRight(LIMIARES, c.ranking.nota_final)]]);
  }

  function desenhar() {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, largura, altura);
    // em lote: um caminho por cor
    const grupos = new Map();
    for (let i = 0; i < n; i++) {
      if (atual.a[i] < 0.02) continue;
      const k = corPorPonto[i];
      if (!grupos.has(k)) grupos.set(k, []);
      grupos.get(k).push(i);
    }
    ctx.globalAlpha = 0.9;
    for (const [k, lista] of grupos) {
      ctx.fillStyle = k;
      ctx.beginPath();
      for (const i of lista) { ctx.moveTo(atual.x[i] + atual.r[i], atual.y[i]); ctx.arc(atual.x[i], atual.y[i], atual.r[i], 0, Math.PI * 2); }
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    // recomendadas: contorno verde-limão e etiqueta; cidade da busca e sob o mouse: contorno na cor do texto
    ctx.font = paleta.fonte;
    const ocupados = [];
    const colide = (a) => ocupados.some((b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y);
    const rotular = (i, cor) => {
      if (atual.a[i] < 0.2) return;
      ctx.lineWidth = 2.5;
      ctx.strokeStyle = cor;
      ctx.beginPath(); ctx.arc(atual.x[i], atual.y[i], atual.r[i] + 3, 0, Math.PI * 2); ctx.stroke();
      const texto = cidades[i].municipio_nome.toUpperCase();
      const w = ctx.measureText(texto).width;
      const tx = Math.min(atual.x[i] + atual.r[i] + 8, largura - w - 4);
      // primeiro ao lado do ponto; se encostar em outra etiqueta, sobe ou desce de 16 em 16 px
      let ty = atual.y[i] + 4;
      for (const d of [0, -16, 16, -32, 32, -48, 48, -64, 64]) {
        const caixa = { x: tx - 2, y: atual.y[i] + d - 10, w: w + 4, h: 14 };
        if (!colide(caixa)) { ty = atual.y[i] + d + 4; ocupados.push(caixa); break; }
      }
      if (Math.abs(ty - atual.y[i] - 4) > 1) {       // etiqueta deslocada: um fio liga ao ponto
        ctx.lineWidth = 1; ctx.strokeStyle = cor;
        ctx.beginPath(); ctx.moveTo(atual.x[i] + atual.r[i] + 3, atual.y[i]); ctx.lineTo(tx - 2, ty - 4); ctx.stroke();
      }
      ctx.lineWidth = 4; ctx.strokeStyle = paleta.halo; ctx.strokeText(texto, tx, ty);
      ctx.fillStyle = paleta.tinta; ctx.fillText(texto, tx, ty);
    };
    for (let i = 0; i < n; i++) if (recomendada(cidades[i])) rotular(i, paleta.limao);
    if (fixada >= 0) rotular(fixada, paleta.tinta);
    if (sobMouse >= 0 && sobMouse !== fixada) {
      ctx.lineWidth = 2; ctx.strokeStyle = paleta.tinta;
      ctx.beginPath(); ctx.arc(atual.x[sobMouse], atual.y[sobMouse], atual.r[sobMouse] + 3, 0, Math.PI * 2); ctx.stroke();
    }
  }

  function passo(agora) {
    const t = Math.min(1, (agora - inicio) / DURACAO);
    const e = facilitar(t);
    for (const k of ["x", "y", "r", "a"]) {
      const de = origem[k], para = alvo[k], at = atual[k];
      for (let i = 0; i < n; i++) at[i] = de[i] + (para[i] - de[i]) * e;
    }
    desenhar();
    quadro = t < 1 ? requestAnimationFrame(passo) : null;
  }

  function irPara(chave, { animar = true } = {}) {
    vista = chave;
    alvo = layouts[chave];
    for (const g of svg.selectAll(".explorar__camada").nodes()) g.classList.toggle("ativa", g.dataset.vista === chave);
    frase.textContent = fraseDa(chave);
    palco.dataset.vista = chave;
    if (quadro) cancelAnimationFrame(quadro);
    if (!animar || prefereMenos.matches) {
      for (const k of ["x", "y", "r", "a"]) atual[k].set(alvo[k]);
      quadro = null;
      desenhar();
      return;
    }
    for (const k of ["x", "y", "r", "a"]) origem[k].set(atual[k]);   // parte de onde está, mesmo no meio de outra troca
    inicio = performance.now();
    quadro = requestAnimationFrame(passo);
  }

  function dimensionar() {
    const caixa = palco.getBoundingClientRect();
    largura = Math.round(caixa.width);
    altura = Math.round(caixa.height);
    if (!largura || !altura) return;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = largura * dpr;
    canvas.height = altura * dpr;
    lerCores();
    layouts = calcularLayouts();
    desenharEixos();
    irPara(vista, { animar: false });
  }

  // ------------------------------------------------------------ abas (tablist acessível)
  abas.innerHTML = VISTAS.map((v, i) => `<button type="button" role="tab" id="aba-explorar-${v.chave}" data-vista="${v.chave}"
    aria-selected="${i === 0}" tabindex="${i === 0 ? 0 : -1}" aria-controls="explorar-palco">${v.rotulo}</button>`).join("");
  function escolher(chave, focar = false) {
    for (const b of abas.querySelectorAll("[role=tab]")) {
      const ativa = b.dataset.vista === chave;
      b.setAttribute("aria-selected", ativa);
      b.tabIndex = ativa ? 0 : -1;
      if (ativa && focar) b.focus();
    }
    palco.setAttribute("aria-labelledby", `aba-explorar-${chave}`);
    irPara(chave);
  }
  abas.addEventListener("click", (e) => { const b = e.target.closest("[role=tab]"); if (b) escolher(b.dataset.vista); });
  abas.addEventListener("keydown", (e) => {
    const i = VISTAS.findIndex((v) => v.chave === vista);
    const passos = { ArrowRight: 1, ArrowLeft: -1 };
    let novo = null;
    if (e.key in passos) novo = (i + passos[e.key] + VISTAS.length) % VISTAS.length;
    if (e.key === "Home") novo = 0;
    if (e.key === "End") novo = VISTAS.length - 1;
    if (novo === null) return;
    e.preventDefault();
    escolher(VISTAS[novo].chave, true);
  });

  // ------------------------------------------------------------ ponteiro: tooltip e clique abre a ficha
  function pontoEm(px, py) {
    let melhor = -1, dist = Infinity;
    for (let i = 0; i < n; i++) {
      if (atual.a[i] < 0.2) continue;
      const d = Math.hypot(px - atual.x[i], py - atual.y[i]) - atual.r[i];
      if (d < dist) { dist = d; melhor = i; }
    }
    return dist <= 6 ? melhor : -1;                 // alvo maior que o ponto
  }
  function dicaDa(i) {
    const c = cidades[i];
    const r = c.ranking;
    const caixa = canvas.getBoundingClientRect();
    const ancora = { left: caixa.left + atual.x[i] - atual.r[i], top: caixa.top + atual.y[i] - atual.r[i], width: atual.r[i] * 2, height: atual.r[i] * 2 };
    ancora.right = ancora.left + ancora.width; ancora.bottom = ancora.top + ancora.height;
    mostrarDica(ancora, conteudoDica({
      titulo: `${c.municipio_nome} · ${c.uf_sigla}`,
      chip: r.recomendado_top5 ? { texto: `Recomendada nº ${r.ordem_recomendacao}`, estado: "verde" } : null,
      linhas: [
        { rotulo: "Nota final", valor: decimal(r.nota_final, 1), detalhe: `${r.posicao_brasil}º no Brasil` },
        { rotulo: "Renda per capita", valor: reais(c.renda_dom_per_capita) },
        { rotulo: "Academias/10 mil", valor: decimal(c.academias_por_10mil_hab, 2) },
        { rotulo: "Crescimento", valor: fracaoAoAno(c.crescimento_pop_aa) },
        { rotulo: "População", valor: compacto(c.populacao) },
      ],
      nota: `Clique para abrir a ficha${menu ? "; botão direito ou toque longo: mais opções" : ""}.`,
    }));
  }
  canvas.addEventListener("pointermove", (e) => {
    const caixa = canvas.getBoundingClientRect();
    const i = pontoEm(e.clientX - caixa.left, e.clientY - caixa.top);
    if (i !== sobMouse) { sobMouse = i; if (!quadro) desenhar(); }
    canvas.style.cursor = i >= 0 ? "pointer" : "default";
    if (i >= 0) dicaDa(i); else esconderDica();
  });
  canvas.addEventListener("pointerleave", () => { sobMouse = -1; esconderDica(); if (!quadro) desenhar(); });
  menu?.ligar(canvas, (e) => {
    const caixa = canvas.getBoundingClientRect();
    const i = pontoEm(e.clientX - caixa.left, e.clientY - caixa.top);
    if (i >= 0) esconderDica();
    return i >= 0 ? cidades[i].municipio_id : null;
  });
  canvas.addEventListener("click", (e) => {
    const caixa = canvas.getBoundingClientRect();
    const i = pontoEm(e.clientX - caixa.left, e.clientY - caixa.top);
    if (i >= 0) { esconderDica(); aoSelecionar(cidades[i].municipio_id); }
  });

  // ------------------------------------------------------------ busca: fixa a etiqueta no ponto
  const opcoes = document.getElementById("explorar-opcoes");
  opcoes.innerHTML = cidades.map((c) => `<option value="${c.municipio_nome} (${c.uf_sigla})"></option>`).join("");
  const porTexto = new Map(cidades.map((c, i) => [normalizar(`${c.municipio_nome} (${c.uf_sigla})`), i]));
  busca.addEventListener("change", () => {
    const i = porTexto.get(normalizar(busca.value));
    fixada = i ?? -1;
    if (!quadro) desenhar();
    if (i !== undefined) dicaDa(i);
  });

  // ------------------------------------------------------------ alternativa em tabela
  const botaoTabela = document.getElementById("explorar-ver-tabela");
  const tabela = document.getElementById("explorar-tabela");
  botaoTabela.addEventListener("click", () => {
    const abrir = tabela.hidden;
    tabela.hidden = !abrir;
    botaoTabela.setAttribute("aria-expanded", abrir);
    botaoTabela.textContent = abrir ? "Esconder a tabela" : "Ver como tabela";
    if (abrir && !tabela.dataset.pronta) {
      tabela.querySelector("tbody").innerHTML = cidades.map((c) => `<tr>
        <td class="num">${c.ranking.posicao_brasil}º</td><th scope="row">${c.municipio_nome} <small>${c.uf_sigla}</small></th>
        <td>${c.regiao_sigla}</td><td class="num">${decimal(c.ranking.nota_final, 1)}</td><td class="num">${reais(c.renda_dom_per_capita)}</td>
        <td class="num">${decimal(c.academias_por_10mil_hab, 2)}</td><td class="num">${fracaoAoAno(c.crescimento_pop_aa)}</td>
        <td>${c.ranking.recomendado_top5 ? `nº ${c.ranking.ordem_recomendacao}` : ""}</td></tr>`).join("");
      tabela.dataset.pronta = "1";
    }
  });

  document.getElementById("titulo-explorar").textContent = `Explorar as ${inteiro(n)} cidades`;
  document.getElementById("explorar-legenda").innerHTML = `Nota final
    <div class="escala">${CORES.map((c) => `<i style="background:var(${c})"></i>`).join("")}</div>
    <div style="display:flex;justify-content:space-between"><span>&lt; ${LIMIARES[0]}</span><span>${LIMIARES.at(-1)}+</span></div>
    ${estado.recomendadas.length ? `<div style="margin-top:8px"><span class="ponto ponto--anel"></span>unidade recomendada (contorno verde-limão)</div>` : ""}`;
  let espera;
  new ResizeObserver(() => { clearTimeout(espera); espera = setTimeout(dimensionar, 120); }).observe(palco);
  document.addEventListener("tema-alterado", () => { lerCores(); desenhar(); });
  dimensionar();
}
