# Engineering Development Log

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**

This log documents chronological engineering actions, commands executed, test results observed, problems encountered, and architectural decisions made. Only verified actions are recorded here. Future work is never pre-filled.

---

## Log Entry: 2026-11-14 — Milestone W1-01

- **Date:** 2026-11-14
- **Task Identifier:** `W1-01: Repository Initialization & Documentation Foundation`
- **Summary of Changes:**
  - Inspected existing empty workspace at `D:\Project AegisMar`. Discovered initial Git repository (`.git`), empty directory structures (`src/aegismar`, `tests`), and a fresh virtual environment (`.venv` running CPython 3.11.9).
  - Pinned runtime version via `.python-version` (3.11.9).
  - Configured project metadata and toolchains in `pyproject.toml` with `hatchling` build backend, PEP 621 metadata, and tool sections for Ruff, Pytest, and Mypy.
  - Implemented initial Python package skeleton `src/aegismar/__init__.py` exposing `__version__ = "0.1.0.dev1"`.
  - Created smoke test suite in `tests/test_smoke.py` verifying package import, version exposure, and Python 3.11 runtime pinning.
  - Configured comprehensive `.gitignore` rules shielding `data/raw/*`, `data/processed/*`, `experiments/outputs/*`, virtualenvs, caches, and credentials, while explicitly preserving `data/samples/` and `.gitkeep` directory anchors.
  - Executed `uv sync` to generate `uv.lock` and install development dependencies (`pytest`, `ruff`, `mypy`, `pytest-cov`).
  - Authored foundational documentation architecture:
    - `docs/01-project/`: `vision.md`, `brs.md`, `srs.md`, `scope.md`, `roadmap.md`
    - `docs/02-architecture/`: `system-architecture.md`, `decisions/ADR-001-modular-monolith.md`
    - `docs/03-research/`: `research-plan.md`, `evaluation-protocol.md`, `datasets.md`
    - `docs/04-development/`: `milestones.md`, `development-log.md`, `testing-strategy.md`
    - `docs/05-guides/`: `installation.md`
  - Created root `README.md` and `CHANGELOG.md` with complete documentation navigation links.
- **Files Changed / Created:**
  - `.python-version`
  - `.gitignore`
  - `pyproject.toml`
  - `uv.lock`
  - `README.md`
  - `CHANGELOG.md`
  - `data/raw/.gitkeep`, `data/processed/.gitkeep`, `data/samples/.gitkeep`
  - `experiments/configs/.gitkeep`, `experiments/outputs/.gitkeep`
  - `src/aegismar/__init__.py`
  - `src/aegismar/py.typed`
  - `tests/test_smoke.py`
  - `docs/01-project/vision.md`
  - `docs/01-project/brs.md`
  - `docs/01-project/srs.md`
  - `docs/01-project/scope.md`
  - `docs/01-project/roadmap.md`
  - `docs/02-architecture/system-architecture.md`
  - `docs/02-architecture/decisions/ADR-001-modular-monolith.md`
  - `docs/03-research/research-plan.md`
  - `docs/03-research/evaluation-protocol.md`
  - `docs/03-research/datasets.md`
  - `docs/04-development/milestones.md`
  - `docs/04-development/development-log.md`
  - `docs/04-development/testing-strategy.md`
  - `docs/05-guides/installation.md`
- **Commands Executed:**
  - `uv sync`
  - `uv run python --version`
  - `uv run python -c "import aegismar; print('Package import OK')"`
  - `uv run pytest -v`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `git status --short`
- **Observed Test Results:**
  - `uv sync`: Successfully resolved 16 packages in 1.84s, built `aegismar 0.1.0.dev1`, installed `pytest 9.2.0`, `ruff 0.17.5`, `mypy 2.4.1`, and generated `uv.lock`.
  - `uv run python --version`: Returned `Python 3.11.9`.
  - `uv run python -c "import aegismar; print('Package import OK')"`: Returned `Package import OK`.
  - `uv run pytest -v`: 2 passed in 0.03s (`test_package_import` and `test_python_runtime_version`).
  - `uv run ruff check .`: `All checks passed!`.
  - `uv run ruff format --check .`: `18 files already formatted`.
  - `uv run mypy src tests`: `Success: no issues found in 2 source files`.
  - `git status --short`: Verified untracked files without unexpected files or committed data.
- **Problems Encountered:**
  - During `uv sync`, a non-fatal warning occurred: `warning: Failed to hardlink files; falling back to full copy. This may lead to degraded performance.` Root cause: cross-filesystem cache boundary on Windows. Resolution: Normal behavior on Windows drive configurations; full copy functions identically.
  - Strict `mypy` initially reported missing library stubs for local package import. Resolution: Created standard PEP 561 marker `src/aegismar/py.typed`. All type checks now pass cleanly in strict mode.
- **Decisions Made:**
  - Pinned runtime to CPython 3.11.9 to ensure binary wheel stability for forthcoming scientific extensions (`h3`, `scikit-learn`, `duckdb`).
  - Implemented modular monolith architecture (ADR-001) to eliminate distributed infrastructure overhead.
  - License decision marked pending user selection; no LICENSE file created.
  - No Git commit or push executed, as per strict instructions.
- **Next Action:**
  - Await review and authorization for GitHub readiness audit (W1-01A).

---

## Log Entry: 2026-11-14 — Task W1-01A

- **Date:** 2026-11-14
- **Task Identifier:** `W1-01A: Documentation, Repository Integrity & GitHub Readiness Audit`
- **Summary of Changes:**
  - Performed deep repository and documentation consistency audit.
  - Re-verified locked dependencies with `uv sync --locked`.
  - Resolved minor Ruff formatting discrepancies in `src/aegismar/__init__.py` and `tests/test_smoke.py`.
  - Updated candidate coastal study regions in `docs/03-research/datasets.md`: explicitly established both Los Angeles / Long Beach and Delaware Bay as `Candidate — Not Selected` with documented selection criteria (coverage, anchorage behavior, berth polygons, computational size, open permissions); no region declared selected.
  - Enhanced `docs/03-research/research-plan.md` with explicit enumeration of the 10 core scientific research principles (exact spatial/temporal filtering, deterministic ST-DBSCAN, boundary/pentagon H3 completeness, equivalent clustering semantics, indexing overhead inclusion, real dataset profiling, holdouts, synthetic perturbations, leakage prevention, zero fabricated results).
  - Fixed heading anchors in `README.md` (`#2-current-status` and `#14-license-attribution`) and safe Mermaid diagram syntax in `docs/01-project/srs.md` and `docs/03-research/research-plan.md`.
  - Verified 100% resolution of relative markdown links across all 16 repository markdown files.
  - Conducted dry-run staging review (`git add --dry-run .`) confirming 28 safe files for the initial commit with zero raw datasets, credentials, virtualenvs, or caches.
- **Files Changed / Created:**
  - `README.md`
  - `src/aegismar/__init__.py`
  - `tests/test_smoke.py`
  - `docs/01-project/scope.md`
  - `docs/01-project/srs.md`
  - `docs/03-research/datasets.md`
  - `docs/03-research/research-plan.md`
  - `docs/04-development/development-log.md`
- **Commands Executed:**
  - `uv sync --locked`
  - `uv run pytest -v`
  - `uv run ruff check .`
  - `uv run ruff format .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `git status --short`
  - `git ls-files`
  - `git remote -v`
  - `git add --dry-run .`
- **Observed Test Results:**
  - `uv sync --locked`: Clean exit (0).
  - `pytest -v`: 2 passed in 0.03s.
  - `ruff check .`: All checks passed (0 errors, 0 warnings).
  - `ruff format --check .`: 18 files already formatted.
  - `mypy src tests`: Success: no issues found in 2 source files.
  - `git status --short`: Clean list of untracked files.
  - `git ls-files`: Empty (no files committed yet).
  - `git remote -v`: Empty (no remote configured yet).
- **Problems Encountered:**
  - Minor trailing whitespace in Python files corrected via `uv run ruff format .`.
  - Anchors in badges corrected to match GitHub cmark-gfm heading slug generation.
- **Decisions Made:**
  - Both Los Angeles / Long Beach and Delaware Bay marked `Candidate — Not Selected` pending empirical profiling in W1-02.
  - No commit, remote creation, or push performed; git working tree preserved for user review.
- **Next Action:**
  - Proceed with W1-01B initial commit and publication to GitHub upon user authorization.

---

## Log Entry: 2026-11-14 — Task W1-01B

- **Date:** 2026-11-14
- **Task Identifier:** `W1-01B: Initial GitHub Commit & Publication`
- **Summary of Changes:**
  - Re-ran pre-push verification gates (`uv sync --locked`, `pytest`, `ruff check`, `ruff format --check`, `mypy`). All checks passed with exit code 0.
  - Verified remote repository status via `git ls-remote`: confirmed `https://github.com/NipunaBhanuka18/Project-AegisMar.git` is online, accessible, and completely empty (no existing commits or branch conflicts).
  - Renamed local default branch from `master` to `main`.
  - Configured remote origin: `https://github.com/NipunaBhanuka18/Project-AegisMar.git`.
  - Staged 28 approved project files, strictly excluding `.venv`, caches, raw/processed data, and experiment outputs.
  - Inspected staged file list with `git diff --cached --name-only`.
  - Created initial commit: `chore: initialize AegisMar research repository and documentation (W1-01)`.
  - Published initial commit to GitHub via `git push -u origin main`.
- **Files Included in Initial Commit:**
  - Configuration & tooling: `.gitignore`, `.python-version`, `pyproject.toml`, `uv.lock`
  - Documentation root: `README.md`, `CHANGELOG.md`
  - Source package: `src/aegismar/__init__.py`, `src/aegismar/py.typed`
  - Test suite: `tests/test_smoke.py`
  - Directory anchors: `data/raw/.gitkeep`, `data/processed/.gitkeep`, `data/samples/.gitkeep`, `experiments/configs/.gitkeep`, `experiments/outputs/.gitkeep`
  - Documentation architecture: `docs/01-project/` (vision, brs, srs, scope, roadmap), `docs/02-architecture/` (system-architecture, ADR-001), `docs/03-research/` (research-plan, evaluation-protocol, datasets), `docs/04-development/` (milestones, development-log, testing-strategy), `docs/05-guides/` (installation)
- **Commands Executed:**
  - `uv sync --locked`
  - `uv run pytest -v`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `git branch -M main`
  - `git remote add origin https://github.com/NipunaBhanuka18/Project-AegisMar.git`
  - `git add .`
  - `git diff --cached --name-only`
  - `git commit -m "chore: initialize AegisMar research repository and documentation (W1-01)"`
  - `git push -u origin main`
- **Observed Results:**
  - Pre-push gates: 100% passed.
  - Remote push: Successfully pushed `main` to `origin/main` with upstream tracking established.
- **Next Action:**
  - Proceed with W1-02A (NOAA AIS Dataset Selection & Schema Investigation).

---

## Log Entry: 2026-11-14 — Task W1-02A

- **Date:** 2026-11-14
- **Task Identifier:** `W1-02A: NOAA AIS Dataset Selection & Schema Investigation`
- **Summary of Changes:**
  - Investigated authoritative NOAA Marine Cadastre AIS data products, inspecting NOAA InPort Item 77594 and July 2026 Data Dictionary.
  - Identified major NOAA 2025 data schema updates: adoption of Zstandard (`.csv.zst`), snake_case column names, longitude reordered before latitude, and conversion of ITU sentinels (`102.3`, `511`, `360.0`, `15`) into explicit null values.
  - Downloaded genuine 24-hour nationwide extract `ais-2025-01-01.csv.zst` (192.82 MB, SHA-256 `36c07f4abad24f86fdd2ae8722b5a1d9422f3a223efc3482a568665275bdde53`) to gitignored `data/raw/`.
  - Profiled complete nationwide dataset (7,337,208 records in 10.54s) and extracted bounding-box slices for Candidate A (Los Angeles / Long Beach: Lat `[33.5, 33.9]`, Lon `[-118.4, -118.0]`) and Candidate B (Delaware Bay: Lat `[38.5, 39.5]`, Lon `[-75.6, -74.5]`).
  - Observed empirical characteristics:
    - LA/LB (San Pedro Bay): 143,156 records, 362 unique MMSIs, 8,569 at-anchor pings (6.0%), 19,716 moored pings (13.8%), 18 implied-speed violations ($>50\text{ kt}$), median interval 179.0s.
    - Delaware Bay: 42,838 records, 95 unique MMSIs, 3,175 at-anchor pings (7.4%), 4,284 moored pings (10.0%), 0 speed violations, median interval 101.0s.
  - Formally selected **Los Angeles / Long Beach (San Pedro Bay)** as the primary study region based on data density directly matching the 10k/50k/100k benchmark tiers, distinct outer anchorage basins versus inner container terminals, and authentic kinematic anomaly instances.
  - Documented anchorage and berth reference data feasibility framework utilizing Port of Los Angeles (GeoPOLA) and Port of Long Beach (MapsLB) open GIS layers.
  - Updated `README.md` to neutralize speculative performance claims (replacing orders-of-magnitude claims with objective empirical measurement and acknowledging 100% neighbor recall is a target requirement not yet achieved).
  - Clarified schema adaptability requirements in `docs/01-project/srs.md` (FR-ING-01, FR-ING-02) and updated `docs/03-research/datasets.md`, `docs/04-development/milestones.md`, and `docs/04-development/development-log.md`.
- **Files Changed:**
  - `README.md`
  - `docs/01-project/srs.md`
  - `docs/03-research/datasets.md`
  - `docs/04-development/milestones.md`
  - `docs/04-development/development-log.md`
- **Commands Executed:**
  - `python check_noaa_urls.py`
  - `python parse_noaa_2025_index.py`
  - `python extract_inport_details.py`
  - `python download_raw_sample.py`
  - `python profile_candidate_data.py`
  - `uv sync --locked`
  - `uv run pytest -v`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `git status --short`
- **Observed Results:**
  - Raw 2025 data downloaded and profiled successfully.
  - Quality gates: 100% passed.
- **Next Action:**
  - Proceed with W1-02B (AIS Ingestion, Data Quality & Parquet Storage).

---

## Log Entry: 2026-11-14 — Task W1-02B

- **Date:** 2026-11-14
- **Task Identifier:** `W1-02B: AIS Ingestion, Data Quality & Parquet Storage`
- **Summary of Changes:**
  - Implemented domain constants, ITU sentinels, domain bounds, and analytical quality flags in `src/aegismar/common/constants.py`.
  - Implemented typed dataclasses `CanonicalPing` and `IngestionManifest` in `src/aegismar/common/types.py`.
  - Implemented haversine spherical geodesic distance metric functions in `src/aegismar/spatial/haversine.py`.
  - Implemented schema adapter in `src/aegismar/ingestion/schema.py` supporting both NOAA 2025 (`snake_case`) and NOAA legacy 2018–2024 (`PascalCase`) CSV headers with ambiguity and missing field checks, and PyArrow canonical schema mapping.
  - Implemented record validator, sentinel nullification, duplicate consolidation, conflict detection, and trajectory implied-speed calculator in `src/aegismar/ingestion/cleaner.py`.
  - Implemented columnar storage layer in `src/aegismar/ingestion/storage.py` (PyArrow table conversion, zstd Parquet writer, manifest manager, and metadata inspector).
  - Implemented end-to-end ingestion pipeline runner in `src/aegismar/ingestion/pipeline.py` with source SHA-256 calculation and overwrite protection.
  - Added `tzdata` dependency for Windows IANA timezone compatibility in standard `zoneinfo` and PyArrow scalar conversion.
  - Implemented CLI and entrypoint in `src/aegismar/cli.py` and `__main__.py` (`python -m aegismar ingest ...`).
  - Authored synthetic CSV fixtures and comprehensive unit test suite:
    - `tests/unit/test_ingestion.py`: 16 unit tests covering dual-schema mapping, sentinel nullification, 9-digit MMSI padding, coordinate bounds, duplicate consolidation, conflict flagging, deterministic ordering, implied speed, zero elapsed time, and Parquet roundtrips.
    - `tests/unit/test_cli.py`: 7 CLI tests covering help display, version output, default behavior, synthetic ingestion, missing input error handling, and overwrite protection.
    - Total tests: 25 passed (0 failures). Total code coverage: 91% across `src/aegismar`.
  - Executed production ingestion run against real Los Angeles / Long Beach sample (`data/raw/sample_lalb_20250101.csv`):
    - Input records scanned: 143,156.
    - Output records accepted: 143,124 (143,156 - 32 duplicate rows).
    - Hard-invalid rows dropped: 0.
    - Duplicates coerced: 32.
    - Same-timestamp coordinate conflicts flagged: 8.
    - Unique vessels (MMSI): 362.
    - Implied speed violations flagged ($>50\text{ kt}$): 18.
    - Temporal range: `2025-01-01T00:00:00+00:00` to `2025-01-01T23:59:57+00:00`.
    - Processing runtime: 7.19 seconds (~19,900 records/sec).
    - Output Parquet: `data/processed/lalb_20250101/cleaned_ais.parquet` (4.15 MB, 1 row group, 19 columns).
    - Manifest: `data/processed/lalb_20250101/manifest.json`.
  - Verified independent Parquet readback schema fidelity and metadata with Python script.
- **Files Created/Modified:**
  - `pyproject.toml`
  - `uv.lock`
  - `src/aegismar/__main__.py`
  - `src/aegismar/cli.py`
  - `src/aegismar/common/__init__.py`
  - `src/aegismar/common/constants.py`
  - `src/aegismar/common/types.py`
  - `src/aegismar/spatial/__init__.py`
  - `src/aegismar/spatial/haversine.py`
  - `src/aegismar/ingestion/__init__.py`
  - `src/aegismar/ingestion/schema.py`
  - `src/aegismar/ingestion/cleaner.py`
  - `src/aegismar/ingestion/storage.py`
  - `src/aegismar/ingestion/pipeline.py`
  - `tests/fixtures/synthetic_2025_sample.csv`
  - `tests/fixtures/synthetic_legacy_sample.csv`
  - `tests/unit/test_cli.py`
  - `tests/unit/test_ingestion.py`
  - `README.md`
  - `docs/01-project/srs.md`
  - `docs/03-research/datasets.md`
  - `docs/04-development/milestones.md`
  - `docs/04-development/development-log.md`
  - `docs/05-guides/installation.md`
  - `CHANGELOG.md`
- **Commands Executed:**
  - `uv add tzdata`
  - `uv sync --locked`
  - `uv run pytest -v`
  - `uv run pytest --cov=aegismar --cov-report=term-missing`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src tests`
  - `uv run python -m aegismar.cli ingest --input data/raw/sample_lalb_20250101.csv --output data/processed/lalb_20250101 --overwrite`
- **Observed Results:**
  - 25 tests passed in 0.68s.
  - Coverage: 91% across `src/aegismar`.
  - Quality gates: 100% passed (Ruff: 0 errors; Ruff format: clean; Mypy: 0 errors in 16 files).
  - Real dataset ingested into Parquet with complete manifest audit trail.
- **Next Action:**
  - Proceed with W2-01 (Ingestion Corrections & BallTree ST-DBSCAN Reference Engine).

---

## Log Entry: 2026-11-18 — Task W2-01

- **Date:** 2026-11-18
- **Task Identifier:** `W2-01: Ingestion Corrections & BallTree ST-DBSCAN Reference Engine`
- **Summary of Changes:**
  - **Bounded W1-02B Ingestion Corrections**:
    - Clarified in `src/aegismar/ingestion/pipeline.py`, `docs/01-project/brs.md`, `docs/01-project/srs.md`, and `docs/03-research/datasets.md` that the current MVP ingestion materializes rows in memory in Python lists prior to `zstd`-compressed Parquet serialization (in-memory batch processing, not bounded-memory streaming).
    - Hardened `sanitize_mmsi` (`src/aegismar/ingestion/cleaner.py`) to strictly accept integer-format MMSIs and reject decimal strings, floats, booleans, signs, and non-ASCII digits rather than silently truncating on `"."`.
    - Hardened duplicate & same-timestamp conflict policy (`src/aegismar/ingestion/cleaner.py`): exact deduplication requires full-record equality (`_full_record_dedup_key`); same-position differing metadata is retained with `TIMESTAMP_METADATA_CONFLICT`; same-timestamp differing coordinates remain retained with `TIMESTAMP_POSITION_CONFLICT`; conflicting same-timestamp observations do not produce fictitious zero-time movement estimates (`prev_source_row`, `elapsed_seconds`, `distance_nm`, and `implied_speed_knots` remain `None`).
    - Hardened `detect_and_build_column_mapping` (`src/aegismar/ingestion/schema.py`) to inspect all raw columns across modern 2025 and legacy vocabularies and reject duplicate or ambiguous canonical mappings (e.g., `LAT` + `latitude`, `mmsi` + `MMSI`, duplicate raw headers) via `SchemaAdapterError`.
  - **Reference Clustering Dependencies**:
    - Installed `numpy==2.4.6` and `scikit-learn==1.9.1` via `uv add numpy scikit-learn` (`h3` intentionally NOT installed; deferred to Week 3).
  - **Reference BallTree ST-DBSCAN Engine & Independent Oracle**:
    - Implemented `src/aegismar/clustering/config.py`: validated `QualityFilterPolicy` and `STDBSCANConfig` (`eps_spatial_m`, `eps_temporal_s`, `min_samples`, radian conversion).
    - Implemented `src/aegismar/clustering/types.py`: canonical total-order sorting `(timestamp_us, mmsi, latitude_deg, longitude_deg, source_row)`, `NeighborhoodGraph` (CSR), `NeighborhoodProvider` protocol, `STDBSCANResult`, and Parquet loader (`load_clustering_dataset_from_parquet`).
    - Implemented `src/aegismar/clustering/balltree_neighbors.py`: `BallTreeNeighborhoodProvider` (`metric="haversine"`, `[lat_rad, lon_rad]`, chunked batch queries avoiding $N \times N$ matrices, exact integer-microsecond temporal filter, exact degree-difference Haversine pruning).
    - Implemented `src/aegismar/clustering/st_dbscan.py`: provider-agnostic deterministic core-first ST-DBSCAN (`stdbscan-core-first-v1.0`) with vectorized BFS core connected components in ascending canonical order and nearest-core border tie-breaking `(dist_m, |dt_us|, cluster_id, core_index)`.
    - Implemented `src/aegismar/clustering/export.py`: Parquet, summary JSON, compact GeoJSON preview, and offline zero-dependency SVG static HTML map exporter; added `aegismar cluster` CLI subcommand in `src/aegismar/cli.py`.
    - Implemented `src/aegismar/spatial/oracle.py`: isolated $O(N^2)$ `BruteForceNeighborhoodOracle` (safety cap $N \le 5{,}000$) and `verify_provider_against_oracle`.
  - **Automated Verification & Oracle Testing**:
    - Added 4 ingestion regression tests (`test_17`–`test_20`), 16 critical ST-DBSCAN fixtures + export roundtrip (`tests/unit/test_st_dbscan.py`), 7 randomized/dateline/polar/guard oracle tests (`tests/unit/test_oracle.py`), and CLI cluster tests (`tests/unit/test_cli.py`).
    - Total test suite: 52 passed (0 failed), 95% total coverage across `src/aegismar` (clustering modules 95%–98%, oracle 98%).
  - **Exploratory Real AIS Baseline (`data/processed/lalb_20250101/cleaned_ais.parquet`)**:
    - Raw and cleaned Parquet inputs strictly untouched (`cleaned_ais.parquet` SHA-256 `4a7ca719dc2a3d9959cc4166edff773ca09156d8d914e54d0ab5f851ece5e88b`).
    - Parameters: `eps_spatial_m=300.0`, `eps_temporal_s=900.0`, `min_samples=5`, `exclude_timestamp_conflicts=True`.
    - Counts: 143,124 input -> 8 excluded (`TIMESTAMP_POSITION_CONFLICT`) -> 143,116 analyzed; 241 clusters; 136,276 core + 934 border + 5,906 noise = 143,116.
    - Performance: uninstrumented wall time 13.680 s (build 0.077 s, query 13.341 s, clustering 0.262 s); under `tracemalloc` 38.014 s with 225.83 MB peak Python heap.
    - Determinism: repeated full run matched saved Parquet labels and roles 100%.
    - Real-data oracle spot-check (first 1,000 canonical LA/LB rows): 27,324 / 27,324 edges matched (recall=1.0, precision=1.0, exact neighborhood/role/label match).
    - Artifacts exported to gitignored `experiments/outputs/w2_01_lalb_balltree/`.
- **Problems Encountered & Fixes**:
  - Detected 1-ULP IEEE-754 difference between `np.deg2rad(lat2) - np.deg2rad(lat1)` vs `np.deg2rad(lat2 - lat1)` on exact spatial boundary tests; aligned `_exact_haversine_to_candidates_m` to compute degree differences prior to radian conversion for bit-for-bit oracle parity.
  - Replaced initial Python scalar Union-Find loop (~89 s under `tracemalloc`) with vectorized NumPy BFS seeded in ascending canonical core-index order, cutting uninstrumented clustering time to 0.262 s (and `tracemalloc` clustering time to 6.583 s) with 100% identical labels.
- **Next Action:**
  - Finalize Week 2 portfolio visualization and pre-Week 3 baseline documentation (`W2-CLOSE`).

---

## Log Entry: 2026-11-18 — Task W2-CLOSE

- **Date:** 2026-11-18
- **Task Identifier:** `W2-CLOSE: Week 2 Documentation and Portfolio Finalization`
- **Scope:** Documentation and public portfolio visualization only; zero scientific or application code changes.
- **Summary of Changes:**
  - Verified clean Git working tree on `main` synced with `origin/main` at reference commit `3ece8593f16fb5191b9f94936e5713ea8fae5be4`.
  - Verified presence and authenticity of all Week 2 experimental artifacts under gitignored `experiments/outputs/w2_01_lalb_balltree/` (`cluster_assignments.parquet`, `clustering_summary.json`, `clusters_preview.geojson`, `clusters_map.html`).
  - Inspected `clusters_map.html` to confirm genuine W2-01 experiment data with zero vessel identifiers, local paths, credentials, or sensitive personal data.
  - Captured a clean `960x780` PNG screenshot (`61,893` bytes) via local headless Chrome to `docs/assets/w2-balltree-clustering.png` and visually inspected the rendered output.
  - Updated `README.md` with the embedded Week 2 visualization, required descriptive caption (Los Angeles / Long Beach, Jan 1 2025 AIS, BallTree ST-DBSCAN, 300 m / 900 s / MinPts 5, explicitly marked exploratory and not validated anchorage identification), and concise pre-Week 3 research baseline metrics.
  - Updated `docs/04-development/milestones.md`, `docs/04-development/development-log.md`, and `CHANGELOG.md` to record Week 2 closure.
- **Verification:**
  - Confirmed zero changes under `src/` or `tests/`.
  - Re-ran `uv sync --locked`, `uv run pytest -v`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src tests` (100% pass).
- **Next Action:**
  - Commit `docs: finalize Week 2 clustering milestone and visualization`, push to `origin/main`, and pause before Week 3 (`W3-01` H3 optimization).

---

## Log Entry: 2026-11-22 — Task: Collaboration Foundation & ML Research Track Initialization

- **Date:** 2026-11-22
- **Task Identifier:** `Collaboration Foundation and ML Research Track Initialization`
- **Scope:** Documentation, integration contract definition, and collaboration infrastructure; zero application or scientific code changes under `src/` or `tests/`.
- **Summary of Changes:**
  - Audited existing repository: verified clean `main` at `929e6a3`, 52 passing tests, 95% test coverage, and confirmed no contradictions with existing data contracts or documentation.
  - Established dual-track collaborative research architecture between Lead Researcher NipunaBhanuka18 (AIS data engineering, BallTree reference ST-DBSCAN, Uber H3 optimization, stay-point/anchorage intelligence, platform integration) and proposed ML Research Collaborator Kishakya (vessel trajectory feature engineering, unsupervised kinematic anomaly detection, explainable incident generation, error analysis; participation and attribution prospective, pending review).
  - Maintained intact eight-week solo roadmap (Weeks 1–8, 200 hours) for Track A while establishing Track B as an independent parallel research track with its own schedule and backlog (ML-01 to ML-04).
  - Authored ML Research Proposal (`docs/03-research/vessel-behavior-ml.md`, marked `PROPOSAL — NOT FINALIZED`):
    - Problem formulation, research questions (RQ-ML1, RQ-ML2), hypotheses ($H_{\text{ML1}}$, $H_{\text{ML2}}$).
    - Detailed evaluation of 19 canonical AIS telemetry fields and sensor/reporting limitations.
    - Trajectory reconstruction assumptions (MMSI partitioning, chronological sorting, gap segmentation $>2\text{ h}$, coordinate conflict isolation).
    - Behavioral feature specifications (kinematic acceleration, angular ROT, course-heading drift angle, reporting intervals, tortuosity).
    - Baseline models (rule-based kinematic heuristic, Isolation Forest, LOF, Mahalanobis distance, ST-DBSCAN density noise baseline).
    - Crucial caveat documented: raw Isolation Forest scores are feature-isolation depths, never calibrated Bayesian probabilities.
    - Evaluation protocol (70/30 vessel-disjoint holdouts, chronological holdouts, synthetic perturbation limitations).
    - Open methodological decisions left for Kishakya to evaluate and decide.
  - Authored Collaborator Onboarding Guide (`docs/05-guides/ml-research-onboarding.md`):
    - Addressed all 15 required onboarding topics (problem domain, completed milestones, `uv` setup, running tests, canonical Parquet schema, reproducible data acquisition without committing raw data, reusable modules, independent ML boundaries in `src/aegismar/anomaly/`, Git branching `feat/ml-...`, PR workflow, AI assistant safety, experiment tracking, protected files, known limitations, and initial tasks ML-01 to ML-04).
  - Defined Integration Contracts:
    - Input contract: 19 canonical fields from `cleaned_ais.parquet` with canonical total order.
    - Output contract: Versioned `vessel_anomaly_v1` GeoJSON Feature schema (`incident_id`, `mmsi`, timestamps, observation source rows, model id/version, non-probabilistic anomaly score, primary factor, factor contributions, data quality context).
  - Added Collaboration Infrastructure:
    - `CONTRIBUTING.md`: Branching, conventional commits, quality gates, strict data protection, research reproducibility, module ownership, co-authorship principles.
    - `.github/pull_request_template.md`: Lightweight PR checklist covering track categorization, quality checks, data protection, and reproducibility tracking.
    - `docs/01-project/collaboration-plan.md`: Track responsibilities, module ownership table, communication/review cycles, conflict resolution, academic attribution principles.
  - Synchronized Project Documentation:
    - `README.md`: Multi-engine vision, dual research tracks, updated Mermaid component architecture, links to onboarding and ML research proposal, accurate milestone table, collaborative attribution.
    - `docs/01-project/vision.md`, `docs/01-project/scope.md`, `docs/01-project/roadmap.md`, `docs/02-architecture/system-architecture.md`, and `docs/03-research/research-plan.md`.
    - `CHANGELOG.md` updated with milestone entry.
- **Verification:**
  - Zero modifications to working clustering, ingestion, or spatial logic (`src/aegismar/ingestion/`, `src/aegismar/clustering/`, `src/aegismar/spatial/`).
  - Ran `uv sync --locked`, `uv run pytest -v`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests`. All passed 100% with exit code 0.
- **Next Action:**
  - Commit with message `docs: establish collaborative research tracks and ML onboarding`, push to `origin/main`, verify remote SHA, and deliver completion report.

---

## Log Entry: 2026-11-22 — Task: Milestone DOC-01 (Evidence-Backed Documentation & Research Knowledge Base)

- **Date:** 2026-11-22
- **Task Identifier:** `DOC-01: Evidence-Backed Research & Engineering Documentation`
- **Scope:** Documentation quality, evidence reconciliation, research traceability, and architectural rationale; zero modifications to application or scientific code under `src/` or `tests/`.
- **Summary of Changes:**
  - Audited repository: verified working tree clean at reference commit `d3c17a0`, 52 passing tests, 95% coverage, and reconciled all historical claims against actual files on disk.
  - Authored comprehensive `docs/START-HERE.md` covering the maritime problem, historical AIS strengths and limits, platform capabilities, dual-track structure, architecture rationale, verified measurements, baseline reproduction steps, code/experiment navigation, and next milestones.
  - Authored complete Architecture Decision Register (`docs/02-architecture/decisions/README.md`) with 10 formal ADRs:
    - Updated `ADR-001` (Modular Monolith) with collaborative context and retrospective multi-repo evaluation.
    - Created `ADR-002` (Historical AIS Batch Telemetry as Primary Research Data Source).
    - Created `ADR-003` (Canonical PyArrow Schema with Quality Flags & Sentinel Nullification).
    - Created `ADR-004` (Apache Parquet Columnar Storage with Manifest Verification).
    - Created `ADR-005` (Scikit-Learn BallTree with Haversine Metric as Reference Neighbor Search Engine).
    - Created `ADR-006` (Strict Dual-Threshold Spatiotemporal Neighborhood Semantics in Integer Microseconds).
    - Created `ADR-007` (Deterministic Core-First Labeling Policy for ST-DBSCAN `stdbscan-core-first-v1.0`).
    - Created `ADR-008` (Independent $O(N^2)$ Brute-Force Geodesic Test Oracle for Verification).
    - Created `ADR-009` (Uber H3 Discrete Hexagonal Grid as Correctness-Preserving Candidate Neighbor Generator).
    - Created `ADR-010` (Decoupled Parallel Behavioral ML Workstream with Contract-Based Integration).
  - Authored Research Evidence Register (`docs/03-research/evidence-register.md`):
    - Reconciled 14 technical claims across ingestion and BallTree clustering with cryptographic hashes, parameter sets, and verification statuses.
    - Explicitly distinguished raw observations (143,156), cleaned observations (143,124), filtered inputs (143,116), visualized preview points (5,000), unique vessels (362 MMSIs), and density clusters (241 exploratory clusters).
    - Established strict scientific guardrails: density clusters $\neq$ confirmed anchorages; oracle matching $\neq$ maritime anomaly detection accuracy; single runs $\neq$ multi-trial benchmarks.
    - Documented deterministic commands to reproduce all gitignored experiment artifacts.
  - Refined ML Research Proposal (`docs/03-research/vessel-behavior-ml.md`, v1.1):
    - Added domain corrections: clarified that AIS gaps stem predominantly from antenna shadowing near cranes and line-of-sight limits; noted that crabbing angles occur naturally in currents; reinforced that Isolation Forest scores are non-probabilistic isolation indices; labeled example incidents as purely synthetic documentation examples; marked the `vessel_anomaly_v1` GeoJSON contract as provisional.
  - Refined Onboarding & Governance:
    - Updated `docs/05-guides/ml-research-onboarding.md` and `docs/01-project/collaboration-plan.md` to reinforce the "One team, one initiative, one integrated product, two complementary lead areas" model with flexible pacing, zero bureaucratic drag, experiment logging guidelines, negative finding documentation, and AI coding assistant safety rules.
    - Updated `README.md` with prominent tip linking to `docs/START-HERE.md` and expanded documentation index.
- **Verification:**
  - Confirmed zero changes under `src/` or `tests/` (`git diff --stat src/ tests/` output empty).
  - Verified all 31+ relative markdown links across all repository Markdown files with automated Python checker script.
  - Re-ran quality gates: `uv sync --locked`, `uv run pytest -v` (52 passed), `uv run ruff check .` (0 errors), `uv run ruff format --check .` (0 unformatted), `uv run mypy src tests` (strict mode clean).
- **Next Action:**
  - Execute Milestone DOC-01A: Research Documentation Accuracy & Collaborator Readiness.

---

## Log Entry: 2026-11-22 — Task DOC-01A

- **Date:** 2026-11-22
- **Task Identifier:** `DOC-01A: Research Documentation Accuracy & Collaborator Readiness`
- **Scope:** Narrowly scoped documentation correction and collaborator onboarding audit; zero changes to source code or tests under `src/` or `tests/`.
- **Summary of Changes:**
  - **Reconciled Evidence Register (`docs/03-research/evidence-register.md`)**:
    - Audited claim IDs: verified exact count of **15 claims** (reconciling previous completion report text stating 14 claims against the 15 actual rows in the register matrix).
    - Added explicit **Claim Accounting & Evidentiary Category Totals** matrix:
      - Category 1 (Implemented and Code-Inspected): 0 (subsumed under Category 2 automated checks)
      - Category 2 (Tested by Automated Checks): 10 claims (`CLM-ING-01` through `CLM-ING-05`, `CLM-SPA-01`, `CLM-SPA-02`, `CLM-CLU-01` through `CLM-CLU-03`)
      - Category 3 (Experimentally Observed): 2 claims (`CLM-ING-06`, `CLM-CLU-04`)
      - Category 4 (Independently Reproduced): 0 (pending multi-trial, multi-environment replication)
      - Category 5 (Reported by Development Assistant): 1 claim (`CLM-CLU-05`)
      - Category 6 (Planned or Hypothesized): 2 claims (`CLM-CLU-06`, `CLM-ANO-01`)
      - Total: 15 claims.
    - Qualified `CLM-CLU-02` (runtime determinism within tested Python environment).
    - Clarified `CLM-CLU-05` to cite both the instrumented `clustering_summary.json` (38.014 s wall time, 225.83 MB peak heap under `tracemalloc`) and uninstrumented development log timing (13.680 s wall time).
  - **Parquet Compression Alignment**:
    - Checked implementation (`src/aegismar/ingestion/storage.py`, `src/aegismar/clustering/export.py`) and confirmed default is `zstd`.
    - Inspected `cleaned_ais.parquet` and `cluster_assignments.parquet` metadata on disk and confirmed compression is `ZSTD`.
    - Corrected outdated references to "Snappy" in `docs/START-HERE.md`, `CHANGELOG.md`, and `docs/04-development/development-log.md` to `zstd`.
  - **CI/CD Status Qualification**:
    - Verified `.github/` contains only `pull_request_template.md` (no active GitHub Actions workflows configured).
    - Replaced claims of "passing in CI/CD" with "passing in local test suite verification via `uv run pytest`" in `docs/START-HERE.md`, `docs/03-research/evidence-register.md`, and `docs/01-project/collaboration-plan.md`.
  - **Evidence-Based Language Qualification**:
    - Qualified "bit-for-bit reproducibility across machines" to deterministic execution within defined numerical tolerances on the tested Python 3.11 Windows runtime (`ADR-002`, `docs/START-HERE.md`).
    - Qualified AIS signal gaps to terrestrial receiving network reception gaps rather than transponder deactivation or clandestine intent (`docs/START-HERE.md`, `README.md`).
    - Qualified operational hazard statements to potential navigational hazards requiring operator review (`docs/START-HERE.md`).
    - Toned down microservice serialization penalties from "massive" to substantial IPC/serialization overhead (`ADR-001`, `docs/START-HERE.md`).
    - Re-verified that 241 density clusters are consistently documented as raw spatiotemporal density groups, not confirmed anchorages (`docs/START-HERE.md`, `README.md`, `docs/03-research/evidence-register.md`).
    - Re-verified non-probabilistic semantics of Isolation Forest anomaly indices (`docs/START-HERE.md`, `docs/03-research/vessel-behavior-ml.md`).
    - Reframed operator alert fatigue assertions as documented findings from maritime decision-support literature (`docs/START-HERE.md`, `README.md`, `docs/03-research/vessel-behavior-ml.md`).
  - **Collaborator Onboarding Practicality**:
    - Embedded the comprehensive 11-step collaborator onboarding checklist into `docs/START-HERE.md` Section 13 with verified commands and cross-links.
    - Verified all paths, command syntax, and relative markdown links across the documentation.
- **Verification:**
  - Confirmed zero modifications under `src/` or `tests/` (`git diff --stat src/ tests/` empty).
  - Re-ran quality gates: `uv sync --locked`, `uv run pytest -v` (52 passed), `uv run ruff check .` (clean), `uv run ruff format --check .` (clean), `uv run mypy src tests` (strict mode clean).
  - Verified 100% relative markdown links across all documentation.
- **Next Action:**
  - Proceed to Milestone W3-01: H3 Spatial Indexing, Neighborhood Completeness & Correctness Verification.

---

## Log Entry: 2026-11-22 — Milestone W3-01

- **Date:** 2026-11-22
- **Task Identifier:** `W3-01: H3 Spatial Indexing, Neighborhood Completeness & Correctness Verification`
- **Branch:** `feat/clu-h3-neighborhood`
- **Scope:** Implementation and correctness verification of the H3 hexagonal neighborhood candidate generator (`H3NeighborhoodProvider`) as a pluggable alternative to `BallTreeNeighborhoodProvider` preserving 100% ST-DBSCAN clustering semantics.
- **Summary of Changes:**
  - **Dependency Addition**: Installed `h3>=4.0.0` via `uv add "h3>=4.0.0"`. Locked `h3==4.5.1` in `uv.lock` and added `h3` typing override in `pyproject.toml`.
  - **Mathematical Clearance & Safe $k$-Ring Lower Bounds (`src/aegismar/clustering/h3_neighbors.py`)**:
    - Formulated conservative candidate lower bound: any point within distance $\varepsilon_s$ of an observation in cell $c$ cannot cross past its $k$-ring if the minimum clearance to cells outside the $k$-ring is $\ge \varepsilon_s$.
    - Implemented `compute_safe_k_ring(resolution, eps_spatial_m)` using exact geometric lower bounds:
      - Res 7 ($k=1$): $\ge 988.13\text{ m} \ge 300\text{ m}$ (safe for $\varepsilon_s \le 988\text{ m}$)
      - Res 8 ($k=1$): $\ge 395.60\text{ m} \ge 300\text{ m}$ (safe for $\varepsilon_s \le 395\text{ m}$)
      - Res 9 ($k=1$): $\ge 141.12\text{ m} < 300\text{ m}$ (insufficient for 300 m); automatic $k=2$ expansion yields $\ge 371.74\text{ m} \ge 300\text{ m}$ (safe)
    - Validated all 12 icosahedral pentagonal cells satisfy the same clearance bounds at Res 8, and provided defense-in-depth pentagon and exception fallback to `BallTreeNeighborhoodProvider`.
  - **H3 Neighborhood Provider Implementation (`src/aegismar/clustering/h3_neighbors.py`)**:
    - Grouped observations by H3 cell index preserving non-decreasing canonical timestamp order.
    - Precomputed active candidate cells present in dataset via `h3.grid_disk(c, k)`.
    - Implemented $O(\log M_{\text{cell}})$ inclusive temporal candidate slicing per cell using `np.searchsorted` (`left = np.searchsorted(times, t_i - eps_t, side='left')`, `right = np.searchsorted(times, t_i + eps_t, side='right')`).
    - Implemented exact spherical Haversine candidate pruning matching `BallTreeNeighborhoodProvider`.
    - Added comprehensive diagnostic metrics (`candidate_generation_time_seconds`, `temporal_filtering_time_seconds`, `distance_filtering_time_seconds`, `fallback_count`, `total_candidates_evaluated`).
  - **Clustering Engine & Configuration Updates (`src/aegismar/clustering/`)**:
    - `config.py`: Extended `STDBSCANConfig` with `provider` (`balltree_haversine` or `h3_haversine`), `h3_resolution` (7, 8, 9; default 8), `h3_k_ring`, and `h3_enable_fallback` with strict parameter validation.
    - `types.py`: Added `provider_metrics` to `STDBSCANResult` and `summary_dict()`.
    - `st_dbscan.py`: Added `run_h3_st_dbscan(...)` convenience runner and collected provider metrics into `STDBSCANResult`.
    - `cli.py`: Added `--provider`, `--h3-resolution`, and `--h3-k-ring` arguments to `cluster` subcommand with full backward compatibility.
  - **Unit Test Suite Authoring (`tests/unit/test_h3_neighbors.py`)**:
    - Created 20 dedicated fixture tests covering: same-cell neighbors, adjacent cells, multi-ring candidate completeness (Res 9, $k=2$), points on opposite sides of cell boundaries ($\delta \le 10\text{ m}$), exact spatial/temporal threshold equality, temporal window traversals, dense cells, sparse isolated cells, pentagonal cells & fallback, high latitudes, antimeridian crossing ($\pm 180^\circ$), multiple resolutions (7, 8, 9), randomized oracle comparisons (seeds 101, 202, 303, 404), input permutation invariance, determinism, empty inputs, invalid configurations, data-quality filter policies, and fallback logging.
  - **Empirical Real-Data Parity on San Pedro Bay Baseline**:
    - Clustered 143,116 analyzed observations (`data/processed/lalb_20250101/cleaned_ais.parquet`) using `H3NeighborhoodProvider` at Resolution 8 ($k=1$):
      - 241 clusters, 136,276 core, 934 border, 5,906 noise
      - Exact parity with BallTree reference: 143,116 / 143,116 label matches (100.0000%), 143,116 / 143,116 role matches (100.0000%)
      - 798 unique occupied cells, 0 pentagons, 0 fallbacks
      - Build time: 0.984 s (uninstrumented: 0.140 s); query time: 46.343 s (uninstrumented: 13.310 s)
  - **Quality Gates Verification**:
    - Pytest: 77 passed in 2.19 s (52 previous + 25 new tests/parameters, 100% pass)
    - Code Coverage: 93% total repository coverage (89% in `h3_neighbors.py`)
    - Ruff: 0 lint errors, 60 files formatted
    - Mypy: 0 errors in 27 source files
- **Verification Commands Executed:**
  - `uv add "h3>=4.0.0"`
  - `uv sync --locked`
  - `uv run pytest -v`
  - `uv run pytest --cov=aegismar --cov-report=term-missing`
  - `uv run ruff format .`
  - `uv run ruff check .`
  - `uv run mypy src tests`
  - `uv run python -m aegismar cluster --input data/processed/lalb_20250101/cleaned_ais.parquet --output experiments/outputs/w3_01_lalb_h3 --provider h3 --h3-resolution 8 --overwrite`
- **Next Action:**
  - Proceed with Milestone W3-02 (Comparative H1 Benchmarking).

---

## Log Entry: 2026-11-23 — Governance: Dual-Track Roadmap & Milestone Harmonization

- **Date:** 2026-11-23
- **Scope:** Complete documentation reconciliation of the dual-track milestone roadmap to eliminate ambiguity regarding Trajectory Anomaly Detection ownership and scheduling.
- **Summary of Changes:**
  - **Reconciled Track A vs. Track B Milestones**:
    - Updated `docs/04-development/milestones.md` by splitting the tracking board into two distinct tables: Track A (Weeks 1–8, Lead: NipunaBhanuka18) and Track B (Phases ML-01 to ML-05, Lead: Kishakya).
    - Reassigned Track A Week 5 to **Platform Analytical Storage & Contract Integration** (`W5-01`), focusing on in-process DuckDB query layer integration and validation of the provisional `vessel_anomaly_v1` GeoJSON contract.
    - Decoupled `W6-01` (FastAPI service) and DuckDB storage from blocking on ML model completion.
    - Added explicit milestone specifications for `ML-01` through `ML-05` under Track B with clear deliverables, capacities, and acceptance checks.
  - **Updated Project Roadmap (`docs/01-project/roadmap.md`)**:
    - Aligned Section 1 and Section 2 to reflect Track A's Week 5 storage focus and Section 3's independent parallel ML track (`ML-01`–`ML-05`).
  - **Aligned README (`README.md`) & Onboarding Guides**:
    - Updated Section 8 and Section 9 in `README.md` to reflect distinct Track A and Track B milestone boards.
    - Updated `docs/START-HERE.md` Section 14 to reflect the harmonized milestone sequence.
    - Updated `docs/01-project/scope.md` to explicitly assign scope items to Track A and Track B.
- **Verification:**
  - Verified zero occurrences of legacy "Week 5: Trajectory Anomaly Detection" across the repository.
  - Verified all relative markdown links remain valid.
  - Confirmed 77 unit tests pass cleanly.

---

## Log Entry: 2026-11-23 — Task: Milestone W3-01A (H3 Completeness Audit, Correctness Hardening & Pull Request Preparation)

- **Date:** 2026-11-23
- **Task Identifier:** `W3-01A: H3 Completeness Audit, Correctness Hardening & Pull Request Preparation`
- **Branch:** `feat/clu-h3-neighborhood`
- **Scope:** Technical audit of H3 clearance geometry, implementation of Option B fail-closed fallback policy, rejection of undersized $k$-rings, elimination of silent downgrades on `grid_disk` errors, hardening of near-pentagon fallback, performance sub-timing instrumentation, authoring 7 new adversarial test fixtures, verifying 100% bit-for-bit graph parity on authentic NOAA AIS data, and preparing pull request.
- **Summary of Changes:**
  - **Audit of H3 Clearance Mathematics & Geometry**:
    - Investigated planar regular hexagon apothem formulas ($k \cdot 2 r_{\text{inscribed}} = k \sqrt{3} s$) versus spherical H3 cells projected from an icosahedron via Snyder equal-area projection.
    - Clarified that Snyder projection induces non-uniform hexagon edge lengths (varying by $\sim 1.4\times$ across each icosahedral face) and introduces 12 pentagonal faces per resolution.
    - Concluded that planar apothem formulas cannot analytically prove global spherical completeness across arbitrary coordinates. Formulated and adopted **Option B**: experimental H3 candidate acceleration supported by an observable, fail-closed BallTree fallback policy for unproven or anomalous conditions.
    - Reconciled documentation in `src/aegismar/clustering/h3_neighbors.py`, `ADR-009`, `evaluation-protocol.md`, and `evidence-register.md` (`CLM-CLU-06`).
  - **Rejection of Undersized $k$-Ring Configurations**:
    - Updated `H3NeighborhoodProvider.__init__`: if user configures `k_ring < safe_k` (either via constructor argument or `STDBSCANConfig`), strictly raise `ValueError` explaining that configured $k$ is smaller than the required completeness bound, preventing silent candidate omissions.
  - **Fail-Closed Discrete Expansion Exception Handling**:
    - Updated `H3NeighborhoodProvider.__init__`: if `h3.grid_disk(c, k)` raises an exception, the cell is marked for fallback in `_cells_requiring_fallback` and recorded in `_fallback_reasons` if fallback is enabled (`enable_fallback=True`).
    - If fallback is disabled (`enable_fallback=False`), the constructor immediately raises `RuntimeError`.
    - Completely eliminated previous silent downgrade behavior where failed expansions defaulted to self-cell `active_candidates[c] = [c]`.
  - **Hardening of Pentagon & Near-Pentagon Fallback**:
    - Precomputed whether any cell in `grid_disk(c, k)` is a pentagon (`near_pentagon`).
    - If `fallback_on_pentagons` is enabled, any cell that is a pentagon or is adjacent to a pentagon in its disk is routed to BallTree fallback (reason: `"pentagon_or_near_pentagon"`).
    - If `fallback_on_pentagons` is enabled but fallback is disabled, index construction immediately fails closed with `RuntimeError`.
  - **Observable Fallback Routing & Sub-Timing Instrumentation**:
    - In `_query_single_index`, cells requiring fallback route to `BallTreeNeighborhoodProvider.query_neighbors`, tracking `fallback_count`, `fallback_time_seconds`, and incrementing `fallback_reasons` distribution counters.
    - Granular performance counters added to `get_metrics()`: `cell_mapping_time_seconds`, `candidate_precomputation_time_seconds`, `candidate_retrieval_time_seconds`, `temporal_filtering_time_seconds`, `distance_filtering_time_seconds`, and `fallback_reasons` dict.
  - **Configuration Extensions (`src/aegismar/clustering/config.py` & `st_dbscan.py`)**:
    - Extended `STDBSCANConfig` with `h3_fallback_on_pentagons: bool = False` with type validation and dictionary serialization.
    - Updated `run_h3_st_dbscan` parameter defaults to `enable_fallback=None, fallback_on_pentagons=None` so config-level values propagate cleanly.
  - **Adversarial Unit Test Suite (`tests/unit/test_h3_neighbors.py`)**:
    - Authored 7 new dedicated adversarial test fixtures (fixtures 21–27; 34 tests in module, 86 in repository):
      - `test_21_undersized_k_ring_rejected`: verifies `ValueError` on direct parameter and config overrides.
      - `test_22_forced_grid_disk_failure_fallback`: mocks `grid_disk` failure, confirms cell marks for fallback, records `grid_disk_failed` reason, and achieves 100% parity with BallTree.
      - `test_23_forced_grid_disk_failure_disabled_fallback`: confirms `RuntimeError` raised when fallback disabled.
      - `test_24_near_pentagon_hex_fallback`: verifies hexagons adjacent to pentagons trigger fallback and match BallTree.
      - `test_25_cell_vertex_and_boundary_adversarial_pairs`: tests sub-meter point pairs across cell vertices against oracle and BallTree.
      - `test_26_multi_region_oracle_parity`: verifies candidate completeness and oracle parity across Equator (Singapore), English Channel (Dover), and Arctic (Tromsø) across resolutions 7, 8, 9.
      - `test_27_spatial_radii_near_clearance_boundaries`: tests $\varepsilon_s$ values immediately below and above clearance thresholds (e.g. 394 m vs 396 m at Res 8, 140 m vs 142 m at Res 9), verifying correct $k$-ring transition and candidate completeness.
  - **Empirical Full-Graph Parity Verification on Authentic NOAA AIS Data**:
    - Evaluated full CSR graph parity between `BallTreeNeighborhoodProvider` and `H3NeighborhoodProvider` on all 143,116 analyzed observations (13,188,256 edges) of `data/processed/lalb_20250101/cleaned_ais.parquet` at $\varepsilon_s = 300\text{ m}, \Delta T = 900\text{ s}$:
      - `CSR indptr match: True` (100.0000% degree identity)
      - `CSR indices match: True` (100.0000% exact neighbor index identity across all 13,188,256 edges)
      - `BallTree build: 0.2748 s, graph query: 41.9774 s`
      - `H3 build: 0.5340 s, graph query: 31.2847 s`
      - `Graph query speedup: 1.34x`
      - `Fallback count: 0` (0 pentagons in San Pedro Bay study sector; zero grid disk errors)
  - **Quality Gates Verification**:
    - `pytest`: 86 passed in 5.71 s (100% pass)
    - Code Coverage: 93% total repository coverage
    - `ruff`: 0 lint errors; 60 files formatted
    - `mypy`: 0 errors across 27 source files in strict mode
- **Next Action:**
  - Execute Milestone W3-01B: H3 Correctness Contract Finalization.

---

## Log Entry: 2026-11-23 — Task: Milestone W3-01B (H3 Correctness Contract Finalization)

- **Date:** 2026-11-23
- **Task Identifier:** `W3-01B: H3 Correctness Contract Finalization`
- **Branch:** `feat/clu-h3-neighborhood`
- **Scope:** Resolution of the mismatch between empirically tested H3 candidate coverage and claims of guaranteed completeness; replacing unsupported extrapolations/approximations with fail-closed rejection or fallback; requiring explicit opt-in for experimental uncalibrated configurations; establishing dataset-scoped parity verification tools; and updating research documentation.
- **Summary of Changes:**
  - **Correctness Contract & Empirical Bounds Audit**:
    - Removed all claims of "guaranteed candidate completeness" or unconditional global mathematical theorems.
    - Formalized the two-tier support policy:
      1. Calibrated regional candidate search on resolutions 7, 8, 9 within empirically tested search radii.
      2. Fail-closed rejection or fallback for uncalibrated resolutions, radii exceeding empirical tables, or expansion anomalies.
  - **Replaced Unsupported Extrapolation with Fail-Closed Configuration Handling**:
    - Updated `compute_safe_k_ring(resolution, eps_spatial_m, allow_uncalibrated=False)`:
      - If resolution is not in `H3_MIN_CLEARANCE_METERS` (calibrated: 7, 8, 9) and `allow_uncalibrated=False`, raises `ValueError`.
      - If `eps_spatial_m` exceeds the maximum empirical clearance in the table and `allow_uncalibrated=False`, raises `ValueError`.
    - Updated `H3NeighborhoodProvider.__init__`:
      - If an unsupported configuration is supplied without opt-in (`allow_uncalibrated=False`):
        * If `enable_fallback=False`: raises `ValueError` immediately.
        * If `enable_fallback=True`: routes all queries cleanly to `BallTreeNeighborhoodProvider` with `completeness_contract = "full_balltree_fallback"`, recording `fallback_reasons["unsupported_configuration..."]`.
      - If explicit experimental opt-in (`allow_uncalibrated=True`) is provided:
        * Emits clear logger warnings.
        * Flags metadata `is_calibrated = False`, `completeness_contract = "experimental_uncalibrated"`.
  - **Configuration Model Extension (`src/aegismar/clustering/config.py`)**:
    - Added `SUPPORTED_CALIBRATED_H3_RESOLUTIONS: tuple[int, ...] = (7, 8, 9)`.
    - Added `h3_allow_uncalibrated: bool = False` to `STDBSCANConfig` with boolean type validation and JSON serialization.
    - Updated `run_h3_st_dbscan` to accept `allow_uncalibrated: bool | None = None`.
  - **Dataset-Scoped Parity Verification Command (`aegismar verify-parity`)**:
    - Created `verify_dataset_h3_balltree_parity` function and `ParityVerificationResult` dataclass in `h3_neighbors.py`.
    - Added `verify-parity` subcommand to `src/aegismar/cli.py` and exported from `src/aegismar/clustering/__init__.py`.
    - Computes input Parquet SHA-256, runs full CSR graph build and ST-DBSCAN for both BallTree and H3, verifies `indptr`, `indices`, cluster count, role counts, and cluster labels, and prints a formatted verification report.
  - **Targeted Unit Test Suite Additions (`tests/unit/`)**:
    - Added fixtures 28–32 in `tests/unit/test_h3_neighbors.py`:
      - `test_28_unsupported_resolution_handling`: verifies `ValueError` in strict mode and full BallTree fallback when enabled.
      - `test_29_radius_exceeding_calibrated_table_handling`: verifies `ValueError` on excessive radii and fallback when enabled.
      - `test_30_experimental_uncalibrated_mode`: verifies opt-in approximate ring estimation, warnings, and contract metadata.
      - `test_31_parity_verification_helper`: verifies `verify_dataset_h3_balltree_parity` helper.
      - `test_32_contract_semantics_and_metadata`: verifies calibrated contract reporting.
    - Added `test_cli_verify_parity_command` in `tests/unit/test_cli.py`.
    - Total test count expanded to 92 tests passing at 94% repository code coverage (98% in `h3_neighbors.py`).
  - **Full-Dataset Parity Execution**:
    - Executed `verify-parity` on canonical NOAA San Pedro Bay dataset (`data/processed/lalb_20250101/cleaned_ais.parquet`, SHA-256: `4a7ca719dc2a3d9959cc4166edff773ca09156d8d914e54d0ab5f851ece5e88b`):
      - 143,116 analyzed observations, 13,188,256 total CSR edges.
      - `CSR indptr Match: PASS (Identical degrees)`
      - `CSR indices Match: PASS (Identical neighbors across all 13.1M edges)`
      - `Cluster Count Match: PASS` (241 clusters)
      - `Core/Border/Noise Match: PASS` (136,276 core, 934 border, 5,906 noise)
      - `Cluster Labels Match: PASS`
      - `Fallback Count: 0`
      - `Completeness Contract: empirical_regional_calibrated`
  - **Documentation Updates**:
    - Updated `README.md`, `ADR-009`, `evidence-register.md` (`CLM-CLU-06`), `evaluation-protocol.md`, `milestones.md`, and `CHANGELOG.md`.
- **Quality Gates Verification**:
  - `pytest`: 92 passed in 5.98 s (100% pass)
  - Code Coverage: 94% total repository coverage (98% in `h3_neighbors.py`)
  - `ruff`: 0 lint errors; 60 files formatted
  - `mypy`: 0 errors across 27 source files in strict mode
  - Markdown link check: 50 markdown files checked, 0 broken links
- **Next Action:**
  - Commit on feature branch `feat/clu-h3-neighborhood` with authorized message, push to origin, and prepare completion report.

---

## Log Entry: 2026-11-23 — Track B: ML-01 (Data Profiling), ML-02, ML-03 and Held-Out Test Days

- **Date:** 2026-11-23
- **Track:** Track B (Vessel Behavior ML) — Kishakya
- **Branches / PRs:** `feat/ml-01-data-profiling` (PR #2, merged), `feat/ml-02-feature-spec` (PR #3, merged), `feat/ml-03-evaluation-protocol` (PR #4)
- **Summary of Work:**
  - **Environment:** `uv sync --locked` (Python 3.11.9) on a second workstation; all quality gates passed before any change.
  - **Independent dataset reproduction:** Downloaded `ais-2025-01-01.csv.zst` (202,190,247 bytes; SHA-256 matches `datasets.md`). Sliced the San Pedro Bay box (lat [33.5, 33.9], lon [-118.4, -118.0]) with a new streaming slicer: 7,337,208 nationwide rows scanned → 143,156 rows / 362 vessels, sample SHA-256 `42e4f766feb98b20e98124685137bcc2be16a20c06dda46e33f415f0b281eac8` (exact match). `aegismar ingest` reproduced 143,124 rows (32 duplicates, 8 conflicts, 18 implied-speed violations). Re-running the W2-01 BallTree configuration reproduced 241 clusters (136,276 core, 934 border, 5,906 noise).
  - **ML-01 profiling** (`experiments/anomaly/ml01_profile_dataset.py`): reporting cadence about 70 s (moving) and about 180 s (stationary); 90.0% of SOG values < 0.5 kt; 135 of 362 vessels ever reach SOG ≥ 1.5 kt; heading present in 63.0% of Class A and 8.8% of Class B rows; two feed-wide silences (03:07:37–03:20:25 and 12:06:09–12:18:20 UTC) spanned by 557 of 1,579 vessel gaps > 600 s.
  - **ML-02 v1.0** (`docs/03-research/ml-02-feature-spec.md`) and `experiments/anomaly/ml02_drift_breakdown.py`: of 429 COG–heading disparities > 45° at SOG ≥ 1.5 kt, 342 are near-reversals (> 135°; 281 from tug/towing vessels) and 87 are lateral drift (45–135°), leading to separate features F7/F8.
  - **ML-03 v1.0** (`docs/03-research/ml-03-evaluation-protocol.md`): frozen before any test-day inspection.
  - **Held-out test days (integrity checks only, per the ML-03 firewall):**
    - T1 2025-01-14: `ais-2025-01-14.csv.zst` 206,100,977 bytes, SHA-256 `973dda3660fe1386da6d4ecbafeaa1e1d4de3c31b3cff535c4d78ec4aa9679f3`; 7,225,757 nationwide rows → 121,778 sample rows / 348 vessels (sample SHA-256 `0725aedd78ca44e736b2c6026846f1cbb66fbe3027e79e95b72ec16f8ca33516`) → 121,742 cleaned rows (36 duplicates, 8 conflicts, 0 hard-invalid); Parquet SHA-256 `5b13767f2a48b4fdff76179049375611cf42a17ce24e8294579a01a7718b42f2`; range 2025-01-14T00:00:00Z → 23:59:59Z.
    - T2 2025-01-22: `ais-2025-01-22.csv.zst` 189,491,631 bytes, SHA-256 `6a238bd4084b5afc1d7d95ccbcee182d5d4a250377224da76721a63a2277f627`; 6,818,100 nationwide rows → 119,803 sample rows / 356 vessels (sample SHA-256 `afd7240b4d8d48fe706d8db5905ab37e8217d4dd80256a58a403876a47e1b120`) → 119,750 cleaned rows (53 duplicates, 4 conflicts, 0 hard-invalid); Parquet SHA-256 `44d5eda18a64af873c13053df383fb806349e34aecc77abfc0dc4afafae816c5`; range 2025-01-22T00:00:00Z → 23:59:59Z.
- **Known open item:** ML-01 literature review notes not yet written.

---

## Log Entry: 2026-11-24 — Track B: Documentation Sync after ML-01–ML-03

- **Date:** 2026-11-24
- **Track:** Track B — Kishakya
- **Branch:** `docs/track-b-ml01-ml03-sync` (based on `feat/ml-03-evaluation-protocol`)
- **Summary of Changes:**
  - Added `scripts/slice_noaa_bbox.py` (re-verified: reproduces the 2025-01-01 sample SHA-256 `42e4f766…`).
  - Updated README, START-HERE, roadmap, milestones, ML onboarding guide (v1.2), ML proposal (v1.2, superseded-part notes), evaluation protocol §3 (pointer to ML-03), collaboration plan §4.1 (row order), evidence register (CLM-ANO-01 references, test-count instruction), and CHANGELOG.
  - Removed a stale duplicate of the W7-02 / W8-01 / W8-02 specifications (and a misplaced dashboard acceptance bullet under ML-05) from the end of `milestones.md`; the current Track A versions are unchanged.
  - Historical records (W2-01 milestone notes, ADRs) intentionally keep the figures valid at their time.
  - Track B leadership confirmed: Kishakya reviewed and accepted the collaboration plan, so the "Proposed / pending review" qualifiers were removed from 14 current documents. ADR-010 keeps its original wording as a historical decision record.
- **Quality Gates:** see the PR description for the executed results.
- **Next Action:** ML-04 — implement `src/aegismar/anomaly/features.py` per ML-02 v1.0.
