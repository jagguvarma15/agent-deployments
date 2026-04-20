# agent-deployments Makefile
#
# Usage:
#   make up PROTOTYPE=customer-support-triage TRACK=python
#   make test PROTOTYPE=customer-support-triage TRACK=python
#   make eval PROTOTYPE=docs-rag-qa TRACK=typescript
#   make security PROTOTYPE=research-assistant

PROTOTYPE ?=
TRACK ?= python

# Validate inputs
_check_prototype:
ifndef PROTOTYPE
	$(error PROTOTYPE is required. Usage: make <target> PROTOTYPE=<name> [TRACK=python|typescript])
endif
	@test -d prototypes/$(PROTOTYPE) || (echo "Error: prototypes/$(PROTOTYPE) does not exist" && exit 1)

_check_track: _check_prototype
	@test -d prototypes/$(PROTOTYPE)/$(TRACK) || (echo "Error: prototypes/$(PROTOTYPE)/$(TRACK) does not exist" && exit 1)

PROTO_DIR = prototypes/$(PROTOTYPE)/$(TRACK)

# ---------------------------------------------------------------------------
# Docker Compose
# ---------------------------------------------------------------------------

.PHONY: up
up: _check_track
	cd $(PROTO_DIR) && docker compose up --build -d

.PHONY: down
down: _check_track
	cd $(PROTO_DIR) && docker compose down

.PHONY: logs
logs: _check_track
	cd $(PROTO_DIR) && docker compose logs -f

.PHONY: restart
restart: _check_track
	cd $(PROTO_DIR) && docker compose restart

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

.PHONY: test
test: _check_track
ifeq ($(TRACK),python)
	cd $(PROTO_DIR) && uv run pytest tests/unit tests/integration -v
else
	cd $(PROTO_DIR) && pnpm run test
endif

.PHONY: test-unit
test-unit: _check_track
ifeq ($(TRACK),python)
	cd $(PROTO_DIR) && uv run pytest tests/unit -v
else
	cd $(PROTO_DIR) && pnpm run test:unit
endif

.PHONY: test-integration
test-integration: _check_track
ifeq ($(TRACK),python)
	cd $(PROTO_DIR) && uv run pytest tests/integration -v
else
	cd $(PROTO_DIR) && pnpm run test:integration
endif

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

.PHONY: eval
eval: _check_track
ifeq ($(TRACK),python)
	cd $(PROTO_DIR) && uv run pytest tests/evals -v
else
	cd $(PROTO_DIR) && pnpm run test:eval
endif

# ---------------------------------------------------------------------------
# Linting
# ---------------------------------------------------------------------------

.PHONY: lint
lint: _check_track
ifeq ($(TRACK),python)
	cd $(PROTO_DIR) && uv run ruff check . && uv run ruff format --check .
else
	cd $(PROTO_DIR) && pnpm run lint
endif

.PHONY: format
format: _check_track
ifeq ($(TRACK),python)
	cd $(PROTO_DIR) && uv run ruff format .
else
	cd $(PROTO_DIR) && pnpm run format
endif

# ---------------------------------------------------------------------------
# Security (Promptfoo — runs both tracks)
# ---------------------------------------------------------------------------

.PHONY: security
security: _check_prototype
	@echo "Running Promptfoo security scan for $(PROTOTYPE)..."
	@if [ -f prototypes/$(PROTOTYPE)/python/eval/promptfoo.yaml ]; then \
		echo "--- Python track ---"; \
		promptfoo redteam run --config prototypes/$(PROTOTYPE)/python/eval/promptfoo.yaml; \
	fi
	@if [ -f prototypes/$(PROTOTYPE)/typescript/eval/promptfoo.yaml ]; then \
		echo "--- TypeScript track ---"; \
		promptfoo redteam run --config prototypes/$(PROTOTYPE)/typescript/eval/promptfoo.yaml; \
	fi

# ---------------------------------------------------------------------------
# Docker build (standalone, no compose)
# ---------------------------------------------------------------------------

.PHONY: docker-build
docker-build: _check_track
	cd $(PROTO_DIR) && docker build -t agent-deployments/$(PROTOTYPE)-$(TRACK) .

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

.PHONY: clean
clean: _check_track
	cd $(PROTO_DIR) && docker compose down -v --remove-orphans

.PHONY: health
health:
	@curl -sf http://localhost:8000/health && echo " OK" || echo " FAIL"

.PHONY: list
list:
	@echo "Available prototypes:"
	@ls prototypes/ 2>/dev/null | grep -v _template || echo "  (none yet)"

.PHONY: help
help:
	@echo "agent-deployments Makefile"
	@echo ""
	@echo "Usage: make <target> PROTOTYPE=<name> [TRACK=python|typescript]"
	@echo ""
	@echo "Targets:"
	@echo "  up              Start services with docker compose"
	@echo "  down            Stop services"
	@echo "  logs            Follow service logs"
	@echo "  restart         Restart services"
	@echo "  test            Run all tests (unit + integration)"
	@echo "  test-unit       Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  eval            Run evaluation suite"
	@echo "  lint            Run linter"
	@echo "  format          Run formatter"
	@echo "  security        Run Promptfoo security scan (both tracks)"
	@echo "  docker-build    Build Docker image"
	@echo "  clean           Stop services and remove volumes"
	@echo "  health          Check if the API is responding"
	@echo "  list            List available prototypes"
	@echo "  help            Show this help"
