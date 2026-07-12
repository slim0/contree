#!/bin/bash
# Lance 4 fenêtres Chrome (1 par profil) avec auto-login pour chaque joueur test.
# Prérequis : docker compose up (backend + frontend démarrés)
set -euo pipefail

AUTOLOGIN="http://localhost:3000/api/dev/autologin"

echo "=== Seed de la base ==="
if docker-compose exec backend uv run /app/DEV/seed.py; then
    echo ""
else
    echo "⚠ Seed échoué — le backend est-il démarré ? (docker compose up)"
    exit 1
fi

PROFILES=("Profile 1" "Profile 2" "Profile 3" "Profile 4")

PLAYERS=("alice" "bob" "charlie" "diana")
echo "=== Ouverture Chrome ==="
for i in "${!PLAYERS[@]}"; do
    profile="${PROFILES[$i]}"
    player="${PLAYERS[$i]}"

    echo "  $profile → $player"

    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" \
        --profile-directory="$profile" \
        --app="$AUTOLOGIN/$player" &

    sleep 0.3
done

echo ""
echo "Les 4 fenêtres sont ouvertes. Chaque joueur est connecté sur localhost:3000."
