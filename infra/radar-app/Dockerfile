# =============================================================================
# Radar de Expansao - imagem do container radar-app (espelho do dashboard)
# Python fixo + as dependencias do requirements.txt do projeto, com todas as
# transitivas fixadas em constraints.txt. O codigo NAO entra na imagem: e
# montado somente leitura em /app (clone da branch do projeto).
# Rebuild so quando mudar o requirements.txt, o constraints.txt ou este arquivo.
# =============================================================================
FROM python:3.12.16-slim-trixie@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=America/Sao_Paulo \
    HOME=/tmp

COPY repo/requirements.txt constraints.txt /opt/radar-app/
RUN pip install --no-cache-dir -r /opt/radar-app/requirements.txt -c /opt/radar-app/constraints.txt \
    && pip check \
    && python -c "import streamlit, pandas, numpy, pyarrow, plotly; print('imports ok', streamlit.__version__)"

USER 1000:1000
WORKDIR /app
EXPOSE 8501

HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"]

CMD ["streamlit", "run", "src/app/app.py", \
     "--server.address", "0.0.0.0", "--server.port", "8501", "--server.headless", "true", \
     "--server.fileWatcherType", "none", "--browser.gatherUsageStats", "false"]
