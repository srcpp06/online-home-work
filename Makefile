.DEFAULT_GOAL := help
UV ?= uv

.PHONY: help setup test test-docker lint format check base-images poc fixtures-dart

help: ## Show available commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-14s %s\n", $$1, $$2}'

setup: ## Install dependencies and git hooks
	$(UV) sync
	$(UV) run pre-commit install

test: ## Fast tests (no Docker)
	$(UV) run pytest -m "not docker"

test-docker: ## Integration tests that need Docker
	$(UV) run pytest -m docker

lint: ## ruff check + ruff format --check
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: ## Fix lint issues and format code
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

check: lint test ## lint + test, run before every commit

base-images: ## Build and smoke-test profile base images (PROFILES="dart flutter")
	scripts/build-base-images.sh $(PROFILES)

poc: ## Run examples/ through the judge and print timings (Markdown)
	$(UV) run python -m scripts.poc --output docs/poc/$$(uname -m)-$$(date +%Y%m%d-%H%M).md

fixtures-dart: ## Re-record dart_json parser fixtures (needs Docker and internet)
	scripts/record-dart-json-fixtures.sh
