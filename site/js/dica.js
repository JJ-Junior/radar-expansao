// Tooltip único do site: compacto, com seta para o alvo, que nunca sai da tela.
// Aparece no hover, no foco por teclado e no toque; some ao sair, ao rolar e com Esc.
// O conteúdo é montado com textContent (os rótulos vêm de dados, nunca viram HTML).

const MARGEM = 8;        // distância mínima das bordas da tela
const AFASTAMENTO = 12;  // distância entre a seta e o alvo

let caixa = null;
let corpo = null;
let seta = null;
let alvoAtual = null;

function criar() {
  if (caixa) return;
  caixa = document.createElement("div");
  caixa.className = "dica";
  caixa.id = "dica-global";
  caixa.setAttribute("role", "tooltip");
  caixa.hidden = true;
  corpo = document.createElement("div");
  corpo.className = "dica__corpo";
  seta = document.createElement("span");
  seta.className = "dica__seta";
  caixa.append(corpo, seta);
  document.body.append(caixa);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") esconderDica(); });
  window.addEventListener("scroll", esconderDica, { passive: true });
  window.addEventListener("resize", esconderDica);
}

/** Retângulo do alvo: um elemento, um ponto do ponteiro ou um retângulo pronto. */
function retangulo(ancora) {
  if (ancora instanceof Element) return ancora.getBoundingClientRect();
  if ("clientX" in ancora) return { left: ancora.clientX, top: ancora.clientY, right: ancora.clientX, bottom: ancora.clientY, width: 0, height: 0 };
  return ancora;
}

/** Mostra o tooltip apontando para `ancora` com o nó `conteudo`. */
export function mostrarDica(ancora, conteudo, { alvo = null } = {}) {
  criar();
  corpo.replaceChildren(conteudo);
  caixa.hidden = false;
  if (alvoAtual && alvoAtual !== alvo) alvoAtual.removeAttribute("aria-describedby");
  alvoAtual = alvo;
  alvo?.setAttribute("aria-describedby", caixa.id);

  const r = retangulo(ancora);
  const largura = caixa.offsetWidth;
  const altura = caixa.offsetHeight;
  const vw = document.documentElement.clientWidth;
  const vh = window.innerHeight;
  const centro = r.left + r.width / 2;

  // acima do alvo; se não couber, abaixo
  const cabeAcima = r.top - altura - AFASTAMENTO >= MARGEM + 56;  // 56: deixa o cabeçalho fixo livre
  const topo = cabeAcima ? r.top - altura - AFASTAMENTO : Math.min(r.bottom + AFASTAMENTO, vh - altura - MARGEM);
  const esquerda = Math.min(Math.max(MARGEM, centro - largura / 2), vw - largura - MARGEM);
  caixa.classList.toggle("dica--abaixo", !cabeAcima);
  caixa.style.transform = `translate(${Math.round(esquerda)}px, ${Math.round(topo)}px)`;
  seta.style.left = `${Math.min(Math.max(12, centro - esquerda), largura - 12)}px`;
}

export function esconderDica() {
  if (!caixa || caixa.hidden) return;
  caixa.hidden = true;
  alvoAtual?.removeAttribute("aria-describedby");
  alvoAtual = null;
}

/**
 * Liga o tooltip a um elemento: hover, foco por teclado e toque.
 * `montar` devolve o conteúdo (chamado a cada exibição, para refletir o estado atual).
 */
export function ligarDica(elemento, montar) {
  const abrir = () => mostrarDica(elemento, montar(), { alvo: elemento });
  elemento.addEventListener("pointerenter", (e) => { if (e.pointerType !== "touch") abrir(); });
  elemento.addEventListener("pointerleave", (e) => { if (e.pointerType !== "touch") esconderDica(); });
  elemento.addEventListener("focus", abrir);
  elemento.addEventListener("blur", esconderDica);
  elemento.addEventListener("pointerup", (e) => { if (e.pointerType === "touch") abrir(); });
}

// ------------------------------------------------------------------ montagem do conteúdo

function el(tag, classe, texto) {
  const n = document.createElement(tag);
  if (classe) n.className = classe;
  if (texto !== undefined && texto !== null) n.textContent = texto;
  return n;
}

/**
 * Conteúdo padrão: título, chip opcional e linhas em grade.
 * linhas: [{ rotulo, valor, detalhe?, estado?: "verde"|"amarelo"|"vermelho", estadoTexto? }]
 */
export function conteudoDica({ titulo, chip = null, linhas = [], nota = null }) {
  const raiz = document.createDocumentFragment();
  const topo = el("div", "dica__topo");
  topo.append(el("strong", "dica__titulo", titulo));
  if (chip) {
    const c = el("span", `dica__chip dica__chip--${chip.estado ?? "neutro"}`, chip.texto);
    topo.append(c);
  }
  raiz.append(topo);
  if (linhas.length) {
    const grade = el("div", "dica__grade");
    for (const l of linhas) {
      grade.append(el("span", "dica__rotulo", l.rotulo), el("span", "dica__valor", l.valor), el("span", "dica__detalhe", l.detalhe ?? ""));
      const estado = el("span", "dica__estado");
      if (l.estado) {
        estado.append(el("i", `ponto-estado ponto-estado--${l.estado}`), document.createTextNode(l.estadoTexto ?? ""));
      }
      grade.append(estado);
      if (l.sub) grade.append(el("span", "dica__sub", l.sub));   // descrição curta, na linha toda
    }
    raiz.append(grade);
  }
  if (nota) raiz.append(el("p", "dica__nota", nota));
  return raiz;
}
