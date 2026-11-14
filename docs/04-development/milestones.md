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
| **W1-02** | Week 1 | AIS Ingestion, Sentinel Handling & Parquet Storage | 15 h | Planned | W1-01 |
| **W2-01** | Week 2 | Geodesic Metric Space & BallTree Baseline | 12 h | Planned | W1-02 |
| **W2-02** | Week 2 | H3 Discrete Hex Grid Candidate Engine & Oracle | 13 h | Planned | W2-01 |
| **W3-01** | Week 3 | Spatiotemporal ST-DBSCAN Clustering Core | 15 h | Planned | W2-02 |
| **W3-02** | Week 3 | Clustering Correctness & Recall Evaluation | 10 h | Planned | W3-01 |
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

### Milestone W1-02: AIS Ingestion, Sentinel Handling & Parquet Storage
- **Goal:** Build the raw AIS parser, explicit sentinel masker, coordinate/speed validator, and columnar Parquet storage writer.
- **Estimated Hours:** 15 Hours
- **Status:** Planned
- **Dependencies:** W1-01
- **Planned Deliverables:**
  - `src/aegismar/common/constants.py` & `types.py`
  - `src/aegismar/ingestion/cleaner.py` & `storage.py`
  - Unit tests covering sentinel values, coordinate boundaries, and Parquet round-trips
- **Acceptance Checks:**
  - Sentinels (`SOG 102.3`, `HDG 511`, `Status 15`) are masked deterministically
  - Teleportation pings ($v_{\text{implied}} > 50\text{ kt}$) are cleanly flagged
  - Parquet output preserves all valid records without data loss

### Milestone W2-01: Geodesic Metric Space & BallTree Baseline
- **Goal:** Implement exact geodesic distance calculations and the reference BallTree spatial nearest-neighbor search.
- **Estimated Hours:** 12 Hours
- **Status:** Planned
- **Dependencies:** W1-02
- **Planned Deliverables:**
  - `src/aegismar/spatial/haversine.py` (vectorized geodesic formulas)
  - `src/aegismar/spatial/balltree.py` (`scikit-learn` BallTree wrapper)
  - Unit tests on known geographical landmark distances
- **Acceptance Checks:**
  - Calculated distances match known geodesic benchmarks within $0.01\%$ relative error

### Milestone W2-02: H3 Discrete Hex Grid Candidate Engine & Oracle
- **Goal:** Implement H3 grid cell indexing, $k$-ring candidate generation, and the brute-force spatial test oracle.
- **Estimated Hours:** 13 Hours
- **Status:** Planned
- **Dependencies:** W2-01
- **Planned Deliverables:**
  - `src/aegismar/spatial/h3_grid.py` (H3 4.x API candidate generator)
  - `src/aegismar/spatial/oracle.py` (Brute-force $O(N^2)$ geodesic test oracle)
  - Oracle comparison tests verifying zero false negatives
- **Acceptance Checks:**
  - Spatial neighbor candidate sets achieve $\ge 99.9\%$ recall against the brute-force oracle across test datasets

### Milestone W3-01: Spatiotemporal ST-DBSCAN Clustering Core
- **Goal:** Implement spatiotemporal clustering with both BallTree baseline and H3 candidate acceleration.
- **Estimated Hours:** 15 Hours
- **Status:** Planned
- **Dependencies:** W2-02
- **Planned Deliverables:**
  - `src/aegismar/clustering/st_dbscan.py`
  - Interchangeable spatial index interface
  - Deterministic core, border, and noise labeling logic
- **Acceptance Checks:**
  - Cluster assignments are identical across repeated runs on sorted input

### Milestone W3-02: Clustering Correctness & Recall Evaluation
- **Goal:** Formally benchmark clustering correctness, neighbor recall, and runtime between BallTree and H3 engines.
- **Estimated Hours:** 10 Hours
- **Status:** Planned
- **Dependencies:** W3-01
- **Planned Deliverables:**
  - Benchmark script comparing runtime, memory, and Rand Index
  - Empirical evaluation table for thesis documentation
- **Acceptance Checks:**
  - H3 engine achieves statistically significant speedup at 100k pings with zero neighbor omissions

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

