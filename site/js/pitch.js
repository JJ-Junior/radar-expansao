// Pitch em vídeo: botão de play sobre o radar do topo e um modal (<dialog>) com o vídeo legendado.
// O vídeo só carrega ao abrir (o src entra no clique). Fecha com X, Esc ou clique fora; ao fechar, pausa e devolve o foco.
// O endereço #pitch abre o modal direto (sem tocar sozinho, porque ainda não houve clique).

export function criarPitch() {
  const botao = document.getElementById("pitch-abrir");
  const modal = document.getElementById("pitch-modal");
  const video = document.getElementById("pitch-video");
  if (!botao || !modal || !video) return;

  let pedidoPlay = null;                          // play() ainda pendente quando o modal fecha não pode voltar a tocar

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
    botao.focus({ preventScroll: true });
  }

  botao.addEventListener("click", () => abrir({ tocar: true }));
  modal.querySelector("[data-fechar]").addEventListener("click", () => modal.close());
  modal.addEventListener("close", aoFechar);
  // clique no fundo escurecido (fora da caixa) fecha
  modal.addEventListener("click", (e) => { if (e.target === modal) modal.close(); });

  const peloEndereco = () => { if (location.hash === "#pitch") abrir(); };
  window.addEventListener("hashchange", peloEndereco);
  peloEndereco();
}

/** Põe o botão no centro do radar (o hero-radar avisa onde fica o centro). */
export function posicionarBotaoPitch(x, y) {
  const botao = document.getElementById("pitch-abrir");
  if (!botao) return;
  botao.style.setProperty("--radar-x", `${Math.round(x)}px`);
  botao.style.setProperty("--radar-y", `${Math.round(y)}px`);
  botao.classList.add("pitch-play--posicionado");
}
