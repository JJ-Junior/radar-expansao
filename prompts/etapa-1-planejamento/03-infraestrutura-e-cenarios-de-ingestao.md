# Etapa 1 · Infraestrutura autohospedada e cenários de ingestão

- **Data:** 26/11/2026
- **Responsável:** _(a preencher)_
- **Arquivos afetados:** `spec.md` (seções 1, 3.1, 3.4, 6, 8, 9, 10 e 11), `.env.example`, `.streamlit/secrets.toml.example`, `README.md`

## Objetivo
Definir onde o Supabase e o n8n rodam, como cada componente chega ao banco sem expô-lo na internet e como a ingestão
pode ser feita em dois cenários (Python ou n8n) sem duplicar as regras de transformação.

## Contexto fornecido
- `spec.md` v0.2 (arquitetura, contrato da bronze, carga incremental).
- Decisão do squad: Supabase e n8n autohospedados via Docker; construir e comparar dois cenários de ingestão.
- Restrição de publicação: nenhum endereço, nome de máquina ou detalhe do servidor no repositório público.

## Entrada (prompt)
> Tarefa: levantar as opções para (1) o dashboard no Streamlit Cloud ler a gold de um Supabase autohospedado,
> (2) o n8n disparar scripts Python e (3) o n8n gravar JSON bruto na bronze; comparar simplicidade e segurança de cada opção
> e recomendar uma. Em seguida, atualizar o `spec.md` e os modelos de variáveis de ambiente com a recomendação.
> Restrições: banco nunca publicado na internet; papel somente leitura para o dashboard; um único caminho de código para
> silver e gold; os dois cenários não podem rodar ao mesmo tempo; fuso America/Sao_Paulo.
> Formato: tabelas de opções com veredito; texto do spec sem dados do servidor.

## Saída esperada
Arquitetura de acesso com camadas de segurança, desenho dos dois cenários com prós e contras, e modelos `.env.example` e
`secrets.toml.example` só com placeholders.

## O que a IA entregou
- **Dashboard:** leitura pela API REST do Supabase restrita ao schema `gold`, com papel `web_leitor` somente leitura, RLS e
  um proxy de acesso na frente da API; snapshot da gold no repositório como plano B.
- **Cenário A:** container de ETL em Python com jobs fixos acionados pelo n8n por HTTP interno (sem porta publicada).
  Opções descartadas: executar comandos dentro do n8n, acesso SSH ao servidor e montar o socket do Docker no n8n — todas
  dão poder demais a quem controla o workflow.
- **Cenário B:** nós HTTP Request + Postgres gravando o JSON em `jsonb`, com lotes por UF para poupar memória.
- Contrato da bronze com `origem_carga`, hash calculado pelo próprio Postgres e trava de carga numa tabela de controle.

## O que foi ajustado
- **Trava:** a primeira ideia era uma trava de sessão do Postgres; como o nó Postgres do n8n pode usar conexões diferentes a
  cada passo, a trava passou a ser uma linha numa tabela de controle (`bronze.trava_carga`), com expiração automática.
- **Comparação A × B:** como B pede os dados por UF e A por ano, comparar o hash das respostas não funcionaria. A comparação
  passou para a silver (resumo por indicador e ano), que é igual nos dois cenários.
- **Princípio da bronze:** ficou explícito que só as respostas são imutáveis; as tabelas de controle são atualizadas.
- **SSL:** deixou de ser fixo no código e virou a variável `DB_SSLMODE`, porque o tráfego interno do servidor não usa SSL.
- Todo detalhe do servidor ficou fora do repositório; o texto público diz só "autohospedados via Docker".

## Lições
Decisão de infraestrutura entra no `spec.md` como regra e como pendência resolvida; detalhes operacionais da máquina ficam
fora do repositório público.
