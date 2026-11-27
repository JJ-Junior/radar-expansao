// Cidades em cards: primeiro as 5 unidades recomendadas (lista oficial da gold), depois o ranking geral por região.
// Desktop: grade (5 colunas, ou 3 + 2) com todos os cards inteiros na tela.
// Celular: carrossel nativo com "snap", card compacto (6 barras no lugar do radar) e indicador de posição com setas.

import { CRITERIOS, REGIOES, pesoDoCriterio, textosCriterios } from "./indicadores.js";
import { compacto, decimal, normalizar } from "./formato.js";
import { graficoRadar } from "./grafico-radar.js";
import { conteudoDica, ligarDica } from "./dica.js";
import { foraDaLista, motivoFora, quantidadeRecomendada, travaDeRenda } from "./recomendacao.js";

const QUANTIDADE = 10;
const RECOMENDADAS = "recomendadas";

export function criarCards({ estado, aoSelecionar }) {
  const trilho = document.getElementById("top-trilho");
  const filtro = document.getElementById("top-filtro");
  const titulo = document.getElementById("titulo-top");
  const explica = document.getElementById("top-explica");
  const fora = document.getElementById("top-fora");
  const temLista = estado.recomendadas.length > 0;
  let escolha = temLista ? RECOMENDADAS : "";

  const opcoes = [
    ...(temLista ? [{ valor: RECOMENDADAS, rotulo: `${estado.recomendadas.length} recomendadas`, nome: "Unidades recomendadas" }] : []),
    { valor: "", rotulo: "Brasil", nome: "Ranking do Brasil" },
    ...REGIOES.map((r) => ({ valor: r.sigla, rotulo: r.sigla, nome: `Ranking da região ${r.nome}` })),
  ];
  filtro.innerHTML = opcoes.map((o) =>
    `<button type="button" role="radio" aria-checked="${o.valor === escolha}" data-valor="${o.valor}" aria-label="${o.nome}">${o.rotulo}</button>`).join("");

  /** Selo sempre no mesmo lugar: recomendada, ou o motivo curto de estar fora da lista. */
  function selo(r) {
    if (r.recomendado_top5) return `<p class="selo selo--recomendada">Recomendada nº ${r.ordem_recomendacao}</p>`;
    if (!temLista) return `<p class="selo selo--vazio" aria-hidden="true">&nbsp;</p>`;
    const motivo = motivoFora(estado, r) ?? "";
    const curto = motivo.startsWith("poder de compra") ? "Fora da lista · trava de renda"
      : motivo.startsWith("mesma região") ? "Fora da lista · região já escolhida" : "Fora da lista";
    return `<p class="selo selo--fora" title="${motivo}">${curto}</p>`;
  }

  /** UF · região imediata; quando a imediata tem o nome da cidade, UF · grande região (sem repetir o nome). */
  function onde(c) {
    const imediata = c.regiao_imediata_nome ?? "";
    if (imediata && normalizar(imediata) !== normalizar(c.municipio_nome)) return `${c.uf_sigla} · ${imediata}`;
    return `${c.uf_sigla} · ${REGIOES.find((r) => r.sigla === c.regiao_sigla)?.nome ?? ""}`;
  }

  const NOME_CURTO = { mercado: "Mercado", poder_compra: "Poder de compra", espaco_competitivo: "Espaço livre", crescimento: "Crescimento", riqueza: "Riqueza", mercado_formal: "Mercado formal" };
  /** No celular, 6 barras curtas no lugar do radar (mesmas notas, leitura mais rápida em tela pequena). */
  const barras = (r) => `<ul class="cartao-cidade__barras" aria-label="Notas dos 6 critérios">${CRITERIOS.map((k) => {
    const v = r[`nota_${k.criterio}`];
    return `<li><span title="${k.nome}">${NOME_CURTO[k.criterio] ?? k.nome}</span><i style="--v:${v ?? 0}%"></i><b>${decimal(v, 0)}</b></li>`;
  }).join("")}</ul>
    <a class="cartao-cidade__ajuda" href="#compoe-nota">O que é cada nota?</a>`;

  const cartao = (c, rotulo) => `
    <li class="cartao-cidade ${c.ranking.recomendado_top5 ? "cartao-cidade--recomendada" : ""}">
      <div class="cartao-cidade__cabeca">
        <div class="cartao-cidade__linha"><span class="cartao-cidade__onde">${onde(c)}</span><span class="cartao-cidade__pos" aria-hidden="true">${rotulo}</span></div>
        <h3 class="cartao-cidade__nome">${c.municipio_nome}</h3>
        ${selo(c.ranking)}
      </div>
      <div class="cartao-cidade__radar" tabindex="0" data-id="${c.municipio_id}">${graficoRadar(c.ranking, { tamanho: 220 })}</div>
      ${barras(c.ranking)}
      <dl class="cartao-cidade__numeros">
        <div class="cartao-cidade__nota"><dt>Nota</dt><dd>${decimal(c.ranking.nota_final, 1)}</dd></div>
        <div><dt>Nº Brasil</dt><dd>${c.ranking.posicao_brasil}º</dd></div>
        <div><dt>Habitantes</dt><dd>${compacto(c.populacao)}</dd></div>
      </dl>
      <button class="botao botao--fantasma" type="button" data-id="${c.municipio_id}">Abrir ficha</button>
    </li>`;

  /** As notas dos 6 critérios no tooltip do radar do card. */
  function ligarRadares() {
    const textos = textosCriterios(estado.meta);
    for (const el of trilho.querySelectorAll(".cartao-cidade__radar")) {
      const c = estado.porId.get(Number(el.dataset.id));
      el.setAttribute("aria-label", `Notas de ${c.municipio_nome}; foco mostra os valores`);
      ligarDica(el, () => conteudoDica({
        titulo: `Notas de ${c.municipio_nome}`,
        chip: { texto: `nota final ${decimal(c.ranking.nota_final, 1)}` },
        linhas: CRITERIOS.map((k) => ({
          rotulo: k.nome, valor: decimal(c.ranking[`nota_${k.criterio}`], 0),
          detalhe: `peso ${Math.round((pesoDoCriterio(estado.criterios, k.criterio) ?? 0) * 100)}%`,
          sub: textos[k.criterio]?.curto,
        })),
        nota: "Notas de 0 a 100: percentil entre as cidades com 50 mil hab. ou mais. Detalhes em “Como o ranking é calculado”.",
      }));
    }
  }

  function desenharFora() {
    const lista = escolha === RECOMENDADAS ? foraDaLista(estado) : [];
    fora.hidden = !lista.length;
    if (!lista.length) return;
    fora.innerHTML = `<p class="top-fora__titulo">Por que não ${lista.map(({ r }) => r.municipio_nome).join(" e ")}?</p>
      <ul>${lista.map(({ r, motivo }) => `<li><button type="button" data-id="${r.municipio_id}"><b>${r.posicao_brasil}º ${r.municipio_nome}</b> <span>${r.uf_sigla}</span></button> — ${motivo}.</li>`).join("")}</ul>
      <p class="discreto">Só entram cidades com nota de poder de compra a partir de ${decimal(travaDeRenda(estado), 0)}, e no máximo uma por região imediata. O ranking completo não muda.</p>`;
  }

  function desenhar() {
    let lista;
    if (escolha === RECOMENDADAS) {
      titulo.textContent = `As ${estado.recomendadas.length} recomendadas`;
      explica.textContent = `A lista para abrir ${quantidadeRecomendada(estado)} unidades: as melhores do ranking, uma por região imediata do IBGE, ` +
        `com trava de renda (poder de compra a partir de ${decimal(travaDeRenda(estado), 0)}). Academia é gasto que o aluno corta primeiro: sem renda, população não vira matrícula.`;
      lista = estado.recomendadas.map((r) => estado.porId.get(r.municipio_id)).filter(Boolean)
        .map((c) => cartao(c, String(c.ranking.ordem_recomendacao).padStart(2, "0")));
    } else {
      const regiao = REGIOES.find((r) => r.sigla === escolha);
      titulo.textContent = regiao ? `As mais prontas do ${regiao.nome}` : "As mais prontas do Brasil";
      explica.textContent = "Ranking geral pela nota final, sem a trava de renda e sem o limite de uma cidade por região imediata.";
      lista = estado.universo.filter((c) => !escolha || c.regiao_sigla === escolha).slice(0, QUANTIDADE)
        .map((c, i) => cartao(c, String(i + 1).padStart(2, "0")));
    }
    trilho.innerHTML = lista.join("");
    trilho.dataset.quantidade = lista.length;
    trilho.scrollLeft = 0;
    montarIndicador(lista.length);
    ligarRadares();
    desenharFora();
    window.ScrollTrigger?.refresh();
  }

  // ------------------------------------------------------------ celular: posição no carrossel (1/5, pontos e setas)
  const navegar = document.getElementById("top-navegar");
  const contador = navegar.querySelector(".top__contador");
  const pontos = navegar.querySelector(".top__pontos");
  const [anterior, proximo] = navegar.querySelectorAll("button");
  const passo = () => {
    const card = trilho.querySelector(".cartao-cidade");
    return card ? card.getBoundingClientRect().width + parseFloat(getComputedStyle(trilho).columnGap || 0) : 1;
  };
  const indiceAtual = () => Math.round(trilho.scrollLeft / passo());
  function montarIndicador(total) {
    pontos.innerHTML = Array.from({ length: total }, () => "<i></i>").join("");
    atualizarIndicador();
  }
  function atualizarIndicador() {
    const total = Number(trilho.dataset.quantidade) || 0;
    const i = Math.min(total - 1, Math.max(0, indiceAtual()));
    contador.textContent = total ? `${i + 1} / ${total}` : "";
    pontos.querySelectorAll("i").forEach((p, k) => p.classList.toggle("ativo", k === i));
    anterior.disabled = i <= 0;
    proximo.disabled = i >= total - 1;
  }
  let quadroIndicador = null;
  trilho.addEventListener("scroll", () => {
    if (quadroIndicador) return;
    quadroIndicador = requestAnimationFrame(() => { quadroIndicador = null; atualizarIndicador(); });
  }, { passive: true });
  const prefereMenos = window.matchMedia("(prefers-reduced-motion: reduce)");
  const irPara = (delta) => trilho.scrollTo({ left: (indiceAtual() + delta) * passo(), behavior: prefereMenos.matches ? "auto" : "smooth" });
  anterior.addEventListener("click", () => irPara(-1));
  proximo.addEventListener("click", () => irPara(1));

  // filtros: no celular viram uma linha rolável; o esmaecido da borda some quando chega ao fim
  const bordasFiltro = () => {
    filtro.classList.toggle("tem-antes", filtro.scrollLeft > 4);
    filtro.classList.toggle("tem-depois", filtro.scrollLeft + filtro.clientWidth < filtro.scrollWidth - 4);
  };
  filtro.addEventListener("scroll", bordasFiltro, { passive: true });
  new ResizeObserver(bordasFiltro).observe(filtro);

  filtro.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    escolha = b.dataset.valor;
    for (const x of filtro.querySelectorAll("button")) x.setAttribute("aria-checked", x === b);
    b.scrollIntoView({ block: "nearest", inline: "nearest" });
    desenhar();
  });
  const abrir = (e) => {
    const b = e.target.closest("button[data-id]");
    if (b) aoSelecionar(Number(b.dataset.id));
  };
  trilho.addEventListener("click", abrir);
  fora.addEventListener("click", abrir);

  desenhar();
}
