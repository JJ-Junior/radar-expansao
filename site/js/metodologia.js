// Critérios (painel em estilo radar: setor = peso), fórmula da nota e camadas do Lakehouse.
// Pesos, descrições e fontes vêm de ranking_criterio.json; nada é fixado aqui além da ordem de exibição.

import { COMPONENTES, CRITERIOS, FRASE_PERCENTIL, nomeComponente, pesoDoCriterio, textosCriterios } from "./indicadores.js";
import { decimal, inteiro } from "./formato.js";
import { quantidadeRecomendada, travaDeRenda } from "./recomendacao.js";
import { movimentoLigado } from "./movimento.js";

const R_INTERNO = 92, R_EXTERNO = 250, FOLGA = 1.6;   // raios e espaço entre setores (graus)

function arco(r0, r1, a0, a1) {
  const p = (r, a) => [r * Math.cos(a), r * Math.sin(a)].map((v) => v.toFixed(2)).join(" ");
  const grande = a1 - a0 > Math.PI ? 1 : 0;
  return `M${p(r1, a0)} A${r1} ${r1} 0 ${grande} 1 ${p(r1, a1)} L${p(r0, a1)} A${r0} ${r0} 0 ${grande} 0 ${p(r0, a0)}Z`;
}

export function desenharCriterios({ estado }) {
  // um setor por componente da gold (a riqueza local aparece como nível + tendência)
  const criterios = estado.criterios.map((c, i) => ({
    ...c, peso: Number(c.peso), codigo: `CRT-0${i + 1}`, nome: nomeComponente(c),
    descricao: COMPONENTES[c.criterio]?.descricao ?? c.descricao,
  }));
  const grupos = new Set(estado.criterios.map((c) => c.grupo ?? c.criterio)).size;
  const rad = (g) => (g * Math.PI) / 180;

  // ------------------------------------------------------------ painel em radar
  let angulo = -90;
  const setores = criterios.map((c) => {
    const graus = (c.peso ?? 0) * 360;
    const a0 = rad(angulo + FOLGA / 2), a1 = rad(angulo + graus - FOLGA / 2), meio = (a0 + a1) / 2;
    angulo += graus;
    const fora = [Math.cos(meio) * 284, Math.sin(meio) * 284];
    const dentro = [Math.cos(meio) * 172, Math.sin(meio) * 172];
    const ancora = Math.abs(fora[0]) < 20 ? "middle" : fora[0] > 0 ? "start" : "end";
    return `<g class="setor-grupo" data-criterio="${c.criterio}">
      <path class="setor" d="${arco(R_INTERNO, R_EXTERNO, a0, a1)}"><title>${c.nome}: peso ${Math.round(c.peso * 100)}%</title></path>
      <text class="peso" x="${dentro[0]}" y="${dentro[1]}" text-anchor="middle" dominant-baseline="middle">${Math.round(c.peso * 100)}%</text>
      <text class="nome" x="${fora[0]}" y="${fora[1]}" text-anchor="${ancora}" dominant-baseline="middle">${c.nome}</text>
    </g>`;
  }).join("");
  const aneis = [R_INTERNO, 140, 195, R_EXTERNO].map((r, i) => `<circle class="anel ${i === 3 ? "anel--forte" : ""}" r="${r}"/>`).join("");
  const tiques = Array.from({ length: 72 }, (_, i) => {
    const a = rad(i * 5), r0 = i % 6 === 0 ? 256 : 258, r1 = i % 6 === 0 ? 268 : 263;
    return `<line class="tique" x1="${r0 * Math.cos(a)}" y1="${r0 * Math.sin(a)}" x2="${r1 * Math.cos(a)}" y2="${r1 * Math.sin(a)}"/>`;
  }).join("");
  document.getElementById("ideal-radar").innerHTML = `
    <svg class="hud" viewBox="-340 -320 680 640" role="img" aria-label="Pesos dos critérios: ${criterios.map((c) => `${c.nome} ${Math.round(c.peso * 100)}%`).join(", ")}">
      <defs><linearGradient id="hud-varredura" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="var(--limao)" stop-opacity="0"/><stop offset="1" stop-color="var(--limao)" stop-opacity=".22"/></linearGradient></defs>
      ${aneis}${tiques}
      <path class="varredura" d="${arco(0, R_EXTERNO, rad(-40), rad(0))}"/>
      ${setores}
      <text class="centro-num" text-anchor="middle" y="8" font-size="64">${grupos}</text>
      <text class="centro-txt" text-anchor="middle" y="36">critérios</text>
    </svg>`;

  document.getElementById("ideal-lista").innerHTML = criterios.map((c) => `
    <li data-criterio="${c.criterio}">
      <span class="codigo">${c.codigo}</span>
      <span class="titulo">${c.nome}</span>
      <span class="peso">${Math.round(c.peso * 100)}%</span>
      <span class="detalhe">${c.descricao ?? ""}<br><span>${c.fonte ?? ""} · ${c.sentido === "menor_melhor" ? "↓ menor é melhor" : "↑ maior é melhor"}</span></span>
    </li>`).join("");

  // setor e linha da lista se acendem juntos
  const marcar = (criterio) => {
    for (const el of document.querySelectorAll("#ideal [data-criterio]")) {
      el.classList.toggle("ativo", el.dataset.criterio === criterio);
      el.querySelector?.(".setor")?.classList.toggle("ativo", el.dataset.criterio === criterio);
    }
  };
  for (const el of document.querySelectorAll("#ideal [data-criterio]")) {
    el.addEventListener("mouseenter", () => marcar(el.dataset.criterio));
    el.addEventListener("mouseleave", () => marcar(null));
  }

  if (movimentoLigado()) {
    const { gsap } = window;
    const disparo = { trigger: "#ideal-radar", start: "top 75%", once: true };
    gsap.from("#ideal-radar .setor-grupo", { scale: 0, svgOrigin: "0 0", opacity: 0, duration: 0.9, ease: "back.out(1.4)", stagger: 0.1, scrollTrigger: disparo });
    gsap.from("#ideal-lista li", { y: 24, opacity: 0, duration: 0.6, ease: "power3.out", stagger: 0.08, scrollTrigger: { ...disparo } });
  }

  // ------------------------------------------------------------ o que compõe a nota (um item por critério do prd)
  const textos = textosCriterios(estado.meta);
  const lista = document.getElementById("compoe-lista");
  if (lista) {
    lista.innerHTML = CRITERIOS.map((k) => {
      const t = textos[k.criterio];
      const peso = Math.round((pesoDoCriterio(estado.criterios, k.criterio) ?? 0) * 100);
      return `<li class="compoe__item">
        <span class="compoe__nome">${k.nome}<span class="compoe__peso">peso ${peso}% · ${t.sentido}</span></span>
        <p><small>O que mede</small>${t.mede}</p>
        <p><small>De onde vem</small>${t.fonte}</p>
        <p><small>Por que importa</small>${t.porque}</p>
      </li>`;
    }).join("");
    document.getElementById("compoe-percentil").textContent = FRASE_PERCENTIL;
  }

  // ------------------------------------------------------------ fórmula
  const nomeColuna = (c) => c.criterio;
  document.getElementById("formula").innerHTML =
    `nota_final = ${criterios.map((c) => `<b>${String(c.peso.toFixed(2)).replace(".", ",")}</b> × nota_${nomeColuna(c)}`).join("\n           + ")}\n\n` +
    `nota_&lt;critério&gt; = percentil da cidade no universo (0 a 100)  · invertido quando menor é melhor
` +
    `sem dado num critério  → nota_final = Σ(peso × nota) / Σ(pesos com dado)`;
  for (const el of document.querySelectorAll('[data-param="trava"]')) el.textContent = decimal(travaDeRenda(estado), 0);
  for (const el of document.querySelectorAll('[data-param="unidades"]')) el.textContent = inteiro(quantidadeRecomendada(estado));

  for (const el of document.querySelectorAll('[data-meta="pop-minima"]')) el.textContent = inteiro(estado.meta.populacao_minima_universo);
}

// Tabelas previstas no spec.md (seção 3), usadas enquanto a contagem real não existe
const PREVISTAS = {
  bronze: ["api_resposta", "execucao"],
  silver: ["dim_regiao", "dim_uf", "dim_municipio", "dim_calendario", "dim_indicador", "fato_indicador_municipal", "fato_indicador_macro"],
  gold: ["indicadores_municipio", "ranking_expansao", "ranking_criterio", "contexto_macro", "momento_expansao"],
};

export function desenharCamadas({ estado }) {
  const { camadas, exportado, eh_previa: previa } = estado.meta;
  const tabelas = (camada) => {
    const reais = camadas?.[camada];
    if (reais) return `<ul>${reais.map((t) => `<li>${t.tabela.split(".")[1]}<span>${inteiro(t.linhas)}</span></li>`).join("")}</ul>`;
    return `<ul>${PREVISTAS[camada].map((t) => {
      const n = camada === "gold" ? exportado?.[t] : null;
      return `<li>${t}<span>${n !== null && n !== undefined ? `${inteiro(n)}*` : "aguardando"}</span></li>`;
    }).join("")}</ul>`;
  };
  const etapas = [
    { classe: "fonte", sub: "fontes", nome: "APIs", texto: "IBGE (Localidades, Agregados, Malhas) e Banco Central (SGS). Coleta em Python, em lotes; o n8n agenda toda segunda.",
      lista: "<ul><li>IBGE agregados<span>7 tabelas</span></li><li>BCB SGS<span>2 séries</span></li></ul>" },
    { classe: "bronze", sub: "camada 1", nome: "Bronze", texto: "O JSON exatamente como a API devolveu, com endpoint, parâmetros e data. Só recebe INSERT.", lista: tabelas("bronze") },
    { classe: "silver", sub: "camada 2", nome: "Silver", texto: "Modelo estrela: dimensões de região, UF, município e calendário; fatos municipais e macroeconômicos.", lista: tabelas("silver") },
    { classe: "gold", sub: "camada 3", nome: "Gold", texto: "Tabelas prontas para consumo: indicadores, ranking, critérios, contexto macro e semáforo.", lista: tabelas("gold") },
    { classe: "uso", sub: "consumo", nome: "Painéis", texto: "Dashboard Streamlit lendo a gold e este site, que lê arquivos JSON exportados da gold.",
      lista: "<ul><li><a href='https://radar-expansao.streamlit.app' target='_blank' rel='noopener'>dashboard ↗</a><span>Streamlit</span></li><li>site de apoio<span>esta página</span></li></ul>" },
  ];
  document.getElementById("camadas").innerHTML = etapas.map((e) => `
    <li class="camada camada--${e.classe}">
      <h3 class="camada__nome"><small>${e.sub}</small>${e.nome}</h3>
      <p>${e.texto}</p>
      ${e.lista}
    </li>`).join("");
  document.getElementById("camadas-nota").textContent = previa
    ? "As contagens de linhas aparecem quando a carga no Supabase estiver rodando. * Linhas da prévia exportada para este site, calculada direto das APIs com as regras da gold."
    : "Linhas contadas no banco no momento da exportação dos dados do site.";

  // as camadas se constroem uma sobre a outra: cada uma entra UMA vez, já no lugar final do layout
  // (translate curto + opacidade, ~350 ms, cascata de 70 ms) e o conector até a anterior se desenha junto.
  // Sem scrub e sem 3D: nunca volta ao subir a página e nunca cruza o texto de outra camada.
  if (movimentoLigado()) {
    const { gsap, ScrollTrigger } = window;
    const camadas = [...document.querySelectorAll("#camadas .camada")];
    gsap.set(camadas, { y: 20, opacity: 0 });
    ScrollTrigger.batch(camadas, {
      start: "top 90%",
      once: true,
      onEnter: (lote) => {
        gsap.to(lote, { y: 0, opacity: 1, duration: 0.35, ease: "power2.out", stagger: 0.07, overwrite: true });
        lote.forEach((el) => el.classList.add("entrou"));
      },
    });
  }
}
