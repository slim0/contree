#!/bin/bash
# Lance 4 fenêtres Chrome (1 par profil) avec auto-login pour chaque joueur test.
# Prérequis : docker compose up (backend + frontend démarrés)
#
# Option -q / --quick : crée automatiquement un salon de test avec les 4 joueurs
# déjà répartis en équipes et la 1re manche démarrée — les fenêtres s'ouvrent
# directement dans la partie, sans passer par la création/le choix des équipes.
set -euo pipefail

AUTOLOGIN="http://localhost:3000/api/dev/autologin"
QUICKSTART="http://localhost:3000/api/dev/quickstart"
ROOM_CODE="TEST"

QUICK=false
for arg in "$@"; do
    case "$arg" in
        -q|--quick) QUICK=true ;;
    esac
done

echo "=== Seed de la base ==="
if docker-compose exec backend uv run /app/DEV/seed.py; then
    echo ""
else
    echo "⚠ Seed échoué — le backend est-il démarré ? (docker compose up)"
    exit 1
fi

PROFILES=("Profile 1" "Profile 2" "Profile 3" "Profile 4")
PLAYERS=("alice" "bob" "charlie" "diana")

ROOM_PARAM=""
if [ "$QUICK" = true ]; then
    echo "=== Création automatique du salon '$ROOM_CODE' (partie prête à jouer) ==="
    if curl -sf -X POST "$QUICKSTART/$ROOM_CODE" > /dev/null; then
        ROOM_PARAM="?room=$ROOM_CODE"
        echo ""
    else
        echo "⚠ Quickstart échoué — le backend est-il démarré en mode DEVELOPMENT=true ?"
        exit 1
    fi
fi

echo "=== Ouverture Chrome ==="
for i in "${!PLAYERS[@]}"; do
    profile="${PROFILES[$i]}"
    player="${PLAYERS[$i]}"

    echo "  $profile → $player"

    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" \
        --profile-directory="$profile" \
        --app="$AUTOLOGIN/$player$ROOM_PARAM" &

    sleep 0.3
done

echo ""
if [ "$QUICK" = true ]; then
    echo "Les 4 fenêtres sont ouvertes, directement dans la partie (salon '$ROOM_CODE')."
else
    echo "Les 4 fenêtres sont ouvertes. Chaque joueur est connecté sur localhost:3000."
fi
