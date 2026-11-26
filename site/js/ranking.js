// Ranking filtrável por região e UF + grade com os três melhores de cada estado.

import { NOMES_UF, REGIOES } from "./indicadores.js";
import { decimal, inteiro } from "./formato.js";

export function criarRanking({ estado, aoSelecionar }) {
  const regiaoEl = document.getElementById("filtro-regiao");
  const ufEl = document.getElementById("filtro-uf");
  const qtdEl = document.getElementById("filtro-qtd");
  const corpo = document.querySelector("#tabela-ranking tbody");
  const grade = document.getElementById("grade-uf");

  let regiao = "";
  const opcoes = [{ sigla: "", nome: "Brasil" }, ...REGIOES];
  regiaoEl.innerHTML = opcoes.map((o) =>
    `<button type="button" role="radio" data-regiao="${o.sigla}" aria-checked="${o.sigla === ""}" tabindex="${o.sigla === "" ? 0 : -1}">${o.sigla || o.nome}</button>`
  ).join("");
  for (const b of regiaoEl.querySelectorAll("button")) {
    const o = opcoes.find((x) => x.sigla === b.dataset.regiao);
    b.setAttribute("aria-label", o.nome);
  }

  const ufsDaRegiao = () => estado.ufs.filter((uf) => !regiao || estado.ranking.some((r) => r.uf_sigla === uf && r.regiao_sigla === regiao));
  function preencherUfs() {
    const atual = ufEl.value;
    ufEl.innerHTML = `<option value="">Todos</option>` + ufsDaRegiao().map((uf) => `<option value="${uf}">${NOMES_UF[uf] ?? uf}</option>`).join("");
    if (ufsDaRegiao().includes(atual)) ufEl.value = atual;
  }

  const linhaNota = (v) =>
    `<div class="barra-nota"><div class="barra-nota__trilho"><div class="barra-nota__valor" style="width:${v}%"></div></div><b>${decimal(v, 1)}</b></div>`;

  function desenharTabela() {
    const uf = ufEl.value;
    const qtd = Number(qtdEl.value);
    const filtrado = estado.ranking.filter((r) => (!regiao || r.regiao_sigla === regiao) && (!uf || r.uf_sigla === uf));
    corpo.innerHTML = filtrado.slice(0, qtd).map((r, i) => `
      <tr data-id="${r.municipio_id}">
        <td class="num pos">${i + 1}</td>
        <td class="municipio"><button type="button" data-id="${r.municipio_id}">${r.municipio_nome}</button><small>${r.uf_sigla}${regiao || uf ? ` (${r.posicao_brasil}º)` : ""}</small>${r.dados_incompletos ? '<span class="icone-alerta" title="Algum critério recebeu nota neutra por falta de dado">⚠ dados incompletos</span>' : ""}</td>
        <td class="num ocultar-celular">${inteiro(r.populacao)}</td>
        <td>${linhaNota(r.nota_final)}</td>
      </tr>`).join("") || `<tr><td colspan="4" class="discreto">Nenhum município neste recorte.</td></tr>`;
  }

  function desenharGrade() {
    const porUf = window.d3.group(estado.ranking, (r) => r.uf_sigla);
    const ordemRegiao = REGIOES.map((r) => r.sigla);
    const ufs = [...porUf.keys()].sort((a, b) =>
      ordemRegiao.indexOf(porUf.get(a)[0].regiao_sigla) - ordemRegiao.indexOf(porUf.get(b)[0].regiao_sigla) || a.localeCompare(b));
    grade.innerHTML = ufs.map((uf) => {
      const lista = porUf.get(uf); // já vem ordenado pela posição no Brasil
      return `<article class="cartao-uf">
        <header><h4 title="${NOMES_UF[uf] ?? uf}">${uf}</h4><span>${lista.length} ${lista.length === 1 ? "município" : "municípios"}</span></header>
        <ol>${lista.slice(0, 3).map((r) => `<li><button type="button" data-id="${r.municipio_id}">
          <span class="nome">${r.municipio_nome}</span><span class="v">${decimal(r.nota_final, 1)}</span>
          <span class="trilho"><i style="width:${r.nota_final}%"></i></span></button></li>`).join("")}</ol>
      </article>`;
    }).join("");
  }

  regiaoEl.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    regiao = b.dataset.regiao;
    for (const x of regiaoEl.querySelectorAll("button")) {
      x.setAttribute("aria-checked", x === b);
      x.tabIndex = x === b ? 0 : -1;
    }
    preencherUfs();
    desenharTabela();
  });
  regiaoEl.addEventListener("keydown", (e) => {
    if (!["ArrowRight", "ArrowLeft"].includes(e.key)) return;
    e.preventDefault();
    const botoes = [...regiaoEl.querySelectorAll("button")];
    const i = botoes.findIndex((b) => b.getAttribute("aria-checked") === "true");
    const novo = botoes[(i + (e.key === "ArrowRight" ? 1 : -1) + botoes.length) % botoes.length];
    novo.click();
    novo.focus();
  });
  ufEl.addEventListener("change", desenharTabela);
  qtdEl.addEventListener("change", desenharTabela);

  const clique = (e) => {
    const alvo = e.target.closest("[data-id]");
    if (alvo) aoSelecionar(Number(alvo.dataset.id));
  };
  corpo.addEventListener("click", clique);
  grade.addEventListener("click", clique);

  preencherUfs();
  desenharTabela();
  desenharGrade();
}
