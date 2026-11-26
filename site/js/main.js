// Ponto de entrada: carrega os dados, liga as seções e cuida do endereço da ficha (?municipio=<código IBGE>).

import { carregarDados, carregarMalha } from "./dados.js";
import { criarMapa } from "./mapa.js";
import { criarFicha } from "./ficha.js";
import { criarRanking } from "./ranking.js";
import { criarMacro } from "./macro.js";
import { criarBusca } from "./busca.js";
import { desenharArquitetura, desenharMetodologia } from "./metodologia.js";
import { STATUS_RECOMENDACAO, iconeStatus } from "./indicadores.js";
import { dataCurta, decimal, inteiro, mesPorExtenso, paraData } from "./formato.js";

const TITULO_BASE = "Radar de Expansão";
const TITULO_INICIAL = document.title;

// ---------------------------------------------------------------- tema claro/escuro
function ligarTema() {
  const botao = document.getElementById("botao-tema");
  const escuroAgora = () => {
    const t = document.documentElement.dataset.theme;
    return t ? t === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  };
  botao.addEventListener("click", () => {
    const novo = escuroAgora() ? "light" : "dark";
    document.documentElement.dataset.theme = novo;
    try { localStorage.setItem("radar-tema", novo); } catch { /* navegação privada: segue sem salvar */ }
    document.dispatchEvent(new Event("tema-alterado"));
  });
}

// ---------------------------------------------------------------- KPIs do topo
function preencherKpis(estado, momentoAtual) {
  const kpi = (nome) => document.querySelector(`[data-kpi="${nome}"]`);
  const { meta, ranking, indicadores } = estado;
  const previa = meta.eh_previa ? " · prévia" : "";

  kpi("universo").textContent = inteiro(ranking.length);
  kpi("universo-nota").textContent = `dos ${inteiro(indicadores.length)} municípios têm ${inteiro(meta.populacao_minima_universo)} hab. ou mais`;

  const primeiro = ranking[0];
  if (primeiro) {
    kpi("topo").innerHTML = `<a href="?municipio=${primeiro.municipio_id}#ficha" data-id="${primeiro.municipio_id}">${primeiro.municipio_nome}</a>`;
    kpi("topo-nota").textContent = `${primeiro.uf_sigla} · nota ${decimal(primeiro.nota_final, 1)}${previa}`;
  }

  if (momentoAtual) {
    const status = STATUS_RECOMENDACAO[momentoAtual.recomendacao];
    kpi("momento").innerHTML = `<span class="kpi__status">${iconeStatus(status)}<span>${momentoAtual.recomendacao}</span></span>`;
    kpi("momento-nota").textContent = `referência: ${mesPorExtenso(paraData(momentoAtual.mes))}${previa}`;
  }

  kpi("data").textContent = dataCurta(meta.gerado_em);
  const p = meta.periodos ?? {};
  kpi("data-nota").textContent = [p.populacao && `população ${p.populacao}`, p.pib && `PIB ${p.pib}`, p.academias && `academias ${p.academias}`].filter(Boolean).join(" · ");

  document.getElementById("hero-lede").textContent =
    `Seis critérios do IBGE dão nota a ${inteiro(ranking.length)} cidades com ${inteiro(meta.populacao_minima_universo)} habitantes ou mais. ` +
    "Juros, inflação e dólar dizem se é hora de abrir ou de segurar o caixa.";
  document.getElementById("rodape-gerado").textContent = `Dados gerados em ${dataCurta(meta.gerado_em)} (${meta.eh_previa ? "prévia direto das APIs" : "camada gold"}).`;
}

// ---------------------------------------------------------------- início
async function iniciar() {
  ligarTema();
  let estado;
  try {
    estado = await carregarDados();
  } catch (erro) {
    document.getElementById("kpis").insertAdjacentHTML("afterend",
      `<p class="aviso-previa">Não foi possível carregar os dados (${erro.message}). Abra o site por um servidor local — veja site/README.md.</p>`);
    throw erro;
  }

  if (estado.meta.eh_previa) {
    document.getElementById("aviso-previa").hidden = false;
    for (const el of document.querySelectorAll("[data-previa]")) el.hidden = false;
  }

  let mapa = null;
  const ficha = criarFicha({ estado, aoSelecionar: selecionar });

  /** Abre a ficha, atualiza o endereço e o título da aba. */
  function selecionar(id, { rolar = true, historico = true } = {}) {
    const m = estado.porId.get(id);
    if (!m) return;
    ficha.mostrar(id);
    mapa?.selecionar(id);
    document.title = `${m.municipio_nome} (${m.uf_sigla}) · ${TITULO_BASE}`;
    if (historico) history.pushState({ id }, "", `?municipio=${id}#ficha`);
    if (rolar) document.getElementById("ficha").scrollIntoView({ block: "start" });
  }

  const macro = criarMacro({ estado });
  preencherKpis(estado, macro.atual);
  criarRanking({ estado, aoSelecionar: selecionar });
  criarBusca({ estado, aoSelecionar: selecionar });
  desenharMetodologia({ estado });
  desenharArquitetura({ estado });

  document.querySelector('[data-kpi="topo"]').addEventListener("click", (e) => {
    const a = e.target.closest("a[data-id]");
    if (a) { e.preventDefault(); selecionar(Number(a.dataset.id)); }
  });

  // endereço com ?municipio= abre a ficha direto; sem ele, mostra o 1º do ranking como exemplo
  const daUrl = () => Number(new URLSearchParams(location.search).get("municipio")) || null;
  const inicial = daUrl();
  if (inicial && estado.porId.has(inicial)) selecionar(inicial, { historico: false });
  else if (estado.ranking[0]) ficha.mostrar(estado.ranking[0].municipio_id, { exemplo: true });

  window.addEventListener("popstate", () => {
    const id = daUrl();
    if (id && estado.porId.has(id)) selecionar(id, { historico: false, rolar: false });
    else document.title = TITULO_INICIAL;
  });

  // a malha (~1,4 MB) chega depois sem travar o resto da página
  try {
    const topo = await carregarMalha();
    mapa = criarMapa({ topo, estado, aoSelecionar: selecionar });
    const id = daUrl();
    if (id) mapa.selecionar(id);
  } catch (erro) {
    document.getElementById("mapa-carregando").textContent = `Não foi possível carregar o mapa (${erro.message}).`;
    throw erro;
  }
}

iniciar();
