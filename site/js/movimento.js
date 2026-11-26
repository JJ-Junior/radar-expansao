// Movimento: scroll suave (Lenis), animações de scroll (GSAP + ScrollTrigger), contadores.
// Tudo é opcional: com "reduzir movimento" ligado ou sem as bibliotecas, a página fica estática e completa.

const prefereMenos = window.matchMedia("(prefers-reduced-motion: reduce)");

export const movimentoLigado = () => !prefereMenos.matches && !!window.gsap && !!window.ScrollTrigger;

let lenis = null;

/** Guarda a altura real do cabeçalho (com o aviso de prévia) em --topo-total, para o mapa fixo e as âncoras. */
export function medirCabecalho() {
  const topo = document.querySelector(".topo");
  const medir = () => document.documentElement.style.setProperty("--topo-total", `${topo.offsetHeight}px`);
  medir();
  new ResizeObserver(medir).observe(topo);
}

/** Liga Lenis + ScrollTrigger e marca o <html> com a classe "movimento". */
export function iniciarMovimento() {
  if (!movimentoLigado()) return false;
  const { gsap, ScrollTrigger } = window;
  gsap.registerPlugin(ScrollTrigger);
  document.documentElement.classList.add("movimento");

  if (window.Lenis) {
    lenis = new window.Lenis({ duration: 1.1, smoothWheel: true });
    lenis.on("scroll", ScrollTrigger.update);
    gsap.ticker.add((t) => lenis.raf(t * 1000));
    gsap.ticker.lagSmoothing(0);
  }
  return true;
}

/** Âncoras internas (#secao) rolam com o Lenis quando ele está ativo. */
export function ligarAncoras() {
  document.addEventListener("click", (e) => {
    const a = e.target.closest('a[href^="#"]');
    if (!a || a.getAttribute("href").length < 2) return;
    const alvo = document.querySelector(a.getAttribute("href"));
    if (!alvo) return;
    e.preventDefault();
    rolarAte(alvo);
    history.replaceState(history.state, "", a.getAttribute("href"));
  });
}

export function rolarAte(elemento) {
  const topo = document.querySelector(".topo");
  const deslocamento = -(topo ? topo.offsetHeight : 64) - 12;
  if (lenis) lenis.scrollTo(elemento, { offset: deslocamento });
  else elemento.scrollIntoView({ block: "start", behavior: prefereMenos.matches ? "auto" : "smooth" });
}

/** Entrada do hero: linhas do título sobem por trás de uma máscara. */
export function animarHero() {
  if (!movimentoLigado()) return;
  const { gsap } = window;
  gsap.from(".hero__titulo .linha > span", { yPercent: 110, duration: 1, ease: "power4.out", stagger: 0.12, delay: 0.1 });
  gsap.from([".hero__lede", ".busca", ".kpis"], { y: 24, opacity: 0, duration: 0.8, ease: "power3.out", stagger: 0.12, delay: 0.5 });
}

/** Elementos com [data-revela] entram de baixo quando aparecem. */
export function revelarAoRolar(raiz = document) {
  if (!movimentoLigado()) return;
  const { gsap, ScrollTrigger } = window;
  const alvos = [...raiz.querySelectorAll("[data-revela]:not([data-revelado])")];
  alvos.forEach((el) => el.setAttribute("data-revelado", ""));
  gsap.set(alvos, { y: 36, opacity: 0 });
  ScrollTrigger.batch(alvos, {
    start: "top 88%",
    once: true,
    onEnter: (lote) => gsap.to(lote, { y: 0, opacity: 1, duration: 0.8, ease: "power3.out", stagger: 0.08 }),
  });
}

/** Número que conta de 0 até o valor quando entra na tela. */
export function contar(elemento, valor, formatar) {
  if (!movimentoLigado()) { elemento.textContent = formatar(valor); return; }
  const { gsap } = window;
  const obj = { v: 0 };
  elemento.textContent = formatar(0);
  gsap.to(obj, {
    v: valor, duration: 1.6, ease: "power2.out", delay: 0.6,
    onUpdate: () => { elemento.textContent = formatar(obj.v); },
  });
}

/** Recalcula as posições depois de mudar o tamanho de algo. */
export function atualizarGatilhos() {
  if (window.ScrollTrigger) window.ScrollTrigger.refresh();
}
