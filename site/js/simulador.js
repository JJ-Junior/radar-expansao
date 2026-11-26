// Simule sua região (prd P9): uma cidade central e um raio em km.
// Mostra as cidades do ranking dentro do raio (posição no raio e no Brasil, nota, distância, lacuna de academias),
// num mapa com zoom e círculo; a vista "Ranking local" rearranja os mesmos pontos numa fila pela nota (850 ms).
// Distância em linha reta entre centroides (haversine, spec 9.4). Endereço: ?centro=<código IBGE>&raio=<km>.

import { compacto, decimal, inteiro, normalizar } from "./formato.js";
import { conteudoDica, esconderDica, mostrarDica } from "./dica.js";
import { feicoes, objetoDe } from "./geo.js";
import { parametro } from "./indicadores.js";

const RAIO_PADRAO = 100;
const RAIO_MIN = 10, RAIO_MAX = 300;
const DURACAO = 850;
const LIMIARES = [45, 52, 59, 66];
const CORES = ["--pt-1", "--pt-2", "--pt-3", "--pt-4", "--pt-5"];
const ROTULOS_MAPA = 6;
const MOLDURA = 1.3;                              // o mapa mostra 30% além do raio
const prefereMenos = window.matchMedia("(prefers-reduced-motion: reduce)");
const cor = (nome) => getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
const facilitar = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

/** Distância em km entre dois pontos (fórmula de haversine, raio da Terra 6.371 km). */
export function distanciaKm(lat1, lon1, lat2, lon2) {
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad, dLon = (lon2 - lon1) * rad;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(a));
}

export function criarSimulador({ estado, topoUfs, aoSelecionar }) {
  const d3 = window.d3;
  const topojson = window.topojson;
  const el = (id) => document.getElementById(id);
  const palco = el("sim-palco");
  const canvas = el("sim-canvas");
  const ctx = canvas.getContext("2d");
  const campo = el("sim-centro");
  const controleRaio = el("sim-raio");
  const saidaRaio = el("sim-raio-valor");
  const incluirPequenas = el("sim-pequenas");
  const abas = el("sim-abas");

  const ufs = feicoes(topoUfs);
  const divisas = topojson.mesh(topoUfs, objetoDe(topoUfs), (a, b) => a !== b);
  const contorno = topojson.mesh(topoUfs, objetoDe(topoUfs), (a, b) => a === b);
  const todas = estado.indicadores.map((m) => estado.porId.get(m.municipio_id)).filter((m) => m.latitude !== null);
  const n = todas.length;
  const indicePorId = new Map(todas.map((m, i) => [m.municipio_id, i]));
  const anoProjecao = parametro(estado, "ano_projecao_populacao", 2028);
  const faixas = parametro(estado, "faixas_renda_referencia", 5);

  // estado do simulador
  let centro = estado.recomendadas[0]?.municipio_id ?? estado.ranking[0].municipio_id;
  let raio = RAIO_PADRAO;
  let vista = "mapa";
  let dentro = [];                                  // índices dentro do raio (ranqueadas primeiro)
  const distancia = new Float32Array(n);

  // animação: mesma técnica do Explorar (estado atual interpola até o alvo)
  const atual = { x: new Float32Array(n), y: new Float32Array(n), r: new Float32Array(n), a: new Float32Array(n) };
  const origem = { x: new Float32Array(n), y: new Float32Array(n), r: new Float32Array(n), a: new Float32Array(n) };
  let alvo = null, inicio = 0, quadro = null;
  let largura = 0, altura = 0, dpr = 1;
  let projecao = null, caminhoCanvas = null, circuloGeo = null, linhas = [];
  let sobMouse = -1;
  let paleta = {};

  // ------------------------------------------------------------ cálculo da região
  function calcular() {
    const c = estado.porId.get(centro);
    for (let i = 0; i < n; i++) distancia[i] = distanciaKm(c.latitude, c.longitude, todas[i].latitude, todas[i].longitude);
    const noRaio = [];
    for (let i = 0; i < n; i++) if (distancia[i] <= raio) noRaio.push(i);
    const ranqueadas = noRaio.filter((i) => todas[i].ranking).sort((a, b) => todas[b].ranking.nota_final - todas[a].ranking.nota_final);
    const pequenas = noRaio.filter((i) => !todas[i].ranking).sort((a, b) => (todas[b].lacuna_academias ?? -Infinity) - (todas[a].lacuna_academias ?? -Infinity));
    return { ranqueadas, pequenas, noRaio };
  }

  // ------------------------------------------------------------ layouts
  function lerCores() {
    paleta = Object.fromEntries(CORES.map((k) => [k, cor(k)]));
    Object.assign(paleta, { limao: cor("--limao-texto"), tinta: cor("--tinta"), tinta3: cor("--tinta-3"), halo: cor("--halo"),
      linha: cor("--linha-forte"), divisa: cor("--mapa-divisa-fina"), fonte: `600 12px ${cor("--mono") || "monospace"}` });
  }
  const corDe = (m) => (m.ranking ? paleta[CORES[d3.bisectRight(LIMIARES, m.ranking.nota_final)]] : paleta.tinta3);

  function layoutMapa(regiao) {
    const c = estado.porId.get(centro);
    const circulo = d3.geoCircle().center([c.longitude, c.latitude]).radius(raio / 111.195)();
    // enquadra um pouco além do raio, para as cidades de fora aparecerem esmaecidas em volta
    const moldura = d3.geoCircle().center([c.longitude, c.latitude]).radius((raio * MOLDURA) / 111.195)();
    projecao = d3.geoMercator().fitExtent([[16, 16], [largura - 16, altura - 16]], moldura);
    caminhoCanvas = d3.geoPath(projecao, ctx);
    circuloGeo = circulo;
    const zoom = Math.max(1, Math.min(6, 300 / raio));
    const raioPop = d3.scaleSqrt().domain([0, 2e6]).range([0, 7 * Math.sqrt(zoom)]).clamp(true);
    const p = { x: new Float32Array(n), y: new Float32Array(n), r: new Float32Array(n), a: new Float32Array(n) };
    const mostrarPequenas = incluirPequenas.checked;
    for (let i = 0; i < n; i++) {
      const m = todas[i];
      [p.x[i], p.y[i]] = projecao([m.longitude, m.latitude]);
      p.r[i] = Math.max(m.ranking ? 2.5 : 1.6, raioPop(m.populacao ?? 0));
      const visivel = m.ranking || mostrarPequenas;
      p.a[i] = !visivel ? 0 : distancia[i] <= raio ? 1 : 0.18;
    }
    return p;
  }

  function layoutRanking(regiao) {
    const p = layoutMapa(regiao);
    const lista = [...regiao.ranqueadas, ...(incluirPequenas.checked ? regiao.pequenas : [])];
    const m = { topo: 32, base: 48, esq: Math.min(230, largura * 0.4), dir: Math.min(110, largura * 0.2) };
    const linhaH = Math.min(40, (altura - m.topo - m.base) / Math.max(1, lista.length));
    const x = d3.scaleLinear().domain([0, 100]).range([m.esq, largura - m.dir]);
    m.fim = m.topo + lista.length * linhaH;            // as linhas começam no topo; o eixo fica logo abaixo
    for (let i = 0; i < n; i++) p.a[i] = 0;          // quem não está no raio some
    linhas = lista.map((i, k) => {
      const y = m.topo + k * linhaH + linhaH / 2;
      p.x[i] = todas[i].ranking ? x(todas[i].ranking.nota_final) : m.esq - 12;
      p.y[i] = y;
      p.r[i] = Math.max(1.5, Math.min(linhaH / 2 - 2, Math.max(4, p.r[i])));
      p.a[i] = 1;
      return { i, y, k, linhaH };
    });
    p.eixo = { x, m, linhaH };
    return p;
  }

  // ------------------------------------------------------------ desenho
  function desenhar() {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, largura, altura);
    // fundo do mapa (some na vista de ranking)
    ctx.globalAlpha = vista === "mapa" ? 1 : 0.12;
    ctx.lineWidth = 1; ctx.strokeStyle = paleta.divisa; ctx.beginPath(); caminhoCanvas(divisas); ctx.stroke();
    ctx.strokeStyle = paleta.linha; ctx.beginPath(); caminhoCanvas(contorno); ctx.stroke();
    if (vista === "mapa") {
      ctx.fillStyle = paleta.limao; ctx.globalAlpha = 0.06;
      ctx.beginPath(); caminhoCanvas(circuloGeo); ctx.fill();
      ctx.globalAlpha = 1; ctx.lineWidth = 1.5; ctx.strokeStyle = paleta.limao; ctx.stroke();
    }
    ctx.globalAlpha = 1;
    // eixo e nomes da vista de ranking
    if (vista === "ranking" && alvo?.eixo) {
      const { x, m, linhaH } = alvo.eixo;
      ctx.font = `11px ${cor("--mono") || "monospace"}`;
      ctx.fillStyle = paleta.tinta3; ctx.strokeStyle = paleta.divisa;
      const fim = Math.min(altura - m.base, m.fim);
      for (const t of [0, 25, 50, 75, 100]) {
        ctx.beginPath(); ctx.moveTo(x(t), m.topo - 8); ctx.lineTo(x(t), fim + 4); ctx.stroke();
        ctx.fillText(String(t), x(t) - 6, fim + 20);
      }
      ctx.fillText("NOTA FINAL (0 A 100) →", x(0), fim + 38);
      ctx.fillText("CIDADES NO RAIO, PELA NOTA", 8, m.topo - 14);
      const comNome = linhaH >= 11;
      ctx.font = paleta.fonte;
      for (const { i, y, k } of linhas) {
        const mm = todas[i];
        // haste da nota até o ponto (acompanha a animação)
        if (mm.ranking && atual.a[i] > 0.5) {
          ctx.globalAlpha = 0.35; ctx.strokeStyle = corDe(mm); ctx.lineWidth = Math.max(1, Math.min(3, linhaH / 10));
          ctx.beginPath(); ctx.moveTo(x(0), atual.y[i]); ctx.lineTo(atual.x[i], atual.y[i]); ctx.stroke();
          ctx.globalAlpha = 1;
        }
        if (!comNome) continue;
        ctx.fillStyle = mm.municipio_id === centro ? paleta.limao : paleta.tinta;
        const nome = `${mm.ranking ? `${k + 1}. ` : "· "}${mm.municipio_nome} ${mm.uf_sigla}`;
        ctx.fillText(nome.length > 26 ? `${nome.slice(0, 25)}…` : nome, 8, y + 4);
        if (mm.ranking && linhaH >= 14 && atual.a[i] > 0.9) {
          ctx.fillStyle = paleta.tinta3;
          ctx.fillText(`${decimal(mm.ranking.nota_final, 1)} · ${inteiro(Math.round(distancia[i]))} km`, atual.x[i] + atual.r[i] + 8, atual.y[i] + 4);
        }
      }
    }
    // pontos em lote por cor (os de fora do raio, esmaecidos)
    const grupos = new Map();
    for (let i = 0; i < n; i++) {
      if (atual.a[i] < 0.02) continue;
      const k = `${corDe(todas[i])}|${atual.a[i] > 0.6 ? 1 : 0.2}`;
      if (!grupos.has(k)) grupos.set(k, []);
      grupos.get(k).push(i);
    }
    for (const [k, lista] of grupos) {
      const [c, a] = k.split("|");
      ctx.globalAlpha = Number(a); ctx.fillStyle = c;
      ctx.beginPath();
      for (const i of lista) { ctx.moveTo(atual.x[i] + atual.r[i], atual.y[i]); ctx.arc(atual.x[i], atual.y[i], atual.r[i], 0, Math.PI * 2); }
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    // centro, as melhores do raio (só no mapa) e o ponto sob o mouse
    ctx.font = paleta.fonte;
    // rótulos sem sobreposição: tenta à direita, à esquerda, acima e abaixo; se nada couber, fica só o anel
    const ocupados = [];
    const cabe = (c) => c.x >= 2 && c.x + c.w <= largura - 2 && c.y >= 2 && c.y + c.h <= altura - 2 &&
      !ocupados.some((o) => c.x < o.x + o.w && c.x + c.w > o.x && c.y < o.y + o.h && c.y + c.h > o.y);
    const anel = (i, corAnel, rotulo) => {
      ctx.lineWidth = 2.5; ctx.strokeStyle = corAnel;
      ctx.beginPath(); ctx.arc(atual.x[i], atual.y[i], atual.r[i] + 3, 0, Math.PI * 2); ctx.stroke();
      if (!rotulo) return;
      const w = ctx.measureText(rotulo).width, h = 14, x = atual.x[i], y = atual.y[i], d = atual.r[i] + 8;
      const lugar = [{ x: x + d, y: y - h / 2 }, { x: x - d - w, y: y - h / 2 }, { x: x - w / 2, y: y - d - h }, { x: x - w / 2, y: y + d }]
        .map((c) => ({ ...c, w, h })).find(cabe);
      if (!lugar) return;
      ocupados.push(lugar);
      ctx.lineJoin = "round";
      ctx.lineWidth = 4; ctx.strokeStyle = paleta.halo; ctx.strokeText(rotulo, lugar.x, lugar.y + 11);
      ctx.fillStyle = paleta.tinta; ctx.fillText(rotulo, lugar.x, lugar.y + 11);
    };
    if (vista === "mapa") {
      const ic = indicePorId.get(centro);
      if (ic !== undefined) anel(ic, paleta.tinta, `CENTRO: ${todas[ic].municipio_nome.toUpperCase()}`);
      dentroRanqueadas.slice(0, ROTULOS_MAPA).forEach((i, k) => {
        if (i !== ic) anel(i, paleta.limao, `${k + 1}. ${todas[i].municipio_nome.toUpperCase()}`);
      });
    }
    if (sobMouse >= 0) anel(sobMouse, paleta.tinta, null);
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

  let dentroRanqueadas = [];
  function aplicar({ animar = true } = {}) {
    const regiao = calcular();
    dentro = [...regiao.ranqueadas, ...regiao.pequenas];
    dentroRanqueadas = regiao.ranqueadas;
    alvo = vista === "mapa" ? layoutMapa(regiao) : layoutRanking(regiao);
    if (quadro) cancelAnimationFrame(quadro);
    if (!animar || prefereMenos.matches) {
      for (const k of ["x", "y", "r", "a"]) atual[k].set(alvo[k]);
      quadro = null;
      desenhar();
    } else {
      for (const k of ["x", "y", "r", "a"]) origem[k].set(atual[k]);
      inicio = performance.now();
      quadro = requestAnimationFrame(passo);
    }
    desenharLista(regiao);
    desenharResumo(regiao);
    atualizarEndereco();
  }

  // ------------------------------------------------------------ lista, resumo e avisos
  function desenharLista(regiao) {
    const corpo = el("sim-lista").querySelector("tbody");
    const linhasHtml = regiao.ranqueadas.map((i, k) => {
      const m = todas[i];
      return `<tr data-id="${m.municipio_id}" ${m.municipio_id === centro ? 'class="sim__centro"' : ""}>
        <td class="num">${k + 1}º</td>
        <th scope="row"><button type="button" data-id="${m.municipio_id}">${m.municipio_nome}</button> <small>${m.uf_sigla}</small>${m.ranking.recomendado_top5 ? ` <span class="selo selo--recomendada">nº ${m.ranking.ordem_recomendacao}</span>` : ""}</th>
        <td class="num">${m.ranking.posicao_brasil}º</td>
        <td class="num"><b>${decimal(m.ranking.nota_final, 1)}</b></td>
        <td class="num">${inteiro(Math.round(distancia[i]))} km</td>
        <td class="num ${lacunaClasse(m.lacuna_academias)}">${lacunaTexto(m.lacuna_academias)}</td>
        <td class="num">${compacto(m.populacao_projetada)}</td>
      </tr>`;
    });
    if (incluirPequenas.checked) {
      linhasHtml.push(...regiao.pequenas.map((i) => {
        const m = todas[i];
        return `<tr class="sim__pequena" data-id="${m.municipio_id}"><td class="num">—</td>
          <th scope="row"><button type="button" data-id="${m.municipio_id}">${m.municipio_nome}</button> <small>${m.uf_sigla} · sem nota</small></th>
          <td class="num">—</td><td class="num">—</td><td class="num">${inteiro(Math.round(distancia[i]))} km</td>
          <td class="num ${lacunaClasse(m.lacuna_academias)}">${lacunaTexto(m.lacuna_academias)}</td><td class="num">${compacto(m.populacao_projetada)}</td></tr>`;
      }));
    }
    corpo.innerHTML = linhasHtml.join("") || `<tr><td colspan="7" class="discreto">Nenhuma cidade do ranking neste raio. Aumente o raio ou inclua as cidades menores.</td></tr>`;
  }
  const lacunaTexto = (v) => (v === null || v === undefined ? "—" : v > 0 ? `+${inteiro(v)}` : inteiro(v));
  const lacunaClasse = (v) => (v > 0 ? "sim__lacuna--espaco" : v < 0 ? "sim__lacuna--saturada" : "");

  function desenharResumo(regiao) {
    const c = estado.porId.get(centro);
    const ranq = regiao.ranqueadas.map((i) => todas[i]);
    const todasNoRaio = regiao.noRaio.map((i) => todas[i]);
    const melhor = ranq[0];
    const somaLacuna = d3.sum(todasNoRaio, (m) => (m.lacuna_academias > 0 ? m.lacuna_academias : 0));
    const pop = d3.sum(todasNoRaio, (m) => m.populacao ?? 0);
    const popProj = d3.sum(todasNoRaio, (m) => m.populacao_projetada ?? m.populacao ?? 0);
    const recomendadas = ranq.filter((m) => m.ranking.recomendado_top5).map((m) => m.municipio_nome);
    el("sim-resumo").innerHTML = `
      <p class="sim__frase">${ranq.length ? `<b>${inteiro(ranq.length)}</b> ${ranq.length === 1 ? "cidade do ranking" : "cidades do ranking"} num raio de <b>${raio} km</b> de ${c.municipio_nome} (${c.uf_sigla}). A melhor é <b>${melhor.municipio_nome}</b>, ${melhor.ranking.posicao_brasil}ª no Brasil, nota ${decimal(melhor.ranking.nota_final, 1)}.` : `Nenhuma cidade do ranking num raio de ${raio} km de ${c.municipio_nome} (${c.uf_sigla}).`}
      ${recomendadas.length ? ` Recomendadas no raio: ${recomendadas.join(", ")}.` : ""}</p>
      <dl class="sim__numeros">
        <div><dt>Municípios no raio</dt><dd>${inteiro(regiao.noRaio.length)}</dd></div>
        <div><dt>População</dt><dd>${compacto(pop)}</dd></div>
        <div><dt>Projetada ${anoProjecao}*</dt><dd>${compacto(popProj)}</dd></div>
        <div><dt>Lacuna de academias*</dt><dd>+${inteiro(somaLacuna)}</dd></div>
      </dl>`;
    el("sim-aviso").textContent = `* Estimativas simples, não são previsão garantida. População ${anoProjecao}: população atual × (1 + crescimento anual desde o Censo 2022) até ${anoProjecao}. ` +
      `Lacuna: (densidade de referência − densidade atual) × população ÷ 10 mil, em que a referência é a mediana de academias por 10 mil hab. das cidades da mesma faixa de renda (${faixas} faixas). ` +
      `A soma considera só lacunas positivas de todos os municípios do raio, inclusive os menores que 50 mil hab. Distância em linha reta entre os centros dos municípios.`;
  }

  // ------------------------------------------------------------ endereço compartilhável
  function atualizarEndereco() {
    const p = new URLSearchParams(location.search);
    p.set("centro", centro);
    p.set("raio", raio);
    history.replaceState(history.state, "", `?${p.toString()}${location.hash}`);
  }
  function lerEndereco() {
    const p = new URLSearchParams(location.search);
    const c = Number(p.get("centro"));
    const r = Number(p.get("raio"));
    if (c && estado.porId.get(c)?.latitude !== undefined) centro = c;
    if (r) raio = Math.min(RAIO_MAX, Math.max(RAIO_MIN, Math.round(r)));
    return !!c;
  }

  // ------------------------------------------------------------ controles
  const opcoes = el("sim-opcoes");
  opcoes.innerHTML = todas.map((m) => `<option value="${m.municipio_nome} (${m.uf_sigla})"></option>`).join("");
  const porTexto = new Map(todas.map((m) => [normalizar(`${m.municipio_nome} (${m.uf_sigla})`), m.municipio_id]));
  const nomeCentro = () => { const m = estado.porId.get(centro); return `${m.municipio_nome} (${m.uf_sigla})`; };
  campo.addEventListener("change", () => {
    const id = porTexto.get(normalizar(campo.value));
    if (id) { centro = id; aplicar(); }
    campo.value = nomeCentro();
  });
  controleRaio.min = RAIO_MIN; controleRaio.max = RAIO_MAX; controleRaio.step = 10;
  controleRaio.addEventListener("input", () => { raio = Number(controleRaio.value); saidaRaio.textContent = `${raio} km`; aplicar({ animar: false }); });
  controleRaio.addEventListener("change", () => aplicar());
  incluirPequenas.addEventListener("change", () => aplicar());
  el("sim-copiar").addEventListener("click", async (e) => {
    const b = e.currentTarget;
    try { await navigator.clipboard.writeText(location.href); b.textContent = "Link copiado"; } catch { b.textContent = "Copie o endereço da barra"; }
    setTimeout(() => { b.textContent = "Copiar link da simulação"; }, 2500);
  });
  abas.addEventListener("click", (e) => {
    const b = e.target.closest("[role=tab]");
    if (!b) return;
    vista = b.dataset.vista;
    for (const x of abas.querySelectorAll("[role=tab]")) { x.setAttribute("aria-selected", x === b); x.tabIndex = x === b ? 0 : -1; }
    aplicar();
  });
  abas.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const outro = abas.querySelector(`[role=tab]:not([aria-selected="true"])`);
    outro.click(); outro.focus();
  });
  el("sim-lista").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-id]");
    if (b) aoSelecionar(Number(b.dataset.id));
  });

  // ponteiro: tooltip único e clique abre a ficha
  function pontoEm(px, py) {
    let melhor = -1, dist = Infinity;
    for (let i = 0; i < n; i++) {
      if (atual.a[i] < 0.5) continue;
      const d = Math.hypot(px - atual.x[i], py - atual.y[i]) - atual.r[i];
      if (d < dist) { dist = d; melhor = i; }
    }
    return dist <= 6 ? melhor : -1;
  }
  canvas.addEventListener("pointermove", (e) => {
    const caixa = canvas.getBoundingClientRect();
    const i = pontoEm(e.clientX - caixa.left, e.clientY - caixa.top);
    if (i !== sobMouse) { sobMouse = i; if (!quadro) desenhar(); }
    canvas.style.cursor = i >= 0 ? "pointer" : "default";
    if (i < 0) { esconderDica(); return; }
    const m = todas[i];
    mostrarDica({ left: caixa.left + atual.x[i] - atual.r[i], right: caixa.left + atual.x[i] + atual.r[i], top: caixa.top + atual.y[i] - atual.r[i],
      bottom: caixa.top + atual.y[i] + atual.r[i], width: atual.r[i] * 2, height: atual.r[i] * 2 }, conteudoDica({
      titulo: `${m.municipio_nome} · ${m.uf_sigla}`,
      chip: m.ranking?.recomendado_top5 ? { texto: `Recomendada nº ${m.ranking.ordem_recomendacao}`, estado: "verde" } : (m.ranking ? null : { texto: "sem nota" }),
      linhas: [
        m.ranking ? { rotulo: "Nota final", valor: decimal(m.ranking.nota_final, 1), detalhe: `${m.ranking.posicao_brasil}º no Brasil` } : null,
        { rotulo: "Distância", valor: `${inteiro(Math.round(distancia[i]))} km`, detalhe: "linha reta" },
        { rotulo: "Lacuna de academias*", valor: lacunaTexto(m.lacuna_academias), detalhe: "estimativa" },
        { rotulo: "População", valor: compacto(m.populacao), detalhe: `${compacto(m.populacao_projetada)} em ${anoProjecao}*` },
      ].filter(Boolean),
      nota: "Clique para abrir a ficha. * estimativa simples.",
    }));
  });
  canvas.addEventListener("pointerleave", () => { sobMouse = -1; esconderDica(); if (!quadro) desenhar(); });
  canvas.addEventListener("click", (e) => {
    const caixa = canvas.getBoundingClientRect();
    const i = pontoEm(e.clientX - caixa.left, e.clientY - caixa.top);
    if (i >= 0) { esconderDica(); aoSelecionar(todas[i].municipio_id); }
  });

  function dimensionar() {
    const caixa = palco.getBoundingClientRect();
    largura = Math.round(caixa.width); altura = Math.round(caixa.height);
    if (!largura || !altura) return;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = largura * dpr; canvas.height = altura * dpr;
    lerCores();
    aplicar({ animar: false });
  }

  const veioDoEndereco = lerEndereco();
  campo.value = nomeCentro();
  controleRaio.value = raio;
  saidaRaio.textContent = `${raio} km`;
  let espera;
  new ResizeObserver(() => { clearTimeout(espera); espera = setTimeout(dimensionar, 120); }).observe(palco);
  document.addEventListener("tema-alterado", () => { lerCores(); desenhar(); });
  dimensionar();
  return { veioDoEndereco };
}
