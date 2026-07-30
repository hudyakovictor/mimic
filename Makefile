.PHONY: help bootstrap dev test lint typecheck architecture-check seed migrate clean fmt check all

help:
	@echo "MimicGuard — make targets:"
	@echo "  bootstrap   - install dev dependencies (uv + pnpm)"
	@echo "  migrate     - run alembic migrations"
	@echo "  seed        - seed default tenant + admin + model versions"
	@echo "  dev         - start docker-compose dev stack"
	@echo "  test        - run pytest"
	@echo "  lint        - ruff + eslint"
	@echo "  typecheck   - mypy + tsc"
	@echo "  fmt         - ruff format + prettier"
	@echo "  architecture-check - inventory MG-STUB references"
	@echo "  check       - lint + typecheck + tests"
	@echo "  clean       - remove build artifacts"

bootstrap:
	@echo "Installing Python deps via uv..."
	uv sync --all-extras
	@echo "Installing frontend deps via pnpm..."
	cd apps/admin && pnpm install
	@echo "Bootstrap complete. Copy .env.example to .env and edit."

migrate:
	cd services/api && PYTHONPATH=../.. alembic upgrade head

seed:
	PYTHONPATH=services/api:packages:services/worker python -m scripts.seed

dev:
	docker compose -f infra/docker-compose.yml up --build

test:
	PYTHONPATH=services/api:packages:services/worker python -m pytest -q

test-unit:
	PYTHONPATH=services/api:packages:services/worker python -m pytest -q tests/unit packages/landmark_engine/tests

test-integration:
	PYTHONPATH=services/api:packages:services/worker python -m pytest -q tests/integration

test-e2e:
	cd apps/admin && pnpm test:e2e

test-all: test
	@echo "All tests passed."

lint:
	ruff check services packages scripts
	cd apps/admin && pnpm lint

typecheck:
	cd services/api && PYTHONPATH=../.. mypy app packages
	cd apps/admin && pnpm typecheck

fmt:
	ruff format services packages scripts
	cd apps/admin && pnpm format

architecture-check:
	PYTHONPATH=services/api:packages python -m tools.check_stubs

ci: lint typecheck test architecture-check
	@echo "CI passed."

check: ci
	@echo "All checks passed."

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	find . -type d -name .mypy_cache -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
	find . -type d -name node_modules -prune -exec rm -rf {} +
	find . -type d -name dist -prune -exec rm -rf {} +
	rm -f services/api/mimicguard.db
	rm -rf .coverage htmlcov/

.PHONY: install-hooks
install-hooks:
	@which pre-commit && pre-commit install || echo "pre-commit not installed; skipping"
