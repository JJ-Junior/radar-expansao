// Busca de município (combobox acessível: setas, Enter, Esc).

import { normalizar, ordinal } from "./formato.js";

const MAXIMO = 8;

export function criarBusca({ estado, aoSelecionar }) {
  const campo = document.getElementById("busca-campo");
  const lista = document.getElementById("busca-lista");
  const indice = estado.indicadores.map((m) => ({
    id: m.municipio_id,
    texto: normalizar(`${m.municipio_nome} ${m.uf_sigla}`),
    nome: m.municipio_nome,
    uf: m.uf_sigla,
    populacao: m.populacao ?? 0,
  }));
  let resultados = [];
  let ativo = -1;

  function fechar() {
    lista.hidden = true;
    campo.setAttribute("aria-expanded", "false");
    campo.removeAttribute("aria-activedescendant");
    ativo = -1;
  }

  function desenhar() {
    lista.innerHTML = resultados.map((r, i) => {
      const m = estado.porId.get(r.id);
      const extra = m.ranking ? `${ordinal(m.ranking.posicao_brasil)} no ranking` : "fora do ranking";
      return `<li role="option" id="busca-op-${i}" data-id="${r.id}" aria-selected="${i === ativo}">
        <span>${r.nome} <span class="discreto">${r.uf}</span></span><span class="discreto">${extra}</span></li>`;
    }).join("") || `<li role="option" aria-disabled="true" class="discreto">Nenhum município encontrado</li>`;
    lista.hidden = false;
    campo.setAttribute("aria-expanded", "true");
    if (ativo >= 0) campo.setAttribute("aria-activedescendant", `busca-op-${ativo}`);
    else campo.removeAttribute("aria-activedescendant");
  }

  function procurar() {
    const termo = normalizar(campo.value);
    if (termo.length < 2) { fechar(); return; }
    // começa com o termo vem antes de contém o termo; depois, os mais populosos
    resultados = indice
      .filter((r) => r.texto.includes(termo))
      .sort((a, b) => (b.texto.startsWith(termo) - a.texto.startsWith(termo)) || b.populacao - a.populacao)
      .slice(0, MAXIMO);
    ativo = resultados.length ? 0 : -1;
    desenhar();
  }

  function escolher(id) {
    const m = estado.porId.get(id);
    campo.value = `${m.municipio_nome} (${m.uf_sigla})`;
    fechar();
    aoSelecionar(id);
  }

  campo.addEventListener("input", procurar);
  campo.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (lista.hidden) { procurar(); return; }
      e.preventDefault();
      const n = resultados.length;
      if (!n) return;
      ativo = (ativo + (e.key === "ArrowDown" ? 1 : -1) + n) % n;
      desenhar();
    } else if (e.key === "Enter" && ativo >= 0 && resultados[ativo]) {
      e.preventDefault();
      escolher(resultados[ativo].id);
    } else if (e.key === "Escape") {
      fechar();
    }
  });
  lista.addEventListener("mousedown", (e) => {
    const item = e.target.closest("li[data-id]");
    if (item) { e.preventDefault(); escolher(Number(item.dataset.id)); }
  });
  campo.addEventListener("blur", () => setTimeout(fechar, 120));
}
