FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN chmod +x scripts/*.sh \
    && useradd --create-home --uid 1000 cargopulse \
    && chown -R cargopulse:cargopulse /app

USER cargopulse
EXPOSE 8000

CMD ["sh", "scripts/start-api.sh"]
