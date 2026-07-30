.PHONY: bootstrap dev test lint typecheck architecture-check
bootstrap:
	@echo "Install Python with uv and frontend dependencies with pnpm. See docs/11-local-development.md"
dev:
	docker compose -f infra/docker-compose.yml up
lint:
	python -m compileall -q services packages
	@echo "Run: ruff check . && pnpm lint"
typecheck:
	@echo "Run: mypy services packages && pnpm typecheck"
test:
	python -m unittest discover -s packages/landmark_engine/tests -p 'test_*.py'
architecture-check:
	python tools/check_stubs.py
