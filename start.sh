#!/usr/bin/env bash
set -e
ROOT=$(cd "$(dirname "$0")" && pwd)

echo "=== Belote Contrée ==="
echo "Installation des dépendances..."
cd "$ROOT"
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
