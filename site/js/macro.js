// Quando: o semáforo de hoje (gold.momento_atual: câmbio e juros pela janela móvel até o último fechamento,
// inflação pelo último IPCA), os três sinais como cards de dado com a data de cada um,
// a recomendação mês a mês e as três séries.
// Cada série tem o próprio gráfico (escalas diferentes não dividem eixo); a mira é sincronizada
// e o tooltip é o componente único do site (dica.js).

import { ROTULO_SINAL, STATUS_RECOMENDACAO } from "./indicadores.js";
import { dataCurta, decimal, mesCurto, mesPorExtenso, paraData, porcento, reaisCentavos } from "./formato.js";
import { movimentoLigado } from "./movimento.js";
import { conteudoDica, esconderDica, mostrarDica } from "./dica.js";

const MESES_SPARKLINE = 24;
const COR_STATUS = { verde: "var(--verde)", amarelo: "var(--amarelo)", vermelho: "var(--vermelho)" };

/** Seta + valor absoluto: ▲ subiu, ▼ caiu, = estável. */
function variacao(v, formatar) {
  if (v === null || v === undefined || Number.isNaN(v)) return null;
  const seta = v > 0.0001 ? "▲" : v < -0.0001 ? "▼" : "=";
  return `${seta} ${formatar(Math.abs(v))}`;
}

/** "2026-11-26" -> "26/11". */
const diaMesIso = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}` : "—");

/** Os três sinais do semáforo e como mostrar cada um: no mês (contexto_macro) e hoje (momento_atual). */
const SINAIS = [
  {
    chave: "sinal_juros", nome: "Juros", indicador: "Meta da Selic", coluna: "selic_meta",
    valor: (l) => `${decimal(l.selic_meta, 2)}% a.a.`,
    variacao: (l) => variacao(l.selic_var_12m_pp, (v) => `${decimal(v, 2)} p.p.`),
    periodo: "em 12 meses",
    hoje: {
      indicador: (a) => `Meta da Selic · em ${diaMesIso(a.ref_juros)}`,
      valor: (a) => `${decimal(a.selic_meta, 2)}% a.a.`,
      variacao: (a) => variacao(a.selic_var_12m_pp, (v) => `${decimal(v, 2)} p.p.`),
    },
  },
  {
    chave: "sinal_inflacao", nome: "Inflação", indicador: "IPCA acumulado em 12 meses", coluna: "ipca_12m",
    valor: (l) => porcento(l.ipca_12m, 2),
    variacao: (l, antes) => variacao(antes ? l.ipca_12m - antes.ipca_12m : null, (v) => `${decimal(v, 2)} p.p.`),
    periodo: "vs. 3 meses antes", referencia: 4.5,
    hoje: {
      indicador: (a) => `IPCA em 12 meses · até ${mesCurto(paraData(a.ref_inflacao))}`,
      valor: (a) => porcento(a.ipca_12m, 2),
      variacao: (a) => variacao(a.ipca_12m - a.ipca_12m_meses_antes, (v) => `${decimal(v, 2)} p.p.`),
    },
  },
  {
    chave: "sinal_cambio", nome: "Câmbio", indicador: "Dólar, média do mês", coluna: "dolar_medio",
    valor: (l) => reaisCentavos(l.dolar_medio, 2),
    variacao: (l) => variacao(l.dolar_var_12m_pct, (v) => `${decimal(v, 1)}%`),
    periodo: "em 12 meses",
    hoje: {
      indicador: (a) => `Dólar, média de ${a.janela_dias} dias · até ${diaMesIso(a.ref_cambio)}`,
      valor: (a) => reaisCentavos(a.dolar_media_janela, 2),
      variacao: (a) => variacao(a.dolar_var_12m_pct, (v) => `${decimal(v, 1)}%`),
      extra: (a) => `último fechamento ${diaMesIso(a.ref_cambio)}: ${reaisCentavos(a.dolar_ultimo, 2)} · ` +
        `${variacao(a.dolar_var_janela_pct, (v) => `${decimal(v, 1)}%`)} sobre os ${a.janela_dias} dias anteriores` +
        (a.alerta_cambio_curto_prazo ? " (alerta de alta)" : ""),
    },
  },
];

export function criarMacro({ estado }) {
  const d3 = window.d3;
  const momento = estado.momento.map((l) => ({ ...l, data: paraData(l.mes) }));
  const macro = estado.macro.map((l) => ({ ...l, data: paraData(l.mes) }));
  const indiceMacro = new Map(macro.map((l, i) => [l.mes, i]));
  const momentoPorMes = new Map(momento.map((l) => [l.mes, l]));
  const agora = estado.agora ? { ...estado.agora, data: paraData(estado.agora.mes) } : null;
  const atual = agora ?? momento.at(-1);                          // o semáforo exibido
  const linhaAtual = atual ? macro[indiceMacro.get(atual.mes)] : null;
  const tresAntes = (l) => macro[(indiceMacro.get(l.mes) ?? 0) - 3] ?? null;

  // mês corrente (parcial): médias só até o último fechamento; o semáforo de hoje usa a janela móvel
  const parcial = macro.find((l) => l.mes_parcial) ?? null;
  const ultimoDia = agora?.ref_cambio ?? parcial?.dolar_ultimo_data ?? null;
  const textoFechamento = {
    selic_meta: parcial?.selic_ultima_data ? `meta em ${diaMesIso(parcial.selic_ultima_data)}: ${decimal(parcial.selic_meta, 2)}% a.a.` : "",
    dolar_medio: parcial?.dolar_ultimo ? `último fechamento ${diaMesIso(parcial.dolar_ultimo_data)}: ${reaisCentavos(parcial.dolar_ultimo, 2)}` : "",
  };
  const mesAno = (d) => `${mesCurto(d).slice(0, 3)}/${d.getFullYear()}`;          // "nov/2026"
  const janelaHoje = agora ? `semáforo: média de ${agora.janela_dias} dias até ${diaMesIso(agora.ref_cambio)}: ${reaisCentavos(agora.dolar_media_janela, 2)}` : "";
  const rotuloParcial = (l) => `${mesPorExtenso(l.data)} (parcial${ultimoDia ? `, até ${diaMesIso(ultimoDia)}` : ""})`;
  const datasHoje = agora
    ? `dólar e Selic até ${diaMesIso(agora.ref_cambio)}, IPCA até ${mesCurto(paraData(agora.ref_inflacao))}`
    : atual ? `referência ${mesCurto(atual.data)}` : "";

  /** Linhas do tooltip de um mês: Juros · Inflação · Câmbio → valor, variação, estado. */
  function conteudoDoMes(linha) {
    const m = momentoPorMes.get(linha.mes);
    const linhas = SINAIS.filter((s) => linha[s.coluna] !== null).map((s) => {
      const est = m?.[s.chave];
      return {
        rotulo: s.nome, valor: s.valor(linha), detalhe: s.variacao(linha, tresAntes(linha)) ?? "",
        estado: est, estadoTexto: est ? ROTULO_SINAL[est] : "",
      };
    });
    const nota = linha.mes_parcial
      ? `Média do mês até ${ultimoDia ? diaMesIso(ultimoDia) : "hoje"}. ${[textoFechamento.dolar_medio, textoFechamento.selic_meta].filter(Boolean).join(" · ")}. ` +
        (agora ? `Semáforo de hoje: câmbio pela média de ${agora.janela_dias} dias até ${diaMesIso(agora.ref_cambio)}, juros pela meta de ${diaMesIso(agora.ref_juros)} e inflação pelo IPCA de ${mesCurto(paraData(agora.ref_inflacao))}.` : "")
      : "Variação: juros e câmbio em 12 meses; inflação contra 3 meses antes.";
    return conteudoDica({
      titulo: linha.mes_parcial ? rotuloParcial(linha) : mesPorExtenso(linha.data),
      chip: m ? { texto: m.recomendacao, estado: STATUS_RECOMENDACAO[m.recomendacao] } : null,
      linhas,
      nota,
    });
  }

  // ------------------------------------------------------------ recomendação do mês
  if (atual && linhaAtual) {
    const status = STATUS_RECOMENDACAO[atual.recomendacao];
    const estados = SINAIS.map((s) => atual[s.chave]);
    const conta = (e) => estados.filter((x) => x === e).length;
    const partes = [`${conta("verde")} de ${SINAIS.length} sinais favoráveis`];
    if (conta("vermelho")) partes.push(`${conta("vermelho")} ${conta("vermelho") > 1 ? "desfavoráveis" : "desfavorável"}`);
    if (datasHoje) partes.push(datasHoje);

    document.querySelector(".semaforo__principal").style.setProperty("--status", COR_STATUS[status]);
    document.getElementById("semaforo-mes").textContent = agora ? `Momento econômico · ${dataCurta(agora.ref_cambio)}` : "Momento econômico";
    document.getElementById("semaforo-recomendacao").textContent = atual.recomendacao;
    document.getElementById("semaforo-contexto").textContent = partes.join(" · ");

    // os três sinais como cards de dado
    const lista = document.getElementById("semaforo-sinais");
    lista.replaceChildren();
    const fim = indiceMacro.get(atual.mes);
    const linhaIpca = [...macro].reverse().find((l) => l.ipca_12m !== null);   // o IPCA sai com ~1 mês de atraso
    for (const s of SINAIS) {
      const est = atual[s.chave];
      const li = document.createElement("li");
      li.className = `sinal sinal--${est}`;
      li.setAttribute("data-revela", "");
      li.innerHTML = `
        <div class="sinal__topo"><span class="sinal__rotulo"></span><span class="sinal__estado"><i class="ponto-estado ponto-estado--${est}"></i><span></span></span></div>
        <p class="sinal__indicador"></p>
        <p class="sinal__valor"></p>
        <p class="sinal__variacao"></p>`;
      li.querySelector(".sinal__rotulo").textContent = s.nome;
      li.querySelector(".sinal__estado span").textContent = ROTULO_SINAL[est];
      // hoje (momento_atual) com a data de cada sinal; sem ele, a linha mensal do mês de referência
      const base = s.coluna === "ipca_12m" ? linhaIpca : linhaAtual;
      li.querySelector(".sinal__indicador").textContent = agora ? s.hoje.indicador(agora) : `${s.indicador} · ${mesCurto(atual.data)}`;
      li.querySelector(".sinal__valor").textContent = agora ? s.hoje.valor(agora) : s.valor(base);
      const v = agora ? s.hoje.variacao(agora) : s.variacao(base, tresAntes(base));
      li.querySelector(".sinal__variacao").textContent = v ? `${v} ${s.periodo}` : "";
      if (agora && s.hoje.extra) {
        const extra = document.createElement("p");
        extra.className = "sinal__fechamento";
        extra.textContent = s.hoje.extra(agora);
        li.querySelector(".sinal__variacao").after(extra);
      }
      // a série mensal vai até o último mês com dado (o câmbio e a Selic incluem o mês corrente, parcial)
      li.append(sparkline(macro.slice(Math.max(0, fim - MESES_SPARKLINE + 1), fim + 1), s));
      lista.append(li);
    }
  }

  /** Mini linha dos últimos meses de um indicador (SVG), com o último ponto marcado. */
  function sparkline(trecho, s) {
    const L = 240, A = 44, m = 4;
    const pontos = trecho.filter((l) => l[s.coluna] !== null);
    const x = d3.scaleLinear().domain([0, pontos.length - 1]).range([m, L - m]);
    const dominio = d3.extent(pontos, (l) => l[s.coluna]);
    if (s.referencia) { dominio[0] = Math.min(dominio[0], s.referencia); dominio[1] = Math.max(dominio[1], s.referencia); }
    const y = d3.scaleLinear().domain(dominio).range([A - m, m]);
    const svg = d3.create("svg").attr("class", "sparkline").attr("viewBox", `0 0 ${L} ${A}`).attr("preserveAspectRatio", "none")
      .attr("role", "img").attr("aria-label", `${s.indicador}, últimos ${pontos.length} meses`);
    if (s.referencia) {
      svg.append("line").attr("class", "sparkline__referencia").attr("x1", 0).attr("x2", L).attr("y1", y(s.referencia)).attr("y2", y(s.referencia));
    }
    svg.append("path").attr("class", "sparkline__linha").attr("d", d3.line().x((_, i) => x(i)).y((l) => y(l[s.coluna]))(pontos));
    const ultimo = pontos.at(-1);
    svg.append("circle").attr("class", "sparkline__ponto").attr("r", 3).attr("cx", x(pontos.length - 1)).attr("cy", y(ultimo[s.coluna]));
    const rotulo = document.createElement("p");
    rotulo.className = "sparkline__eixo";
    rotulo.textContent = `${mesCurto(pontos[0].data)} → ${mesCurto(ultimo.data)}${ultimo.mes_parcial ? " (parcial)" : ""}`;
    const caixa = document.createElement("div");
    caixa.className = "sinal__grafico";
    caixa.append(svg.node(), rotulo);
    return caixa;
  }

  // ------------------------------------------------------------ recomendação mês a mês
  const historico = document.getElementById("historico-momento");
  historico.innerHTML = momento.map((l, i) =>
    `<span class="historico__mes" data-i="${i}" style="background:${COR_STATUS[STATUS_RECOMENDACAO[l.recomendacao]]}"></span>`).join("");
  momento.forEach((l, i) => {
    if (l.data.getMonth() === 0 || i === 0) {
      historico.insertAdjacentHTML("beforeend", `<span class="historico__ano" style="left:${(i / momento.length) * 100}%">${l.data.getFullYear()}</span>`);
    }
  });
  const contagem = d3.rollup(momento, (v) => v.length, (l) => l.recomendacao);
  historico.setAttribute("tabindex", "0");
  historico.setAttribute("role", "group");
  if (momento.length) {
    historico.setAttribute("aria-label", `Recomendação mês a mês, de ${mesPorExtenso(momento[0].data)} a ${mesPorExtenso(atual.data)}. ` +
      `Use as setas para percorrer os meses. ` + Object.keys(STATUS_RECOMENDACAO).map((r) => `${r}: ${contagem.get(r) ?? 0} meses`).join("; "));
  }
  const celulas = [...historico.querySelectorAll(".historico__mes")];
  let ativo = celulas.length - 1;
  function marcar(i) {
    celulas[ativo]?.classList.remove("ativo");
    ativo = Math.max(0, Math.min(celulas.length - 1, i));
    const cel = celulas[ativo];
    cel.classList.add("ativo");
    const linha = macro[indiceMacro.get(momento[ativo].mes)];
    if (linha) mostrarDica(cel, conteudoDoMes(linha), { alvo: historico });
  }
  historico.addEventListener("pointermove", (e) => {
    const cel = e.target.closest(".historico__mes");
    if (cel) marcar(Number(cel.dataset.i));
  });
  historico.addEventListener("pointerleave", (e) => { if (e.pointerType !== "touch") { celulas[ativo]?.classList.remove("ativo"); esconderDica(); } });
  historico.addEventListener("focus", () => marcar(ativo));
  historico.addEventListener("blur", () => { celulas[ativo]?.classList.remove("ativo"); esconderDica(); });
  historico.addEventListener("keydown", (e) => {
    const passos = { ArrowRight: 1, ArrowLeft: -1, ArrowUp: 12, ArrowDown: -12 };
    if (e.key in passos) { e.preventDefault(); marcar(ativo + passos[e.key]); }
    if (e.key === "Home") { e.preventDefault(); marcar(0); }
    if (e.key === "End") { e.preventDefault(); marcar(celulas.length - 1); }
  });

  document.getElementById("historico-legenda").innerHTML = Object.entries(STATUS_RECOMENDACAO).map(([rec, st]) =>
    `<span><i class="amostra" style="background:${COR_STATUS[st]}"></i>${rec} <span class="discreto">${contagem.get(rec) ?? 0} meses</span></span>`).join("");

  // ------------------------------------------------------------ gráficos de linha
  const area = document.getElementById("graficos-macro");
  const L = 360, A = 170, m = { topo: 12, dir: 8, base: 22, esq: 34 };
  const x = d3.scaleTime().domain(d3.extent(macro, (l) => l.data)).range([m.esq, L - m.dir]);
  const graficos = [];
  const SERIES = [
    { coluna: "selic_meta", titulo: "Meta da Selic · % a.a.", formato: (v) => `${decimal(v, 2)}%`, sinal: SINAIS[0] },
    { coluna: "ipca_12m", titulo: "IPCA em 12 meses · %", formato: (v) => porcento(v, 2), referencia: { valor: 4.5, texto: "teto 4,5%" }, sinal: SINAIS[1] },
    { coluna: "dolar_medio", titulo: "Dólar · média do mês", formato: (v) => reaisCentavos(v, 2), sinal: SINAIS[2] },
  ];

  for (const serie of SERIES) {
    const pontos = macro.filter((l) => l[serie.coluna] !== null);
    if (!pontos.length) continue;
    const ultimo = pontos.at(-1);
    const extremo = d3.extent(pontos, (l) => l[serie.coluna]);
    if (serie.referencia) extremo[0] = Math.min(extremo[0], serie.referencia.valor);
    const y = d3.scaleLinear().domain(extremo).nice(4).range([A - m.base, m.topo]);

    const cartao = document.createElement("figure");
    cartao.className = "grafico";
    cartao.setAttribute("data-revela", "");
    cartao.innerHTML = `<h4></h4><p class="grafico__atual"></p><p class="grafico__var"></p>`;
    cartao.querySelector("h4").textContent = serie.titulo;
    cartao.querySelector(".grafico__atual").textContent = serie.formato(ultimo[serie.coluna]);
    const v = serie.sinal.variacao(ultimo, tresAntes(ultimo));
    cartao.querySelector(".grafico__var").textContent = ultimo.mes_parcial
      ? [`${serie.coluna === "dolar_medio" ? "média de " : ""}${mesAno(ultimo.data)} (parcial${ultimoDia ? `, até ${diaMesIso(ultimoDia)}` : ""})`,
        textoFechamento[serie.coluna], serie.coluna === "dolar_medio" ? janelaHoje : ""].filter(Boolean).join(" · ")
      : `${mesCurto(ultimo.data)}${v ? ` · ${v} ${serie.sinal.periodo}` : ""}`;
    area.appendChild(cartao);

    const svg = d3.select(cartao).append("svg").attr("viewBox", `0 0 ${L} ${A}`).attr("tabindex", "0")
      .attr("role", "img").attr("aria-label", `${serie.titulo} de ${mesCurto(pontos[0].data)} a ${mesCurto(ultimo.data)}; último valor ${serie.formato(ultimo[serie.coluna])}. Use as setas para percorrer os meses.`);
    svg.append("g").attr("class", "grade").selectAll("line").data(y.ticks(4)).join("line")
      .attr("x1", m.esq).attr("x2", L - m.dir).attr("y1", y).attr("y2", y);
    svg.append("g").attr("class", "eixo").attr("transform", `translate(0,${A - m.base})`)
      .call(d3.axisBottom(x).ticks(d3.timeYear.every(2)).tickFormat(d3.timeFormat("%Y")).tickSize(0).tickPadding(8));
    svg.append("g").attr("class", "eixo").attr("transform", `translate(${m.esq},0)`)
      .call(d3.axisLeft(y).ticks(4).tickSize(0).tickPadding(6).tickFormat((t) => decimal(t, t % 1 ? 1 : 0)));
    if (serie.referencia) {
      const yr = y(serie.referencia.valor);
      svg.append("line").attr("class", "referencia").attr("x1", m.esq).attr("x2", L - m.dir).attr("y1", yr).attr("y2", yr);
      svg.append("text").attr("class", "referencia-texto").attr("x", m.esq + 4).attr("y", yr - 4).text(serie.referencia.texto);
    }
    svg.append("path").datum(pontos).attr("class", "area")
      .attr("d", d3.area().x((l) => x(l.data)).y0(A - m.base).y1((l) => y(l[serie.coluna])));
    const linha = svg.append("path").datum(pontos).attr("class", "serie")
      .attr("d", d3.line().x((l) => x(l.data)).y((l) => y(l[serie.coluna])));
    const mira = svg.append("line").attr("class", "mira").attr("y1", m.topo).attr("y2", A - m.base).style("display", "none");
    const ponto = svg.append("circle").attr("class", "ponto").attr("r", 4.5).style("display", "none");
    const g = { serie, y, mira, ponto, svg, indice: macro.length - 1 };
    svg.append("rect").attr("x", m.esq).attr("y", 0).attr("width", L - m.esq - m.dir).attr("height", A).attr("fill", "transparent")
      .on("pointermove", (e) => mover(macro[d3.bisector((l) => l.data).center(macro, x.invert(d3.pointer(e)[0]))], g))
      .on("pointerleave", (e) => { if (e.pointerType !== "touch") mover(null); });
    svg.on("focus", () => mover(macro[g.indice], g)).on("blur", () => mover(null));
    svg.on("keydown", (e) => {
      const passos = { ArrowRight: 1, ArrowLeft: -1 };
      if (!(e.key in passos)) return;
      e.preventDefault();
      g.indice = Math.max(0, Math.min(macro.length - 1, g.indice + passos[e.key]));
      mover(macro[g.indice], g);
    });
    graficos.push(g);

    // a linha "se desenha" quando o gráfico entra na tela
    if (movimentoLigado()) {
      const comprimento = linha.node().getTotalLength();
      linha.attr("stroke-dasharray", comprimento).attr("stroke-dashoffset", comprimento);
      window.gsap.to(linha.node(), { strokeDashoffset: 0, duration: 1.8, ease: "power2.inOut",
        scrollTrigger: { trigger: cartao, start: "top 85%", once: true } });
    }
  }

  /** Mira sincronizada nos três gráficos; o tooltip aparece no gráfico sob o ponteiro (ou com foco). */
  function mover(linha, origem = null) {
    for (const g of graficos) {
      const v = linha?.[g.serie.coluna];
      const visivel = linha && v !== null && v !== undefined;
      g.mira.style("display", visivel ? null : "none");
      g.ponto.style("display", visivel ? null : "none");
      if (!visivel) continue;
      g.mira.attr("x1", x(linha.data)).attr("x2", x(linha.data));
      g.ponto.attr("cx", x(linha.data)).attr("cy", g.y(v));
    }
    if (!linha) { esconderDica(); return; }
    if (origem) {
      origem.indice = indiceMacro.get(linha.mes) ?? origem.indice;
      const alvo = linha[origem.serie.coluna] !== null ? origem.ponto.node() : origem.svg.node();
      mostrarDica(alvo, conteudoDoMes(linha), { alvo: origem.svg.node() });
    }
  }

  // o histórico cresce da base, mês a mês
  if (movimentoLigado()) {
    window.gsap.from(celulas, {
      scaleY: 0, duration: 0.5, ease: "power2.out", stagger: 0.012,
      scrollTrigger: { trigger: historico, start: "top 85%", once: true },
    });
  }

  return { atual, linhaAtual, agora };
}
