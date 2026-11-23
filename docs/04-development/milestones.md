# Milestone Schedule & Tracking

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**

**Document Version:** 2.3  
**Status:** Collaborative Dual-Track Milestone Architecture  
**Research Tracks & Capacity:**  
- **Track A (Maritime Traffic & Geospatial Clustering Lead):** NipunaBhanuka18 (200 Hours across 8 Weeks, 25 Hours/Week)  
- **Track B (Vessel Behavior ML Track Lead):** Kishakya *(participation pending review; independent parallel schedule)*  
**Status Key:** `Planned` | `In Progress` | `Completed` | `Deferred`  

---

## 1. Track A Milestone Tracking Board (Maritime Traffic & Platform Foundation)

**Lead:** NipunaBhanuka18  
**Scope:** AIS Data Engineering, BallTree/H3 ST-DBSCAN Clustering, Stay-Point & Anchorage Intelligence, Analytical Storage, FastAPI Serving, Web Map UI, and Benchmarking.

| Milestone ID | Target Week | Target Deliverable | Est. Hours | Status | Dependencies |
|---|---|---|---|---|---|
| **W1-01** | Week 1 | Repository Initialization & Documentation Foundation | 10 h | **Completed** | None |
| **W1-02A** | Week 1 | NOAA AIS Dataset Selection & Schema Investigation | 5 h | **Completed** | W1-01 |
| **W1-02B** | Week 1 | Production AIS Ingestion, Sentinel Handling & Parquet Storage | 10 h | **Completed** | W1-02A |
| **W2-01** | Week 2 | Ingestion Corrections, BallTree Reference ST-DBSCAN & Brute-Force Oracle | 15 h | **Completed** | W1-02B |
| **DOC-01** | Week 2+ | Evidence-Backed Research & Engineering Documentation | 10 h | **Completed** | W2-01 |
| **DOC-01A** | Week 2+ | Research Documentation Accuracy & Collaborator Readiness | 4 h | **Completed** | DOC-01 |
| **W3-01** | Week 3 | H3 Candidate Optimization & Completeness Verification | 15 h | **Completed** | W2-01 |
| **W3-01A** | Week 3 | H3 Completeness Audit, Correctness Hardening & PR Preparation | 6 h | **Completed** | W3-01 |
| **W3-01B** | Week 3 | H3 Correctness Contract Finalization | 4 h | **Completed** | W3-01A |
| **W3-02** | Week 3 | Comparative H1 Benchmarking (BallTree vs. H3) | 10 h | Planned | W3-01B |
| **W4-01** | Week 4 | Stay-Point Extraction & Berth Polygon Exclusion | 15 h | Planned | W3-02 |
| **W4-02** | Week 4 | Anchorage Dwell Metrics & Utilization Analytics | 10 h | Planned | W4-01 |
| **W5-01** | Week 5 | DuckDB In-Process Analytics & Contract Integration | 15 h | Planned | W3-02, W4-02 |
| **W6-01** | Week 6 | Read-Only FastAPI Service Implementation | 10 h | Planned | W5-01 |
| **W7-01** | Week 7 | Interactive Geospatial Web Map Dashboard | 15 h | Planned | W6-01 |
| **W7-02** | Week 7 | End-to-End Pipeline Integration & Verification | 10 h | Planned | W7-01 |
| **W8-01** | Week 8 | Automated Benchmark Execution (10k, 50k, 100k) | 15 h | Planned | W7-02 |
| **W8-02** | Week 8 | Reproducibility Package, Final Audit & Thesis Report | 10 h | Planned | W8-01 |

---

## 2. Track B Milestone Tracking Board (Vessel Behavior ML & Anomaly Detection)

**Proposed Lead:** Kishakya *(participation pending review)*  
**Scope:** Vessel Trajectory Feature Engineering, Explainable Rule-Based Kinematic Scoring, Unsupervised Anomaly Modeling (Isolation Forest / LOF), Controlled Perturbation Evaluation, and Explainable GeoJSON Incident Export.  
**Schedule Governance:** Independent parallel schedule; milestones advance based on Kishakya's availability without hard week-number deadlines.

| Milestone ID | Target Phase | Target Deliverable | Est. Hours | Status | Dependencies |
|---|---|---|---|---|---|
| **ML-01** | Phase 1 | Domain Literature, AIS Schema & Telemetry Review | 10 h | Planned | None (Cleaned Parquet available) |
| **ML-02** | Phase 2 | Vessel Trajectory Kinematic Feature Specification | 15 h | Planned | ML-01 |
| **ML-03** | Phase 3 | Baseline Models & Evaluation Protocol Freezing | 15 h | Planned | ML-02 |
| **ML-04** | Phase 4 | Feature Engineering Module & Baseline Experiments | 20 h | Planned | ML-03, `cleaned_ais.parquet` |
| **ML-05** | Phase 5 | Anomaly Model Evaluation & `vessel_anomaly_v1` Export | 20 h | Planned | ML-04 |

---

## 3. Milestone Detail Specifications — Track A (Platform & Clustering)

### Milestone W1-01: Repository Initialization & Documentation Foundation
- **Goal:** Establish a robust, reproducible Git repository, CPython 3.11 environment, testing/linting/typing quality gates, and exhaustive documentation architecture.
- **Estimated Hours:** 10 Hours
- **Status:** **Completed** (Implementation & audit verified; initial commit and GitHub push authorized)
- **Planned Deliverables:**
  - `.python-version` pinned to 3.11.9
  - Strict `.gitignore` protecting raw data and caches
  - `pyproject.toml` with `hatchling`, Ruff, Pytest, and Mypy
  - Locked `uv.lock`
  - Complete `docs/` hierarchy (`01-project`, `02-architecture`, `03-research`, `04-development`, `05-guides`)
  - Root `README.md` and `CHANGELOG.md`
  - Smoke test suite (`tests/test_smoke.py`)
- **Acceptance Checks:**
  - [x] `uv sync --locked` succeeds without error
  - [x] `pytest` passes 100% (`test_package_import`, `test_python_runtime_version`)
  - [x] `ruff check .` and `ruff format --check .` exit cleanly (0 errors)
  - [x] `mypy src tests` passes in strict mode
  - [x] Documentation index links resolve properly (15 relative links, 2 heading anchors)
  - [x] Dry-run staging audit confirms zero credentials, datasets, or caches tracked

### Milestone W1-02A: NOAA AIS Dataset Selection & Schema Investigation
- **Goal:** Investigate official NOAA 2025 AIS distribution, empirically compare candidate study regions (Los Angeles / Long Beach vs Delaware Bay), profile source schema and sentinels, and select primary research sector.
- **Estimated Hours:** 5 Hours
- **Status:** **Completed**
- **Dependencies:** W1-01
- **Deliverables:**
  - Acquired authentic 2025 NOAA extract (`ais-2025-01-01.csv.zst`, 192.82 MB, preserved in `data/raw/`)
  - Comparative profiling across LA/LB (143k pings) and Delaware Bay (42k pings)
  - Formal selection of Los Angeles / Long Beach (San Pedro Bay) as primary research sector
  - Detailed schema evolution findings (2025 snake_case, coordinate order, sentinel nullification)
  - Anchorage and berth reference data feasibility framework
  - Updated `datasets.md`, `srs.md`, `milestones.md`, and `development-log.md`
- **Acceptance Checks:**
  - [x] Official NOAA 2025 bulk source identified and verified
  - [x] Download size within limits (<500 MB); raw bytes preserved in ignored directory
  - [x] Real schema documented without speculation
  - [x] Selection of LA/LB supported by empirical data density and anchorage geometry

### Milestone W1-02B: Production AIS Ingestion, Sentinel Handling & Parquet Storage
- **Goal:** Build the production AIS parser, sentinel/null coercion engine, coordinate/speed validator, and columnar Parquet storage writer.
- **Estimated Hours:** 10 Hours
- **Status:** **Completed**
- **Dependencies:** W1-02A
- **Deliverables:**
  - `src/aegismar/common/constants.py` & `types.py` (canonical types, sentinels, domain bounds, and quality flags)
  - `src/aegismar/spatial/haversine.py` (spherical geodesic metric functions)
  - `src/aegismar/ingestion/schema.py` (dual 2025/legacy schema adapter and Arrow canonical schema)
  - `src/aegismar/ingestion/cleaner.py` (record validation, sentinel nullification, duplicate consolidation, conflict detection, implied speed calculation)
  - `src/aegismar/ingestion/storage.py` (Arrow table conversion, zstd Parquet writer, manifest manager, metadata inspector)
  - `src/aegismar/ingestion/pipeline.py` (in-memory batch CSV-to-Parquet pipeline runner with SHA-256 computation and overwrite protection)
  - `src/aegismar/cli.py` & `__main__.py` (CLI entrypoints with `ingest` subcommand)
  - Unit test suite (`tests/unit/test_ingestion.py`, `tests/unit/test_cli.py`, 25 total tests, 91% coverage)
  - Production dataset ingestion: 143,156 input records parsed -> 143,124 output rows in `data/processed/lalb_20250101/cleaned_ais.parquet` (4.15 MB) + `manifest.json` in 7.19 s
- **Acceptance Checks:**
  - [x] Sentinels (`SOG 102.3`, `HDG 511`, `COG 360.0`, `Status 15`, and 2025 nulls) coerced deterministically
  - [x] Teleportation pings ($v_{\text{implied}} > 50\text{ kt}$) cleanly flagged (`IMPLIED_SPEED_VIOLATION`, 18 occurrences)
  - [x] Parquet output preserves all valid records without data loss with roundtrip schema fidelity
  - [x] Leading zero MMSIs strictly preserved as 9-character strings
  - [x] Duplicate observations consolidated and same-timestamp conflicts flagged
  - [x] All 25 unit tests pass; test coverage $\ge 90\%$; ruff and mypy exit cleanly with 0 errors

### Milestone W2-01: Ingestion Corrections, BallTree Reference ST-DBSCAN & Brute-Force Oracle
- **Goal:** Complete bounded W1-02B ingestion corrections and implement the verified `scikit-learn` Haversine `BallTree` reference ST-DBSCAN engine, injectable neighborhood provider architecture, independent brute-force oracle, and exploratory LA/LB baseline.
- **Estimated Hours:** 15 Hours
- **Status:** **Completed**
- **Dependencies:** W1-02B
- **Deliverables:**
  - Ingestion corrections: strict integer-format `sanitize_mmsi`, full-record deduplication & `TIMESTAMP_METADATA_CONFLICT` preservation, zero fictitious movement on same-timestamp conflicts, ambiguous/duplicate header rejection in `schema.py`, accurate in-memory batch documentation.
  - `src/aegismar/clustering/config.py` (`STDBSCANConfig`, `QualityFilterPolicy` with strict validation & radian conversion).
  - `src/aegismar/clustering/types.py` (`ClusteringInputDataset`, `NeighborhoodGraph` CSR, `NeighborhoodProvider` protocol, `STDBSCANResult`, Parquet loader with canonical total ordering).
  - `src/aegismar/clustering/balltree_neighbors.py` (`BallTreeNeighborhoodProvider` with `metric="haversine"`, `[lat_rad, lon_rad]` radians, chunked batch queries, exact integer-microsecond temporal filter, exact Haversine pruning).
  - `src/aegismar/clustering/st_dbscan.py` (provider-agnostic deterministic core-first ST-DBSCAN `stdbscan-core-first-v1.0` with nearest-core border tie-breaking).
  - `src/aegismar/clustering/export.py` (Parquet, summary JSON, compact GeoJSON preview, and offline SVG static map exporter) + CLI `aegismar cluster`.
  - `src/aegismar/spatial/oracle.py` (isolated $O(N^2)$ `BruteForceNeighborhoodOracle` with $N \le 5{,}000$ safety cap and `verify_provider_against_oracle`).
  - Test suites (`tests/unit/test_st_dbscan.py`, `tests/unit/test_oracle.py`, updated `test_ingestion.py` & `test_cli.py`): 52 passing tests, 95% total coverage ($\ge 95\%$ across clustering & oracle modules).
  - Exploratory LA/LB baseline (`experiments/outputs/w2_01_lalb_balltree/`): 143,116 analyzed rows (8 `TIMESTAMP_POSITION_CONFLICT` excluded), 241 clusters, 136,276 core, 934 border, 5,906 noise; 13.68 s uninstrumented wall time (38.01 s / 225.83 MB peak heap under `tracemalloc`); 100% oracle match on 1,000-row real subset; 100% deterministic across repeated runs.
  - Public portfolio visualization (`W2-CLOSE`): Genuine screenshot of the recorded LA/LB exploratory BallTree ST-DBSCAN preview saved at `docs/assets/w2-balltree-clustering.png` and embedded in `README.md` with explicit exploratory/non-anchorage caveats.
- **Acceptance Checks:**
  - [x] All 5 W1-02B ingestion corrections implemented with regression tests
  - [x] `BallTree` neighborhoods, core/border/noise roles, and cluster labels match brute-force oracle 100% across all synthetic, dateline, high-latitude, randomized, and real 1,000-row LA/LB fixtures
  - [x] Cluster accounting verified: `core + border + noise == analyzed`
  - [x] Full LA/LB baseline deterministic across repeated runs with artifacts exported to gitignored directory
  - [x] `uv sync --locked`, `pytest` (52 passed, 95% coverage), `ruff check`, `ruff format --check`, and `mypy src tests` exit cleanly with 0 errors
  - [x] Week 2 closure (`W2-CLOSE`) verified: public visualization published, research baseline recorded prior to Week 3 H3 optimization

### Milestone DOC-01: Evidence-Backed Research & Engineering Documentation
- **Goal:** Establish a professional, evidence-backed research and engineering knowledge base for collaborative AI research, linking all factual claims to concrete code, test, and artifact evidence.
- **Estimated Hours:** 10 Hours
- **Status:** **Completed**
- **Dependencies:** W2-01
- **Deliverables:**
  - `docs/START-HERE.md`: Central executive and collaborator onboarding guide (14 sections).
  - `docs/02-architecture/decisions/`: ADR register and 10 formal Architecture Decision Records (`ADR-001` through `ADR-010`).
  - `docs/03-research/evidence-register.md`: Comprehensive claims verification matrix reconciling 14 claims with hashes, commits, and parameters.
  - `docs/03-research/vessel-behavior-ml.md` (v1.1): Critical scientific corrections (AIS gaps, crabbing angles, non-probabilistic IF scores, synthetic documentation examples).
  - `docs/01-project/collaboration-plan.md` & `docs/05-guides/ml-research-onboarding.md`: Reconciled governance (One team, two complementary lead areas, flexible pace) and experimental guidelines.
  - `README.md`: Prominent tip linking to `START-HERE.md` and expanded documentation index.
- **Acceptance Checks:**
  - [x] Zero code modifications to working clustering, ingestion, or spatial logic (`src/`, `tests/`)
  - [x] All relative markdown links and paths verified across all repository documents
  - [x] 10 formal ADRs documented with context, alternatives, rationale, and evidence links
  - [x] Evidence register reconciles 14 claims with explicit categories and verification statuses
  - [x] ML proposal updated with domain corrections and synthetic documentation labeling
  - [x] All 5 automated quality gates pass: `uv sync --locked`, `pytest`, `ruff check`, `ruff format --check`, and strict `mypy`

### Milestone DOC-01A: Research Documentation Accuracy & Collaborator Readiness
- **Goal:** Conduct a rigorous documentation audit, reconcile claim accounting in the Evidence Register (exactly 15 claims), align Parquet compression statements with `zstd` implementation, remove unverified CI claims, qualify domain statements, and verify practical onboarding.
- **Estimated Hours:** 4 Hours
- **Status:** **Completed**
- **Dependencies:** DOC-01
- **Deliverables:**
  - `docs/03-research/evidence-register.md`: Audited all 15 claims and added explicit Claim Accounting & Evidentiary Category Totals matrix (10 automated, 2 observed, 1 assistant reported, 2 hypothesized); qualified `CLM-CLU-02` (runtime determinism) and `CLM-CLU-05` (uninstrumented dev log vs instrumented summary JSON); aligned Parquet reference to `zstd`.
  - `docs/START-HERE.md`: Corrected Parquet compression to `zstd`, qualified CI/CD claims to local pytest suite, qualified domain claims (reception gaps, potential hazards, alert fatigue literature), toned down microservice serialization phrasing, distinguished uninstrumented vs `tracemalloc` metrics, and embedded the complete 11-step collaborator onboarding checklist.
  - `README.md`: Qualified explainability motivation and dark-vessel scope exclusions.
  - `docs/03-research/vessel-behavior-ml.md`: Qualified black-box opacity motivation and heuristic kinematic baseline bounds.
  - `docs/01-project/collaboration-plan.md`: Reconciled quality enforcement to pre-commit quality gates.
  - `docs/02-architecture/decisions/`: ADR-001 (toned down serialization phrasing) and ADR-002 (qualified cross-machine floating point reproducibility).
  - `CHANGELOG.md` & `docs/04-development/development-log.md`: Reconciled historical Snappy references to `zstd`.
- **Acceptance Checks:**
  - [x] Evidence Register claim count reconciled to exact 15 claims with verified category breakdown
  - [x] All Parquet compression references aligned to `zstd` matching codebase implementation
  - [x] CI/CD claims qualified to local pre-commit quality gates
  - [x] Overbroad domain and architectural claims qualified with evidence-based nuance
  - [x] Practical 11-step collaborator onboarding checklist verified
  - [x] Zero code modifications under `src/` or `tests/`
  - [x] All 5 automated quality gates pass cleanly

### Milestone W3-01: H3 Candidate Optimization & Completeness Verification
- **Goal:** Install Uber H3 (4.x), implement `H3NeighborhoodProvider` plugging into the shared `run_st_dbscan` engine, and verify 100% eligible-neighbor completeness against the brute-force oracle and BallTree reference across cell boundaries, pentagons, dateline, and high latitudes.
- **Estimated Hours:** 15 Hours
- **Status:** **Completed**
- **Dependencies:** W2-01
- **Deliverables:**
  - `src/aegismar/clustering/h3_neighbors.py`: `H3NeighborhoodProvider` implementing `NeighborhoodProvider` protocol with conservative mathematical $k$-ring coverage (`compute_safe_k_ring`), discrete cell grouping, active candidate cell precomputation (`grid_disk`), `np.searchsorted` temporal candidate slicing, exact spherical Haversine distance verification, and defense-in-depth pentagon fallback.
  - `src/aegismar/clustering/config.py`: Extended `STDBSCANConfig` with `provider`, `h3_resolution` (7, 8, 9; default 8), `h3_k_ring`, and `h3_enable_fallback` with strict validation.
  - `src/aegismar/clustering/types.py`: Added `provider_metrics` to `STDBSCANResult` and `summary_dict()`.
  - `src/aegismar/clustering/st_dbscan.py`: Added `run_h3_st_dbscan` convenience runner and metric collection.
  - `src/aegismar/cli.py`: Extended `cluster` CLI command with `--provider`, `--h3-resolution`, and `--h3-k-ring` options while preserving 100% backward compatibility.
  - Dependency Management: Added `h3>=4.0.0` via `uv` (`h3==4.5.1` locked in `uv.lock`).
  - Unit Test Suite: Authored `tests/unit/test_h3_neighbors.py` covering all 20 required fixture categories (boundaries, thresholds, pentagons, dateline, high latitudes, empty inputs, config errors, filter policies, fallback logging).
  - Empirical Real-Data Parity: Clustered 143,116 real San Pedro Bay observations (`data/processed/lalb_20250101/cleaned_ais.parquet`), achieving 100.00% label and role identity with the BallTree reference (241 clusters, 136,276 core, 934 border, 5,906 noise).
- **Acceptance Checks:**
  - [x] Zero missing neighbors against brute-force oracle ($\text{Recall} = 1.0$) across all synthetic, boundary, and extreme fixtures
  - [x] 100% role and cluster label identity with BallTree reference on synthetic datasets and 143,116 real LA/LB observations
  - [x] H3 resolutions 7, 8, and 9 verified with conservative safe $k$-ring candidate lower bounds
  - [x] Inclusive temporal candidate windowing verified with `np.searchsorted`
  - [x] Defense-in-depth pentagon fallback mechanism verified and instrumented with diagnostic logging
  - [x] CLI `--provider h3` verified with backward compatibility for default BallTree behavior
  - [x] Full quality gates pass: 77 tests pass, 93% total coverage (89% in `h3_neighbors.py`), ruff clean, mypy clean

### Milestone W3-01A: H3 Completeness Audit, Correctness Hardening & Pull Request Preparation
- **Goal:** Audit H3 spherical clearance geometry, eliminate unsupported global analytical claims in favor of Option B (empirical candidate lower bounds with observable, fail-closed fallback), reject unsafe user $k$-ring configurations, harden discrete expansion and pentagon fallback semantics, author 7 new adversarial test fixtures, verify bit-for-bit graph parity on the authentic NOAA San Pedro Bay dataset, and prepare feature branch pull request.
- **Estimated Hours:** 6 Hours
- **Status:** **Completed**
- **Dependencies:** W3-01
- **Deliverables:**
  - Audited clearance geometry: clarified Snyder projection distortion, edge length variance ($\sim 1.4\times$), pentagon face distortion, and formulated Option B support policy in `src/aegismar/clustering/h3_neighbors.py` and `ADR-009`.
  - Rejection of undersized $k$-rings: `H3NeighborhoodProvider` and `STDBSCANConfig` raise `ValueError` when user-configured `k_ring < safe_k`.
  - Fail-closed discrete expansion: `h3.grid_disk` failures mark cells for BallTree fallback with recorded `fallback_reasons` when fallback is enabled; raise `RuntimeError` immediately when fallback is disabled. Silent self-cell downgrades eliminated.
  - Hardened near-pentagon fallback: precomputes whether any cell in `grid_disk(c, k)` is a pentagon (`near_pentagon`); routes near-pentagon cells to BallTree fallback when `fallback_on_pentagons` is enabled, or fails closed with `RuntimeError` if fallback is disabled.
  - Sub-timing instrumentation: separated `cell_mapping_time_seconds`, `candidate_precomputation_time_seconds`, `candidate_retrieval_time_seconds`, `temporal_filtering_time_seconds`, `distance_filtering_time_seconds`, and `fallback_reasons`.
  - 7 new adversarial unit test fixtures in `tests/unit/test_h3_neighbors.py` (fixtures 21–27): undersized $k$-ring rejection, forced `grid_disk` failure fallback, forced failure with disabled fallback, near-pentagon hexagon fallback, sub-meter vertex boundary pairs, multi-region oracle parity (Equator, English Channel, Arctic), and clearance boundary transitions.
  - Verified 100% bit-for-bit CSR graph parity (`indptr` and `indices`) across all 143,116 analyzed observations (13,188,256 edges) of `data/processed/lalb_20250101/cleaned_ais.parquet` against BallTree reference, observing 1.34x graph query speedup and 0 fallbacks.
  - Quality gates: 86 passing tests in 5.71 s, 93% total repository coverage, ruff clean, mypy clean (27 source files).
- **Acceptance Checks:**
  - [x] Clearance mathematics and planar regular hexagon apothem claims audited; Option B formalized
  - [x] Undersized user $k$-ring overrides strictly rejected with `ValueError`
  - [x] Fail-closed `grid_disk` exception handling verified; silent self-cell downgrades eliminated
  - [x] Near-pentagon fallback logic verified on regular hexagons adjacent to pentagons
  - [x] Performance instrumentation audited and sub-timings separated
  - [x] 7 adversarial test fixtures pass (fixtures 21–27; 34 tests in module, 86 in repository)
  - [x] 100% bit-for-bit CSR graph parity verified on 143,116 authentic NOAA AIS observations (13,188,256 edges)
  - [x] All quality gates (pytest, ruff, mypy) pass cleanly in local workspace

### Milestone W3-01B: H3 Correctness Contract Finalization
- **Goal:** Finalize the empirical correctness contract for the H3 provider, replace unsupported ring extrapolations and approximations with fail-closed rejection or fallback, require explicit opt-in for experimental modes, provide an explicit dataset-scoped parity verification command, and update research documentation.
- **Estimated Hours:** 4 Hours
- **Status:** **Completed**
- **Dependencies:** W3-01A
- **Deliverables:**
  - Audited correctness contract: qualified module docstrings, functions, and documentation to reflect empirical calibration on resolutions 7, 8, 9 rather than global mathematical theorems.
  - Fail-closed handling for unsupported configurations: `compute_safe_k_ring` and `H3NeighborhoodProvider` strictly reject uncalibrated resolutions or radii exceeding empirical tables with `ValueError` (when fallback disabled) or route to BallTree fallback (when enabled).
  - Explicit experimental opt-in: `allow_uncalibrated=True` / `h3_allow_uncalibrated` permits approximate estimation, logging clear warnings and tagging metadata as `experimental_uncalibrated`.
  - Precise fallback categorization: documented and tested the 3 actual runtime triggers (API failures, pentagons/near-pentagons, unsupported configurations), explicitly removing claims of automated omitted-candidate detection.
  - Dataset-scoped parity verification: implemented `verify_dataset_h3_balltree_parity` and added `aegismar verify-parity` CLI subcommand with dataset SHA-256 verification and detailed parity reporting.
  - Targeted unit test suite (`tests/unit/test_h3_neighbors.py`, `tests/unit/test_cli.py`): added fixtures 28–32 covering unsupported resolutions, radii limits, experimental opt-in, contract metadata, and CLI parity verification (total 92 tests in repository, 100% pass).
  - Rerun full-dataset verification on canonical San Pedro Bay dataset (`cleaned_ais.parquet`, SHA-256: `4a7ca719dc2a3d9959cc4166edff773ca09156d8d914e54d0ab5f851ece5e88b`): confirmed 100% bit-for-bit parity across all 143,116 analyzed observations (13,188,256 edges, 0 fallbacks).
- **Acceptance Checks:**
  - [x] Uncalibrated resolutions and excessive radii strictly rejected or routed to BallTree fallback
  - [x] Experimental opt-in (`allow_uncalibrated=True`) correctly tracked and logged
  - [x] Fallback triggers documented and separated from omission detection
  - [x] CLI `verify-parity` command operational and validated on historical dataset
  - [x] All 92 automated tests pass; repository code coverage reaches 94%
  - [x] All documentation updated to eliminate unproven global theorems

### Milestone W3-02: Comparative H1 Benchmarking (BallTree vs. H3)
- **Goal:** Formally benchmark runtime (build, query, pruning, clustering), peak memory, neighbor recall/precision, and Adjusted Rand Index between `BallTreeNeighborhoodProvider` and `H3NeighborhoodProvider` across dataset scales (10k, 50k, 100k, full LA/LB). *(Not yet started.)*
- **Estimated Hours:** 10 Hours
- **Status:** Planned
- **Dependencies:** W3-01
- **Planned Deliverables:**
  - Automated H1 benchmark harness writing structured experiment JSON records under `experiments/outputs/`
  - Empirical comparative evaluation tables for thesis documentation
- **Acceptance Checks:**
  - Statistically rigorous comparison of BallTree vs. H3 across repeated deterministic trials with zero fabricated numbers

### Milestone W4-01: Stay-Point Extraction & Berth Polygon Exclusion
- **Goal:** Detect vessel dwell periods and exclude terminal berths using spatial polygon clipping.
- **Estimated Hours:** 15 Hours
- **Status:** Planned
- **Dependencies:** W3-02
- **Planned Deliverables:**
  - `src/aegismar/staypoint/extractor.py`
  - `src/aegismar/staypoint/berth.py` (GeoJSON berth loader and point-in-polygon filter)
- **Acceptance Checks:**
  - Berthed vessels are 100% excluded from anchorage candidate sets

### Milestone W4-02: Anchorage Dwell Metrics & Utilization Analytics
- **Goal:** Aggregate stay-points into geographic anchorage basins and compute unique-vessel dwell statistics.
- **Estimated Hours:** 10 Hours
- **Status:** Planned
- **Dependencies:** W4-01
- **Planned Deliverables:**
  - Anchorage polygon generation and utilization metrics engine
  - Metrics export to GeoJSON and DuckDB
- **Acceptance Checks:**
  - Anchorage dwell hours and vessel counts are accurately aggregated by `MMSI`

### Milestone W5-01: DuckDB In-Process Analytics & Contract Integration
- **Goal:** Integrate in-process DuckDB analytical query layer over Parquet partitions, generate precomputed GeoJSON layers, and establish contract ingestion validation for the provisional `vessel_anomaly_v1` GeoJSON schema.
- **Estimated Hours:** 15 Hours
- **Status:** Planned
- **Dependencies:** W3-02, W4-02
- **Planned Deliverables:**
  - `src/aegismar/storage/duckdb_engine.py` (DuckDB connection manager, Parquet view registration, analytical aggregation queries)
  - Precomputed GeoJSON export pipelines for clusters and anchorages
  - Contract validator and loader for `vessel_anomaly_v1` GeoJSON FeatureCollections
- **Acceptance Checks:**
  - Analytical queries execute in $< 50\text{ ms}$ over 100k precomputed records
  - Storage layer ingests spatial layers and validates `vessel_anomaly_v1` contract payloads seamlessly

### Milestone W6-01: Read-Only FastAPI Service Implementation
- **Goal:** Implement stateless, read-only HTTP API serving precomputed analytical layers from DuckDB.
- **Estimated Hours:** 10 Hours
- **Status:** Planned
- **Dependencies:** W5-01
- **Planned Deliverables:**
  - `src/aegismar/api/main.py`
  - Endpoints for `/health`, `/api/v1/clusters`, `/api/v1/anchorages`, `/api/v1/anomalies`
- **Acceptance Checks:**
  - API returns valid GeoJSON FeatureCollections; zero state mutation endpoints exist

### Milestone W7-01: Interactive Geospatial Web Map Dashboard
- **Goal:** Build the browser-based map interface for geospatial layer inspection and anomaly triage.
- **Estimated Hours:** 15 Hours
- **Status:** Planned
- **Dependencies:** W6-01
- **Planned Deliverables:**
  - `src/aegismar/ui/` (HTML/JS Leaflet dashboard)
  - Interactive layer toggle (clusters, anchorages, vessel tracks, anomaly markers)
  - Anomaly incident inspection modal with factor breakdown
- **Acceptance Checks:**
  - Map renders 100k+ points smoothly using pre-filtered GeoJSON layers; incident review modal displays factor decompositions

### Milestone W7-02: End-to-End Pipeline Integration & Verification
- **Goal:** Verify seamless data flow from raw AIS CSV through Parquet, clustering, stay-points, DuckDB, FastAPI, and UI dashboard.
- **Estimated Hours:** 10 Hours
- **Status:** Planned
- **Dependencies:** W7-01
- **Planned Deliverables:**
  - End-to-end integration test suite (`tests/integration/test_pipeline.py`)
  - Verification checklist and offline static map artifact validation
- **Acceptance Checks:**
  - Pipeline executes end-to-end deterministically; UI renders correctly from local API

### Milestone W8-01: Automated Benchmark Execution (10k, 50k, 100k)
- **Goal:** Execute automated multi-trial performance benchmarks evaluating Hypothesis H1 across standardized dataset scales.
- **Estimated Hours:** 15 Hours
- **Status:** Planned
- **Dependencies:** W7-02
- **Planned Deliverables:**
  - Multi-trial automated benchmark harness emitting structured JSON records
  - Empirical tables and charts comparing BallTree vs. H3 runtime, memory, and indexing overhead
- **Acceptance Checks:**
  - 10 deterministic trials executed per scale; p-values and confidence intervals recorded; zero fabricated numbers

### Milestone W8-02: Reproducibility Package, Final Audit & Thesis Report
- **Goal:** Package the complete repository for one-command independent verification, conduct code audit, and finalize thesis documentation.
- **Estimated Hours:** 10 Hours
- **Status:** Planned
- **Dependencies:** W8-01
- **Planned Deliverables:**
  - One-command reproduction script
  - Final research thesis and empirical evaluation report
  - Clean working tree verification and GitHub release tag
- **Acceptance Checks:**
  - External reviewer can reproduce all research results from scratch with `uv sync --locked`

---

## 4. Milestone Detail Specifications — Track B (Vessel Behavior ML & Anomaly Detection)

**Proposed Lead:** Kishakya *(participation pending review)*  
**Governance:** Track B operates on an independent parallel schedule with flexible pacing. Milestones advance based on Kishakya's availability and research goals without rigid week-number constraints.

### Milestone ML-01: Domain Literature & AIS Telemetry Review
- **Goal:** Review maritime anomaly detection literature and existing `docs/03-research/vessel-behavior-ml.md`. Profile canonical AIS telemetry fields (`cleaned_ais.parquet`) and understand sensor sentinels/limits.
- **Estimated Hours:** 10 Hours
- **Status:** Planned
- **Dependencies:** Cleaned Parquet available (`data/processed/lalb_20250101/cleaned_ais.parquet`)
- **Planned Deliverables:**
  - Literature review notes and telemetry field profiling summary
  - Confirmed kinematic feature candidate list
- **Acceptance Checks:**
  - Telemetry limits, sentinels, and reception gap realities clearly documented

### Milestone ML-02: Vessel Trajectory Kinematic Feature Specification
- **Goal:** Formulate mathematical definitions for kinematic acceleration, angular course rates, drift angles, and transponder reporting intervals. Define windowing parameters (sliding time window vs. fixed-ping strides).
- **Estimated Hours:** 15 Hours
- **Status:** Planned
- **Dependencies:** ML-01
- **Planned Deliverables:**
  - Trajectory feature extraction specification document
  - Mathematical formulation of windowing and kinematic delta calculations
- **Acceptance Checks:**
  - Windowing parameters and feature formulas physically grounded in commercial vessel dynamics

### Milestone ML-03: Baseline Models & Evaluation Protocol Freezing
- **Goal:** Formalize rule-based heuristic scoring thresholds and Isolation Forest architecture. Specify vessel-disjoint (70/30 MMSI) and chronological holdout splits. Parameterize synthetic perturbation types (speed jumps, crabbing, coverage dropouts).
- **Estimated Hours:** 15 Hours
- **Status:** Planned
- **Dependencies:** ML-02
- **Planned Deliverables:**
  - Evaluation protocol document and perturbation configuration schema
  - Baseline model definitions and hyperparameter search space
- **Acceptance Checks:**
  - Data leakage strictly prevented via vessel-disjoint splitting; perturbations bounded by maritime physics

### Milestone ML-04: Feature Engineering Module & Baseline Experiments
- **Goal:** Implement `src/aegismar/anomaly/features.py` with comprehensive unit tests (`tests/unit/test_anomaly.py`). Extract feature representations across test partitions and log reproducible experiment artifacts.
- **Estimated Hours:** 20 Hours
- **Status:** Planned
- **Dependencies:** ML-03
- **Planned Deliverables:**
  - `src/aegismar/anomaly/features.py` and `tests/unit/test_anomaly.py`
  - Baseline feature extraction experiment logged under `experiments/outputs/anomaly/`
- **Acceptance Checks:**
  - Unit tests pass with $\ge 90\%$ code coverage; feature vectors conform to expected dimensions

### Milestone ML-05: Anomaly Model Evaluation & `vessel_anomaly_v1` Export
- **Goal:** Implement rule-based scorer and Isolation Forest model. Evaluate PR-AUC, precision, recall, and false alarm rates against density noise baselines. Export explainable incident GeoJSON adhering to `vessel_anomaly_v1`.
- **Estimated Hours:** 20 Hours
- **Status:** Planned
- **Dependencies:** ML-04
- **Planned Deliverables:**
  - `src/aegismar/anomaly/rules.py` and `src/aegismar/anomaly/models.py`
  - `src/aegismar/anomaly/evaluation.py`
  - Exported `vessel_anomaly_v1` GeoJSON artifacts ready for DuckDB ingestion
- **Acceptance Checks:**
  - Rule-based and ML models evaluated on held-out splits; incident outputs validate against `vessel_anomaly_v1` schema; factor attributions provide physical explanations for 100% of alerts
  - Smooth client-side rendering without build steps; clicks on anomaly markers show full physical justification

### Milestone W7-02: End-to-End Pipeline Integration & Verification
- **Goal:** Run end-to-end integration tests connecting raw sample ingestion to web map display.
- **Estimated Hours:** 10 Hours
- **Status:** Planned
- **Dependencies:** W7-01
- **Planned Deliverables:**
  - End-to-end integration test suite
  - CLI runner orchestrating full pipeline
- **Acceptance Checks:**
  - Single CLI command runs sample data through ingestion, clustering, anomaly detection, and starts dashboard

### Milestone W8-01: Automated Benchmark Execution (10k, 50k, 100k)
- **Goal:** Execute scientific benchmark suite, capturing runtimes, memory, recall, and hypothesis tests.
- **Estimated Hours:** 15 Hours
- **Status:** Planned
- **Dependencies:** W7-02
- **Planned Deliverables:**
  - Benchmark runner script producing structured JSON outputs
  - Statistical significance tests for Hypotheses H1 and H2
- **Acceptance Checks:**
  - 10 repeated benchmark runs completed across all scales without manual intervention

### Milestone W8-02: Reproducibility Package, Final Audit & Thesis Report
- **Goal:** Complete final codebase freeze, reproducibility verification guide, and academic thesis documentation.
- **Estimated Hours:** 10 Hours
- **Status:** Planned
- **Dependencies:** W8-01
- **Planned Deliverables:**
  - Final research thesis document and reproducibility artifacts
  - Comprehensive codebase audit ensuring zero unverified claims
- **Acceptance Checks:**
  - Clean execution of reproducibility instructions on a fresh environment

