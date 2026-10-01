#!/usr/bin/env bash
# Builds runner profile base images for this machine's architecture, then smoke-tests
# each one the way the judge runs tests: no network, uid 1000.
#
# Usage: scripts/build-base-images.sh [dart] [flutter]   (default: all)
# Versions come from the environment, else from .env (see .env.example).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

config() {
    local name="$1" value="${!1:-}"
    if [[ -z "$value" && -f "$root/.env" ]]; then
        value="$(grep -E "^${name}=" "$root/.env" | tail -n 1 | cut -d= -f2- || true)"
    fi
    if [[ -z "$value" ]]; then
        echo "error: $name is not set. Add it to .env (see .env.example) or set it in the environment." >&2
        exit 1
    fi
    printf '%s' "$value"
}

smoke_test() {
    local image="$1" commands="$2"
    echo "smoke test: $image (offline, uid 1000)"
    docker run --rm --network none --user 1000:1000 "$image" \
        bash -euo pipefail -c "cp -r /opt/ohw/warmup /tmp/warmup && cd /tmp/warmup && $commands"
}

build_dart() {
    local version image
    version="$(config DART_VERSION)"
    image="ohw-base-dart:$version"
    docker build --tag "$image" --build-arg "DART_VERSION=$version" "$root/profiles/dart"
    smoke_test "$image" "dart pub get --offline && dart test"
}

build_flutter() {
    local version image
    version="$(config FLUTTER_VERSION)"
    image="ohw-base-flutter:$version"
    docker build --tag "$image" --build-arg "FLUTTER_VERSION=$version" "$root/profiles/flutter"
    smoke_test "$image" "flutter --version && flutter pub get --offline && flutter test --no-pub"
}

profiles=("$@")
if [[ ${#profiles[@]} -eq 0 ]]; then
    profiles=(dart flutter)
fi
for profile in "${profiles[@]}"; do
    case "$profile" in
        dart) build_dart ;;
        flutter) build_flutter ;;
        *) echo "error: unknown profile '$profile' (expected: dart, flutter)" >&2; exit 1 ;;
    esac
done
