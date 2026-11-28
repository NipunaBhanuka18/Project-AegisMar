# Contributing to Project AegisMar

> **Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**

Thank you for contributing to Project AegisMar! This document outlines our collaborative workflow, coding standards, quality gates, and research reproducibility guidelines.

---

## 1. Collaborative Research Architecture

Project AegisMar is developed collaboratively between two AI undergraduate researchers:
- **Clustering & Spatial Indexing Track (Lead: NipunaBhanuka18)**: AIS ingestion foundation, BallTree reference ST-DBSCAN, Uber H3 candidate optimization, stay-point/anchorage analytics, shared platform integration.
- **Vessel Behavior Anomaly Detection Track (Lead: Kishakya)**: Vessel trajectory feature engineering, unsupervised kinematic anomaly detection, synthetic perturbation evaluation, explainable anomaly incidents.

Both tracks share common data engineering foundations and integration contracts while maintaining modular autonomy in development.

---

## 2. Development Setup

The project uses Python 3.11.9 and `uv` for reproducible dependency management.

```bash
# Clone the repository
git clone https://github.com/NipunaBhanuka18/Project-AegisMar.git
cd Project-AegisMar

# Synchronize virtual environment with locked dependencies
uv sync --locked
```

---

## 3. Branching & Git Conventions

### Branch Naming
Create focused topic branches off `main`:
- `feat/clu-...`: Clustering & spatial indexing features (Clustering track)
- `feat/ml-...`: Trajectory features and anomaly detection (ML track)
- `exp/...`: Experimental research spikes and benchmark harnesses
- `fix/...`: Bug fixes or data quality patches
- `docs/...`: Documentation updates, research reports, guides

### Commit Messages
We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:
- `feat: add trajectory kinematic feature extraction module`
- `fix: resolve radian conversion bug on polar coordinates`
- `test: add unit tests for sliding window trajectory segmenter`
- `docs: update evaluation protocol with vessel-disjoint holdouts`
- `refactor: optimize neighborhood CSR graph memory allocation`
- `chore: update dependencies in uv.lock`

---

## 4. Quality Gates & Continuous Verification

Before staging files or opening a Pull Request, all five automated quality gates must pass cleanly. The same gates run in GitHub Actions on every push and pull request to `main` ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

**Coverage policy:**
- **Enforced in CI:** at least 85% line coverage of `aegismar`. CI uses `--cov-fail-under=85`, so a pull request below that fails.
- **Recommended quality target:** at least 90%.

```bash
# 1. Run unit and oracle tests
uv run pytest -v

# 2. Check test coverage: identical to the CI gate (fails below 85%; recommended target >= 90%)
uv run pytest --cov=aegismar --cov-report=term-missing --cov-fail-under=85 -v

# 3. Fast linter check
uv run ruff check .

# 4. Code formatting check
uv run ruff format --check .

# 5. Strict static type check
uv run mypy src tests
```

To automatically format code, run:
```bash
uv run ruff format .
```

---

## 5. Strict Data Protection Policy

> [!CAUTION]
> **NEVER COMMIT AIS DATASETS, CREDENTIALS, OR EXPERIMENT OUTPUTS TO GIT**
>
> To protect repository integrity and adhere to data redistribution guidelines:
> - Raw AIS files (`data/raw/*`) must NEVER be tracked in Git.
> - Processed Parquet partitions (`data/processed/*`) must NEVER be tracked in Git.
> - Local experiment output files (`experiments/outputs/*`) must NEVER be tracked in Git.
> - Credentials, tokens, private keys, or `.env` files must NEVER be committed.
>
> The root `.gitignore` file enforces these protections. Always run `git status` before committing to verify that no large datasets or caches are staged.

---

## 6. Scientific Research Integrity & Reproducibility

To maintain academic rigor and defend our research findings:
1. **Zero Fabricated Results**: Never commit simulated or mock benchmark numbers. All reported runtimes, memory readings, and accuracy figures must derive from automated experiment execution logs.
2. **Deterministic Seeds**: All stochastic algorithms (e.g. Isolation Forest estimators, synthetic perturbation generators, train/test partition splitters) must accept explicit, fixed integer random seeds (e.g., `random_state=42`).
3. **Independent Test Oracles**: Algorithmic correctness tests must execute against isolated reference oracles (such as `aegismar.spatial.oracle.BruteForceNeighborhoodOracle`) rather than circular self-validation.
4. **Audit Trail**: Benchmark logs must capture input dataset SHA-256 hashes, parameter dictionaries, git commit hashes, and host environment metadata.

---

## 7. Module Ownership & Code Review

To enable independent progress while protecting shared core infrastructure:

| Subsystem | Primary Owner | Review Policy |
|---|---|---|
| `src/aegismar/ingestion/` | NipunaBhanuka18 | Must be reviewed by NipunaBhanuka18 |
| `src/aegismar/clustering/` | NipunaBhanuka18 | Must be reviewed by NipunaBhanuka18 |
| `src/aegismar/spatial/` | NipunaBhanuka18 | Must be reviewed by NipunaBhanuka18 |
| `src/aegismar/staypoint/` | NipunaBhanuka18 | Must be reviewed by NipunaBhanuka18 |
| `src/aegismar/anomaly/` | Kishakya | Owned by Kishakya; reviewed collaboratively |
| `src/aegismar/storage/`, `api/` | Shared | Joint review prior to merging |
| `docs/03-research/vessel-behavior-ml.md` | Kishakya | Kishakya has editorial ownership |
| `pyproject.toml`, `.python-version` | Shared | Core dependency changes must be mutually agreed |

### Pull Request Workflow
1. Push branch to `origin`.
2. Open a Pull Request referencing the AegisMar PR template (`.github/pull_request_template.md`).
3. Confirm all quality gate checkboxes are checked.
4. Request review from the other researcher.
5. Resolve feedback and merge via standard merge commit or squash-and-merge.

---

## 8. Authorship & Intellectual Contribution

Both researchers are equal academic partners in Project AegisMar:
- Research contributions will be attributed transparently according to track responsibilities.
- All joint academic papers, thesis submissions, or public presentations resulting from this work will list both researchers as co-authors, with primary track leads acknowledged on their respective core contributions.
- Kishakya's participation, Track B leadership, and attribution were confirmed on 2026-11-24 after Kishakya reviewed and accepted the collaboration plan.
