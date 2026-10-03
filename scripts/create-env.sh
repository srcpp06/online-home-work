#!/usr/bin/env bash
# Creates .env from .env.example with a new random DJANGO_SECRET_KEY. Never overwrites .env.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -e .env ]]; then
    echo ".env already exists; delete it first to create a new one" >&2
    exit 1
fi

# 48 random bytes: about 60 characters after dropping the symbols sed and URLs dislike.
secret=$(head -c 48 /dev/urandom | base64 | tr -d '\n/+=')
sed "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=${secret}|" .env.example > .env
echo "Created .env from .env.example with a new DJANGO_SECRET_KEY"
