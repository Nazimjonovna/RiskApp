#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  python manage.py migrate --noinput
fi

python manage.py collectstatic --noinput

RUN_ASGI="${RUN_ASGI:-true}"
if [ "$RUN_ASGI" = "true" ]; then
  ASGI_BIND_HOST="${ASGI_BIND_HOST:-0.0.0.0}"
  ASGI_BIND_PORT="${ASGI_BIND_PORT:-8000}"
  exec daphne -b "$ASGI_BIND_HOST" -p "$ASGI_BIND_PORT" conf.asgi:application
fi

exec "$@"
