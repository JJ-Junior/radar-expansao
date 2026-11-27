// Simule sua região (prd P9): uma cidade central e um raio em km.
// Mostra as cidades do ranking dentro do raio (posição no raio e no Brasil, nota, distância, lacuna de academias),
// num mapa com zoom e círculo; a vista "Ranking local" rearranja os mesmos pontos numa fila pela nota (850 ms).
// Distância em linha reta entre centroides (haversine, spec 9.4). Endereço: ?centro=<código IBGE>&raio=<km>.
// Com a malha municipal do IBGE (dados/malha/municipios/<UF>.topo.json, só as UFs que o mapa mostra), cada município
// vira um polígono pintado pela nota; sem ela (ou enquanto carrega) ficam os pontos nos centroides.

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
const PASTA_MALHA = "dados/malha/municipios";
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

  // malha municipal: carregada por UF, sob demanda, e guardada (null = não carregou: fica o ponto)
  const caixasUf = ufs.features.map((f) => ({ cod: Number(f.properties?.codarea ?? f.id), caixa: d3.geoBounds(f) }));
  const malhaUf = new Map();                        // código da UF -> Map(municipio_id -> { f, caixa })
  const pedidos = new Map();
  let quadroGeo = null;                             // o que o mapa mostra, em longitude/latitude
  let caminhos = new Map();                         // índice -> Path2D do município, na projeção atual
  let caixasPx = new Map();                         // índice -> [x0, y0, x1, y1] (para achar o município sob o ponteiro)
  let divisasMun = null;                            // todas as divisas municipais num caminho só
  let malhaAtual = 0, malhaDe = 0, malhaPara = 0;   // opacidade da malha (anima junto com os pontos)
  let chaveQuadro = "";
  let recarga = false;

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
      linha: cor("--linha-forte"), divisa: cor("--mapa-divisa-fina"), divisaForte: cor("--mapa-divisa"),
      fonte: `600 12px ${cor("--mono") || "monospace"}` });
  }
  const corDe = (m) => (m.ranking ? paleta[CORES[d3.bisectRight(LIMIARES, m.ranking.nota_final)]] : paleta.tinta3);

  const tocaQuadro = (c) => c[0][0] <= quadroGeo.leste && c[1][0] >= quadroGeo.oeste && c[0][1] <= quadroGeo.norte && c[1][1] >= quadroGeo.sul;

  function carregarUf(cod) {
    if (!pedidos.has(cod)) {
      pedidos.set(cod, fetch(`${PASTA_MALHA}/${String(cod).padStart(2, "0")}.topo.json`)
        .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
        .then((topo) => {
          const mapa = new Map();
          for (const f of feicoes(topo).features) mapa.set(Number(f.id), { f, caixa: d3.geoBounds(f) });
          malhaUf.set(cod, mapa);
        })
        .catch(() => malhaUf.set(cod, null)));       // sem a malha da UF, os pontos continuam
    }
    return pedidos.get(cod);
  }

  /** Monta os polígonos dos municípios que aparecem no quadro; se faltar alguma UF, pede e redesenha quando chegar. */
  function montarMalha() {
    const necessarias = caixasUf.filter((u) => tocaQuadro(u.caixa)).map((u) => u.cod);
    const faltam = necessarias.filter((c) => !malhaUf.has(c));
    caminhos = new Map(); caixasPx = new Map(); divisasMun = null;
    if (faltam.length) {
      Promise.all(faltam.map(carregarUf)).then(() => {
        if (recarga) return;
        recarga = true;
        requestAnimationFrame(() => { recarga = false; if (vista === "mapa") aplicar(); });
      });
      return;
    }
    const gerador = d3.geoPath(projecao);
    divisasMun = new Path2D();
    for (const cod of necessarias) {
      const mapa = malhaUf.get(cod);
      if (!mapa) continue;
      for (const [id, { f, caixa }] of mapa) {
        if (!tocaQuadro(caixa)) continue;
        const i = indicePorId.get(id);
        if (i === undefined) continue;
        const d = gerador(f);
        if (!d) continue;
        const caminho = new Path2D(d);
        caminhos.set(i, caminho);
        divisasMun.addPath(caminho);
        const [x0, y1] = projecao(caixa[0]), [x1, y0] = projecao(caixa[1]);
        caixasPx.set(i, [x0, y0, x1, y1]);
      }
    }
  }

  function layoutMapa(regiao, { malha = true } = {}) {
    const c = estado.porId.get(centro);
    const circulo = d3.geoCircle().center([c.longitude, c.latitude]).radius(raio / 111.195)();
    // enquadra um pouco além do raio, para as cidades de fora aparecerem esmaecidas em volta
    const moldura = d3.geoCircle().center([c.longitude, c.latitude]).radius((raio * MOLDURA) / 111.195)();
    projecao = d3.geoMercator().fitExtent([[16, 16], [largura - 16, altura - 16]], moldura);
    caminhoCanvas = d3.geoPath(projecao, ctx);
    circuloGeo = circulo;
    const [oeste, norte] = projecao.invert([0, 0]), [leste, sul] = projecao.invert([largura, altura]);
    quadroGeo = { oeste, norte, leste, sul };
    if (malha) montarMalha();
    const zoom = Math.max(1, Math.min(6, 300 / raio));
    const raioPop = d3.scaleSqrt().domain([0, 2e6]).range([0, 7 * Math.sqrt(zoom)]).clamp(true);
    const p = { x: new Float32Array(n), y: new Float32Array(n), r: new Float32Array(n), a: new Float32Array(n) };
    const mostrarPequenas = incluirPequenas.checked;
    for (let i = 0; i < n; i++) {
      const m = todas[i];
      [p.x[i], p.y[i]] = projecao([m.longitude, m.latitude]);
      p.r[i] = Math.max(m.ranking ? 2.5 : 1.6, raioPop(m.populacao ?? 0));
      const visivel = (m.ranking || mostrarPequenas) && !caminhos.has(i);   // com polígono, o ponto dá lugar a ele
      p.a[i] = !visivel ? 0 : distancia[i] <= raio ? 1 : 0.18;
    }
    return p;
  }

  function layoutRanking(regiao) {
    const p = layoutMapa(regiao, { malha: false });
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
    // municípios pintados pela nota: no raio, cheios; fora, esmaecidos; < 50 mil em cinza se a opção estiver ligada
    const comMalha = malhaAtual > 0.01 && caminhos.size > 0;
    if (comMalha) {
      const pequenas = incluirPequenas.checked;
      for (const [i, caminho] of caminhos) {
        const m = todas[i], noRaio = distancia[i] <= raio;
        let preenche = null, a = 0;
        if (m.ranking) { preenche = corDe(m); a = noRaio ? 0.92 : 0.16; }
        else if (pequenas) { preenche = paleta.tinta3; a = noRaio ? 0.32 : 0.08; }
        if (!preenche) continue;
        ctx.globalAlpha = a * malhaAtual; ctx.fillStyle = preenche; ctx.fill(caminho);
      }
      ctx.globalAlpha = malhaAtual; ctx.lineWidth = 0.6; ctx.strokeStyle = paleta.divisa; ctx.stroke(divisasMun);
    }
    // fundo do mapa (some na vista de ranking)
    ctx.globalAlpha = vista === "mapa" ? 1 : 0.12;
    ctx.lineWidth = 1; ctx.strokeStyle = comMalha ? paleta.divisaForte : paleta.divisa; ctx.beginPath(); caminhoCanvas(divisas); ctx.stroke();
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
    // com a malha, o destaque é o contorno do município; sem ela, um anel em volta do ponto
    const anel = (i, corAnel, rotulo, espessura = 2.5) => {
      const caminho = vista === "mapa" && malhaAtual > 0.5 ? caminhos.get(i) : null;
      ctx.lineWidth = espessura; ctx.strokeStyle = corAnel; ctx.globalAlpha = 1;
      if (caminho) ctx.stroke(caminho);
      else { ctx.beginPath(); ctx.arc(atual.x[i], atual.y[i], atual.r[i] + 3, 0, Math.PI * 2); ctx.stroke(); }
      if (rotulo) pendentes.push([i, rotulo, !!caminho]);
    };
    // rótulos depois de todos os contornos, para nenhum contorno passar por cima de um nome
    const pendentes = [];
    const escrever = ([i, rotulo, comCaminho]) => {
      const w = ctx.measureText(rotulo).width, h = 14, x = atual.x[i], y = atual.y[i], d = comCaminho ? 6 : atual.r[i] + 8;
      const lugar = [{ x: x + d, y: y - h / 2 }, { x: x - d - w, y: y - h / 2 }, { x: x - w / 2, y: y - d - h }, { x: x - w / 2, y: y + d }]
        .map((c) => ({ ...c, w, h })).find(cabe);
      if (!lugar) return;
      ocupados.push({ x: lugar.x - 3, y: lugar.y - 3, w: lugar.w + 6, h: lugar.h + 6 });   // folga para o halo do texto
      ctx.lineJoin = "round";
      ctx.lineWidth = 4; ctx.strokeStyle = paleta.halo; ctx.strokeText(rotulo, lugar.x, lugar.y + 11);
      ctx.fillStyle = paleta.tinta; ctx.fillText(rotulo, lugar.x, lugar.y + 11);
    };
    if (vista === "mapa") {
      const ic = indicePorId.get(centro);
      // o rótulo do centro tem prioridade; o contorno dele é desenhado por último, por cima dos vizinhos
      if (ic !== undefined) anel(ic, paleta.tinta, `CENTRO: ${todas[ic].municipio_nome.toUpperCase()}`, 3);
      dentroRanqueadas.slice(0, ROTULOS_MAPA).forEach((i, k) => {
        if (i !== ic) anel(i, paleta.limao, `${k + 1}. ${todas[i].municipio_nome.toUpperCase()}`);
      });
      if (ic !== undefined && caminhos.has(ic) && malhaAtual > 0.5) {
        anel(ic, paleta.halo, null, 6);               // halo escuro/claro por baixo: o contorno aparece sobre qualquer cor
        anel(ic, paleta.tinta, null, 2.5);
        ctx.fillStyle = paleta.tinta; ctx.beginPath(); ctx.arc(atual.x[ic], atual.y[ic], 3.5, 0, Math.PI * 2); ctx.fill();
      }
      pendentes.forEach(escrever);
    }
    if (sobMouse >= 0) anel(sobMouse, paleta.tinta, null, 2);
  }

  function passo(agora) {
    const t = Math.min(1, (agora - inicio) / DURACAO);
    const e = facilitar(t);
    for (const k of ["x", "y", "r", "a"]) {
      const de = origem[k], para = alvo[k], at = atual[k];
      for (let i = 0; i < n; i++) at[i] = de[i] + (para[i] - de[i]) * e;
    }
    malhaAtual = malhaDe + (malhaPara - malhaDe) * e;
    desenhar();
    quadro = t < 1 ? requestAnimationFrame(passo) : null;
  }

  let dentroRanqueadas = [];
  function aplicar({ animar = true } = {}) {
    const regiao = calcular();
    dentro = [...regiao.ranqueadas, ...regiao.pequenas];
    dentroRanqueadas = regiao.ranqueadas;
    alvo = vista === "mapa" ? layoutMapa(regiao) : layoutRanking(regiao);
    // a malha some no ranking e, quando o quadro muda (outro centro ou raio), reaparece já na posição nova
    const chave = `${centro}|${raio}|${largura}|${altura}`;
    malhaPara = vista === "mapa" && caminhos.size ? 1 : 0;
    malhaDe = chave !== chaveQuadro ? 0 : malhaAtual;
    chaveQuadro = chave;
    if (quadro) cancelAnimationFrame(quadro);
    if (!animar || prefereMenos.matches) {
      malhaAtual = malhaPara;
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
    desenharLegenda();
    if (compartilhar) atualizarEndereco();
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

  function desenharLegenda() {
    const alvoLegenda = el("sim-legenda");
    if (!alvoLegenda) return;
    alvoLegenda.innerHTML = `Nota final
      <div class="escala">${CORES.map((c) => `<i style="background:var(${c})"></i>`).join("")}</div>
      <div style="display:flex;justify-content:space-between"><span>&lt; ${LIMIARES[0]}</span><span>${LIMIARES.at(-1)}+</span></div>
      ${incluirPequenas.checked ? `<div style="margin-top:8px"><span class="ponto ponto--cinza"></span>menos de 50 mil hab. (sem nota)</div>` : ""}
      <div style="margin-top:4px"><span class="ponto ponto--anel"></span>as ${ROTULOS_MAPA} melhores do raio</div>`;
  }

  // ------------------------------------------------------------ endereço compartilhável
  // o endereço só ganha ?centro=&raio= quando a simulação é do usuário (mexeu nos controles ou abriu um link)
  let compartilhar = false;
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
    if (id) { centro = id; compartilhar = true; aplicar(); }
    campo.value = nomeCentro();
  });
  controleRaio.min = RAIO_MIN; controleRaio.max = RAIO_MAX; controleRaio.step = 10;
  let quadroRaio = null;
  controleRaio.addEventListener("input", () => {
    compartilhar = true; raio = Number(controleRaio.value); saidaRaio.textContent = `${raio} km`;
    if (!quadroRaio) quadroRaio = requestAnimationFrame(() => { quadroRaio = null; aplicar({ animar: false }); });
  });
  controleRaio.addEventListener("change", () => aplicar());
  incluirPequenas.addEventListener("change", () => aplicar());
  el("sim-copiar").addEventListener("click", async (e) => {
    const b = e.currentTarget;
    compartilhar = true; atualizarEndereco();
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
  function municipioEm(px, py) {
    if (vista !== "mapa" || malhaAtual < 0.5) return -1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    let achou = -1;
    for (const [i, [x0, y0, x1, y1]] of caixasPx) {
      if (px < x0 || px > x1 || py < y0 || py > y1) continue;
      if (ctx.isPointInPath(caminhos.get(i), px * dpr, py * dpr)) { achou = i; if (distancia[i] <= raio) break; }
    }
    return achou;
  }
  function alvoEm(px, py) {
    const i = pontoEm(px, py);
    return i >= 0 ? i : municipioEm(px, py);
  }
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
    const i = alvoEm(e.clientX - caixa.left, e.clientY - caixa.top);
    if (i !== sobMouse) { sobMouse = i; if (!quadro) desenhar(); }
    canvas.style.cursor = i >= 0 ? "pointer" : "default";
    if (i < 0) { esconderDica(); return; }
    const m = todas[i];
    const ancora = atual.a[i] >= 0.5
      ? { left: caixa.left + atual.x[i] - atual.r[i], right: caixa.left + atual.x[i] + atual.r[i], top: caixa.top + atual.y[i] - atual.r[i],
        bottom: caixa.top + atual.y[i] + atual.r[i], width: atual.r[i] * 2, height: atual.r[i] * 2 }
      : e;                                           // polígono: a dica segue o ponteiro
    mostrarDica(ancora, conteudoDica({
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
    const i = alvoEm(e.clientX - caixa.left, e.clientY - caixa.top);
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
  compartilhar = veioDoEndereco;
  campo.value = nomeCentro();
  controleRaio.value = raio;
  saidaRaio.textContent = `${raio} km`;
  let espera;
  new ResizeObserver(() => { clearTimeout(espera); espera = setTimeout(dimensionar, 120); }).observe(palco);
  document.addEventListener("tema-alterado", () => { lerCores(); desenhar(); });
  dimensionar();
  return { veioDoEndereco };
}
