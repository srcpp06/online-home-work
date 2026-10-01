# check=skip=InvalidDefaultArgInFrom
# (DART_VERSION has no default on purpose: it comes from .env via make base-images.)
#
# Base image for the `dart` runner profile (SPEC §3.1). The official Dart image is
# published for linux/amd64 and linux/arm64, so this builds on either.
ARG DART_VERSION
FROM dart:${DART_VERSION}

# Tests run as uid/gid 1000 (SPEC §3.6).
RUN groupadd --gid 1000 ohw \
    && useradd --uid 1000 --gid 1000 --create-home ohw \
    && install --directory --owner=ohw --group=ohw /opt/ohw
USER ohw
ENV PUB_CACHE=/home/ohw/.pub-cache
WORKDIR /home/ohw

# Warm-up: puts package:test into the pub cache and checks that tests run.
COPY --chown=ohw:ohw warmup /opt/ohw/warmup
RUN dart --disable-analytics \
    && cd /opt/ohw/warmup \
    && dart pub get \
    && dart test \
    && rm -rf .dart_tool
