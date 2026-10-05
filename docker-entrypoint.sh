#!/bin/sh
# Applique les migrations (schéma + données de démonstration), puis démarre l'API.
set -e
alembic upgrade head
exec uvicorn candronex.main:create_app --factory --host 0.0.0.0 --port 8000
