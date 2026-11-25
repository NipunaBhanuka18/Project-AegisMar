# CLAUDE.md — Local Execution Agent Contract (`D:\Project AegisMar`)

## Read Before Editing
Inspect `PROJECT_STATE.md`, `CONTRIBUTING.md`, `docs/02-architecture/system-architecture.md`, `docs/04-development/testing-strategy.md`, and relevant ADRs in `docs/02-architecture/decisions/` before modifying code.

## Environment & Quality Gates
- **Runtime:** Python `3.11` managed via `uv` (`pyproject.toml`).
- **Verification commands** (confirm current thresholds in `CONTRIBUTING.md` and `docs/04-development/testing-strategy.md`):
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `uv run pytest -v` (and `--cov=aegismar` when checking coverage)
- Never claim tests, linters, or type checks passed without executing them and reporting exact command output.

## Hard Safety Guardrails
1. **Immutable Data:** Never overwrite, delete, or modify `data/raw/` or `data/processed/lalb_20250101/` (`4a7ca719...e88b`). Never commit files under `data/` or `experiments/outputs/`.
2. **No Unauthorized Runs:** Do not regenerate datasets or run multi-scale benchmarks unless explicitly instructed in the approved task prompt.
3. **Git Hygiene:** Use `CONTRIBUTING.md` branch prefixes (`feat/clu-`, `fix/`, `docs/`, `exp/`) and Conventional Commits. Never force-push, commit, push, modify PRs, or merge without explicit authorization. Never edit unrelated files outside the approved task scope.
4. **Track Boundary (`ADR-010`):** Do not modify Track B files (`src/aegismar/anomaly/`, `experiments/anomaly/`, `docs/03-research/ml-*.md`) unless explicitly scoped for an approved integration task.

## Reporting Standard
Every completion report must include:
- Exact `git branch`, `git rev-parse HEAD`, `git status`, and `git diff --stat`.
- Exact verification commands run and verbatim pass/fail summaries.
- Explicit separation of **verified results** from **unverified items or assumptions** (e.g., never equate Git mergeability or GitGuardian checks with code review or passing tests).
- Any temporary files or side effects created outside the repository.
