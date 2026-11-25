# Changelog

All notable changes to Project AegisMar will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> [!NOTE]
> Project AegisMar is currently in pre-alpha research and MVP development. Documentation versioning adheres to the v2.1 solo MVP baseline, while package implementation starts at `0.1.0.dev1`.

## [Unreleased]

### Documentation - Track B Documentation Sync after ML-01–ML-03 (2026-11-24)
- **README / START-HERE / Roadmap / Milestones**: Track B statuses updated (ML-01 in progress: data profiling completed, literature review pending; ML-02 and ML-03 completed; ML-04 next). Current-state test figures updated to 92 tests / 94% coverage. Stale "H3 not yet implemented" statements updated. ML-02/ML-03 linked from the documentation indexes.
- **Milestones**: Removed a stale duplicate copy of the W7-02, W8-01 and W8-02 specifications that sat after the Track B section, including a misplaced dashboard acceptance bullet under ML-05. The current versions in the Track A section are unchanged.
- **ML Onboarding Guide (v1.2)**: Corrected the Haversine import example (`haversine_distance_meters`); documented the on-disk Parquet row order `(mmsi, timestamp_utc, source_row)`; replaced the undocumented "decompress and slice" step with `scripts/slice_noaa_bbox.py` plus verified expected results; added the held-out test days, feed-wide outage and reporting-cadence limitations.
- **ML Proposal (v1.2)**: Added notes marking the parts superseded by ML-02 (low-speed guard, features) and ML-03 (rule thresholds, within-day split, perturbations). Corrected the input-contract row-order statement.
- **Evaluation Protocol §3 / Collaboration Plan §4.1**: Added a pointer to ML-03 as the authoritative Track B protocol; corrected the input-contract row-order statement.
- **Evidence Register**: CLM-ANO-01 now references the frozen ML-03 decision rules; the reproduction step no longer hard-codes 52 tests.
- **Track B leadership confirmed**: Kishakya reviewed and accepted the collaboration plan; "Proposed / pending review" qualifiers removed across README, CONTRIBUTING, the PR template, vision, scope, roadmap, collaboration plan, system architecture, research plan, ML proposal, evidence register, milestones, START-HERE and the onboarding guide. ADR-010 is unchanged as a historical record of its decision date.

### Added - Track B Milestones ML-01 (partial), ML-02, ML-03 (2026-11-23)
- **ML-01 data profiling** (`experiments/anomaly/ml01_profile_dataset.py`, PR #2): reproducible profile of the cleaned dataset (reporting cadence, SOG distribution, field availability, segmentation, kinematic ranges, feed-wide silences), recording the git commit and input SHA-256. Literature review still pending.
- **ML-02 feature specification v1.0** (`docs/03-research/ml-02-feature-spec.md`, PR #3) and supporting `experiments/anomaly/ml02_drift_breakdown.py`.
- **ML-03 evaluation protocol v1.0, frozen** (`docs/03-research/ml-03-evaluation-protocol.md`, PR #4): held-out test days 2025-01-14 and 2025-01-22, stratified vessel-disjoint split, perturbation framework, baselines, metrics and statistical decision rules.
- **NOAA slicer** (`scripts/slice_noaa_bbox.py`): stream-decompresses a NOAA `.csv.zst` daily extract with pyarrow (no new dependency) and slices a bounding box byte-for-byte. Reproduces the documented 2025-01-01 sample exactly (143,156 rows, 362 vessels, SHA-256 `42e4f766…`).

### Fixed & Hardened - Milestone W3-01B: H3 Correctness Contract Finalization (2026-11-23)
- **H3 Correctness Contract Finalization**:
  - Removed all statements claiming unconditional global mathematical completeness for H3 discrete hexagonal candidate generation.
  - Formalized two-tier empirical support contract: calibrated regional indexing on resolutions 7, 8, 9 within documented clearance tables vs fail-closed rejection or BallTree fallback for uncalibrated configurations.
- **Fail-Closed Unsupported Configuration Handling**:
  - Replaced unproven ring extrapolations and approximations in `compute_safe_k_ring` with strict fail-closed validation: uncalibrated resolutions or radii exceeding empirical clearance tables raise `ValueError` unless `allow_uncalibrated=True` is explicitly specified.
  - Configured `H3NeighborhoodProvider` to route unsupported configurations cleanly to `BallTreeNeighborhoodProvider` when fallback is enabled, or fail closed with `ValueError` when fallback is disabled.
  - Added explicit experimental opt-in via `allow_uncalibrated=True` (and `STDBSCANConfig(h3_allow_uncalibrated=True)`), logging clear warnings and marking execution metadata as `completeness_contract = "experimental_uncalibrated"`.
- **Dataset-Scoped Parity Verification Command (`aegismar verify-parity`)**:
  - Implemented `verify_dataset_h3_balltree_parity` and the `aegismar verify-parity` CLI subcommand with dataset SHA-256 verification and comprehensive bit-for-bit parity reporting.
  - Validated full CSR graph parity (`indptr`, `indices`) and clustering parity across all 143,116 observations of `cleaned_ais.parquet` (SHA-256: `4a7ca719dc2a3d9959cc4166edff773ca09156d8d914e54d0ab5f851ece5e88b`) with 0 fallbacks and identical cluster accounting.
- **Targeted Test Suite Expansion**:
  - Added test fixtures 28–32 in `tests/unit/test_h3_neighbors.py` covering unsupported resolutions, radii limits, experimental opt-in, contract metadata, and parity verification.
  - Added `test_cli_verify_parity_command` in `tests/unit/test_cli.py`.
  - Expanded automated test suite to 92 passing tests at 94% repository coverage (98% in `h3_neighbors.py`).


### Fixed & Hardened - Milestone W3-01A: H3 Completeness Audit & Correctness Hardening (2026-11-23)
- **H3 Spherical Clearance Mathematics Audit**:
  - Audited planar regular hexagon apothem formulas ($k \cdot 2 r_{\text{inscribed}} = k \sqrt{3} s$) against spherical Snyder equal-area icosahedron projections; clarified edge length variance ($\sim 1.4\times$) and 12 pentagonal face distortions.
  - Eliminated unsupported global analytical theorems in favor of **Option B**: experimental H3 candidate acceleration supported by an observable, fail-closed reference fallback policy.
  - Reconciled documentation in `src/aegismar/clustering/h3_neighbors.py`, `docs/02-architecture/decisions/ADR-009-planned-h3-candidate-acceleration.md`, `docs/03-research/evaluation-protocol.md`, and `docs/03-research/evidence-register.md`.
- **Fail-Closed Safety & Validation Hardening**:
  - Configured `H3NeighborhoodProvider` and `STDBSCANConfig` to strictly reject undersized $k$-rings (`k_ring < safe_k`) with `ValueError`, preventing silent candidate omissions.
  - Hardened discrete expansion exception handling: `h3.grid_disk` failures mark cells for BallTree fallback when enabled; raise `RuntimeError` immediately when fallback is disabled. Silent self-cell downgrades eliminated.
  - Hardened near-pentagon fallback: precomputes whether any cell in `grid_disk(c, k)` is a pentagon (`near_pentagon`); routes near-pentagon hexagons to BallTree fallback when `fallback_on_pentagons` is enabled, or fails closed with `RuntimeError` if fallback is disabled.
  - Extended `STDBSCANConfig` with `h3_fallback_on_pentagons: bool = False` with strict boolean validation.
  - Granular diagnostic instrumentation: separated `cell_mapping_time_seconds`, `candidate_precomputation_time_seconds`, `candidate_retrieval_time_seconds`, `temporal_filtering_time_seconds`, `distance_filtering_time_seconds`, and `fallback_reasons`.
- **Adversarial Unit Test Suite**:
  - Added 7 new adversarial test fixtures (fixtures 21–27) to `tests/unit/test_h3_neighbors.py` covering undersized $k$-ring rejection, forced `grid_disk` failures, disabled fallback exceptions, near-pentagon hexagon fallback, sub-meter cell vertex point pairs, multi-region oracle parity (Equator, English Channel, Arctic), and clearance boundary transitions.
  - Test suite expanded to 86 tests passing at 93% total repository code coverage.
- **Empirical Parity on Authentic NOAA AIS Data**:
  - Evaluated full CSR graph parity between `BallTreeNeighborhoodProvider` and `H3NeighborhoodProvider` on all 143,116 analyzed observations (13,188,256 edges) of `data/processed/lalb_20250101/cleaned_ais.parquet`:
    - Bit-for-bit identical CSR graphs: `indptr` (100.0000% degree identity) and `indices` (100.0000% neighbor identity across all 13,188,256 edges).
    - Achieved 1.34x graph query speedup (31.28 s vs 41.98 s) with 0 fallbacks.


### Documentation & Governance - Dual-Track Roadmap & Milestone Harmonization (2026-11-23)
- **Eliminated Week 5 Anomaly Detection Ambiguity**:
  - Reconciled milestone tracking across `README.md`, `docs/01-project/roadmap.md`, `docs/04-development/milestones.md`, `docs/01-project/scope.md`, and `docs/START-HERE.md`.
  - Reassigned Track A Week 5 to **Platform Analytical Storage & Contract Integration** (`W5-01`), focusing on in-process DuckDB query layer integration and validation of the provisional `vessel_anomaly_v1` GeoJSON contract.
  - Fully transitioned Behavioral Trajectory Anomaly Detection to **Track B (Lead: Kishakya)**, governed by dedicated milestones `ML-01` through `ML-05` on an independent, flexible schedule without artificial week-number deadlines.
  - Decoupled `W6-01` (FastAPI serving) and DuckDB storage from blocking on ML model completion.
  - Updated the official Milestone Tracking Board in `milestones.md` into distinct Track A and Track B tables with explicit capacities, deliverables, and acceptance criteria.

### Added - Milestone W3-01: H3 Spatial Indexing, Neighborhood Completeness & Correctness Verification (2026-11-22)
- **H3 Discrete Hexagonal Neighborhood Provider**:
  - Implemented `H3NeighborhoodProvider` in `src/aegismar/clustering/h3_neighbors.py` conforming to the `NeighborhoodProvider` protocol.
  - Implemented `compute_safe_k_ring(resolution, eps_spatial_m)` enforcing geometric candidate lower bounds ($\ge 988\text{ m}$ for Res 7, $\ge 395\text{ m}$ for Res 8, $\ge 371\text{ m}$ for Res 9 with $k=2$) guaranteeing zero missing spatial neighbors across cell boundaries.
  - Implemented inclusive temporal candidate slicing per cell using `np.searchsorted` in $O(\log M_{\text{cell}})$, eliminating temporal edge effects.
  - Pre-filtered active candidate cells present in the dataset using `h3.grid_disk(c, k)`.
  - Added defense-in-depth fallback mechanism to `BallTreeNeighborhoodProvider` for pentagonal cells and query exceptions.
- **Engine & CLI Integration**:
  - Extended `STDBSCANConfig` with `provider` (`balltree_haversine` vs `h3_haversine`), `h3_resolution` (7, 8, 9; default 8), `h3_k_ring`, and `h3_enable_fallback`.
  - Added `provider_metrics` tracking to `STDBSCANResult` and `summary_dict()`.
  - Implemented `run_h3_st_dbscan(...)` convenience runner in `src/aegismar/clustering/st_dbscan.py`.
  - Extended CLI `cluster` subcommand with `--provider`, `--h3-resolution`, and `--h3-k-ring` options with 100% backward compatibility.
  - Pinned `h3>=4.0.0` in `pyproject.toml` and locked `h3==4.5.1` in `uv.lock`.
- **Automated Verification & Real Data Parity**:
  - Authored comprehensive test suite `tests/unit/test_h3_neighbors.py` with 20 fixture categories (same-cell, adjacent, multi-ring, cell boundaries $\delta \le 10\text{ m}$, exact thresholds, dense/sparse cells, pentagons, high latitudes, antimeridian crossing, randomized oracle parity, input permutation invariance, determinism, empty inputs, invalid configs, quality filters, and fallback logging).
  - Validated 100.00% exact parity (143,116 / 143,116 label matches, 143,116 / 143,116 role matches) on the authentic NOAA San Pedro Bay dataset (241 clusters, 136,276 core, 934 border, 5,906 noise; 0 fallbacks).
  - Raised automated test count to 77 tests passing at 93% total repository code coverage.

### Documentation & Quality - Milestone DOC-01A: Research Documentation Accuracy & Collaborator Readiness (2026-11-22)
- **Evidence Register Claim Count Reconciliation**:
  - Audited `docs/03-research/evidence-register.md` to reconcile claim accounting, formally indexing all 15 claims across the evidentiary hierarchy (10 Tested by Automated Checks, 2 Experimentally Observed, 1 Reported by Development Assistant, 2 Planned or Hypothesized).
  - Qualified `CLM-CLU-02` (runtime determinism within tested Python environment) and `CLM-CLU-05` (uninstrumented dev log timing vs instrumented summary JSON).
- **Parquet Compression Alignment**:
  - Verified codebase implementation defaults to `zstd` compression across `src/aegismar/ingestion/storage.py` and `src/aegismar/clustering/export.py`, and verified on-disk Parquet files are `ZSTD`-compressed. Corrected outdated mentions of Snappy in `docs/START-HERE.md`, `CHANGELOG.md`, and `development-log.md`.
- **Pre-Commit Quality Gate vs. CI Clarification**:
  - Replaced claims of "passing in CI/CD" with "passing in local test suite verification" since GitHub Actions workflows are not yet configured.
- **Evidence-Based Language Qualification**:
  - Qualified claims regarding cross-machine floating-point reproducibility, AIS reception gaps versus clandestine transponder deactivation, potential navigational hazards requiring operator review, and microservice serialization overhead.
- **Comprehensive Onboarding Workflow**:
  - Embedded the verified 11-step collaborator onboarding checklist into `docs/START-HERE.md` Section 13 with verified commands and relative links.

### Documentation & Research Traceability - Milestone DOC-01 (2026-11-22)
- **Research-Oriented START HERE Guide**:
  - Authored comprehensive `docs/START-HERE.md` as the primary onboarding entry point for both researchers and external evaluators. Covers maritime problem context, AIS telemetry strengths and limits, platform capabilities, dual-track structure, architecture rationale, verified measurements, baseline reproduction steps, code/experiment navigation, and next milestones.
- **Evidence-Backed Architecture Decision Records (ADRs 001–010)**:
  - Created ADR register `docs/02-architecture/decisions/README.md` and authored 9 new formal Architecture Decision Records alongside updated `ADR-001`:
    - `ADR-001`: Modular Monolith Architecture for Solo/Collaborative Research Platform
    - `ADR-002`: Historical AIS Batch Telemetry as Primary Research Data Source
    - `ADR-003`: Canonical PyArrow Schema with Explicit Quality Flags & Sentinel Nullification
    - `ADR-004`: Apache Parquet Columnar Storage with Manifest Verification
    - `ADR-005`: Scikit-Learn BallTree with Haversine Metric as Reference Neighbor Search Engine
    - `ADR-006`: Strict Dual-Threshold Spatiotemporal Neighborhood Semantics in Integer Microseconds
    - `ADR-007`: Deterministic Core-First Labeling Policy for ST-DBSCAN (`stdbscan-core-first-v1.0`)
    - `ADR-008`: Independent $O(N^2)$ Brute-Force Geodesic Test Oracle for Verification
    - `ADR-009`: Uber H3 Discrete Hexagonal Grid as Correctness-Preserving Candidate Neighbor Generator
    - `ADR-010`: Decoupled Parallel Behavioral ML Workstream with Contract-Based Integration
- **Research Evidence Register & Claims Matrix**:
  - Authored `docs/03-research/evidence-register.md`, creating a traceable claims matrix reconciling 14 specific technical claims across ingestion and BallTree clustering with dataset provenance hashes, commit SHAs, configuration parameters, and verification statuses.
  - Reconciled technical facts: clearly distinguished raw observations (143,156), cleaned observations (143,124), filtered inputs (143,116), visualized preview points (5,000), unique vessels (362 MMSIs), and density clusters (241 exploratory clusters); added explicit guardrails clarifying that density clusters are not confirmed anchorages, oracle matching is not detection accuracy, and single runs are not multi-trial benchmarks.
- **Scientific Refinement of ML Proposal**:
  - Updated `docs/03-research/vessel-behavior-ml.md` (v1.1) with domain corrections: clarified that AIS gaps stem predominantly from crane shadowing and line-of-sight limits rather than deliberate transponder disabling; noted that crabbing angles occur naturally in currents; reinforced that Isolation Forest scores are non-probabilistic isolation indices; labeled example incidents as purely synthetic documentation examples; marked the `vessel_anomaly_v1` GeoJSON contract as provisional.
- **Onboarding & Governance Alignment**:
  - Updated `docs/05-guides/ml-research-onboarding.md` and `docs/01-project/collaboration-plan.md` to reinforce the "One team, one initiative, one integrated product, two complementary lead areas" model with flexible pacing, zero bureaucratic drag, experiment logging guidelines, negative finding documentation, and AI coding assistant safety rules.
  - Updated `README.md` with prominent tip linking to `docs/START-HERE.md` and expanded documentation index.

### Documentation & Collaboration - Collaboration Foundation & ML Research Track (2026-11-22)
- **Collaborative Research Tracks**:
  - Established dual-track collaborative research architecture between Lead Researcher NipunaBhanuka18 (AIS ingestion, BallTree reference ST-DBSCAN, Uber H3 optimization, stay-point/anchorage intelligence) and proposed ML Research Collaborator Kishakya (vessel trajectory feature engineering, unsupervised kinematic anomaly detection, explainable incident generation).
  - Maintained the intact 8-week solo clustering roadmap for Track A while defining Track B as an independent parallel research track with its own schedule.
- **ML Research Proposal & Onboarding Documentation**:
  - Authored `docs/03-research/vessel-behavior-ml.md` (marked `PROPOSAL — NOT FINALIZED`), defining problem formulation, research questions (RQ-ML1, RQ-ML2), hypotheses, canonical telemetry fields, trajectory windowing, kinematic feature definitions, rule-based baseline, Isolation Forest baseline, alternative baselines (LOF, Mahalanobis), evaluation methodology (vessel-disjoint & chronological splits, synthetic perturbation limits), and open decisions for Kishakya.
  - Authored `docs/05-guides/ml-research-onboarding.md`, providing a 15-point comprehensive onboarding guide covering problem domain, completed milestones, setup via `uv`, running tests, cleaned AIS Parquet schema, reproducible data acquisition, module boundaries, branch workflow (`feat/ml-...`), AI assistant safety, experiment tracking, protected files, and initial tasks ML-01 to ML-04.
- **Shared Integration Contracts**:
  - Documented canonical AIS input contract based on 19 standardized columns in `cleaned_ais.parquet`.
  - Defined proposed `vessel_anomaly_v1` GeoJSON Feature output contract (`incident_id`, `mmsi`, timestamps, observation source rows, model id/version, non-probabilistic anomaly score, primary factor, factor contributions, data quality context).
- **Collaboration Infrastructure**:
  - Created `CONTRIBUTING.md` outlining quality gates, branching conventions, data protection, and reproducibility standards.
  - Created `.github/pull_request_template.md` providing a lightweight PR checklist for track categorization, quality checks, data protection, and experiment tracking.
  - Authored `docs/01-project/collaboration-plan.md` defining track responsibilities, module ownership, conflict resolution, and academic co-authorship principles.
- **Project Documentation Updates**:
  - Updated `README.md`, `docs/01-project/vision.md`, `docs/01-project/scope.md`, `docs/01-project/roadmap.md`, `docs/02-architecture/system-architecture.md`, and `docs/03-research/research-plan.md` with multi-engine architecture, parallel research tracks, and updated Mermaid component diagrams (zero application or scientific code changes).

### Documentation & Visualization - Milestone W2-CLOSE (2026-11-18)
- **Public Clustering Visualization**: Captured genuine headless-browser PNG screenshot of the recorded Week 2 Los Angeles / Long Beach BallTree ST-DBSCAN spatial preview at `docs/assets/w2-balltree-clustering.png` (60.4 KB, no vessel identifiers or private paths) and embedded it in `README.md` with full exploratory methodology caveats.
- **Week 2 Portfolio Finalization**: Recorded the pre-Week 3 BallTree reference baseline summary in `README.md` and finalized Week 2 closure records in `docs/04-development/milestones.md`, `docs/04-development/development-log.md`, and `CHANGELOG.md` (zero application or scientific code changes).

### Added & Fixed - Milestone W2-01 (2026-11-18)
- **Ingestion Hardening & Audit Corrections**:
  - Updated `sanitize_mmsi` (`src/aegismar/ingestion/cleaner.py`) to strictly accept integer-format MMSIs and reject malformed decimal/float/boolean inputs rather than truncating.
  - Hardened duplicate and same-timestamp conflict semantics: exact deduplication requires full-record equality; same-position differing metadata is preserved with `TIMESTAMP_METADATA_CONFLICT`; conflicting same-timestamp observations never produce fictitious zero-time movement estimates (`distance_nm`, `implied_speed_knots`, `elapsed_seconds`, `prev_source_row` set to `None`).
  - Hardened `detect_and_build_column_mapping` (`src/aegismar/ingestion/schema.py`) to reject duplicate raw headers and ambiguous mixed legacy/modern canonical mappings (e.g., `LAT` + `latitude`, `mmsi` + `MMSI`) via `SchemaAdapterError`.
  - Corrected documentation (`pipeline.py`, `brs.md`, `srs.md`, `datasets.md`) to state explicitly that MVP ingestion materializes rows in memory in Python lists prior to `zstd`-compressed Parquet serialization rather than bounded-memory streaming.
- **Reference BallTree ST-DBSCAN Engine**:
  - Added `numpy` and `scikit-learn` via `uv` (`h3` intentionally deferred to Week 3).
  - Implemented typed configuration (`src/aegismar/clustering/config.py`: `QualityFilterPolicy`, `STDBSCANConfig`), canonical data structures & Parquet loader (`src/aegismar/clustering/types.py`), and `BallTreeNeighborhoodProvider` (`src/aegismar/clustering/balltree_neighbors.py`) using `metric="haversine"` with `[lat_rad, lon_rad]` radians, chunked batch queries, exact integer-microsecond temporal filtering, and exact Haversine pruning.
  - Implemented provider-agnostic deterministic core-first ST-DBSCAN (`src/aegismar/clustering/st_dbscan.py`, policy `stdbscan-core-first-v1.0`) with ascending canonical core-index component numbering and nearest-core border tie-breaking.
  - Implemented result exporters (`src/aegismar/clustering/export.py`) writing Parquet assignments, summary JSON, compact GeoJSON preview, and offline SVG static HTML map, plus CLI subcommand `aegismar cluster`.
- **Independent Brute-Force Oracle & Test Suite**:
  - Implemented isolated $O(N^2)$ `BruteForceNeighborhoodOracle` and `verify_provider_against_oracle` (`src/aegismar/spatial/oracle.py`) with safety cap ($N \le 5{,}000$).
  - Authored all 16 critical ST-DBSCAN fixtures, randomized oracle tests, ingestion regression tests, and CLI cluster tests (`tests/unit/test_st_dbscan.py`, `tests/unit/test_oracle.py`, `tests/unit/test_ingestion.py`, `tests/unit/test_cli.py`): 52 tests passing, 95% total code coverage.
- **Exploratory Real AIS Baseline (Los Angeles / Long Beach)**:
  - Executed BallTree ST-DBSCAN on `data/processed/lalb_20250101/cleaned_ais.parquet` (`eps_spatial_m=300.0`, `eps_temporal_s=900.0`, `min_samples=5`, excluding 8 `TIMESTAMP_POSITION_CONFLICT` rows -> 143,116 analyzed): 241 clusters, 136,276 core, 934 border, 5,906 noise; 13.68 s uninstrumented wall time (38.01 s / 225.83 MB peak heap under `tracemalloc`); 100% oracle match on 1,000-row real subset; 100% deterministic across repeated runs.

### Added - Milestone W1-02B (2026-11-14)
- **AIS Ingestion & Cleaning Engine**:
  - Implemented `src/aegismar/common/` domain constants, ITU sentinels, and typed dataclasses (`CanonicalPing`, `IngestionManifest`).
  - Implemented spherical geodesic haversine metric module (`src/aegismar/spatial/haversine.py`).
  - Implemented dual-format schema adapter (`src/aegismar/ingestion/schema.py`) supporting NOAA 2025 (`snake_case`) and legacy 2018–2024 (`PascalCase`) CSV headers.
  - Implemented cleaning and validation engine (`src/aegismar/ingestion/cleaner.py`): ISO 8601 UTC timestamp parsing, 9-digit zero-padded MMSI preservation, sentinel nullification (`102.3`, `360.0`, `511`, `15`), duplicate consolidation, same-timestamp coordinate conflict flagging, deterministic trajectory sorting, and implied speed calculation ($>50\text{ kt}$).
  - Implemented columnar storage writer (`src/aegismar/ingestion/storage.py`) writing zstd-compressed Parquet files and cryptographic `manifest.json`.
  - Implemented end-to-end pipeline runner (`src/aegismar/ingestion/pipeline.py`) with source SHA-256 computation and overwrite protection.
  - Added `tzdata` dependency for cross-platform IANA timezone support.
- **CLI Interface**:
  - Added CLI entrypoint `aegismar ingest` (`src/aegismar/cli.py`, `src/aegismar/__main__.py`) supporting `--input`, `--output`, `--speed-threshold`, and `--overwrite`.
- **Unit Testing & Test Fixtures**:
  - Added synthetic CSV test fixtures (`tests/fixtures/synthetic_2025_sample.csv`, `synthetic_legacy_sample.csv`).
  - Authored comprehensive test suites: 16 ingestion unit tests (`test_ingestion.py`) and 7 CLI tests (`test_cli.py`). Total 25 tests passing with 91% code coverage.
- **Production Dataset Ingestion**:
  - Ingested authentic Los Angeles / Long Beach sample (`sample_lalb_20250101.csv`): 143,156 input rows scanned, 143,124 output rows generated in 7.19s, 32 duplicates consolidated, 8 coordinate conflicts flagged, 18 implied speed violations flagged into `data/processed/lalb_20250101/cleaned_ais.parquet` (4.15 MB) and `manifest.json`.

### Added - Milestone W1-02A (2026-11-14)
- **NOAA 2025 Dataset Investigation**: Acquired genuine nationwide sample `ais-2025-01-01.csv.zst` (192.82 MB, preserved in `data/raw/`), identified NOAA 2025 schema evolution (snake_case, coordinate order swap, sentinel nullification).
- **Study Region Selection**: Empirically profiled candidate regions and selected Los Angeles / Long Beach (San Pedro Bay) with 143,156 records across 362 vessels; documented anchorage/berth disambiguation framework in `docs/03-research/datasets.md`.
- **Requirements & Documentation Alignment**: Clarified schema adaptability in `docs/01-project/srs.md` and neutralized speculative claims in `README.md`.

### Added - Milestone W1-01 (2026-11-14)
- **Repository Setup**: Initialized Git repository structure with Python-first modular monolith layout (`src/aegismar`).
- **Toolchain & Packaging**: Configured `pyproject.toml` using `hatchling` build backend and pinned CPython `3.11.9` with `uv` package manager.
- **Quality Gates**: Configured Ruff (linting and formatting), Mypy (strict static type checking), and Pytest with initial smoke tests (`tests/test_smoke.py`).
- **Data Protection**: Established strict `.gitignore` rules preventing tracking of raw/processed AIS datasets, caches, virtual environments, and benchmark outputs, while preserving test fixtures.
- **Documentation Architecture**:
  - `docs/01-project/`: Vision, BRS (Draft v2.1), SRS (Draft v2.1), Scope breakdown, and 8-week Roadmap.
  - `docs/02-architecture/`: System Architecture and ADR-001 (Modular Monolith Decision).
  - `docs/03-research/`: Research Plan (H3 vs BallTree ST-DBSCAN), Evaluation Protocol, and Dataset Strategy.
  - `docs/04-development/`: Milestones, Development Log, and Testing Strategy.
  - `docs/05-guides/`: Developer Installation Guide.
  - Root `README.md` linking the entire documentation tree.

