# The site and the judge worker share this image (SPEC §8): compose.prod.yml runs it as
# `web` (gunicorn), `worker` (manage.py judge_worker) and the one-off `migrate`.
# Multi-arch: nothing here names an architecture, so it builds on x86_64 and arm64 alike.
FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir uv==0.8.17

WORKDIR /app
# Dependencies first: this layer is rebuilt only when the lock file changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# Tailwind (the pinned standalone binary, no Node) and collectstatic run at build time with
# the example settings; the real .env is never part of the image.
RUN set -a && . ./.env.example && set +a \
    && export DJANGO_SECRET_KEY=build-only DJANGO_DEBUG=false \
    && python manage.py tailwind build \
    && python manage.py collectstatic --noinput \
    && rm -rf .django_tailwind_cli

# Uploaded files live in a volume mounted here; it inherits this owner on first use.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data/media \
    && chown app:app /data/media
USER app

EXPOSE 8000
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000"]
