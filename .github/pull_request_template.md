## Description of Changes

<!-- Briefly describe the purpose of this PR, the problem it solves, or the research hypothesis it tests. -->

## Research Track

- [ ] **Clustering & Spatial Indexing** (Track Lead: NipunaBhanuka18)
- [ ] **Vessel Behavior Anomaly Detection** (Proposed Track Lead: Kishakya)
- [ ] **Shared Platform Infrastructure & Documentation**

## Type of Change

- [ ] `feat`: New feature or analytical capability
- [ ] `fix`: Bug fix or quality correction
- [ ] `docs`: Documentation, research proposal, or guide update
- [ ] `test`: New unit tests, test fixtures, or oracle verifications
- [ ] `refactor`: Code refactoring without functional changes
- [ ] `exp`: Experimental benchmark harness or evaluation script

## Pre-Merge Quality Checklist

- [ ] `uv sync --locked` resolves and installs cleanly
- [ ] `uv run pytest -v` passes 100% (all existing and new tests pass)
- [ ] `uv run pytest --cov=aegismar --cov-report=term-missing` confirms adequate coverage
- [ ] `uv run ruff check .` reports zero linting errors
- [ ] `uv run ruff format --check .` reports all files formatted
- [ ] `uv run mypy src tests` passes in strict mode with zero type errors
- [ ] Relative markdown links verified in any added or modified documentation

## Data Protection & Security Checklist

- [ ] Confirmed NO raw AIS files (`data/raw/`) are staged or committed
- [ ] Confirmed NO processed Parquet files (`data/processed/`) are staged or committed
- [ ] Confirmed NO local experiment outputs (`experiments/outputs/`) are staged or committed
- [ ] Confirmed NO secrets, API keys, credentials, or `.env` files are included
- [ ] Confirmed `git status` shows only authorized source/test/documentation files

## Research Reproducibility (if applicable)

- [ ] Deterministic random seeds are fixed and documented
- [ ] Input dataset SHA-256 hash is recorded in experiment configuration
- [ ] Evaluation metrics derive from actual execution runs (zero simulated numbers)
