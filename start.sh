#!/usr/bin/env bash
set -e
ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"

MODE="${1:-docker}"

usage() {
  echo "Usage: ./start.sh [docker|prod|local]"
  echo ""
  echo "  docker  (défaut) — dev local avec hot-reload via Docker Compose"
  echo "  prod             — déploiement production (nécessite JWT_SECRET_KEY)"
  echo "  local            — dev local sans Docker (uv + npm)"
  exit 1
}

# ── Mode Docker dev (défaut) ───────────────────────────────────
if [[ "$MODE" == "docker" ]]; then
  echo "=== Belote Contrée — Dev (Docker) ==="
  echo ""
  echo "Backend  → http://localhost:8000"
  echo "Frontend → http://localhost:3000"
  echo ""
  echo "Ouvre 4 onglets sur http://localhost:3000"
  echo "Même salon (ex: salon1), 4 pseudos différents."
  echo ""
  docker compose up --build
  exit 0
fi

# ── Mode Production ────────────────────────────────────────────
if [[ "$MODE" == "prod" ]]; then
  if [[ -z "$JWT_SECRET_KEY" ]]; then
    echo "Erreur : JWT_SECRET_KEY est obligatoire en production."
    echo "Exemple : JWT_SECRET_KEY=<clé> ./start.sh prod"
    exit 1
  fi
  echo "=== Belote Contrée — Production ==="
  echo ""
  echo "Application → http://localhost:80"
  echo ""
  docker compose -f docker-compose.prod.yml up --build -d
  echo ""
  echo "Déployé. Logs : docker compose -f docker-compose.prod.yml logs -f"
  exit 0
fi

# ── Mode local sans Docker ─────────────────────────────────────
if [[ "$MODE" == "local" ]]; then
  echo "=== Belote Contrée — Dev (local) ==="
  echo "Installation des dépendances..."
  uv sync

  echo ""
  echo "Backend  → http://localhost:8000"
  echo "Frontend → http://localhost:3000"
  echo ""
  echo "Ouvre 4 onglets sur http://localhost:3000"
  echo "Même salon (ex: salon1), 4 pseudos différents."
  echo ""

  uv run uvicorn backend.main:app --reload --port 8000 &
  BACKEND_PID=$!

  cd "$ROOT/frontend"
  npm run dev &
  FRONTEND_PID=$!

  trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
  wait
  exit 0
fi

usage
