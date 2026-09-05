# AlleleForge developer tasks. CI runs the same commands; this is the local
# mirror so `make ci` reproduces the gate before a push.
.PHONY: help install lint type test docs examples reproduce figures native ci

help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Editable install with the dev + genome extras.
	pip install -e ".[dev,cli,web]" "pyfaidx>=0.8" "pyliftover>=0.4"

lint: ## Ruff lint + format check.
	ruff check src tests scripts
	ruff format --check src tests scripts

type: ## mypy --strict over the library.
	mypy --strict src/alleleforge

test: ## Run the test suite with the coverage gate.
	pytest

docs: ## Build the docs site in strict mode.
	mkdocs build --strict

examples: ## Execute the runnable notebooks, as CI's `examples` job does.
	pytest --nbmake examples/ --no-cov

reproduce: ## Re-derive the canonical run and diff it against the golden (R0).
	python scripts/reproduce.py

figures: ## Regenerate the committed docs/preprint figures (dependency-free SVG).
	python scripts/figures.py

native: ## Build the Rust crate and run the native parity tests.
	cd rust && maturin build --release --out dist
	pip install rust/dist/*.whl --force-reinstall
	pytest -m native --no-cov

# Mirrors every blocking CI job, in CI's order. `examples` is here because it was
# once missing and a change that passed lint, types, tests, docs and reproduce still
# broke a notebook — a gate is only as good as its least convenient member, and the
# member most likely to be left out is the slow one that catches a different class
# of failure. The `security` job is advisory in CI (`|| true`) and the `rust` job
# needs the crate built (`make native`), so neither is included here.
ci: lint type test docs examples reproduce ## Run the full local CI gate.
