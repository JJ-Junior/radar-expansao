# Responsabilidades do squad — Radar de Expansão

> ⚠️ **PROPOSTA — validar com o squad.** Versão 0.1 (26/11/2026). Donos, apoios e datas podem mudar no próximo check-in;
> toda mudança é registrada aqui.

**Squad:** DROP Database — Squad #21001

| Membro | Branch |
|---|---|
| José Martins (Junior) | `junior` |
| Marco Pereira | `marco` |
| Mario Castilho | `mario` |
| Rodrigo Oliveira (Rodrigo Cesar Silva De Oliveira) | `rodrigo-oliveira` |
| Rodrigo Vincensi | `rodrigo-vincensi` |

---

## 1. Objetivo e prazo

Entregar o **Radar de Expansão** para a **rede de academias**: um Lakehouse (bronze → silver → gold) no Supabase alimentado pelas
APIs do IBGE e do Banco Central, atualizado sozinho pelo n8n, com ranking de municípios num dashboard Streamlit publicado,
README completo, registro de prompts e apresentação de até 6 slides.

- **Início:** 18/11/2026 · **Entrega:** **20/12/2026**
- Cronograma de referência: [`prd.md`, seção 8](../prd.md#8-marcos-e-prazo).
- Documentos que todos leem antes de começar: [`prd.md`](../prd.md), [`spec.md`](../spec.md) e [`agents.md`](../agents.md).

## 2. Como o squad trabalha

**Branches e Pull Requests**
- Cada membro trabalha na **sua branch**, criada a partir do `main` (tabela acima). Ninguém commita direto no `main`.
- Antes de começar uma tarefa, atualize a sua branch com o `main`:

  ```powershell
  git switch main
  git pull
  git switch <sua-branch>          # na primeira vez: git switch -c <sua-branch>
  git merge main
  ```

- A entrega vai para o `main` **por Pull Request**, com **revisão e aprovação de pelo menos 1 outro membro** (de preferência o apoio da frente).
- Um PR por assunto, pequeno o bastante para ser revisado em 15 minutos. Na descrição: o que muda, como testar e a Issue relacionada.

**Commits**
- Padrão do [`agents.md`](../agents.md), seção 7: `tipo(escopo): descrição no imperativo`.
  Exemplo: `feat(ingestao): busca população do IBGE em lotes por ano`.
- Antes de cada commit: `git status` e `git diff --staged` revisados.

**Credenciais**
- **Nunca** commitar `.env`, senha, token ou string de conexão. Cada membro tem o próprio `.env` local, criado a partir do `.env.example`.
- A senha do banco é passada só por canal privado do squad, nunca por Issue, PR ou arquivo do repositório.

## 3. Frentes de trabalho

| # | Frente | Etapa do enunciado | Período | Dono | Apoio |
|---|---|---|---|---|---|
| F1 | Coordenação, planejamento (prd, spec, agents), revisão de PRs e integração | 1 e 8 | 26/11 → 20/12 | José | todos |
| F2 | Supabase + camada Bronze (ingestão IBGE e BCB, lotes, try/except) | 2 e 3 | 26/11 → 03/12 | Marco | José |
| F3 | Camada Silver (modelo estrela, limpeza, tipos, nulos) | 4 | 04/12 → 08/12 | Mario | Marco |
| F4 | Camada Gold + ranking (indicadores, ranking, contexto macro, semáforo) | 5 | 09/12 → 11/12 | Rodrigo Vincensi | Mario |
| F5 | Automação n8n (agenda semanal, checagem de período novo, export, print) | 6 | 06/12 → 14/12 | Rodrigo Oliveira | Marco |
| F6 | Dashboard Streamlit + deploy no Streamlit Cloud | 7 | 12/12 → 14/12 | Rodrigo Vincensi | Rodrigo Oliveira |
| F7 | Site de apoio (documentação + vitrine de dados) | extra | 15/12 → 17/12 | José | Rodrigo Vincensi |
| F8 | README, `prompts/` e prints | 8 | contínuo · fechamento 15/12 → 17/12 | José | todos |
| F9 | Apresentação (até 6 slides) | entregável | 15/12 → 19/12 | Rodrigo Oliveira | todos |

### Dependências

```mermaid
flowchart LR
    F1[F1 Planejamento] --> F2[F2 Supabase + Bronze]
    F2 --> F3[F3 Silver]
    F3 --> F4[F4 Gold + ranking]
    F4 --> F6[F6 Streamlit]
    F2 --> F5[F5 n8n]
    F4 -.execução completa.-> F5
    F4 --> F7[F7 Site de apoio]
    F6 --> F9[F9 Apresentação]
    F5 --> F8[F8 README + prompts + prints]
    F6 --> F8
```

Quem espera quem: **bronze → silver → gold → Streamlit**. O n8n começa assim que a bronze existe (06/12) e fecha a execução
completa quando a gold estiver pronta. Enquanto espera, cada frente adianta o que não depende da anterior
(ex.: a silver escreve o SQL com uma amostra da bronze; o Streamlit monta o layout com dados de exemplo).

## 4. Detalhe de cada frente

### F1 · Coordenação, planejamento e integração — Dono José · Apoio todos
- **Entregáveis:** `prd.md`, `spec.md` e `agents.md` revisados; quadro de tarefas no GitHub Projects; revisão dos PRs; integração final no `main`.
- **Pronto quando:** os três documentos aprovados pelo squad até 28/11; todo PR revisado em até 24 h; em 19/12 o `main` roda do início ao fim (ingestão → gold → dashboard).
- **Depende de:** —. **Destrava:** todas as frentes.

### F2 · Supabase + camada Bronze — Dono Marco · Apoio José
- **Entregáveis:** projeto no Supabase com os schemas `bronze`, `silver` e `gold`; `sql/bronze/` (`api_resposta`, `execucao`, `vw_ultimo_periodo`);
  `src/ingestao/` (localidades, agregados do IBGE em lotes, séries do BCB, carga inicial).
- **Pronto quando:**
  - Supabase criado e acessível pelo Session pooler até 28/11;
  - `bronze.api_resposta` tem respostas de todos os recursos do `spec.md`, seção 2 (localidades, 6579, 4714, 5938, 7060, 10295, 9418, 9509, BCB 432 e 10813);
  - nenhuma chamada passa do limite de valores do IBGE (lotes por ano/UF);
  - rodar a carga duas vezes não duplica respostas;
  - erros de API ficam registrados em `bronze.execucao` sem derrubar o script.
- **Depende de:** F1 (`spec.md` aprovado). **Destrava:** F3 e F5.

### F3 · Camada Silver — Dono Mario · Apoio Marco
- **Entregáveis:** `sql/silver/` (dimensões `dim_regiao`, `dim_uf`, `dim_municipio`, `dim_calendario`, `dim_indicador`;
  fatos `fato_indicador_municipal` e `fato_indicador_macro`); execução em `src/transformacao/`.
- **Pronto quando:**
  - 5 regiões, 27 UFs e 5.571 municípios nas dimensões;
  - fatos sem duplicatas (chave primária) e com tipos corretos (número e data);
  - `"-"`, `"..."`, `"X"` e `".."` viram nulo com a flag certa;
  - 100% dos fatos casam com `dim_municipio`, e toda linha tem `bronze_id`.
- **Depende de:** F2. **Destrava:** F4.

### F4 · Camada Gold + ranking — Dono Rodrigo Vincensi · Apoio Mario
- **Entregáveis:** `sql/gold/` com `indicadores_municipio`, `ranking_expansao`, `ranking_criterio`, `contexto_macro` e `momento_expansao`.
- **Pronto quando:**
  - ranking com todos os municípios do universo (≥ 50 mil habitantes), notas entre 0 e 100 e soma dos pesos = 100%;
  - critérios e pesos iguais aos do `prd.md`;
  - `contexto_macro` mensal desde o início do histórico até o último mês disponível;
  - semáforo com recomendação e justificativa;
  - um número da gold é rastreado até a bronze numa demonstração.
- **Depende de:** F3. **Destrava:** F5 (execução completa), F6, F7 e F9.

### F5 · Automação n8n — Dono Rodrigo Oliveira · Apoio Marco
- **Entregáveis:** `n8n/radar-expansao.json` (exportado sem credenciais) e print de uma execução bem-sucedida em `docs/img/`.
- **Pronto quando:**
  - agenda semanal ativa (segunda, 06:00);
  - o workflow compara com o último período salvo e busca só o que é novo;
  - uma execução de ponta a ponta termina com `sucesso` ou `sem_novidade` em `bronze.execucao`;
  - rodar duas vezes seguidas não duplica dados;
  - o JSON exportado não tem senha nem token.
- **Depende de:** F2 (bronze) e F4 (para a execução completa). Decisão pendente: onde o n8n roda (`spec.md`, seção 8).

### F6 · Dashboard Streamlit + deploy — Dono Rodrigo Vincensi · Apoio Rodrigo Oliveira
- **Entregáveis:** `src/app/` (páginas Ranking, Município, Momento econômico e Como o ranking é calculado); app publicado no Streamlit Cloud; prints em `docs/img/`.
- **Pronto quando:**
  - lê só a gold, com credenciais nos *Secrets* do Streamlit Cloud;
  - filtros por região e estado funcionando;
  - link público no README;
  - teste dos 30 segundos: alguém de fora do squad aponta as 5 cidades recomendadas e o motivo.
- **Depende de:** F4. **Destrava:** F8 (prints) e F9.

### F7 · Site de apoio — Dono José · Apoio Rodrigo Vincensi
- **Entregáveis:** `site/` publicado, com metodologia, arquitetura e vitrine de dados da gold.
- **Pronto quando:** publicado com link no README; números iguais aos do dashboard; sem nenhuma credencial no código.
- **Depende de:** F4. Decisão pendente: stack do site.

### F8 · README, prompts e prints — Dono José · Apoio todos
- **Entregáveis:** README com todas as seções do enunciado (problema, cliente, arquitetura, prints, link do app, como rodar,
  "Como eu usei IA neste projeto"); `prompts/` com registros de todas as etapas; prints em `docs/img/`.
- **Pronto quando:** nenhuma seção "a preencher" no README; pelo menos um registro de prompt por etapa; todos os links funcionando.
- **Regra para todos:** **cada membro registra os próprios prompts** em `prompts/`, no modelo de `prompts/README.md`, no mesmo PR da entrega.
- **Depende de:** todas as frentes.

### F9 · Apresentação — Dono Rodrigo Oliveira · Apoio todos
- **Entregáveis:** até 6 slides: o cliente e o problema · como o Radar resolve · arquitetura (bronze → silver → gold) ·
  o ranking final e o que ele recomenda · como a IA foi usada · próximos passos. Versão final em PDF em `docs/`.
- **Pronto quando:** no máximo 6 slides; números iguais aos do dashboard; ensaio completo feito até 19/12.
- **Depende de:** F4 e F6.

## 5. Matriz por membro

| Membro | Dono de | Apoio em | Datas-chave |
|---|---|---|---|
| **José Martins (Junior)** | F1 Coordenação · F7 Site · F8 README e prompts | F2 Bronze | docs revisados até 28/11 · site e README 15–17/12 · integração 19/12 |
| **Marco Pereira** | F2 Supabase + Bronze | F3 Silver · F5 n8n | Supabase até 28/11 · bronze completa até 03/12 |
| **Mario Castilho** | F3 Silver | F4 Gold | silver completa até 08/12 |
| **Rodrigo Oliveira** | F5 n8n · F9 Apresentação | F6 Streamlit | n8n de 06/12 a 14/12 · slides e ensaio até 19/12 |
| **Rodrigo Vincensi** | F4 Gold + ranking · F6 Streamlit | F7 Site | gold até 11/12 · dashboard publicado até 14/12 |
| **Todos** | os próprios registros em `prompts/` | F1 (revisão de PRs) · F8 · F9 | check-ins 2x por semana · ensaio em 19/12 |

## 6. Rituais

- **Check-in curto, 2x por semana** (proposta: terça e sexta, 15 minutos): cada um diz o que fez, o que vai fazer e o que está travando.
- **Quadro de tarefas** no GitHub (Issues + Projects), com colunas *A fazer · Fazendo · Em revisão · Pronto*.
  Uma Issue por tarefa, com o rótulo da frente (`f2-bronze`, `f3-silver`...) e o responsável. O PR cita a Issue que fecha.
- **Como pedir ajuda:** travou por mais de 2 horas? Comente na Issue chamando o apoio da frente e avise no grupo do squad.
  Ajuda pedida cedo custa menos que atraso descoberto tarde.
- **Se uma frente atrasar:** passou 1 dia do fim previsto e a frente seguinte está parada, **o apoio assume** a parte pendente,
  em par com o dono, e o cronograma é revisto no próximo check-in. A folga de 18–19/12 é a reserva para imprevistos, não para trabalho novo.
- **Definição de pronto de qualquer entrega:** PR aprovado por pelo menos 1 membro · nenhum `.env` ou senha no PR ·
  `spec.md` ou `prd.md` atualizados se a entrega mudou modelo ou critério · prompts registrados em `prompts/`.
