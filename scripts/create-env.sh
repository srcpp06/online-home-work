#!/usr/bin/env bash
# Creates .env from .env.example with a new random DJANGO_SECRET_KEY. Never overwrites .env.
#
#   scripts/create-env.sh                        development values (make setup)
#   scripts/create-env.sh --production DOMAIN    the server's values (docs/deploy.md):
#       DEBUG off, the domain, a new database password, /data/media, the docker group id,
#       the secret of the superadmin's private door
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -e .env ]]; then
    echo ".env already exists; delete it first to create a new one" >&2
    exit 1
fi

# Random letters and digits: 48 random bytes give about 60 after dropping / + =.
random() {
    head -c "$1" /dev/urandom | base64 | tr -d '\n/+='
}

secret=$(random 48)
production=()
if [[ "${1:-}" == "--production" ]]; then
    domain="${2:-}"
    if [[ ! "$domain" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}$ ]]; then
        echo "usage: $0 --production DOMAIN  (a domain such as ohw.example.uz, got '$domain')" >&2
        exit 1
    fi
    gid="${DOCKER_GID:-$(getent group docker | cut -d: -f3 || true)}"
    if [[ ! "$gid" =~ ^[0-9]+$ ]]; then
        echo "no docker group: install Docker first (docs/deploy.md)" >&2
        exit 1
    fi
    password=$(random 32)
    gate=$(random 48)
    production=(
        -e "s|^DJANGO_DEBUG=.*|DJANGO_DEBUG=false|"
        -e "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=${domain}|"
        -e "s|^DATABASE_URL=.*|DATABASE_URL=postgres://ohw:${password}@db:5432/ohw|"
        -e "s|^MEDIA_ROOT=.*|MEDIA_ROOT=/data/media|"
        -e "s|^#SITE_DOMAIN=.*|SITE_DOMAIN=${domain}|"
        -e "s|^#POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${password}|"
        -e "s|^#DOCKER_GID=.*|DOCKER_GID=${gid}|"
        -e "s|^#GUNICORN_CMD_ARGS=|GUNICORN_CMD_ARGS=|"
        -e "s|^#UPLOAD_MAX_BODY=|UPLOAD_MAX_BODY=|"
        -e "s|^#ADMIN_GATE_SECRET=.*|ADMIN_GATE_SECRET=${gate}|"
    )
elif [[ $# -gt 0 ]]; then
    echo "usage: $0 [--production DOMAIN]" >&2
    exit 1
fi

sed -e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=${secret}|" "${production[@]}" .env.example > .env
echo "Created .env from .env.example with a new DJANGO_SECRET_KEY${production:+ and the production values}"
