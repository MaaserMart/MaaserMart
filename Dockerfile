# One container: Caddy in front (static files, the public port) and Gunicorn
# behind it on 127.0.0.1:8000, the shape §4.10/§4.11 describe (D-YOSEF-railway).
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv
COPY --from=caddy:2.8.4 /usr/bin/caddy /usr/local/bin/caddy

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first, so a code change doesn't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

# Versioned static files for Caddy. Production settings refuse to load without
# their secrets, so this step gets throwaway values; none reach the runtime.
RUN DJANGO_SECRET_KEY=collectstatic-only-not-a-real-secret-0000 \
    DJANGO_ALLOWED_HOSTS=build \
    DATABASE_URL=postgres://build@localhost/build \
    EMAIL_HOST=build EMAIL_HOST_USER=build EMAIL_HOST_PASSWORD=build \
    python manage.py collectstatic --noinput

RUN chmod +x deploy/start.sh deploy/predeploy.sh
CMD ["deploy/start.sh"]
