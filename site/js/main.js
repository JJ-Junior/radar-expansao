// Ponto de entrada: carrega os dados, liga as seções, o movimento e o endereço da ficha (?municipio=<código IBGE>).

import { carregarDados, carregarMalhas } from "./dados.js";
import { animarHero, atualizarGatilhos, contar, iniciarMovimento, ligarAncoras, medirCabecalho, revelarAoRolar, rolarAte } from "./movimento.js";
import { criarRadarHero } from "./hero-radar.js";
import { criarMacro } from "./macro.js";
import { criarMapaRegioes } from "./mapa-regioes.js";
import { criarCards } from "./cards.js";
import { criarExplorar } from "./explorar.js";
import { criarFicha } from "./ficha.js";
import { criarBusca } from "./busca.js";
import { desenharCamadas, desenharCriterios } from "./metodologia.js";
import { STATUS_RECOMENDACAO } from "./indicadores.js";
import { dataCurta, decimal, inteiro, mesPorExtenso, paraData, porcento, reaisCentavos } from "./formato.js";

const TITULO_BASE = "Radar de Expansão · Squad DROP Database";
const TITULO_INICIAL = document.title;

// ---------------------------------------------------------------- tema (escuro é o padrão da marca)
function ligarTema() {
  document.getElementById("botao-tema").addEventListener("click", () => {
    const novo = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = novo;
    try { localStorage.setItem("radar-tema", novo); } catch { /* navegação privada: segue sem salvar */ }
    document.dispatchEvent(new Event("tema-alterado"));
  });
}

// ---------------------------------------------------------------- KPIs do hero
function preencherKpis(estado, momentoAtual) {
  const kpi = (nome) => document.querySelector(`[data-kpi="${nome}"]`);
  const { meta, ranking, indicadores } = estado;
  const previa = meta.eh_previa ? " · prévia" : "";

  contar(kpi("universo"), ranking.length, (v) => inteiro(Math.round(v)));
  kpi("universo-nota").textContent = `de ${inteiro(indicadores.length)} municípios · ${inteiro(meta.populacao_minima_universo)}+ hab.`;

  const primeiro = ranking[0];
  if (primeiro) {
    kpi("topo").innerHTML = `<a href="?municipio=${primeiro.municipio_id}#ficha" data-id="${primeiro.municipio_id}">${primeiro.municipio_nome}</a>`;
    kpi("topo-nota").textContent = `${primeiro.uf_sigla} · nota ${decimal(primeiro.nota_final, 1)}${previa}`;
  }
  if (momentoAtual) {
    kpi("momento").innerHTML = `<i class="ponto-estado ponto-estado--${STATUS_RECOMENDACAO[momentoAtual.recomendacao]}"></i><span>${momentoAtual.recomendacao}</span>`;
    kpi("momento-nota").textContent = `${mesPorExtenso(paraData(momentoAtual.mes))}${previa}`;
  }
  kpi("data").textContent = dataCurta(meta.gerado_em);
  const p = meta.periodos ?? {};
  kpi("data-nota").textContent = [p.populacao && `população ${p.populacao}`, p.pib && `PIB ${p.pib}`, p.academias && `academias ${p.academias}`].filter(Boolean).join(" · ");

  document.getElementById("rodape-gerado").textContent = `Dados gerados em ${dataCurta(meta.gerado_em)} (${meta.eh_previa ? "prévia direto das APIs" : "camada gold"}).`;
}

// ---------------------------------------------------------------- letreiro com números reais
function montarLetreiro(estado, { atual, linhaAtual }) {
  const ultimoDolar = [...estado.macro].reverse().find((l) => l.dolar_medio !== null);
  const primeiro = estado.ranking[0];
  const itens = [
    linhaAtual && ["Selic", `${decimal(linhaAtual.selic_meta, 2)}% a.a.`],
    linhaAtual && ["IPCA 12 meses", porcento(linhaAtual.ipca_12m, 2)],
    ultimoDolar && ["Dólar", reaisCentavos(ultimoDolar.dolar_medio, 2)],
    ["Cidades no radar", inteiro(estado.ranking.length)],
    primeiro && ["1ª do ranking", `${primeiro.municipio_nome} ${decimal(primeiro.nota_final, 1)}`],
    atual && ["Momento", atual.recomendacao],
    estado.recomendadas.length && [`${estado.recomendadas.length} recomendadas`, estado.recomendadas.map((r) => r.municipio_nome).join(" · ")],
  ].filter(Boolean);
  const grupo = (oculto) => `<div class="letreiro__grupo" ${oculto ? 'aria-hidden="true"' : ""}>${itens.map(([r, v]) => `<span class="letreiro__item">${r}<b>${v}</b></span>`).join("")}</div>`;
  // dois grupos iguais: o trilho anda metade da largura e recomeça sem emenda
  document.getElementById("letreiro").innerHTML = grupo(false) + grupo(true);
}

// ---------------------------------------------------------------- início
async function iniciar() {
  ligarTema();
  iniciarMovimento();
  ligarAncoras();

  let estado;
  try {
    estado = await carregarDados();
  } catch (erro) {
    document.getElementById("kpis").insertAdjacentHTML("afterend",
      `<p class="previa">Não foi possível carregar os dados (${erro.message}). Abra o site por um servidor local — veja site/README.md.</p>`);
    throw erro;
  }
  if (estado.meta.eh_previa) document.getElementById("aviso-previa").hidden = false;
  medirCabecalho();

  const ficha = criarFicha({ estado, aoSelecionar: selecionar });

  /** Abre a ficha, atualiza o endereço e o título da aba. */
  function selecionar(id, { rolar = true, historico = true } = {}) {
    const m = estado.porId.get(id);
    if (!m) return;
    ficha.mostrar(id);
    document.title = `${m.municipio_nome} (${m.uf_sigla}) · ${TITULO_BASE}`;
    if (historico) history.pushState({ id }, "", `?municipio=${id}#ficha`);
    atualizarGatilhos();
    if (rolar) rolarAte(document.getElementById("ficha"));
  }

  const macro = criarMacro({ estado });
  preencherKpis(estado, macro.atual);
  montarLetreiro(estado, macro);
  criarCards({ estado, aoSelecionar: selecionar });
  criarBusca({ estado, aoSelecionar: selecionar });
  desenharCriterios({ estado });
  desenharCamadas({ estado });

  document.querySelector('[data-kpi="topo"]').addEventListener("click", (e) => {
    const a = e.target.closest("a[data-id]");
    if (a) { e.preventDefault(); selecionar(Number(a.dataset.id)); }
  });

  // ?municipio= abre a ficha direto; sem ele, a ficha mostra a 1ª do ranking como exemplo
  const daUrl = () => Number(new URLSearchParams(location.search).get("municipio")) || null;
  const inicial = daUrl();
  if (inicial && estado.porId.has(inicial)) selecionar(inicial, { historico: false, rolar: false });
  else if (estado.ranking[0]) ficha.mostrar((estado.recomendadas[0] ?? estado.ranking[0]).municipio_id, { exemplo: true });
  window.addEventListener("popstate", () => {
    const id = daUrl();
    if (id && estado.porId.has(id)) selecionar(id, { historico: false, rolar: false });
    else document.title = TITULO_INICIAL;
  });

  animarHero();
  revelarAoRolar();

  // malhas: as UFs primeiro (radar do hero), depois o resto (mapa por regiões)
  try {
    const { ufs } = await carregarMalhas(["ufs"]);
    criarRadarHero({ canvas: document.getElementById("hero-radar"), topoUfs: ufs, cidades: estado.universo });
    criarExplorar({ estado, topoUfs: ufs, aoSelecionar: selecionar });
    const outras = await carregarMalhas(["regioes", "intermediarias", "imediatas"]);
    criarMapaRegioes({ topos: { ufs, ...outras }, estado, aoSelecionar: selecionar });
  } catch (erro) {
    const aviso = document.getElementById("mapa-carregando");
    if (aviso) aviso.textContent = `Não foi possível carregar o mapa (${erro.message}).`;
    throw erro;
  } finally {
    atualizarGatilhos();
    // endereço com ?municipio=: vai direto à ficha depois que o layout assentou (mapa e seções presas)
    if (inicial && estado.porId.has(inicial)) {
      rolarAte(document.getElementById("ficha"), { imediato: true });
    }
  }
}

iniciar();
