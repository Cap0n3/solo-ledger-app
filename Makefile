.DEFAULT_GOAL := help
SHELL := /bin/sh

COMPOSE := docker compose -f compose.yaml -f compose.dev.yaml
# Drop the pseudo-TTY when make is not driven by a terminal (CI, editors, agents).
TTY := $(shell [ -t 0 ] || echo -T)

# Inside the container (IN_CONTAINER=1 is set by the Dockerfile) commands run
# directly; from the host they go through docker compose.
ifeq ($(IN_CONTAINER),1)
EXEC :=
else
EXEC := $(COMPOSE) exec $(TTY) web
endif

define require_host
$(if $(IN_CONTAINER),$(error Target "$@" must be run from the host, not inside the container))
endef

.PHONY: help setup up down build logs reset-db run migrate migrations test lint format npm assets assets-watch seed shell lock createsuperuser

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- Host only ----------------------------------------------------------------

setup: ## First run: create .env, build, start, migrate, build assets, seed
	$(require_host)
	[ -f .env ] || cp .env.example .env
	$(COMPOSE) build
	$(COMPOSE) up -d
	$(MAKE) migrate npm assets seed

up: ## Start the stack in the background
	$(require_host)
	$(COMPOSE) up -d

down: ## Stop the stack
	$(require_host)
	$(COMPOSE) down

build: ## Rebuild the web image (after changing pyproject.toml, uv.lock or Dockerfile)
	$(require_host)
	$(COMPOSE) build web
	$(COMPOSE) up -d web

logs: ## Follow the stack logs
	$(require_host)
	$(COMPOSE) logs -f

reset-db: ## Stop the stack and delete the database volume (all data is lost)
	$(require_host)
	$(COMPOSE) down -v

# --- Host or container --------------------------------------------------------

run: ## Run the Django development server (used from the Dev Container)
	$(EXEC) python manage.py runserver 0.0.0.0:8000

migrate: ## Apply migrations
	$(EXEC) python manage.py migrate

migrations: ## Create migrations
	$(EXEC) python manage.py makemigrations

test: ## Run the test suite
	$(EXEC) pytest

lint: ## Run ruff, mypy, djlint, prettier and the migration check
	$(EXEC) ruff check .
	$(EXEC) ruff format --check .
	$(EXEC) mypy
	$(EXEC) djlint core/templates --lint
	$(EXEC) djlint core/templates --check
	$(EXEC) npm run --silent format:check
	$(EXEC) python manage.py makemigrations --check --dry-run

format: ## Auto-format all code
	$(EXEC) ruff check --fix .
	$(EXEC) ruff format .
	$(EXEC) djlint core/templates --reformat
	$(EXEC) npm run --silent format

npm: ## Install JS dependencies when package-lock.json changed
	$(EXEC) sh -c '[ node_modules/.package-lock.json -nt package-lock.json ] || npm ci'

assets: npm ## Build CSS and JS into core/static/dist
	$(EXEC) npm run --silent build

assets-watch: npm ## Rebuild assets on change
	$(EXEC) npm run --silent watch

seed: ## Load obviously fake development data (test accounts and activities)
	$(EXEC) python manage.py seed

shell: ## Open a Django shell
	$(EXEC) python manage.py shell

lock: ## Regenerate uv.lock after editing pyproject.toml (then run: make build)
	$(EXEC) uv lock

createsuperuser: ## Create the technical admin account
	$(EXEC) python manage.py createsuperuser
