.DEFAULT_GOAL := help
UV ?= uv

.PHONY: help setup test test-docker lint format check base-images poc fixtures-dart
.PHONY: needs-uv needs-docker

help: ## Show available commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-14s %s\n", $$1, $$2}'

# Stop early with a message that says how to fix it, instead of "command not found".
needs-uv:
	@command -v $(UV) > /dev/null || { \
		echo "error: uv is not installed. CachyOS: sudo pacman -S uv (others: https://docs.astral.sh/uv/)" >&2; \
		exit 1; }

needs-docker:
	@command -v docker > /dev/null || { \
		echo "error: docker is not installed. CachyOS: sudo pacman -S docker docker-buildx" >&2; \
		exit 1; }
	@docker info > /dev/null 2>&1 || { \
		echo "error: can't reach the Docker daemon. Start it: sudo systemctl enable --now docker" >&2; \
		echo "       and allow your user: sudo usermod -aG docker \$$USER, then log out and in again." >&2; \
		exit 1; }

# The settings every command reads; created once, never overwritten.
.env:
	cp .env.example .env
	@echo "Created .env from .env.example"

setup: needs-uv .env ## Install dependencies and git hooks, create .env
	$(UV) sync
	$(UV) run pre-commit install

test: needs-uv ## Fast tests (no Docker)
	$(UV) run pytest -m "not docker"

test-docker: needs-uv needs-docker .env ## Integration tests that need Docker
	$(UV) run pytest -m docker

lint: needs-uv ## ruff check + ruff format --check
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: needs-uv ## Fix lint issues and format code
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

check: lint test ## lint + test, run before every commit

base-images: needs-docker .env ## Build and smoke-test profile base images (PROFILES="dart flutter")
	scripts/build-base-images.sh $(PROFILES)

poc: needs-uv needs-docker .env ## Run examples/ through the judge and print timings (Markdown)
	$(UV) run python -m scripts.poc --output docs/poc/$$(uname -m)-$$(date +%Y%m%d-%H%M).md

fixtures-dart: needs-docker ## Re-record dart_json parser fixtures (needs Docker and internet)
	scripts/record-dart-json-fixtures.sh
