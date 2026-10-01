# Base image for the `flutter` runner profile (SPEC §4). Builds on linux/amd64 and
# linux/arm64: the SDK comes from git (the release archives are x86_64 only), and the
# flutter tool downloads the Dart SDK and engine artifacts for the machine it runs on.
FROM debian:bookworm-slim

ARG FLUTTER_VERSION
RUN test -n "$FLUTTER_VERSION" || { echo "FLUTTER_VERSION build arg is required" >&2; exit 1; }

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl git unzip xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Tests run as uid/gid 1000 (SPEC §3.6). The SDK belongs to that user because the
# flutter tool writes lock and stamp files into its own cache.
RUN groupadd --gid 1000 ohw \
    && useradd --uid 1000 --gid 1000 --create-home ohw \
    && install --directory --owner=ohw --group=ohw /opt/flutter /opt/ohw
USER ohw
ENV FLUTTER_ROOT=/opt/flutter \
    PUB_CACHE=/home/ohw/.pub-cache \
    PATH=/opt/flutter/bin:/opt/flutter/bin/cache/dart-sdk/bin:$PATH
WORKDIR /home/ohw

RUN git clone --depth 1 --branch "$FLUTTER_VERSION" https://github.com/flutter/flutter.git /opt/flutter \
    && flutter config --no-analytics --no-cli-animations \
    && flutter --disable-analytics \
    && dart --disable-analytics \
    && flutter --version

# Warm-up: one `flutter test` downloads and caches what tests need (flutter_tester, fonts,
# sky_engine), and the common packages land in the pub cache for faster task builds.
COPY --chown=ohw:ohw common_packages.txt /opt/ohw/
COPY --chown=ohw:ohw warmup /opt/ohw/warmup
RUN cd /opt/ohw/warmup \
    && flutter pub add $(grep -E '^[^#[:space:]]' /opt/ohw/common_packages.txt) \
    && flutter test \
    && rm -rf .dart_tool build
