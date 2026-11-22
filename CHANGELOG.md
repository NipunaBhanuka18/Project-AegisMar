# Changelog

All notable changes to Project AegisMar will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> [!NOTE]
> Project AegisMar is currently in pre-alpha research and MVP development. Documentation versioning adheres to the v2.1 solo MVP baseline, while package implementation starts at `0.1.0.dev1`.

## [Unreleased]

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
  - Implemented columnar storage writer (`src/aegismar/ingestion/storage.py`) writing Snappy-compressed Parquet files and cryptographic `manifest.json`.
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

