// Cidades em cards: primeiro as 5 unidades recomendadas (lista oficial da gold), depois o ranking geral por região.
// No desktop com movimento, a seção fica presa e o scroll vertical empurra o trilho para o lado;
// no celular é um carrossel nativo com "snap".

import { REGIOES } from "./indicadores.js";
import { compacto, decimal } from "./formato.js";
import { graficoRadar } from "./grafico-radar.js";
import { movimentoLigado } from "./movimento.js";
import { foraDaLista, quantidadeRecomendada, travaDeRenda } from "./recomendacao.js";

const QUANTIDADE = 10;
const RECOMENDADAS = "recomendadas";

export function criarCards({ estado, aoSelecionar }) {
  const trilho = document.getElementById("top-trilho");
  const filtro = document.getElementById("top-filtro");
  const titulo = document.getElementById("titulo-top");
  const explica = document.getElementById("top-explica");
  const secao = document.getElementById("top");
  const temLista = estado.recomendadas.length > 0;
  let escolha = temLista ? RECOMENDADAS : "";
  let gatilho = null;

  const opcoes = [
    ...(temLista ? [{ valor: RECOMENDADAS, rotulo: `${estado.recomendadas.length} recomendadas`, nome: "Unidades recomendadas" }] : []),
    { valor: "", rotulo: "Brasil", nome: "Ranking do Brasil" },
    ...REGIOES.map((r) => ({ valor: r.sigla, rotulo: r.sigla, nome: `Ranking da região ${r.nome}` })),
  ];
  filtro.innerHTML = opcoes.map((o) =>
    `<button type="button" role="radio" aria-checked="${o.valor === escolha}" data-valor="${o.valor}" aria-label="${o.nome}">${o.rotulo}</button>`).join("");

  const cartao = (c, rotulo) => `
    <li class="cartao-cidade ${c.ranking.recomendado_top5 ? "cartao-cidade--recomendada" : ""}">
      <span class="cartao-cidade__pos" aria-hidden="true">${rotulo}</span>
      <p class="cartao-cidade__onde">${c.uf_sigla} · ${c.regiao_imediata_nome ?? ""}</p>
      <h3 class="cartao-cidade__nome">${c.municipio_nome}</h3>
      ${c.ranking.recomendado_top5 ? `<p class="selo-recomendada">Recomendada nº ${c.ranking.ordem_recomendacao}</p>` : ""}
      <div class="cartao-cidade__radar">${graficoRadar(c.ranking, { tamanho: 220 })}</div>
      <div class="cartao-cidade__numeros">
        <div class="cartao-cidade__nota"><b>${decimal(c.ranking.nota_final, 1)}</b><span>nota</span></div>
        <div><b>${c.ranking.posicao_brasil}º</b><span>no Brasil</span></div>
        <div><b>${compacto(c.populacao)}</b><span>habitantes</span></div>
      </div>
      <button class="botao botao--fantasma" type="button" data-id="${c.municipio_id}">Abrir ficha</button>
    </li>`;

  function cartaoForaDaLista() {
    const fora = foraDaLista(estado);
    if (!fora.length) return "";
    return `<li class="cartao-cidade cartao-cidade--nota">
      <p class="cartao-cidade__onde">Regra da lista</p>
      <h3 class="cartao-cidade__nome">Por que não ${fora.length === 1 ? "ela" : "elas"}?</h3>
      <ul class="fora-lista">${fora.map(({ r, motivo }) => `<li><button type="button" data-id="${r.municipio_id}">
        <b>${r.posicao_brasil}º ${r.municipio_nome}</b> <span>${r.uf_sigla}</span></button><small>${motivo}</small></li>`).join("")}</ul>
      <p class="discreto">Só entram cidades com nota de poder de compra a partir de ${decimal(travaDeRenda(estado), 0)}, e no máximo uma por região imediata. O ranking completo não muda.</p>
    </li>`;
  }

  function desenhar() {
    if (escolha === RECOMENDADAS) {
      titulo.textContent = `As ${estado.recomendadas.length} recomendadas`;
      explica.textContent = `A lista para abrir ${quantidadeRecomendada(estado)} unidades: as melhores do ranking, uma por região imediata do IBGE, ` +
        `com trava de renda (poder de compra a partir de ${decimal(travaDeRenda(estado), 0)}). Academia é gasto que o aluno corta primeiro: sem renda, população não vira matrícula.`;
      const lista = estado.recomendadas.map((r) => estado.porId.get(r.municipio_id)).filter(Boolean);
      trilho.innerHTML = lista.map((c) => cartao(c, String(c.ranking.ordem_recomendacao).padStart(2, "0"))).join("") + cartaoForaDaLista();
    } else {
      const regiao = REGIOES.find((r) => r.sigla === escolha);
      titulo.textContent = regiao ? `As mais prontas do ${regiao.nome}` : "As mais prontas do Brasil";
      explica.textContent = "Ranking geral pela nota final, sem a trava de renda e sem o limite de uma cidade por região imediata.";
      const lista = estado.universo.filter((c) => !escolha || c.regiao_sigla === escolha).slice(0, QUANTIDADE);
      trilho.innerHTML = lista.map((c, i) => cartao(c, String(i + 1).padStart(2, "0"))).join("");
    }
    ligarTrilho();
  }

  /** Trilho preso + scroll horizontal (GSAP). Refeito a cada troca de filtro. */
  function ligarTrilho() {
    gatilho?.kill();
    gatilho = null;
    window.gsap?.set(trilho, { x: 0 });
    if (!movimentoLigado() || window.matchMedia("(max-width: 860px)").matches) return;
    const { gsap, ScrollTrigger } = window;
    const distancia = () => Math.max(0, trilho.scrollWidth - document.documentElement.clientWidth);
    if (distancia() < 40) { ScrollTrigger.refresh(); return; }
    const animacao = gsap.to(trilho, { x: () => -distancia(), ease: "none" });
    gatilho = ScrollTrigger.create({
      trigger: secao, start: () => `top top+=${document.querySelector(".topo").offsetHeight}`, end: () => `+=${distancia()}`,
      pin: true, scrub: 0.6, animation: animacao, invalidateOnRefresh: true,
    });
    ScrollTrigger.refresh();
  }

  filtro.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    escolha = b.dataset.valor;
    for (const x of filtro.querySelectorAll("button")) x.setAttribute("aria-checked", x === b);
    desenhar();
  });
  trilho.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-id]");
    if (b) aoSelecionar(Number(b.dataset.id));
  });
  window.matchMedia("(max-width: 860px)").addEventListener("change", ligarTrilho);

  desenhar();
}
