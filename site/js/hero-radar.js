// Radar do hero: uma linha de varredura gira sobre o Brasil e "acende" as cidades avaliadas
// (pontos reais: centro de cada município, tamanho = população). Canvas puro, sem vídeo.

import { feicoes, objetoDe } from "./geo.js";
import { posicionarBotaoPitch } from "./pitch.js";

const VELOCIDADE = 0.85;          // radianos por segundo (~7 s por volta)
const LARGURA_RASTRO = 1.1;       // abertura do rastro da varredura, em radianos
const MEIA_VIDA = 1.8;            // segundos que um ponto leva para apagar depois de varrido
const ROTULOS = 5;                // sem lista de recomendadas: quantas do topo ganham nome

const cor = (nome) => getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
function rgba(hex, a) {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

export function criarRadarHero({ canvas, topoUfs, cidades }) {
  const d3 = window.d3;
  const topojson = window.topojson;
  const ctx = canvas.getContext("2d");
  const estatico = document.createElement("canvas");
  const sctx = estatico.getContext("2d");
  const reduzir = window.matchMedia("(prefers-reduced-motion: reduce)");

  const objeto = objetoDe(topoUfs);
  const brasil = feicoes(topoUfs);
  const divisas = topojson.mesh(topoUfs, objeto, (a, b) => a !== b);
  const contorno = topojson.mesh(topoUfs, objeto, (a, b) => a === b);

  let w = 0, h = 0, dpr = 1, cx = 0, cy = 0, raio = 0;
  let pontos = [];
  let rodando = false;
  let visivel = true;
  let inicio = performance.now();
  let quadro = null;

  function preparar() {
    const caixa = canvas.getBoundingClientRect();
    w = caixa.width; h = caixa.height;
    if (!w || !h) return;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    for (const c of [canvas, estatico]) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); }

    const margem = Math.min(w, h) * 0.08;
    const projecao = d3.geoMercator().fitExtent([[margem, margem], [w - margem, h - margem]], brasil);
    const caminho = d3.geoPath(projecao, sctx);
    const [[x0, y0], [x1, y1]] = d3.geoPath(projecao).bounds(brasil);
    cx = (x0 + x1) / 2; cy = (y0 + y1) / 2;
    raio = Math.hypot(x1 - x0, y1 - y0) / 2;
    posicionarBotaoPitch(canvas.offsetLeft + cx, canvas.offsetTop + cy);   // play do pitch no centro do radar

    // camada fixa: anéis, raios e o desenho do Brasil
    sctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    sctx.clearRect(0, 0, w, h);
    sctx.strokeStyle = rgba(cor("--tinta-3"), 0.18);
    sctx.lineWidth = 1;
    for (let r = raio / 4; r <= raio * 1.05; r += raio / 4) { sctx.beginPath(); sctx.arc(cx, cy, r, 0, Math.PI * 2); sctx.stroke(); }
    for (let a = 0; a < Math.PI * 2; a += Math.PI / 6) {
      sctx.beginPath(); sctx.moveTo(cx, cy); sctx.lineTo(cx + Math.cos(a) * raio, cy + Math.sin(a) * raio); sctx.stroke();
    }
    sctx.fillStyle = rgba(cor("--tinta"), 0.03);
    sctx.beginPath(); caminho(brasil); sctx.fill();
    sctx.strokeStyle = rgba(cor("--tinta-3"), 0.28); sctx.lineWidth = 0.7;
    sctx.beginPath(); caminho(divisas); sctx.stroke();
    sctx.strokeStyle = rgba(cor("--tinta-2"), 0.55); sctx.lineWidth = 1.2;
    sctx.beginPath(); caminho(contorno); sctx.stroke();

    const temLista = cidades.some((c) => c.ranking?.recomendado_top5);
    pontos = cidades.filter((c) => c.longitude !== null).map((c, i) => {
      const [x, y] = projecao([c.longitude, c.latitude]);
      return {
        x, y,
        angulo: Math.atan2(y - cy, x - cx),
        r: 1.3 + Math.sqrt(c.populacao / 1e6) * 3.2,
        // nomes no radar: as unidades recomendadas (ou as primeiras do ranking, se não houver lista)
        nome: (temLista ? c.ranking?.recomendado_top5 : i < ROTULOS) ? c.municipio_nome : null,
      };
    });
  }

  function desenhar(agora) {
    if (!w) return;
    const t = reduzir.matches ? 2.2 : (agora - inicio) / 1000;
    const theta = (t * VELOCIDADE) % (Math.PI * 2);
    const marca = cor("--limao-texto");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(estatico, 0, 0);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // rastro da varredura
    if (ctx.createConicGradient) {
      const g = ctx.createConicGradient(theta - LARGURA_RASTRO, cx, cy);
      const fim = LARGURA_RASTRO / (Math.PI * 2);
      g.addColorStop(0, rgba(marca, 0));
      g.addColorStop(fim, rgba(marca, 0.22));
      g.addColorStop(Math.min(fim + 0.001, 1), rgba(marca, 0));
      ctx.fillStyle = g;
    } else {
      ctx.fillStyle = rgba(marca, 0.08);
    }
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, raio, theta - LARGURA_RASTRO, theta); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = rgba(marca, 0.85); ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(theta) * raio, cy + Math.sin(theta) * raio); ctx.stroke();

    // cidades: acendem quando a linha passa e apagam devagar
    ctx.font = `600 11px ${cor("--mono") || "monospace"}`;
    for (const p of pontos) {
      const atraso = (((theta - p.angulo) % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2) / VELOCIDADE;
      const brilho = reduzir.matches ? 0.55 : Math.exp(-atraso / MEIA_VIDA);
      ctx.fillStyle = rgba(marca, 0.22 + 0.78 * brilho);
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r * (1 + brilho * 0.5), 0, Math.PI * 2); ctx.fill();
      if (p.nome && brilho > 0.25) {
        ctx.fillStyle = rgba(cor("--tinta"), Math.min(1, brilho * 1.4));
        ctx.fillText(p.nome.toUpperCase(), p.x + p.r + 6, p.y + 4);
      }
    }
  }

  function laco(agora) {
    desenhar(agora);
    if (rodando) quadro = requestAnimationFrame(laco);
  }
  function atualizarLaco() {
    const deve = visivel && !document.hidden && !reduzir.matches;
    if (deve && !rodando) { rodando = true; quadro = requestAnimationFrame(laco); }
    if (!deve && rodando) { rodando = false; cancelAnimationFrame(quadro); }
    if (!deve) desenhar(performance.now());
  }

  new IntersectionObserver(([e]) => { visivel = e.isIntersecting; atualizarLaco(); }).observe(canvas);
  document.addEventListener("visibilitychange", atualizarLaco);
  reduzir.addEventListener("change", atualizarLaco);
  let espera;
  new ResizeObserver(() => { clearTimeout(espera); espera = setTimeout(() => { preparar(); desenhar(performance.now()); }, 100); }).observe(canvas);
  document.addEventListener("tema-alterado", () => { preparar(); desenhar(performance.now()); });

  preparar();
  atualizarLaco();
}
