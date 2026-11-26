// Top cidades: trilho horizontal de cards. No desktop com movimento, a seção fica presa
// e o scroll vertical empurra o trilho para o lado; no celular é um carrossel nativo com "snap".

import { REGIOES } from "./indicadores.js";
import { compacto, decimal } from "./formato.js";
import { graficoRadar } from "./grafico-radar.js";
import { movimentoLigado } from "./movimento.js";

const QUANTIDADE = 10;

export function criarCards({ estado, aoSelecionar }) {
  const trilho = document.getElementById("top-trilho");
  const filtro = document.getElementById("top-filtro");
  const secao = document.getElementById("top");
  let regiao = "";
  let gatilho = null;

  const opcoes = [{ sigla: "", nome: "Brasil" }, ...REGIOES];
  filtro.innerHTML = opcoes.map((o) =>
    `<button type="button" role="radio" aria-checked="${o.sigla === ""}" data-regiao="${o.sigla}" aria-label="${o.nome}">${o.sigla || "Brasil"}</button>`).join("");

  function desenhar() {
    const lista = estado.universo.filter((c) => !regiao || c.regiao_sigla === regiao).slice(0, QUANTIDADE);
    trilho.innerHTML = lista.map((c, i) => `
      <li class="cartao-cidade">
        <span class="cartao-cidade__pos" aria-hidden="true">${String(i + 1).padStart(2, "0")}</span>
        <p class="cartao-cidade__onde">${c.uf_sigla} · ${c.regiao_imediata_nome ?? ""}</p>
        <h3 class="cartao-cidade__nome">${c.municipio_nome}</h3>
        <div class="cartao-cidade__radar">${graficoRadar(c.ranking, { tamanho: 220 })}</div>
        <div class="cartao-cidade__numeros">
          <div class="cartao-cidade__nota"><b>${decimal(c.ranking.nota_final, 1)}</b><span>nota</span></div>
          <div><b>${c.ranking.posicao_brasil}º</b><span>no Brasil</span></div>
          <div><b>${compacto(c.populacao)}</b><span>habitantes</span></div>
        </div>
        <button class="botao botao--fantasma" type="button" data-id="${c.municipio_id}">Abrir ficha</button>
      </li>`).join("");
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
    if (distancia() < 40) return;
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
    regiao = b.dataset.regiao;
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
