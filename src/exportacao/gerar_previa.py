# +======================================================================================+
# |                                                                                      |
# |    ____    ___   _   _      _     ____      ____     _     ___    ___     _          |
# |   / ___|  / _ \ | | | |    / \   |  _ \     |___ \  / |   / _ \  / _ \   / |         |
# |   \___ \ | | | || | | |   / _ \  | | | |      __) | | |  | | | || | | |  | |         |
# |    ___) || |_| || |_| |  / ___ \ | |_| |     / __/  | |  | |_| || |_| |  | |         |
# |   |____/  \__\_\ \___/  /_/   \_\|____/     |_____| |_|   \___/  \___/   |_|         |
# |                                                                                      |
# +======================================================================================+
#
# =============================================================================
# RADAR DE EXPANSAO - ETAPA 6: SITE DE APOIO (IMAGEM DE PREVIA DO LINK)
# =============================================================================
#
# OBJETIVO: gerar a imagem que aparece quando o link do site e compartilhado
#           (WhatsApp, redes sociais): 1200 x 630, com os dados reais do site
#           (momento economico e as unidades recomendadas).
# ENTRADA:  site/dados/meta.json, ranking_expansao.json, momento_expansao.json
#           e contexto_macro.json (exportados da gold)
# SAIDA:    site/img/previa.jpg (substitui o arquivo a cada execucao)
#
# =============================================================================
# NOVIDADES DESTA ETAPA (vs o que voce ja aprendeu no curso)
# =============================================================================
#
# JA APRENDIDO:
#   - ler JSON com o modulo json e montar texto com f-strings
#   - subprocess para chamar um programa externo
#
# NOVIDADES:
#   1. Open Graph            -> as tags og:image do HTML dizem qual imagem os
#                               aplicativos mostram na previa do link
#   2. navegador headless    -> Edge/Chrome sem janela "fotografa" uma pagina
#                               HTML nossa (--screenshot), sem imagem de terceiros
#   3. Pillow                -> converte o PNG em JPG e baixa a qualidade ate o
#                               arquivo ficar abaixo do limite de tamanho
#   4. html.escape           -> nomes vindos dos dados entram no HTML sem virar
#                               codigo
#
# INSTALACAO: pip install pillow   (ja vem junto com o streamlit do requirements.txt)
# COMO RODAR: python src/exportacao/gerar_previa.py
#             (o exportar_site.py chama este script no fim)
#
# =============================================================================

# ============================== CONFIG ==============================
LARGURA = 1200
ALTURA = 630
LIMITE_KB = 300                  # WhatsApp e redes recusam imagens grandes demais
QUALIDADE_INICIAL = 88           # JPG: desce de 4 em 4 ate caber no limite
QUALIDADE_MINIMA = 60
ESPERA_FONTES_MS = 8000          # tempo para o navegador carregar as fontes do Google Fonts
TIMEOUT_SEGUNDOS = 90
NAVEGADORES = [                  # o primeiro que existir na maquina e usado
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome",
]
ENDERECO = "radar-expansao.lovelearning.com.br"
FRASE = "Abra onde o Brasil está pronto."
# ====================================================================

import html
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PASTA_DADOS = RAIZ / "site" / "dados"
ARQUIVO_SAIDA = RAIZ / "site" / "img" / "previa.jpg"
COR_STATUS = {"Expandir agora": "#0ca30c", "Expandir com cautela": "#fab219", "Esperar": "#d03b3b"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def ler_tabela(nome: str) -> list:
    """Le um JSON colunar de site/dados e devolve uma lista de dicionarios."""
    t = json.loads((PASTA_DADOS / f"{nome}.json").read_text(encoding="utf-8"))
    return [dict(zip(t["colunas"], linha)) for linha in t["linhas"]]


def numero_br(valor: float, casas: int = 1) -> str:
    """81.03 -> '81,0'."""
    return f"{valor:.{casas}f}".replace(".", ",")


def montar_html() -> str:
    """Pagina 1200 x 630 com os dados reais (escrita do zero, so CSS e SVG nossos)."""
    meta = json.loads((PASTA_DADOS / "meta.json").read_text(encoding="utf-8"))
    ranking = ler_tabela("ranking_expansao")
    momento = ler_tabela("momento_expansao")
    recomendadas = sorted((r for r in ranking if r.get("recomendado_top5")), key=lambda r: r["ordem_recomendacao"])
    if not recomendadas:  # sem lista na gold: mostra as 5 primeiras do ranking
        recomendadas = sorted(ranking, key=lambda r: r["posicao_brasil"])[:5]
    atual = momento[-1]
    ano, mes = atual["mes"][:4], int(atual["mes"][5:7])
    referencia = f"{MESES[mes - 1]}/{ano}"
    sinais = [atual["sinal_juros"], atual["sinal_inflacao"], atual["sinal_cambio"]]
    favoraveis = sinais.count("verde")

    linhas = "\n".join(
        f'<li><span class="pos">{i:02d}</span><span class="nome" style="font-size:{40 if len(r["municipio_nome"]) <= 14 else 30}px">{html.escape(r["municipio_nome"])}'
        f' <small>{html.escape(r["uf_sigla"].strip())}</small></span><span class="nota">{numero_br(r["nota_final"])}</span></li>'
        for i, r in enumerate(recomendadas, start=1))
    rotulo_lista = "As 5 recomendadas" if any(r.get("recomendado_top5") for r in recomendadas) else "As 5 primeiras do ranking"

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@700;900&family=Archivo:wght@500;700&family=JetBrains+Mono:wght@600&display=block" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ width: {LARGURA}px; height: {ALTURA}px; overflow: hidden; background: #0b0d0f; color: #f2f1ec; font-family: Archivo, Arial, sans-serif; }}
  .quadro {{ position: absolute; inset: 0; padding: 56px 64px; display: grid; grid-template-columns: 1.15fr 1fr; gap: 56px; }}
  .anel {{ position: absolute; right: -140px; top: -140px; width: 520px; height: 520px; border-radius: 50%; border: 2px solid rgba(196,240,59,.12); }}
  .anel.b {{ right: -40px; top: -40px; width: 320px; height: 320px; border-color: rgba(196,240,59,.18); }}
  .marca {{ display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }}
  .marca svg {{ width: 56px; height: 56px; color: #c4f03b; }}
  .squad {{ font-family: "JetBrains Mono", monospace; font-weight: 600; font-size: 22px; letter-spacing: .14em; color: #8a929b; }}
  h1 {{ font-family: "Big Shoulders Display", Impact, sans-serif; font-weight: 900; font-size: 118px; line-height: .86; text-transform: uppercase; }}
  .frase {{ margin-top: 24px; font-size: 34px; font-weight: 700; color: #c4f03b; }}
  .momento {{ margin-top: 40px; display: flex; align-items: center; gap: 16px; padding: 16px 24px; border-radius: 12px; background: #151a1f; border-left: 8px solid {COR_STATUS.get(atual["recomendacao"], "#8a929b")}; }}
  .momento b {{ font-family: "Big Shoulders Display", Impact, sans-serif; font-weight: 900; font-size: 40px; text-transform: uppercase; line-height: 1; }}
  .momento span {{ font-family: "JetBrains Mono", monospace; font-size: 18px; color: #bcc2c9; }}
  .lista h2 {{ font-family: "JetBrains Mono", monospace; font-weight: 600; font-size: 22px; letter-spacing: .14em; text-transform: uppercase; color: #8a929b; margin: 8px 0 16px; }}
  ol {{ list-style: none; display: grid; gap: 12px; }}
  li {{ display: grid; grid-template-columns: 56px 1fr auto; align-items: baseline; gap: 12px; padding: 12px 20px; border-radius: 12px; background: #151a1f; }}
  .pos {{ font-family: "Big Shoulders Display", Impact, sans-serif; font-weight: 900; font-size: 34px; color: #c4f03b; }}
  .nome {{ font-family: "Big Shoulders Display", Impact, sans-serif; font-weight: 900; font-size: 40px; text-transform: uppercase; line-height: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .nome small {{ font-family: "JetBrains Mono", monospace; font-size: 18px; color: #8a929b; }}
  .nota {{ font-family: "Big Shoulders Display", Impact, sans-serif; font-weight: 900; font-size: 40px; }}
  .rodape {{ position: absolute; left: 64px; right: 64px; bottom: 28px; display: flex; justify-content: space-between; font-family: "JetBrains Mono", monospace; font-size: 18px; color: #8a929b; }}
</style></head>
<body>
  <div class="anel"></div><div class="anel b"></div>
  <div class="quadro">
    <div>
      <div class="marca">
        <svg viewBox="0 0 32 32" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round">
          <path d="M16 27a11 11 0 1 1 11-11" opacity=".45"/><path d="M16 21.5a5.5 5.5 0 1 1 5.5-5.5" opacity=".75"/><path d="M16 16 24.5 7.5"/></g>
          <circle cx="16" cy="16" r="2.4" fill="currentColor"/></svg>
        <span class="squad">SQUAD DROP DATABASE</span>
      </div>
      <h1>Radar de<br>Expansão</h1>
      <p class="frase">{html.escape(FRASE)}</p>
      <div class="momento"><b>{html.escape(atual["recomendacao"])}</b><span>{favoraveis} de 3 sinais favoráveis · {referencia}</span></div>
    </div>
    <div class="lista">
      <h2>{rotulo_lista}</h2>
      <ol>{linhas}</ol>
    </div>
  </div>
  <div class="rodape"><span>Dados: IBGE e Banco Central · pesos {html.escape(str(meta.get("versao_pesos") or ""))}</span><span>{ENDERECO}</span></div>
</body></html>"""


def achar_navegador() -> str:
    """Primeiro navegador da lista NAVEGADORES que existe nesta maquina."""
    for caminho in NAVEGADORES:
        if Path(caminho).exists() or shutil.which(caminho):
            return caminho
    raise FileNotFoundError("nenhum navegador Edge/Chrome/Chromium encontrado (ajuste NAVEGADORES no CONFIG)")


def fotografar(pagina: Path, png: Path) -> None:
    """Abre a pagina no navegador sem janela e salva o PNG do tamanho exato."""
    comando = [achar_navegador(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
               "--force-device-scale-factor=1", f"--window-size={LARGURA},{ALTURA}",
               f"--virtual-time-budget={ESPERA_FONTES_MS}", f"--screenshot={png}", pagina.as_uri()]
    subprocess.run(comando, check=True, timeout=TIMEOUT_SEGUNDOS, capture_output=True)
    if not png.exists():
        raise RuntimeError("o navegador nao gerou o PNG")


def salvar_jpg(png: Path) -> tuple:
    """Converte para JPG, baixando a qualidade ate ficar abaixo de LIMITE_KB; devolve (KB, qualidade)."""
    from PIL import Image

    imagem = Image.open(png).convert("RGB")
    if imagem.size != (LARGURA, ALTURA):
        imagem = imagem.resize((LARGURA, ALTURA))
    ARQUIVO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
    qualidade = QUALIDADE_INICIAL
    while True:
        imagem.save(ARQUIVO_SAIDA, "JPEG", quality=qualidade, optimize=True, progressive=True)
        kb = ARQUIVO_SAIDA.stat().st_size / 1024
        if kb <= LIMITE_KB or qualidade <= QUALIDADE_MINIMA:
            return kb, qualidade
        qualidade -= 4


def gerar() -> Path:
    """Monta a pagina, fotografa e grava site/img/previa.jpg."""
    with tempfile.TemporaryDirectory() as pasta:
        pagina = Path(pasta) / "previa.html"
        pagina.write_text(montar_html(), encoding="utf-8")
        png = Path(pasta) / "previa.png"
        fotografar(pagina, png)
        kb, qualidade = salvar_jpg(png)
    print(f"  {ARQUIVO_SAIDA.relative_to(RAIZ)}: {LARGURA}x{ALTURA}, {kb:,.0f} KB (qualidade {qualidade})")
    return ARQUIVO_SAIDA


if __name__ == "__main__":
    try:
        gerar()
    except Exception as erro:  # mensagem clara em vez de traceback
        sys.exit(f"Nao foi possivel gerar a previa: {erro}")
