// Pitch em vídeo: botão de play sobre o radar do topo e um modal (<dialog>) com o vídeo legendado.
// O vídeo só carrega ao abrir (o src entra no clique). Fecha com X, Esc ou clique fora; ao fechar, pausa e devolve o foco.
// O endereço #pitch abre o modal direto (sem tocar sozinho, porque ainda não houve clique).

export function criarPitch() {
  const botao = document.getElementById("pitch-abrir");
  const modal = document.getElementById("pitch-modal");
  const video = document.getElementById("pitch-video");
  if (!botao || !modal || !video) return;

  let pedidoPlay = null;
  let origem = botao;                             // quem abriu o modal recebe o foco de volta                          // play() ainda pendente quando o modal fecha não pode voltar a tocar

  function abrir({ tocar = false } = {}) {
    if (!video.getAttribute("src")) { video.src = video.dataset.src; video.preload = "metadata"; }
    if (!modal.open) modal.showModal();
    if (tocar) pedidoPlay = video.play().catch(() => {});        // o clique é gesto do usuário; se o navegador barrar, fica o play manual
    else video.focus({ preventScroll: true });
  }

  function aoFechar() {
    video.pause();
    pedidoPlay?.then(() => { if (!modal.open) video.pause(); });
    if (location.hash === "#pitch") history.replaceState(history.state, "", location.pathname + location.search);
    origem.focus({ preventScroll: true });
    origem = botao;
  }

  for (const b of [botao, ...document.querySelectorAll("[data-abrir-pitch]")]) {
    b.addEventListener("click", () => { origem = b; abrir({ tocar: true }); });
  }
  // o evento "close" pode chegar com atraso: o vídeo pausa já no gesto de fechar (X, clique fora, Esc)
  const fechar = () => { video.pause(); modal.close(); };
  modal.querySelector("[data-fechar]").addEventListener("click", fechar);
  modal.addEventListener("cancel", () => video.pause());
  video.addEventListener("contextmenu", (e) => e.preventDefault());   // sem "salvar vídeo como" no menu do botão direito
  modal.addEventListener("close", aoFechar);
  // clique no fundo escurecido (fora da caixa) fecha
  modal.addEventListener("click", (e) => { if (e.target === modal) fechar(); });

  posicionarPlayTitulo();
  document.fonts?.ready.then(posicionarPlayTitulo);
  let espera;
  window.addEventListener("resize", () => { clearTimeout(espera); espera = setTimeout(posicionarPlayTitulo, 120); });

  const peloEndereco = () => { if (location.hash === "#pitch") abrir(); };
  window.addEventListener("hashchange", peloEndereco);
  peloEndereco();
}

/**
 * Celular: o play do título fica à direita do título, na altura da linha com mais sobra, sem tocar em nenhuma letra:
 * o botão começa depois do fim de TODAS as linhas que cruzam a altura dele. Usa offsetLeft/offsetTop (não mudam com a
 * animação de entrada do título). Se não couber em nenhuma linha, o botão não aparece.
 */
export function posicionarPlayTitulo() {
  const botao = document.getElementById("pitch-titulo");
  const texto = botao?.closest(".hero__texto");
  const linhas = [...document.querySelectorAll(".hero__titulo .linha > span")];
  if (!botao || !texto || !linhas.length) return;
  const D = 44, FOLGA = 8;                        // diâmetro (área de toque mínima) e respiro das letras
  const caixas = linhas.map((s) => ({ topo: s.offsetTop, base: s.offsetTop + s.offsetHeight, fim: s.offsetLeft + s.offsetWidth }));
  let melhor = null;
  for (const c of caixas) {
    const y = (c.topo + c.base) / 2;
    const x0 = Math.max(...caixas.filter((o) => o.topo < y + D / 2 && o.base > y - D / 2).map((o) => o.fim)) + FOLGA;
    const sobra = texto.clientWidth - (x0 + D);
    if (sobra >= 0 && (!melhor || sobra > melhor.sobra)) melhor = { x: x0 + D / 2 + Math.min(sobra / 2, D / 2), y, sobra };
  }
  botao.classList.toggle("pitch-titulo--posicionado", !!melhor);
  if (!melhor) return;
  botao.style.setProperty("--pt-x", `${Math.round(melhor.x)}px`);
  botao.style.setProperty("--pt-y", `${Math.round(melhor.y)}px`);
}

/** Põe o botão no centro do radar (o hero-radar avisa onde fica o centro). */
export function posicionarBotaoPitch(x, y) {
  const botao = document.getElementById("pitch-abrir");
  if (!botao) return;
  botao.style.setProperty("--radar-x", `${Math.round(x)}px`);
  botao.style.setProperty("--radar-y", `${Math.round(y)}px`);
  botao.classList.add("pitch-play--posicionado");
}
