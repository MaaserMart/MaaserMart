#!/usr/bin/env bash
# Railway runs this once per deploy, before the new container takes traffic.
# Deploy only from main: this migrates the shared RDS database (D-YOSEF-railway).
set -euo pipefail

if [ -n "${RDS_INSTANCE_ID:-}" ]; then
  python manage.py wake_db --wait
fi
python manage.py migrate --noinput
python manage.py createcachetable
