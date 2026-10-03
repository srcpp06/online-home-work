.DEFAULT_GOAL := help
UV ?= uv

.PHONY: help setup db db-down migrate css dev test test-docker lint format check
.PHONY: worker base-images poc fixtures-dart needs-uv needs-docker needs-compose deploy prod-logs backup
COMPOSE_DEV = docker compose -f compose.dev.yml
COMPOSE_PROD = docker compose -f compose.prod.yml

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

needs-compose: needs-docker
	@docker compose version > /dev/null 2>&1 || { \
		echo "error: docker compose is not installed. CachyOS: sudo pacman -S docker-compose" >&2; \
		exit 1; }

# The settings every command reads; created once with a new secret key, never overwritten.
.env:
	scripts/create-env.sh

setup: needs-uv .env ## Install dependencies and git hooks, create .env
	$(UV) sync
	$(UV) run pre-commit install

db: needs-compose .env ## Start the development PostgreSQL (compose.dev.yml)
	$(COMPOSE_DEV) up --detach --wait db

db-down: needs-compose ## Stop the development PostgreSQL; its data stays
	$(COMPOSE_DEV) down

migrate: needs-uv db ## Apply database migrations and load runner profiles
	$(UV) run python manage.py migrate
	$(UV) run python manage.py load_profiles

css: needs-uv ## Build static/css/app.css from assets/source.css (Tailwind; first run downloads it)
	$(UV) run python manage.py tailwind build

# css first: a failed Tailwind download stops here with its error, not as unstyled pages.
dev: migrate css ## Run the site at http://127.0.0.1:8000 and rebuild the CSS on every change
	$(UV) run python manage.py tailwind runserver

worker: needs-uv needs-docker migrate ## Run the judge worker: builds task images and checks submissions
	$(UV) run python manage.py judge_worker

test: needs-uv db ## Fast tests: the judge without Docker, the site with the development PostgreSQL
	$(UV) run pytest -m "not docker"

test-docker: needs-uv needs-docker .env ## Integration tests that need Docker
	$(UV) run pytest -m docker

lint: needs-uv ## ruff check + ruff format --check, djLint for templates
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run djlint templates apps --lint
	$(UV) run djlint templates apps --check

format: needs-uv ## Fix lint issues and format code and templates
	$(UV) run ruff check --fix .
	$(UV) run ruff format .
	$(UV) run djlint templates apps --reformat --quiet

check: lint test ## lint + test, run before every commit

base-images: needs-docker .env ## Build and smoke-test profile base images (PROFILES="dart flutter")
	scripts/build-base-images.sh $(PROFILES)

poc: needs-uv needs-docker .env ## Run examples/ through the judge and print timings (Markdown)
	$(UV) run python -m scripts.poc --output docs/poc/$$(uname -m)-$$(date +%Y%m%d-%H%M).md

fixtures-dart: needs-docker ## Re-record dart_json parser fixtures (needs Docker and internet)
	scripts/record-dart-json-fixtures.sh

# --- Production (docs/deploy.md) ---
deploy: needs-compose ## Production: build and start, or update, everything in compose.prod.yml
	$(COMPOSE_PROD) up --detach --build
	$(COMPOSE_PROD) ps --all

prod-logs: needs-compose ## Production: follow the logs (SERVICE=worker for one service)
	$(COMPOSE_PROD) logs --follow --tail 100 $(SERVICE)

backup: needs-compose ## Production: save the database now (backups/)
	scripts/backup.sh db
