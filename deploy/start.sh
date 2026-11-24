#!/usr/bin/env bash
# Run Gunicorn (and optionally a Celery worker) behind Caddy. If any of them
# exits, exit too, so Railway restarts the container (D-YOSEF-railway).
set -euo pipefail

gunicorn config.wsgi \
  --bind 127.0.0.1:8000 \
  --workers "${WEB_CONCURRENCY:-3}" \
  --access-logfile - \
  --error-logfile - &

# Off by default: with CELERY_TASK_ALWAYS_EAGER=true, emails send inside the
# request and no worker or SQS queue is needed.
if [ "${RUN_CELERY_WORKER:-false}" = "true" ]; then
  celery -A config worker --loglevel=info --concurrency=1 &
fi

caddy run --config /app/deploy/Caddyfile --adapter caddyfile &

wait -n
exit 1
