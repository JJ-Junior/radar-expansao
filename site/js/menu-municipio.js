// Menu de contexto de um município nos mapas do site (simulador, Explorar e mapa por regiões).
// Abre com o botão direito, com a tecla de menu / Shift+F10 num item focado e, no celular, com toque longo.
// Fecha com Esc, clique fora, rolagem ou ao escolher uma opção; o foco volta para onde estava.
// Opções: ver a cidade (ficha do site), ver os bairros no dashboard (qualquer município) e abrir no dashboard
// (só cidades do ranking, com 50 mil hab. ou mais: as outras não têm ficha lá).

/** Endereço do dashboard oficial (Streamlit Community Cloud). */
export const DASHBOARD_URL = "https://radar-expansao.streamlit.app";
/** Caminho de cada página do dashboard; o município vai em ?municipio=<código IBGE de 7 dígitos>. */
export const PAGINAS_DASHBOARD = { municipio: "municipio", bairros: "bairros" };
export const linkDashboard = (pagina, id) => `${DASHBOARD_URL}/${PAGINAS_DASHBOARD[pagina]}?municipio=${id}`;

const TOQUE_LONGO_MS = 550;
const TOLERANCIA_PX = 10;     // o dedo pode tremer um pouco sem cancelar o toque longo
const MARGEM = 8;

export function criarMenuMunicipio({ estado, aoSelecionar }) {
  const menu = document.createElement("div");
  menu.className = "menu-mun";
  menu.id = "menu-municipio";
  menu.setAttribute("role", "menu");
  menu.hidden = true;
  document.body.append(menu);

  let foco = null;             // elemento que tinha o foco antes do menu
  let ignorarClique = 0;       // depois de um toque longo, o clique que vem em seguida não abre a ficha

  function itens() { return [...menu.querySelectorAll("[role=menuitem]")]; }

  function fechar({ devolverFoco = true } = {}) {
    if (menu.hidden) return;
    menu.hidden = true;
    if (devolverFoco && foco && document.contains(foco)) foco.focus({ preventScroll: true });
    foco = null;
  }

  /** Abre o menu do município `id` no ponto (x, y) da tela. */
  function abrir(id, x, y) {
    const m = estado.porId.get(id);
    foco = document.activeElement;
    const nome = m ? `${m.municipio_nome} · ${m.uf_sigla}` : `Município ${id}`;
    menu.setAttribute("aria-label", `Opções para ${m ? `${m.municipio_nome} (${m.uf_sigla})` : `o município ${id}`}`);
    menu.replaceChildren();
    const titulo = document.createElement("p");
    titulo.className = "menu-mun__titulo";
    titulo.textContent = nome;
    titulo.setAttribute("aria-hidden", "true");
    menu.append(titulo);

    const item = (texto, detalhe, { href = null, acao = null } = {}) => {
      const el = document.createElement(href ? "a" : "button");
      el.className = "menu-mun__item";
      el.setAttribute("role", "menuitem");
      el.tabIndex = -1;
      if (href) { el.href = href; el.target = "_blank"; el.rel = "noopener"; }
      else el.type = "button";
      const t = document.createElement("span"); t.textContent = texto;
      const d = document.createElement("small"); d.textContent = detalhe;
      el.append(t, d);
      el.addEventListener("click", () => { fechar({ devolverFoco: !href }); acao?.(); });
      menu.append(el);
    };
    // a ficha do site cobre todos os municípios; sem ela, a opção some (nunca cai na ficha do dashboard)
    if (m) item("Ver cidade", "ficha neste site", { acao: () => aoSelecionar(id) });
    // Bairros do dashboard aceita qualquer município (calcula sob demanda)
    item("Ver bairros", "no dashboard ↗", { href: linkDashboard("bairros", id) });
    // a página Município do dashboard só tem ficha para quem está no ranking (50 mil hab. ou mais)
    if (m?.ranking) item("Abrir no dashboard", "página do município ↗", { href: linkDashboard("municipio", id) });

    menu.hidden = false;
    const larg = menu.offsetWidth, alt = menu.offsetHeight;
    const vw = document.documentElement.clientWidth, vh = window.innerHeight;
    const esq = Math.min(Math.max(MARGEM, x), vw - larg - MARGEM);
    const topo = y + alt + MARGEM > vh ? Math.max(MARGEM, y - alt) : y;
    menu.style.transform = `translate(${Math.round(esq)}px, ${Math.round(topo)}px)`;
    itens()[0].focus({ preventScroll: true });
  }

  menu.addEventListener("keydown", (e) => {
    const lista = itens();
    const i = lista.indexOf(document.activeElement);
    const ir = (k) => { e.preventDefault(); lista[(k + lista.length) % lista.length].focus(); };
    if (e.key === "ArrowDown") ir(i + 1);
    else if (e.key === "ArrowUp") ir(i - 1);
    else if (e.key === "Home") ir(0);
    else if (e.key === "End") ir(lista.length - 1);
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); fechar(); }
    else if (e.key === "Tab") fechar({ devolverFoco: false });
  });
  menu.addEventListener("contextmenu", (e) => e.preventDefault());
  document.addEventListener("pointerdown", (e) => { if (!menu.hidden && !menu.contains(e.target)) fechar({ devolverFoco: false }); }, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !menu.hidden) fechar(); });
  window.addEventListener("scroll", () => fechar({ devolverFoco: false }), { passive: true });
  window.addEventListener("resize", () => fechar({ devolverFoco: false }));

  /**
   * Liga o menu a um elemento. `achar(evento)` devolve o código do município sob o ponteiro (ou null).
   * Pelo teclado (tecla de menu, Shift+F10) o evento vem sem coordenadas: o menu abre junto do elemento focado.
   */
  function ligar(elemento, achar) {
    elemento.addEventListener("contextmenu", (e) => {
      const id = achar(e);
      if (!id) return;                         // fora de um município: fica o menu do navegador
      e.preventDefault();
      let { clientX: x, clientY: y } = e;
      if (!x && !y) { const r = (e.target instanceof Element ? e.target : elemento).getBoundingClientRect(); x = r.left + 8; y = r.bottom; }
      abrir(id, x, y);
    });
    // toque longo (o Android também dispara contextmenu; abrir de novo no mesmo lugar não tem efeito visível)
    let espera = null, inicio = null;
    const cancelar = () => { clearTimeout(espera); espera = null; };
    elemento.addEventListener("pointerdown", (e) => {
      if (e.pointerType !== "touch") return;
      inicio = { x: e.clientX, y: e.clientY };
      cancelar();
      espera = setTimeout(() => {
        espera = null;
        const id = achar(e);
        if (!id) return;
        ignorarClique = performance.now() + 800;
        abrir(id, inicio.x, inicio.y);
      }, TOQUE_LONGO_MS);
    });
    elemento.addEventListener("pointermove", (e) => {
      if (espera && inicio && Math.hypot(e.clientX - inicio.x, e.clientY - inicio.y) > TOLERANCIA_PX) cancelar();
    });
    for (const tipo of ["pointerup", "pointercancel", "pointerleave"]) elemento.addEventListener(tipo, cancelar);
    // o clique que encerra um toque longo não abre a ficha
    elemento.addEventListener("click", (e) => {
      if (performance.now() < ignorarClique) { e.stopImmediatePropagation(); e.preventDefault(); ignorarClique = 0; }
    }, true);
  }

  return { abrir, fechar, ligar };
}
