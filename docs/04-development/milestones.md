# Milestone Schedule & Tracking

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**

**Document Version:** 2.1  
**Total Development Baseline:** 200 Hours across 8 Weeks (25 Hours/Week)  
**Developer:** Solo Undergraduate AI Engineer  
**Status Key:** `Planned` | `In Progress` | `Completed` | `Deferred`  

---

## Milestone Tracking Board

| Milestone ID | Week | Target Deliverable | Est. Hours | Status | Dependencies |
|---|---|---|---|---|---|
| **W1-01** | Week 1 | Repository Initialization & Documentation Foundation | 10 h | **Completed** | None |
| **W1-02A** | Week 1 | NOAA AIS Dataset Selection & Schema Investigation | 5 h | **Completed** | W1-01 |
| **W1-02B** | Week 1 | Production AIS Ingestion, Sentinel Handling & Parquet Storage | 10 h | **Completed** | W1-02A |
| **W2-01** | Week 2 | Ingestion Corrections, BallTree Reference ST-DBSCAN & Brute-Force Oracle | 15 h | **Completed** | W1-02B |
| **DOC-01** | Week 2+ | Evidence-Backed Research & Engineering Documentation | 10 h | **Completed** | W2-01 |
| **W3-01** | Week 3 | H3 Candidate Optimization & Completeness Verification | 15 h | Planned | W2-01 |
| **W3-02** | Week 3 | Comparative H1 Benchmarking (BallTree vs. H3) | 10 h | Planned | W3-01 |
| **W4-01** | Week 4 | Stay-Point Extraction & Berth Polygon Exclusion | 15 h | Planned | W3-02 |
| **W4-02** | Week 4 | Anchorage Dwell Metrics & Utilization Analytics | 10 h | Planned | W4-01 |
| **W5-01** | Week 5 | Kinematic Trajectory Anomaly Detector (Rule-based) | 15 h | Planned | W1-02, W4-01 |
| **W5-02** | Week 5 | Anomaly Evaluation & *(Conditional)* Isolation Forest | 10 h | Planned | W5-01 |
| **W6-01** | Week 6 | DuckDB In-Process Analytics & GeoJSON Generation | 15 h | Planned | W3-02, W4-02, W5-01 |
| **W6-02** | Week 6 | Read-Only FastAPI Service Implementation | 10 h | Planned | W6-01 |
| **W7-01** | Week 7 | Interactive Geospatial Web Map Dashboard | 15 h | Planned | W6-02 |
| **W7-02** | Week 7 | End-to-End Pipeline Integration & Verification | 10 h | Planned | W7-01 |
| **W8-01** | Week 8 | Automated Benchmark Execution (10k, 50k, 100k) | 15 h | Planned | W7-02 |
| **W8-02** | Week 8 | Reproducibility Package, Final Audit & Thesis Report | 10 h | Planned | W8-01 |

---

## Milestone Detail Specifications

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

### Milestone W3-01: H3 Candidate Optimization & Completeness Verification
- **Goal:** Install Uber H3 (4.x), implement `H3NeighborhoodProvider` plugging into the shared `run_st_dbscan` engine, and verify 100% eligible-neighbor completeness against the brute-force oracle and BallTree reference across cell boundaries, pentagons, dateline, and high latitudes. *(Not yet started.)*
- **Estimated Hours:** 15 Hours
- **Status:** Planned
- **Dependencies:** W2-01
- **Planned Deliverables:**
  - `src/aegismar/clustering/h3_neighbors.py` (`H3NeighborhoodProvider` implementing `NeighborhoodProvider`)
  - Exact geodesic and temporal pruning over $k$-ring cell candidates
  - Completeness tests targeting H3 cell edges ($\delta \le 10\text{ m}$) and pentagonal distortion zones
- **Acceptance Checks:**
  - Zero missing neighbors against brute-force oracle ($\text{Recall} = 1.0$) and 100% label identity with BallTree reference

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

### Milestone W5-01: Kinematic Trajectory Anomaly Detector (Rule-Based)
- **Goal:** Implement multi-factor kinematic anomaly detection on vessel trajectories.
- **Estimated Hours:** 15 Hours
- **Status:** Planned
- **Dependencies:** W1-02, W4-01
- **Planned Deliverables:**
  - `src/aegismar/anomaly/kinematics.py`
  - `src/aegismar/anomaly/rules.py`
  - Explainable JSON factor payload generator
- **Acceptance Checks:**
  - Anomaly scorer flags speed discontinuities, unpowered drift, and transponder dropouts with explicit factor explanations

### Milestone W5-02: Anomaly Evaluation & (Conditional) Isolation Forest
- **Goal:** Benchmark rule-based anomaly detector against synthetic perturbations and optional Isolation Forest baseline.
- **Estimated Hours:** 10 Hours
- **Status:** Planned
- **Dependencies:** W5-01
- **Planned Deliverables:**
  - Anomaly benchmark harness with synthetic perturbation injection
  - *(Conditional)* `src/aegismar/anomaly/isolation_forest.py`
- **Acceptance Checks:**
  - Rule-based detector achieves target $F_1$ improvement over density noise baseline

### Milestone W6-01: DuckDB In-Process Analytics & GeoJSON Generation
- **Goal:** Integrate in-process DuckDB analytical query layer over Parquet partitions.
- **Estimated Hours:** 15 Hours
- **Status:** Planned
- **Dependencies:** W3-02, W4-02, W5-01
- **Planned Deliverables:**
  - `src/aegismar/storage/duckdb_engine.py`
  - Precomputed GeoJSON export pipelines
- **Acceptance Checks:**
  - Analytical queries execute in $< 50\text{ ms}$ over 100k precomputed records

### Milestone W6-02: Read-Only FastAPI Service Implementation
- **Goal:** Implement stateless, read-only HTTP API serving precomputed analytical layers.
- **Estimated Hours:** 10 Hours
- **Status:** Planned
- **Dependencies:** W6-01
- **Planned Deliverables:**
  - `src/aegismar/api/main.py`
  - Endpoints for `/health`, `/clusters`, `/anchorages`, `/anomalies`
- **Acceptance Checks:**
  - API returns valid GeoJSON FeatureCollections; zero state mutation endpoints exist

### Milestone W7-01: Interactive Geospatial Web Map Dashboard
- **Goal:** Build the browser-based map interface for geospatial layer inspection and anomaly triage.
- **Estimated Hours:** 15 Hours
- **Status:** Planned
- **Dependencies:** W6-02
- **Planned Deliverables:**
  - `src/aegismar/ui/` (HTML/JS Leaflet dashboard)
  - Interactive layer toggle (clusters, anchorages, vessel tracks, anomaly markers)
  - Anomaly incident inspection modal with factor breakdown
- **Acceptance Checks:**
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

