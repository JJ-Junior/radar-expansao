# =============================================================================
# Radar de Expansao - imagem do container radar-etl (cenario A)
# Python fixo + dependencias fixas + o disparador HTTP interno.
# O codigo do projeto NAO entra na imagem: e montado somente leitura em /app
# (um clone da branch do projeto), entao atualizar o codigo nao exige rebuild.
# Rebuild so quando mudar este Dockerfile, o requirements.txt ou o disparador.
# =============================================================================
FROM python:3.12.16-slim-trixie@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=America/Sao_Paulo

COPY requirements.txt /opt/radar-etl/requirements.txt
RUN pip install --no-cache-dir --no-deps -r /opt/radar-etl/requirements.txt \
    && pip check

COPY disparador.py /opt/radar-etl/disparador.py

# usuario sem privilegios (o compose.yml troca pelo uid do dono da pasta de logs)
USER 1000:1000
WORKDIR /app
EXPOSE 9000

HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9000/saude', timeout=4)"]

CMD ["python", "/opt/radar-etl/disparador.py"]
