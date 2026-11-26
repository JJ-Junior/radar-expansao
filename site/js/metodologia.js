// Metodologia (pesos e critérios, lidos de ranking_criterio.json) e arquitetura (camadas e linhas).

import { CRITERIOS } from "./indicadores.js";
import { inteiro } from "./formato.js";

export function desenharMetodologia({ estado }) {
  const criterios = CRITERIOS.map((c) => ({ ...c, ...estado.criterios.find((x) => x.criterio === c.criterio) }));
  const maior = Math.max(...criterios.map((c) => c.peso ?? 0));

  document.getElementById("lista-pesos").innerHTML = criterios.map((c) => `
    <li class="peso"><span class="peso__nome">${c.nome}</span>
      <span class="peso__trilho" role="img" aria-label="${c.nome}: ${Math.round(c.peso * 100)}%"><i style="width:${(c.peso / maior) * 100}%"></i></span>
      <b>${Math.round(c.peso * 100)}%</b></li>`).join("");

  document.querySelector("#tabela-criterios tbody").innerHTML = criterios.map((c) => `
    <tr><td>${c.nome}</td><td>${c.descricao ?? ""}</td><td>${c.fonte ?? ""}</td>
      <td>${c.sentido === "menor_melhor" ? "menor é melhor" : "maior é melhor"}</td>
      <td class="num"><b>${Math.round(c.peso * 100)}%</b></td></tr>`).join("");

  const minima = estado.meta.populacao_minima_universo;
  for (const el of document.querySelectorAll('[data-meta="pop-minima"]')) el.textContent = `${inteiro(minima)}`;
}

// Tabelas previstas no spec.md (seção 3), usadas enquanto a contagem real não existe
const PREVISTAS = {
  bronze: ["api_resposta", "execucao"],
  silver: ["dim_regiao", "dim_uf", "dim_municipio", "dim_calendario", "dim_indicador", "fato_indicador_municipal", "fato_indicador_macro"],
  gold: ["indicadores_municipio", "ranking_expansao", "ranking_criterio", "contexto_macro", "momento_expansao"],
};

export function desenharArquitetura({ estado }) {
  const { camadas, exportado, eh_previa: previa } = estado.meta;

  const listaTabelas = (camada) => {
    const reais = camadas?.[camada];
    if (reais) {
      return `<ul>${reais.map((t) => `<li><code>${t.tabela.split(".")[1]}</code><span>${inteiro(t.linhas)}</span></li>`).join("")}</ul>`;
    }
    const linhas = PREVISTAS[camada].map((t) => {
      const n = camada === "gold" ? exportado?.[t] : null;
      return `<li><code>${t}</code><span class="discreto">${n !== null && n !== undefined ? `${inteiro(n)}*` : "—"}</span></li>`;
    });
    return `<ul>${linhas.join("")}</ul>`;
  };

  const etapas = [
    { classe: "fonte", camada: "fontes", titulo: "APIs", texto: "IBGE (Localidades, Agregados e Malhas) e Banco Central (SGS). Coleta em Python, em lotes, agendada pelo n8n toda segunda." },
    { classe: "bronze", camada: "camada 1", titulo: "Bronze", texto: "O JSON exatamente como a API devolveu, com endpoint, parâmetros e data. Só recebe INSERT.", tabelas: "bronze" },
    { classe: "silver", camada: "camada 2", titulo: "Silver", texto: "Modelo estrela: dimensões de região, UF, município e calendário; fatos municipais e macro.", tabelas: "silver" },
    { classe: "gold", camada: "camada 3", titulo: "Gold", texto: "Tabelas prontas para consumo: indicadores, ranking, critérios, contexto macro e semáforo.", tabelas: "gold" },
    { classe: "uso", camada: "consumo", titulo: "Painéis", texto: "Dashboard Streamlit lendo a gold e este site, que lê arquivos JSON exportados da gold." },
  ];
  document.getElementById("fluxo").innerHTML = etapas.map((e) => `
    <li class="etapa etapa--${e.classe}">
      <span class="etapa__camada">${e.camada}</span>
      <h3>${e.titulo}</h3>
      <p>${e.texto}</p>
      ${e.tabelas ? listaTabelas(e.tabelas) : ""}
    </li>`).join("");

  document.getElementById("fluxo-nota").textContent = previa
    ? "As contagens de linhas aparecem quando a carga no Supabase estiver rodando. * Linhas da prévia exportada para este site, calculada direto das APIs com as regras da gold."
    : "Linhas contadas no banco no momento da exportação dos dados do site.";
}
