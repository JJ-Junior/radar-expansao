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
 * Celular: o play fica no canto superior direito do título, encostado na margem direita, sem tocar em nenhuma letra.
 * Tenta, nesta ordem: entre a 1ª e a 2ª linha, na altura da 1ª linha, na altura do sobretítulo; e com 52, 48 e 44 px.
 * Se nada couber (tela muito estreita), vai para o fim da linha com mais sobra, com 44 px (área de toque mínima).
 * Usa offsetTop/offsetLeft (não mudam com a animação de entrada do título).
 */
export function posicionarPlayTitulo() {
  const botao = document.getElementById("pitch-titulo");
  const texto = botao?.closest(".hero__texto");
  const linhas = [...document.querySelectorAll(".hero__titulo .linha > span")];
  const sobretitulo = texto?.querySelector(".rotulo");
  if (!botao || !texto || !linhas.length) return;
  const W = texto.clientWidth, FOLGA = 8;
  const caixa = (el, largura = el.offsetWidth) => ({ esq: el.offsetLeft, dir: el.offsetLeft + largura, topo: el.offsetTop, base: el.offsetTop + el.offsetHeight });
  const obstaculos = linhas.map((s) => caixa(s));
  let rotulo = null;
  if (sobretitulo) {
    const faixa = document.createRange(); faixa.selectNodeContents(sobretitulo);
    rotulo = caixa(sobretitulo, Math.min(sobretitulo.offsetWidth, faixa.getBoundingClientRect().width));
    obstaculos.push(rotulo);
  }
  const livre = (x, y, d) => obstaculos.every((o) =>
    x + d / 2 + FOLGA <= o.esq || x - d / 2 - FOLGA >= o.dir || y + d / 2 + FOLGA <= o.topo || y - d / 2 - FOLGA >= o.base);
  const [l1, l2] = obstaculos;
  const alturas = [l2 ? (l1.base + l2.topo) / 2 : null, (l1.topo + l1.base) / 2, rotulo ? (rotulo.topo + rotulo.base) / 2 : null].filter((y) => y !== null);
  let escolha = null;
  for (const d of [52, 48, 44]) {
    for (const y of alturas) { const x = W - d / 2; if (livre(x, y, d)) { escolha = { x, y, d }; break; } }
    if (escolha) break;
  }
  if (!escolha) {                                   // reserva: fim da linha com mais sobra, 44 px
    const d = 44;
    for (const o of obstaculos.slice(0, linhas.length)) {
      const y = (o.topo + o.base) / 2, x = W - d / 2;
      if (livre(x, y, d) && (!escolha || o.dir < escolha.fim)) escolha = { x, y, d, fim: o.dir };
    }
  }
  botao.classList.toggle("pitch-titulo--posicionado", !!escolha);
  if (!escolha) return;
  botao.style.setProperty("--pt-x", `${Math.round(escolha.x)}px`);
  botao.style.setProperty("--pt-y", `${Math.round(escolha.y)}px`);
  botao.style.setProperty("--pt-d", `${escolha.d}px`);
}

/** Põe o botão no centro do radar (o hero-radar avisa onde fica o centro). */
export function posicionarBotaoPitch(x, y) {
  const botao = document.getElementById("pitch-abrir");
  if (!botao) return;
  botao.style.setProperty("--radar-x", `${Math.round(x)}px`);
  botao.style.setProperty("--radar-y", `${Math.round(y)}px`);
  botao.classList.add("pitch-play--posicionado");
}
