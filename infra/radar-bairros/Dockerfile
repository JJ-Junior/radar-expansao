# =============================================================================
# Radar de Expansao - imagem do container radar-bairros (worker da fila de bairros)
# Python fixo + requirements.txt do projeto + requirements-bairros.txt (se existir),
# com as transitivas presas em constraints.txt. O codigo NAO entra na imagem:
# e montado somente leitura em /app (clone da branch do projeto).
# Rebuild so quando mudar algum requirements, o constraints.txt ou o worker.
# =============================================================================
FROM python:3.12.16-slim-trixie@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=America/Sao_Paulo \
    HOME=/tmp

COPY repo/requirements*.txt constraints.txt /opt/radar-bairros/
RUN cd /opt/radar-bairros \
    && pip install --no-cache-dir -r requirements.txt -c constraints.txt \
    && if [ -f requirements-bairros.txt ]; then pip install --no-cache-dir -r requirements-bairros.txt -c constraints.txt; fi \
    && pip check

COPY worker.py /opt/radar-bairros/worker.py

USER 1000:1000
WORKDIR /app

# o worker atualiza /tmp/batimento a cada volta (e a cada 5 s durante um pedido)
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import os,sys,time; sys.exit(time.time() - os.path.getmtime('/tmp/batimento') > 120)"]

CMD ["python", "/opt/radar-bairros/worker.py"]
