#!/usr/bin/env bash
# Records real `dart test --reporter json` output for the dart_json parser tests.
#
# Each folder in solutions/ is one student lib/ run against the same project.
# Needs Docker and internet (pub get). Re-run after a Dart SDK upgrade and
# review the diff: the parser tests must still pass on the new output.
set -euo pipefail

DART_IMAGE="${DART_IMAGE:-dart:stable}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixtures="$root/tests/judge/parsers/fixtures/dart_json"

docker run --rm \
    --user "$(id -u):$(id -g)" \
    --env HOME=/tmp --env PUB_CACHE=/tmp/pub-cache \
    --volume "$fixtures:/fixtures" \
    "$DART_IMAGE" bash -euo pipefail -c '
        cp -r /fixtures/project /tmp/work
        cd /tmp/work
        dart pub get > /dev/null
        dart --version > /fixtures/VERSION 2>&1
        for solution in /fixtures/solutions/*/; do
            name="$(basename "$solution")"
            rm -rf lib
            cp -r "$solution/lib" lib
            # Exit code is non-zero when tests fail; the output is what we want.
            dart test --reporter json --concurrency=1 test/_ohw_all_test.dart \
                > "/fixtures/$name.jsonl" || true
            echo "recorded $name"
        done
    '
