// Mapa coroplético dos municípios em <canvas>.
// Canvas em vez de SVG: são 5.570 polígonos, e o canvas desenha tudo de uma vez sem pesar o navegador.
// Para saber qual município está sob o mouse: filtra pela caixa (bounds) e confirma com isPointInPath.

import { INDICADORES_MAPA, NOMES_UF } from "./indicadores.js";
import { ordinal } from "./formato.js";

const CLASSES_SEQUENCIAL = 7;

/** Lê um token de cor do CSS (muda com o tema). */
const cor = (nome) => getComputedStyle(document.documentElement).getPropertyValue(nome).trim();

export function criarMapa({ topo, estado, aoSelecionar }) {
  const d3 = window.d3;
  const topojson = window.topojson;

  const tela = document.getElementById("mapa-tela");
  const canvas = document.getElementById("mapa-canvas");
  const ctx = canvas.getContext("2d");
  const teste = document.createElement("canvas").getContext("2d"); // contexto sem escala, só para isPointInPath
  const dica = document.getElementById("mapa-dica");
  const legenda = document.getElementById("mapa-legenda");
  const destaques = document.getElementById("mapa-destaques");

  const objeto = topo.objects.BRMU;
  // O d3 espera o anel externo no sentido horário; o padrão GeoJSON é o contrário.
  // Se um polígono "ocupa mais que meia esfera", o sentido está invertido: inverte os anéis.
  const acertarSentido = (f) => {
    if (d3.geoArea(f) > 2 * Math.PI) {
      const poligonos = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
      for (const p of poligonos) for (const anel of p) anel.reverse();
    }
    return f;
  };
  const municipios = topojson.feature(topo, objeto).features.map(acertarSentido).map((f) => ({
    id: Number(f.properties.codarea),
    uf: estado.porId.get(Number(f.properties.codarea))?.uf_sigla ?? null,
    feicao: f,
    caminho: null,
    caixa: null,
  }));
  // Divisas entre UFs: arestas cujos vizinhos têm códigos de UF (2 primeiros dígitos) diferentes
  const divisasUf = topojson.mesh(topo, objeto, (a, b) => a !== b && a.properties.codarea.slice(0, 2) !== b.properties.codarea.slice(0, 2));
  const contorno = topojson.mesh(topo, objeto, (a, b) => a === b);

  let indicador = INDICADORES_MAPA[0];
  let escala = null;
  let selecionado = null;
  let sobMouse = null;
  let ufZoom = "";
  let largura = 0;
  let altura = 0;
  let dpr = 1;
  let pathDivisas = null;
  let pathContorno = null;

  // ------------------------------------------------------------ escala de cor
  function montarEscala() {
    const valores = estado.indicadores.map((m) => indicador.valor(estado.porId.get(m.municipio_id))).filter((v) => v !== null && v !== undefined);
    if (indicador.escala === "divergente") {
      const tokens = ["--div-n2", "--div-n1", "--div-0", "--div-p1", "--div-p2", "--div-p3"];
      escala = { tipo: "limites", limites: indicador.limites, tokens, s: d3.scaleThreshold().domain(indicador.limites).range(tokens) };
    } else {
      const tokens = Array.from({ length: CLASSES_SEQUENCIAL }, (_, i) => `--seq-${i + 1}`);
      const s = d3.scaleQuantile().domain(valores).range(tokens);
      escala = { tipo: "quantil", limites: s.quantiles(), tokens, s };
    }
  }

  // ------------------------------------------------------------ projeção e geometria
  function projetar() {
    const caixa = tela.getBoundingClientRect();
    largura = caixa.width;
    altura = caixa.height;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(largura * dpr);
    canvas.height = Math.round(altura * dpr);

    const alvo = ufZoom
      ? { type: "FeatureCollection", features: municipios.filter((m) => m.uf === ufZoom).map((m) => m.feicao) }
      : { type: "FeatureCollection", features: municipios.map((m) => m.feicao) };
    const margem = Math.max(12, largura * 0.03);
    const projecao = d3.geoMercator().fitExtent([[margem, margem + (ufZoom ? 36 : 0)], [largura - margem, altura - margem]], alvo);
    const gerador = d3.geoPath(projecao);
    for (const m of municipios) {
      m.caminho = new Path2D(gerador(m.feicao) || "");
      m.caixa = gerador.bounds(m.feicao);
    }
    pathDivisas = new Path2D(gerador(divisasUf) || "");
    pathContorno = new Path2D(gerador(contorno) || "");
  }

  // ------------------------------------------------------------ desenho
  /** "Sem dado" em hachura: não se confunde com nenhuma cor da escala (nem com o cinza do meio). */
  function padraoSemDado() {
    const p = document.createElement("canvas");
    p.width = p.height = 6;
    const c = p.getContext("2d");
    c.fillStyle = cor("--sem-dado");
    c.fillRect(0, 0, 6, 6);
    c.strokeStyle = cor("--linha-forte");
    c.lineWidth = 1;
    c.beginPath();
    c.moveTo(0, 6); c.lineTo(6, 0);
    c.moveTo(-1, 1); c.lineTo(1, -1);
    c.moveTo(5, 7); c.lineTo(7, 5);
    c.stroke();
    return ctx.createPattern(p, "repeat");
  }

  function desenhar() {
    if (!escala) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, largura, altura);
    const paleta = Object.fromEntries(escala.tokens.map((t) => [t, cor(t)]));
    // na nota, "fora do universo" é a maioria: cor lisa; nos demais, "sem dado" é exceção: hachura
    const semDado = indicador.chave === "nota" ? cor("--sem-dado") : padraoSemDado();

    // pinta agrupado por cor: menos trocas de fillStyle
    const grupos = new Map();
    for (const m of municipios) {
      const v = indicador.valor(estado.porId.get(m.id) ?? {});
      const c = v === null || v === undefined ? semDado : paleta[escala.s(v)];
      if (!grupos.has(c)) grupos.set(c, []);
      grupos.get(c).push(m);
    }
    for (const [c, lista] of grupos) {
      ctx.fillStyle = c;
      for (const m of lista) ctx.fill(m.caminho);
    }
    ctx.lineWidth = ufZoom ? 0.6 : 0.3;
    ctx.strokeStyle = cor("--divisa-mun");
    for (const m of municipios) ctx.stroke(m.caminho);

    ctx.lineWidth = ufZoom ? 1.6 : 0.9;
    ctx.strokeStyle = cor("--divisa-uf");
    ctx.stroke(pathDivisas);
    ctx.stroke(pathContorno);

    for (const [id, espessura] of [[sobMouse, 1.6], [selecionado, 2.6]]) {
      const m = id && municipios.find((x) => x.id === id);
      if (!m) continue;
      ctx.lineWidth = espessura + 3;
      ctx.strokeStyle = cor("--superficie");
      ctx.stroke(m.caminho);
      ctx.lineWidth = espessura;
      ctx.strokeStyle = cor("--tinta");
      ctx.stroke(m.caminho);
    }
  }

  // ------------------------------------------------------------ legenda e destaques
  function desenharLegenda() {
    const fmt = indicador.formato;
    const partes = escala.tokens.map((t, i) => {
      const de = i === 0 ? null : escala.limites[i - 1];
      const ate = i < escala.limites.length ? escala.limites[i] : null;
      const texto = de === null ? `até ${fmt(ate)}` : ate === null ? `${fmt(de)} ou mais` : `${fmt(de)}`;
      return `<div class="legenda__classe"><span class="legenda__cor" style="background:var(${t})"></span>${i === 0 || i === escala.tokens.length - 1 || escala.tipo === "limites" ? texto : ""}</div>`;
    });
    legenda.innerHTML = partes.join("") +
      `<div class="legenda__extra"><span class="legenda__cor ${indicador.chave === "nota" ? "legenda__cor--lisa" : "legenda__cor--hachura"}"></span>${indicador.semDado}</div>` +
      `<div class="legenda__extra discreto">${escala.tipo === "quantil" ? "Cada faixa reúne a mesma quantidade de municípios." : "Faixas fixas de crescimento anual."}</div>`;

    document.getElementById("mapa-indicador-titulo").textContent = indicador.titulo;
    document.getElementById("mapa-indicador-explica").textContent = indicador.explica;
    document.getElementById("mapa-destaques-titulo").textContent = `${indicador.destaques} · 50 mil hab. ou mais`;

    const lista = estado.ranking
      .map((r) => ({ r, v: indicador.valor(estado.porId.get(r.municipio_id)) }))
      .filter((x) => x.v !== null && x.v !== undefined && (!ufZoom || x.r.uf_sigla === ufZoom))
      .sort((a, b) => b.v - a.v)
      .slice(0, 10);
    destaques.innerHTML = lista.map(({ r, v }) =>
      `<li><button type="button" data-id="${r.municipio_id}">${r.municipio_nome} <span class="discreto">${r.uf_sigla}</span></button><span class="v">${indicador.formato(v)}</span></li>`
    ).join("");
  }

  // ------------------------------------------------------------ interação
  function municipioEm(x, y) {
    for (let i = municipios.length - 1; i >= 0; i--) {
      const m = municipios[i];
      const [[x0, y0], [x1, y1]] = m.caixa;
      if (x < x0 || x > x1 || y < y0 || y > y1) continue;
      if (teste.isPointInPath(m.caminho, x, y)) return m.id;
    }
    return null;
  }

  function mostrarDica(id, x, y) {
    const m = estado.porId.get(id);
    if (!m) { dica.hidden = true; return; }
    const v = indicador.valor(m);
    const pos = m.ranking ? `${ordinal(m.ranking.posicao_brasil)} no ranking · nota ${m.ranking.nota_final.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}` : "Fora do universo do ranking";
    dica.innerHTML = `<strong>${m.municipio_nome} <span class="discreto">${m.uf_sigla}</span></strong>
      <span class="discreto">${indicador.titulo}</span><br><span class="valor">${v === null || v === undefined ? "sem dado" : indicador.formato(v)}</span><br>
      <span class="discreto">${pos}</span>`;
    dica.hidden = false;
    const w = dica.offsetWidth;
    const h = dica.offsetHeight;
    const left = x + 16 + w > largura ? x - w - 16 : x + 16;
    const top = Math.min(Math.max(8, y - h / 2), altura - h - 8);
    dica.style.left = `${Math.max(8, left)}px`;
    dica.style.top = `${top}px`;
  }

  canvas.addEventListener("mousemove", (e) => {
    const r = canvas.getBoundingClientRect();
    const x = e.clientX - r.left;
    const y = e.clientY - r.top;
    const id = municipioEm(x, y);
    if (id !== sobMouse) { sobMouse = id; desenhar(); }
    if (id) mostrarDica(id, x, y); else dica.hidden = true;
    canvas.style.cursor = id ? "pointer" : "default";
  });
  canvas.addEventListener("mouseleave", () => { sobMouse = null; dica.hidden = true; desenhar(); });
  canvas.addEventListener("click", (e) => {
    const r = canvas.getBoundingClientRect();
    const id = municipioEm(e.clientX - r.left, e.clientY - r.top);
    if (id && estado.porId.has(id)) aoSelecionar(id);
  });
  destaques.addEventListener("click", (e) => {
    const botao = e.target.closest("button[data-id]");
    if (botao) aoSelecionar(Number(botao.dataset.id));
  });

  // abas (padrão de tabs acessível: setas trocam de aba)
  const abas = document.getElementById("abas-mapa");
  abas.innerHTML = INDICADORES_MAPA.map((ind, i) =>
    `<button class="aba" role="tab" type="button" id="aba-${ind.chave}" data-chave="${ind.chave}" aria-selected="${i === 0}" tabindex="${i === 0 ? 0 : -1}" aria-controls="mapa-tela">${ind.rotulo}</button>`
  ).join("");
  function escolherAba(chave, focar = false) {
    indicador = INDICADORES_MAPA.find((i) => i.chave === chave);
    for (const b of abas.querySelectorAll(".aba")) {
      const ativo = b.dataset.chave === chave;
      b.setAttribute("aria-selected", ativo);
      b.tabIndex = ativo ? 0 : -1;
      if (ativo && focar) b.focus();
    }
    canvas.setAttribute("aria-label", `Mapa dos municípios do Brasil colorido por ${indicador.titulo.toLowerCase()}`);
    montarEscala();
    desenharLegenda();
    desenhar();
  }
  abas.addEventListener("click", (e) => { const b = e.target.closest(".aba"); if (b) escolherAba(b.dataset.chave); });
  abas.addEventListener("keydown", (e) => {
    if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) return;
    e.preventDefault();
    const i = INDICADORES_MAPA.indexOf(indicador);
    const n = INDICADORES_MAPA.length;
    const novo = e.key === "Home" ? 0 : e.key === "End" ? n - 1 : (i + (e.key === "ArrowRight" ? 1 : -1) + n) % n;
    escolherAba(INDICADORES_MAPA[novo].chave, true);
  });

  // zoom por UF
  const seletorUf = document.getElementById("mapa-uf");
  seletorUf.insertAdjacentHTML("beforeend", estado.ufs.map((uf) => `<option value="${uf}">${NOMES_UF[uf] ?? uf}</option>`).join(""));
  seletorUf.addEventListener("change", () => { ufZoom = seletorUf.value; projetar(); desenharLegenda(); desenhar(); });

  // redesenha quando o tamanho ou o tema mudam
  let espera = null;
  new ResizeObserver(() => { clearTimeout(espera); espera = setTimeout(() => { projetar(); desenhar(); }, 80); }).observe(tela);
  document.addEventListener("tema-alterado", desenhar);
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", desenhar);

  document.getElementById("mapa-carregando").remove();
  projetar();
  escolherAba(indicador.chave);

  return {
    selecionar(id) { selecionado = id; desenhar(); },
  };
}
