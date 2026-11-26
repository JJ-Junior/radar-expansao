// Cidades em cards: primeiro as 5 unidades recomendadas (lista oficial da gold), depois o ranking geral por região.
// Desktop: grade (5 colunas, ou 3 + 2) com todos os cards inteiros na tela.
// Celular: carrossel nativo com "snap" e aviso de que rola para o lado.

import { CRITERIOS, REGIOES, pesoDoCriterio } from "./indicadores.js";
import { compacto, decimal } from "./formato.js";
import { graficoRadar } from "./grafico-radar.js";
import { conteudoDica, ligarDica } from "./dica.js";
import { foraDaLista, motivoFora, quantidadeRecomendada, travaDeRenda } from "./recomendacao.js";

const QUANTIDADE = 10;
const RECOMENDADAS = "recomendadas";

export function criarCards({ estado, aoSelecionar }) {
  const trilho = document.getElementById("top-trilho");
  const filtro = document.getElementById("top-filtro");
  const titulo = document.getElementById("titulo-top");
  const explica = document.getElementById("top-explica");
  const fora = document.getElementById("top-fora");
  const temLista = estado.recomendadas.length > 0;
  let escolha = temLista ? RECOMENDADAS : "";

  const opcoes = [
    ...(temLista ? [{ valor: RECOMENDADAS, rotulo: `${estado.recomendadas.length} recomendadas`, nome: "Unidades recomendadas" }] : []),
    { valor: "", rotulo: "Brasil", nome: "Ranking do Brasil" },
    ...REGIOES.map((r) => ({ valor: r.sigla, rotulo: r.sigla, nome: `Ranking da região ${r.nome}` })),
  ];
  filtro.innerHTML = opcoes.map((o) =>
    `<button type="button" role="radio" aria-checked="${o.valor === escolha}" data-valor="${o.valor}" aria-label="${o.nome}">${o.rotulo}</button>`).join("");

  /** Selo sempre no mesmo lugar: recomendada, ou o motivo curto de estar fora da lista. */
  function selo(r) {
    if (r.recomendado_top5) return `<p class="selo selo--recomendada">Recomendada nº ${r.ordem_recomendacao}</p>`;
    if (!temLista) return `<p class="selo selo--vazio" aria-hidden="true">&nbsp;</p>`;
    const motivo = motivoFora(estado, r) ?? "";
    const curto = motivo.startsWith("poder de compra") ? "Fora da lista · trava de renda"
      : motivo.startsWith("mesma região") ? "Fora da lista · região já escolhida" : "Fora da lista";
    return `<p class="selo selo--fora" title="${motivo}">${curto}</p>`;
  }

  const cartao = (c, rotulo) => `
    <li class="cartao-cidade ${c.ranking.recomendado_top5 ? "cartao-cidade--recomendada" : ""}">
      <div class="cartao-cidade__cabeca">
        <div class="cartao-cidade__linha"><span class="cartao-cidade__onde">${c.uf_sigla} · ${c.regiao_imediata_nome ?? ""}</span><span class="cartao-cidade__pos" aria-hidden="true">${rotulo}</span></div>
        <h3 class="cartao-cidade__nome">${c.municipio_nome}</h3>
        ${selo(c.ranking)}
      </div>
      <div class="cartao-cidade__radar" tabindex="0" data-id="${c.municipio_id}">${graficoRadar(c.ranking, { tamanho: 220 })}</div>
      <dl class="cartao-cidade__numeros">
        <div class="cartao-cidade__nota"><dt>Nota</dt><dd>${decimal(c.ranking.nota_final, 1)}</dd></div>
        <div><dt>Nº Brasil</dt><dd>${c.ranking.posicao_brasil}º</dd></div>
        <div><dt>Habitantes</dt><dd>${compacto(c.populacao)}</dd></div>
      </dl>
      <button class="botao botao--fantasma" type="button" data-id="${c.municipio_id}">Abrir ficha</button>
    </li>`;

  /** As notas dos 6 critérios no tooltip do radar do card. */
  function ligarRadares() {
    for (const el of trilho.querySelectorAll(".cartao-cidade__radar")) {
      const c = estado.porId.get(Number(el.dataset.id));
      el.setAttribute("aria-label", `Notas de ${c.municipio_nome}; foco mostra os valores`);
      ligarDica(el, () => conteudoDica({
        titulo: `Notas de ${c.municipio_nome}`,
        chip: { texto: `nota final ${decimal(c.ranking.nota_final, 1)}` },
        linhas: CRITERIOS.map((k) => ({
          rotulo: k.nome, valor: decimal(c.ranking[`nota_${k.criterio}`], 0),
          detalhe: `peso ${Math.round((pesoDoCriterio(estado.criterios, k.criterio) ?? 0) * 100)}%`,
        })),
        nota: "Notas de 0 a 100: percentil no universo do ranking.",
      }));
    }
  }

  function desenharFora() {
    const lista = escolha === RECOMENDADAS ? foraDaLista(estado) : [];
    fora.hidden = !lista.length;
    if (!lista.length) return;
    fora.innerHTML = `<p class="top-fora__titulo">Por que não ${lista.map(({ r }) => r.municipio_nome).join(" e ")}?</p>
      <ul>${lista.map(({ r, motivo }) => `<li><button type="button" data-id="${r.municipio_id}"><b>${r.posicao_brasil}º ${r.municipio_nome}</b> <span>${r.uf_sigla}</span></button> — ${motivo}.</li>`).join("")}</ul>
      <p class="discreto">Só entram cidades com nota de poder de compra a partir de ${decimal(travaDeRenda(estado), 0)}, e no máximo uma por região imediata. O ranking completo não muda.</p>`;
  }

  function desenhar() {
    let lista;
    if (escolha === RECOMENDADAS) {
      titulo.textContent = `As ${estado.recomendadas.length} recomendadas`;
      explica.textContent = `A lista para abrir ${quantidadeRecomendada(estado)} unidades: as melhores do ranking, uma por região imediata do IBGE, ` +
        `com trava de renda (poder de compra a partir de ${decimal(travaDeRenda(estado), 0)}). Academia é gasto que o aluno corta primeiro: sem renda, população não vira matrícula.`;
      lista = estado.recomendadas.map((r) => estado.porId.get(r.municipio_id)).filter(Boolean)
        .map((c) => cartao(c, String(c.ranking.ordem_recomendacao).padStart(2, "0")));
    } else {
      const regiao = REGIOES.find((r) => r.sigla === escolha);
      titulo.textContent = regiao ? `As mais prontas do ${regiao.nome}` : "As mais prontas do Brasil";
      explica.textContent = "Ranking geral pela nota final, sem a trava de renda e sem o limite de uma cidade por região imediata.";
      lista = estado.universo.filter((c) => !escolha || c.regiao_sigla === escolha).slice(0, QUANTIDADE)
        .map((c, i) => cartao(c, String(i + 1).padStart(2, "0")));
    }
    trilho.innerHTML = lista.join("");
    trilho.dataset.quantidade = lista.length;
    trilho.scrollLeft = 0;
    ligarRadares();
    desenharFora();
    window.ScrollTrigger?.refresh();
  }

  filtro.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    escolha = b.dataset.valor;
    for (const x of filtro.querySelectorAll("button")) x.setAttribute("aria-checked", x === b);
    desenhar();
  });
  const abrir = (e) => {
    const b = e.target.closest("button[data-id]");
    if (b) aoSelecionar(Number(b.dataset.id));
  };
  trilho.addEventListener("click", abrir);
  fora.addEventListener("click", abrir);

  desenhar();
}
