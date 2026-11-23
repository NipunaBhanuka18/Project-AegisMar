# Eight-Week Development Roadmap

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**

**Document Version:** 2.2  
**Status:** Approved Roadmap (Collaborative Dual-Track Architecture)  
**Track A Capacity:** 200 Hours (8 Weeks @ 25 Hours/Week) — Lead: NipunaBhanuka18  
**Track B Capacity:** Independent Parallel Track — Proposed Lead: Kishakya *(schedule to be agreed)*  

---

## 1. Roadmap Architecture

The development lifecycle operates across two complementary, decoupled research tracks:
- **Track A (Platform, Clustering & Spatial Intelligence — Lead: NipunaBhanuka18)**:
  1. **Foundations (Weeks 1–2)**: Ingestion, sentinel filtering, spatial indexing, and test oracles.
  2. **Core Research Algorithms (Weeks 3–4)**: ST-DBSCAN clustering, H3 candidate acceleration, stay-points, and anchorages.
  3. **Platform Storage & Serving (Weeks 5–6)**: DuckDB in-process analytics, contract integration, and read-only FastAPI service.
  4. **Geospatial UI & Research Defense (Weeks 7–8)**: Interactive map, benchmarking, reproducibility package, and final thesis documentation.
- **Track B (Parallel Behavioral ML Anomaly Research Track — Lead: Kishakya, *proposed*)**:
  - Operates on an independent schedule decoupled from Track A's critical path.
  - Consumes cleaned Parquet datasets via the canonical schema and exports incident predictions via the `vessel_anomaly_v1` GeoJSON contract.
  - Governed by milestones `ML-01` through `ML-05` with flexible pacing.

---

## 2. Weekly Milestone Breakdown — Track A (Platform & Clustering)

### Week 1: Repository Setup, Data Architecture & Ingestion Engine
- **Capacity**: 25 Hours
- **Primary Goal**: Establish an immutable repository baseline and implement deterministic AIS ingestion with sentinel masking.
- **Key Deliverables**:
  - `W1-01`: Repository initialization, Python 3.11 environment, testing/linting/typing gates, documentation tree.
  - `W1-02`: AIS schema parsing, coordinate boundary filtering, sentinel value coercion, and Parquet storage writer.
- **Dependencies**: None.
- **Acceptance Gate**: 100% passing unit tests on synthetic corrupted AIS pings; strict mypy and ruff compliance; clean Parquet round-trip.

### Week 2: Ingestion Hardening & BallTree Reference ST-DBSCAN Engine
- **Capacity**: 25 Hours
- **Primary Goal**: Complete bounded W1-02B ingestion corrections and implement the verified Haversine BallTree reference ST-DBSCAN engine with an independent brute-force test oracle.
- **Key Deliverables**:
  - `W2-01`: Ingestion corrections (strict MMSI validation, full-record duplicate/conflict semantics, ambiguous header rejection, accurate memory documentation), `scikit-learn` Haversine `BallTree` neighborhood engine, provider-agnostic deterministic core-first ST-DBSCAN, independent $O(N^2)$ brute-force test oracle, 16 critical test fixtures, and exploratory baseline run on the LA/LB dataset.
- **Dependencies**: Week 1 cleaned Parquet dataset.
- **Acceptance Gate**: BallTree neighborhood sets, core/border/noise roles, and final cluster labels match the independent brute-force oracle 100% across all synthetic and randomized test fixtures; real LA/LB dataset baseline executes deterministically.

### Week 3: H3 Candidate Optimization, Completeness Testing & Comparative H1 Benchmarks
- **Capacity**: 25 Hours
- **Primary Goal**: Implement the correctness-preserving Uber H3 neighborhood provider plugging into the shared ST-DBSCAN core, verify completeness across cell boundaries and pentagons, and execute comparative H1 benchmarks against the BallTree reference.
- **Key Deliverables**:
  - `W3-01`: Uber H3 discrete hexagonal grid candidate generation engine (`H3NeighborhoodProvider`) with exact geodesic and temporal pruning.
  - `W3-02`: Completeness verification across H3 cell boundaries, pentagons, dateline, and high latitudes against the brute-force oracle and BallTree reference.
  - `W3-03`: Quantitative comparative H1 benchmark (Neighbor Recall, Precision, ARI, build/query/clustering wall time, peak memory).
- **Dependencies**: Week 2 BallTree ST-DBSCAN reference engine and oracle.
- **Acceptance Gate**: Cluster labels between H3-accelerated and BallTree engines achieve exact concordance with 100% eligible-neighbor recall on correctness tests and empirically measured runtime comparisons.

### Week 4: Stay-Point Extraction & Anchorage Intelligence
- **Capacity**: 25 Hours
- **Primary Goal**: Detect vessel stops and classify anchorage zones while excluding port terminals.
- **Key Deliverables**:
  - `W4-01`: Trajectory stay-point extraction algorithm ($\Delta D_{\text{max}}$, $\Delta T_{\text{min}}$).
  - `W4-02`: GeoJSON berth polygon loader and spatial point-in-polygon exclusion.
  - `W4-03`: Anchorage basin aggregation reporting unique vessel counts (`MMSI`) and dwell duration.
- **Dependencies**: Week 3 clustering engine.
- **Acceptance Gate**: Docked vessels inside berth polygons are strictly excluded from anchorage statistics; unique vessel counts are decoupled from ping counts.

### Week 5: Platform Analytical Storage & Contract Integration
- **Capacity**: 25 Hours
- **Primary Goal**: Integrate in-process DuckDB analytical storage, generate precomputed GeoJSON layers for clusters and anchorages, and establish contract ingestion validation for the provisional `vessel_anomaly_v1` schema.
- **Key Deliverables**:
  - `W5-01`: DuckDB integration querying Parquet partitions and generating GeoJSON outputs.
  - `W5-02`: Contract validation and ingestion pipeline for `vessel_anomaly_v1` GeoJSON FeatureCollections.
- **Dependencies**: Weeks 3 and 4 spatial clustering and anchorage outputs.
- **Acceptance Gate**: Sub-50ms analytical aggregations over Parquet via DuckDB; clean schema validation of anomaly contract payloads.

### Week 6: Read-Only FastAPI Service Implementation
- **Capacity**: 25 Hours
- **Primary Goal**: Implement stateless, read-only HTTP API serving precomputed spatial layers and anomaly incidents from DuckDB.
- **Key Deliverables**:
  - `W6-01`: Lightweight, read-only FastAPI service providing endpoints for clusters, anchorages, and anomalies.
  - `W6-02`: Integration test suite validating API response schemas and performance.
- **Dependencies**: Week 5 DuckDB analytical storage layer.
- **Acceptance Gate**: Sub-50ms API response times on localhost for precomputed GeoJSON layers; zero mutable endpoints.

### Week 7: Geospatial Dashboard & End-to-End Validation
- **Capacity**: 25 Hours
- **Primary Goal**: Build a lightweight web map interface for incident inspection and run end-to-end integration tests.
- **Key Deliverables**:
  - `W7-01`: Browser-based map interface (Leaflet or MapLibre) rendering cluster polygons, anchorage zones, and trajectory tracks.
  - `W7-02`: Incident inspection panel displaying anomaly explanations and kinematic metrics.
  - `W7-03`: End-to-end integration test validating the complete pipeline from raw sample to map visualization.
- **Dependencies**: Week 6 FastAPI service.
- **Acceptance Gate**: Smooth rendering of sample coastal sector; analyst can click an anomaly and see its exact physical justification.

### Week 8: Scientific Benchmarking, Reproducibility & Research Defense
- **Capacity**: 25 Hours
- **Primary Goal**: Execute formal benchmarks, document reproducibility package, and finalize research findings.
- **Key Deliverables**:
  - `W8-01`: Automated benchmark execution across dataset scales (10k, 50k, 100k, 500k pings) measuring runtime, memory, and indexing overhead.
  - `W8-02`: Comprehensive evaluation report with empirical tables, charts, and hypothesis test outcomes (H1, H2).
  - `W8-03`: Final codebase freeze, reproducibility verification guide, and academic thesis submission.
- **Dependencies**: Weeks 1–7 complete.
- **Acceptance Gate**: One-command benchmark execution; zero discrepancies between reported figures and measured data.

---

## 3. Parallel ML Research Track (Proposed Lead: Kishakya)

The machine learning anomaly detection research track proceeds in parallel with its own flexible milestone backlog. No hard deadlines are imposed; milestone timing and priorities will be established collaboratively upon Kishakya's onboarding review.

### Proposed Initial ML Milestones
- **ML-01: Domain Literature & AIS Schema Review**:
  - Review maritime anomaly detection literature and existing `docs/03-research/vessel-behavior-ml.md`.
  - Profile canonical AIS telemetry fields (`cleaned_ais.parquet`) and understand sensor sentinels/limits.
  - *Deliverable*: Literature summary notes and confirmed feature selection strategy.
- **ML-02: Vessel Trajectory Feature Specification**:
  - Formulate mathematical definitions for kinematic acceleration, angular course rates, drift angles, and transponder reporting intervals.
  - Define windowing parameters (sliding time window vs. fixed-ping strides).
  - *Deliverable*: Trajectory feature extraction specification document.
- **ML-03: Baseline Models & Evaluation Protocol Freezing**:
  - Formalize rule-based heuristic scoring thresholds and Isolation Forest architecture.
  - Specify vessel-disjoint (70/30 MMSI) and chronological holdout splits.
  - Parameterize synthetic perturbation types (speed jumps, crabbing, coverage dropouts) with maritime physical bounds.
  - *Deliverable*: Evaluation protocol document and perturbation configuration schema.
- **ML-04: First Reproducible Feature-Engineering Experiment**:
  - Implement `src/aegismar/anomaly/features.py` with comprehensive unit tests (`tests/unit/test_anomaly.py`).
  - Extract feature representations across San Pedro Bay test partition and log reproducible experiment artifacts under `experiments/outputs/anomaly/`.
  - *Deliverable*: Feature extractor module and baseline experiment summary JSON.
- **ML-05: Anomaly Model Evaluation & `vessel_anomaly_v1` Export**:
  - Implement rule-based scoring engine and Isolation Forest model.
  - Evaluate PR-AUC, precision, recall, and false alarm rates on held-out splits.
  - Export explainable incident GeoJSON conforming to the `vessel_anomaly_v1` contract for DuckDB ingestion.
  - *Deliverable*: Anomaly scoring modules, evaluation benchmark logs, and verified incident GeoJSON.

