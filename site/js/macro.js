// Quando: semáforo atual, histórico da recomendação e as três séries (Selic, IPCA, dólar).
// Cada série tem o próprio gráfico (escalas diferentes não dividem eixo) e a mira é sincronizada.

import { ROTULO_SINAL, STATUS_RECOMENDACAO, iconeStatus } from "./indicadores.js";
import { decimal, mesCurto, mesPorExtenso, paraData, porcento, reaisCentavos } from "./formato.js";
import { movimentoLigado } from "./movimento.js";

export const SERIES = [
  {
    coluna: "selic_meta", titulo: "Meta da Selic · % a.a.",
    formato: (v) => `${decimal(v, 2)}%`,
    variacao: (l) => (l?.selic_var_12m_pp == null ? "" : `${l.selic_var_12m_pp > 0 ? "+" : ""}${decimal(l.selic_var_12m_pp, 2)} p.p. em 12 meses`),
  },
  {
    coluna: "ipca_12m", titulo: "IPCA em 12 meses · %",
    formato: (v) => porcento(v, 2), referencia: { valor: 4.5, texto: "limiar 4,5%" },
    variacao: (l) => (l?.ipca_mensal == null ? "" : `${porcento(l.ipca_mensal, 2, true)} no mês`),
  },
  {
    coluna: "dolar_medio", titulo: "Dólar · média do mês",
    formato: (v) => reaisCentavos(v, 2),
    variacao: (l) => (l?.dolar_var_12m_pct == null ? "" : `${porcento(l.dolar_var_12m_pct, 1, true)} em 12 meses`),
  },
];

const NOME_SINAL = { sinal_juros: "Juros", sinal_inflacao: "Inflação", sinal_cambio: "Câmbio" };
const COR_STATUS = { verde: "var(--verde)", amarelo: "var(--amarelo)", vermelho: "var(--vermelho)" };

export function criarMacro({ estado }) {
  const d3 = window.d3;
  const momento = estado.momento.map((l) => ({ ...l, data: paraData(l.mes) }));
  const macro = estado.macro.map((l) => ({ ...l, data: paraData(l.mes) }));
  const atual = momento.at(-1);
  const linhaAtual = atual ? macro.find((l) => l.mes === atual.mes) : null;

  // ------------------------------------------------------------ semáforo
  if (atual) {
    const status = STATUS_RECOMENDACAO[atual.recomendacao];
    document.querySelector(".semaforo__principal").style.setProperty("--status", COR_STATUS[status]);
    document.getElementById("semaforo-mes").textContent = `Referência · ${mesPorExtenso(atual.data)}`;
    document.getElementById("semaforo-recomendacao").innerHTML = `${iconeStatus(status)}<span>${atual.recomendacao}</span>`;
    document.getElementById("semaforo-justificativa").textContent = atual.justificativa;
    const textos = {
      sinal_juros: `Selic ${decimal(linhaAtual?.selic_meta, 2)}% a.a. · ${SERIES[0].variacao(linhaAtual)}`,
      sinal_inflacao: `IPCA ${porcento(linhaAtual?.ipca_12m, 2)} em 12 meses`,
      sinal_cambio: `Dólar ${SERIES[2].variacao(linhaAtual)}`,
    };
    document.getElementById("semaforo-sinais").innerHTML = Object.keys(NOME_SINAL).map((chave) =>
      `<li class="sinal" data-revela>${iconeStatus(atual[chave])}<span class="sinal__nome">${NOME_SINAL[chave]} · ${ROTULO_SINAL[atual[chave]]}</span><span class="sinal__texto">${textos[chave]}</span></li>`
    ).join("");
  }

  // ------------------------------------------------------------ histórico mês a mês
  const historico = document.getElementById("historico-momento");
  historico.innerHTML = momento.map((l) =>
    `<span class="historico__mes" style="background:${COR_STATUS[STATUS_RECOMENDACAO[l.recomendacao]]}" title="${mesPorExtenso(l.data)}: ${l.recomendacao}. ${l.justificativa}"></span>`
  ).join("");
  momento.forEach((l, i) => {
    if (l.data.getMonth() === 0 || i === 0) {
      historico.insertAdjacentHTML("beforeend", `<span class="historico__ano" style="left:${(i / momento.length) * 100}%">${l.data.getFullYear()}</span>`);
    }
  });
  const contagem = d3.rollup(momento, (v) => v.length, (l) => l.recomendacao);
  if (momento.length) {
    historico.setAttribute("aria-label", `Recomendação de ${mesPorExtenso(momento[0].data)} a ${mesPorExtenso(atual.data)}: ` +
      Object.keys(STATUS_RECOMENDACAO).map((r) => `${r}, ${contagem.get(r) ?? 0} meses`).join("; "));
  }
  document.getElementById("historico-legenda").innerHTML = Object.entries(STATUS_RECOMENDACAO).map(([rec, st]) =>
    `<span>${iconeStatus(st)} ${rec} <span class="discreto">(${contagem.get(rec) ?? 0} meses)</span></span>`).join("");

  // ------------------------------------------------------------ gráficos de linha
  const area = document.getElementById("graficos-macro");
  const L = 360, A = 170, m = { topo: 12, dir: 8, base: 22, esq: 34 };
  const x = d3.scaleTime().domain(d3.extent(macro, (l) => l.data)).range([m.esq, L - m.dir]);
  const graficos = [];

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
    cartao.innerHTML = `<h4>${serie.titulo}</h4>
      <p class="grafico__atual">${serie.formato(ultimo[serie.coluna])}</p>
      <p class="grafico__var">${mesCurto(ultimo.data)} · ${serie.variacao(ultimo)}</p>
      <div class="grafico__dica" hidden></div>`;
    area.appendChild(cartao);

    const svg = d3.select(cartao).append("svg").attr("viewBox", `0 0 ${L} ${A}`)
      .attr("role", "img").attr("aria-label", `${serie.titulo} de ${mesCurto(pontos[0].data)} a ${mesCurto(ultimo.data)}; último valor ${serie.formato(ultimo[serie.coluna])}`);
    svg.append("g").attr("class", "grade").selectAll("line").data(y.ticks(4)).join("line")
      .attr("x1", m.esq).attr("x2", L - m.dir).attr("y1", y).attr("y2", y);
    svg.append("g").attr("class", "eixo").attr("transform", `translate(0,${A - m.base})`)
      .call(d3.axisBottom(x).ticks(d3.timeYear.every(2)).tickFormat(d3.timeFormat("%Y")).tickSize(0).tickPadding(8));
    svg.append("g").attr("class", "eixo").attr("transform", `translate(${m.esq},0)`)
      .call(d3.axisLeft(y).ticks(4).tickSize(0).tickPadding(6).tickFormat((v) => decimal(v, v % 1 ? 1 : 0)));
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
    svg.append("rect").attr("x", m.esq).attr("y", 0).attr("width", L - m.esq - m.dir).attr("height", A).attr("fill", "transparent")
      .on("mousemove", (e) => mover(x.invert(d3.pointer(e)[0])))
      .on("mouseleave", () => mover(null));
    graficos.push({ serie, y, mira, ponto, dica: cartao.querySelector(".grafico__dica") });

    // a linha "se desenha" quando o gráfico entra na tela
    if (movimentoLigado()) {
      const comprimento = linha.node().getTotalLength();
      linha.attr("stroke-dasharray", comprimento).attr("stroke-dashoffset", comprimento);
      window.gsap.to(linha.node(), { strokeDashoffset: 0, duration: 1.8, ease: "power2.inOut",
        scrollTrigger: { trigger: cartao, start: "top 85%", once: true } });
    }
  }

  const busca = d3.bisector((l) => l.data).center;
  function mover(data) {
    const linha = data ? macro[busca(macro, data)] : null;
    for (const g of graficos) {
      const v = linha?.[g.serie.coluna];
      const visivel = linha && v !== null && v !== undefined;
      g.mira.style("display", visivel ? null : "none");
      g.ponto.style("display", visivel ? null : "none");
      g.dica.hidden = !visivel;
      if (!visivel) continue;
      g.mira.attr("x1", x(linha.data)).attr("x2", x(linha.data));
      g.ponto.attr("cx", x(linha.data)).attr("cy", g.y(v));
      g.dica.innerHTML = `${mesCurto(linha.data)}<br><b>${g.serie.formato(v)}</b>`;
    }
  }

  // o histórico cresce da base, mês a mês
  if (movimentoLigado()) {
    window.gsap.from(historico.querySelectorAll(".historico__mes"), {
      scaleY: 0, duration: 0.5, ease: "power2.out", stagger: 0.012,
      scrollTrigger: { trigger: historico, start: "top 85%", once: true },
    });
  }

  return { atual, linhaAtual };
}
