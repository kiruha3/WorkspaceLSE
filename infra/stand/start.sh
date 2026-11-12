#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
if [ ! -f infra/stand/.env ]; then
    printf '%s\n' 'Run python3 infra/stand/init_env.py --host <IP> first.'
    exit 1
fi
compose() { docker compose --env-file infra/stand/.env -f infra/stand/compose.yml "$@"; }
compose build
compose up -d db
compose run --rm backend python manage.py migrate --noinput
compose run --rm backend python manage.py populate_stand --count "${AIS_STAND_COUNT:-1200}" --as-of "${AIS_STAND_AS_OF:-2026-11-09}" --credentials-file /access/credentials.json
compose run --rm backend python manage.py collectstatic --noinput
compose up -d backend web
compose ps
printf '%s\n' 'Stand started. Account credentials are in .stand-access/credentials.json.'
