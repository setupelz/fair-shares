# Makefile to help automate key steps
PYTHON := uv run python

.DEFAULT_GOAL := help

.PHONY: help
help:  ## Show available targets
	@echo "fair-shares - Data Processing & Allocation Pipeline"
	@echo ""
	@echo "Getting Started:"
	@echo "  1. Run main entry point notebook (it handles data setup automatically):"
	@echo "     - notebooks/301_custom_fair_share_allocation.py"
	@echo ""
	@echo "Development:"
	@echo "  dev-pipeline-scenarios  Create AR6 scenarios pipeline (for dev/testing)"
	@echo "  dev-pipeline-rcbs       Create RCBs pipeline (for dev/testing)"
	@echo "  dev-pipeline-rcb-pathways  Create RCB-pathways pipeline (for dev/testing)"
	@echo "  sync-ipynb              Sync ipynb files with jupytext"
	@echo "  test                    Run the complete test suite"
	@echo "  test-cov                Run tests with coverage report"
	@echo "  lint                    Run ruff linter (check only)"
	@echo "  lint-fix                Run ruff linter and formatter with auto-fix"
	@echo "  clean                   Remove output files and caches"
	@echo "  unlock                  Remove Snakemake lock files"
	@echo ""
	@echo "Virtual environments:"
	@echo "  virtual-environment      Update with core dependencies only"
	@echo "  virtual-environment-dev  Update with development dependencies"
	@echo "  virtual-environment-docs Update with documentation dependencies"
	@echo "  virtual-environment-all  Update with all dependencies"
	@echo ""
	@echo "Documentation:"
	@echo "  docs-serve              Serve documentation locally"
	@echo "  docs-build              Build documentation for production"
	@echo "  docs-deploy             Deploy documentation to GitHub Pages"

.PHONY: dev-pipeline-scenarios
dev-pipeline-scenarios:  ## [DEV] Create preprocessed data for AR6 scenarios (matches interactive defaults)
	@echo "Syncing notebook files..."
	uv run jupytext --sync notebooks/*.py
	uv run jupytext --set-formats ipynb,py:percent notebooks/*.py
	@echo "Creating data pipeline for AR6 scenarios (all-ghg-ex-co2-lulucf)..."
	uv run snakemake --config \
		emission_category=all-ghg-ex-co2-lulucf \
		active_emissions_source=primap-202503 \
		active_gdp_source=wdi-2025 \
		active_population_source=un-owid-2025 \
		active_gini_source=unu-wider-2025 \
		active_target_source=ar6 \
		--cores 1
	@echo ""
	@echo "  AR6 scenarios pipeline created!"
	@echo "  Output: output/primap-202503_wdi-2025_un-owid-2025_unu-wider-2025_ar6/"

.PHONY: dev-pipeline-rcbs
dev-pipeline-rcbs:  ## [DEV] Create preprocessed data for RCBs (matches interactive defaults)
	@echo "Syncing notebook files..."
	uv run jupytext --sync notebooks/*.py
	uv run jupytext --set-formats ipynb,py:percent notebooks/*.py
	@echo "Creating data pipeline for RCBs (co2-ffi)..."
	uv run snakemake --config \
		emission_category=co2-ffi \
		active_emissions_source=primap-202503 \
		active_gdp_source=wdi-2025 \
		active_population_source=un-owid-2025 \
		active_gini_source=unu-wider-2025 \
		active_target_source=rcbs \
		--cores 1
	@echo ""
	@echo "  RCBs pipeline created!"
	@echo "  Output: output/primap-202503_wdi-2025_un-owid-2025_unu-wider-2025_rcbs/"

.PHONY: dev-pipeline-rcb-pathways
dev-pipeline-rcb-pathways:  ## [DEV] Create preprocessed data for RCB-pathways (matches interactive defaults)
	@echo "Syncing notebook files..."
	uv run jupytext --sync notebooks/*.py
	uv run jupytext --set-formats ipynb,py:percent notebooks/*.py
	@echo "Creating data pipeline for RCB-pathways (co2-ffi)..."
	uv run snakemake --config \
		emission_category=co2-ffi \
		active_emissions_source=primap-202503 \
		active_gdp_source=wdi-2025 \
		active_population_source=un-owid-2025 \
		active_gini_source=unu-wider-2025 \
		active_target_source=rcb-pathways \
		--cores 1
	@echo ""
	@echo "  RCB-pathways pipeline created!"
	@echo "  Output: output/primap-202503_wdi-2025_un-owid-2025_unu-wider-2025_rcb-pathways_co2-ffi/"

.PHONY: virtual-environment
virtual-environment:  ## update virtual environment with core dependencies only
	uv sync

.PHONY: virtual-environment-dev
virtual-environment-dev:  ## update virtual environment with development dependencies
	uv sync --extra dev

.PHONY: virtual-environment-docs
virtual-environment-docs:  ## update virtual environment with documentation dependencies
	uv sync --extra docs

.PHONY: virtual-environment-all
virtual-environment-all:  ## update virtual environment with all dependencies (dev + docs)
	uv sync --all-extras

.PHONY: sync-ipynb
sync-ipynb:  ## sync ipynb files with jupytext
	uv run jupytext --sync notebooks/*.py
	uv run jupytext --set-formats ipynb,py:percent notebooks/*.py

.PHONY: test
test:  ## run the complete test suite
	uv sync --extra dev
	uv run pytest tests/ -v

.PHONY: test-cov
test-cov:  ## run tests with coverage report
	uv sync --extra dev
	uv run pytest tests/ -v --cov=fair_shares --cov-report=term-missing --cov-report=html
	@echo ""
	@echo "Coverage HTML report: htmlcov/index.html"

.PHONY: lint
lint:  ## run ruff linter and formatter
	uv run ruff check src tests
	uv run ruff format --check src tests

.PHONY: lint-fix
lint-fix:  ## run ruff linter and formatter with auto-fix
	uv run ruff check --fix src tests
	uv run ruff format src tests

.PHONY: clean
clean:  ## remove output files and caches
	$(PYTHON) -c "import shutil; import pathlib; [shutil.rmtree(p, ignore_errors=True) for p in [pathlib.Path('output'), pathlib.Path('.snakemake'), pathlib.Path('.pytest_cache'), pathlib.Path('htmlcov')]]"
	$(PYTHON) -c "import pathlib; p = pathlib.Path('.coverage'); p.unlink(missing_ok=True)"
	$(PYTHON) -c "import pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]"
	$(PYTHON) -c "import pathlib; import shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
	@echo "Cleaned output files and caches"

.PHONY: unlock
unlock:  ## remove Snakemake lock files
	$(PYTHON) -c "import pathlib; import shutil; locks = pathlib.Path('.snakemake/locks'); incomplete = pathlib.Path('.snakemake/incomplete'); [p.unlink() for p in locks.glob('*') if p.is_file()] if locks.exists() else None; [p.unlink() for p in incomplete.glob('*') if p.is_file()] if incomplete.exists() else None"
	@echo "Snakemake locks removed"

.PHONY: docs-serve
docs-serve:  ## serve documentation locally
	JUPYTER_PLATFORM_DIRS=1 uv run mkdocs serve

.PHONY: docs-build
docs-build:  ## build documentation for production
	JUPYTER_PLATFORM_DIRS=1 uv run mkdocs build

.PHONY: docs-deploy
docs-deploy:  ## deploy documentation to GitHub Pages
	JUPYTER_PLATFORM_DIRS=1 uv run mkdocs gh-deploy
