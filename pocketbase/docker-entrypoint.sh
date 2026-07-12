#!/bin/sh
set -e

if [ -n "$PB_SUPERUSER_EMAIL" ] && [ -n "$PB_SUPERUSER_PASSWORD" ]; then
    /pb/pocketbase superuser upsert "$PB_SUPERUSER_EMAIL" "$PB_SUPERUSER_PASSWORD"
fi

exec /pb/pocketbase serve --http=0.0.0.0:8090
