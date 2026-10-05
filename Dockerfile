FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
# Les dépendances de test sont incluses pour pouvoir lancer `pytest` et `lint-imports`
# directement dans le conteneur (onglet Exec de Docker Desktop ou `docker compose exec`).
RUN pip install ".[dev]"

COPY alembic.ini docker-entrypoint.sh ./
COPY migrations ./migrations
COPY tests ./tests

RUN useradd --create-home --uid 1000 candronex && chmod +x docker-entrypoint.sh
USER candronex

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
