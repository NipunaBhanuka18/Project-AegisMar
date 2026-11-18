# Eight-Week Development Roadmap

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**

**Document Version:** 2.1  
**Status:** Approved Roadmap  
**Total Planned Capacity:** 200 Hours (8 Weeks @ 25 Hours/Week)  
**Developer:** Solo Undergraduate AI Engineer  

---

## 1. Roadmap Architecture

The eight-week development lifecycle is partitioned into four major phases:
1. **Foundations (Weeks 1–2)**: Ingestion, sentinel filtering, spatial indexing, and test oracles.
2. **Core Research Algorithms (Weeks 3–4)**: ST-DBSCAN clustering, H3 candidate acceleration, stay-points, and anchorages.
3. **Behavioral Analytics & Serving (Weeks 5–6)**: Kinematic anomaly detection, DuckDB analytical storage, and read-only API.
4. **Integration, Geospatial UI & Research Defense (Weeks 7–8)**: Interactive map, benchmarking, reproducibility package, and final thesis documentation.

---

## 2. Weekly Milestone Breakdown

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

### Week 5: Kinematic Trajectory Anomaly Detection
- **Capacity**: 25 Hours
- **Primary Goal**: Implement explainable multi-factor anomaly scoring for vessel trajectories.
- **Key Deliverables**:
  - `W5-01`: Trajectory kinematic feature extractor (acceleration, angular turn rate, drift angle, coverage gaps).
  - `W5-02`: Explainable rule-based anomaly scoring engine with factor breakdown JSON.
  - `W5-03` *(Conditional)*: Secondary Isolation Forest anomaly baseline.
- **Dependencies**: Week 1 trajectory assembly.
- **Acceptance Gate**: Synthetic trajectory perturbations (speed jumps, GPS dropouts, unnatural drifting) are correctly flagged with appropriate factor attributions.

### Week 6: Analytical Storage & Read-Only API
- **Capacity**: 25 Hours
- **Primary Goal**: Integrate in-process DuckDB storage and expose precomputed results via FastAPI.
- **Key Deliverables**:
  - `W6-01`: DuckDB integration querying Parquet partitions and generating GeoJSON outputs.
  - `W6-02`: Lightweight, read-only FastAPI service providing endpoints for clusters, anchorages, and anomalies.
  - `W6-03`: Integration test suite validating API response schemas and performance.
- **Dependencies**: Weeks 3, 4, and 5 analytical outputs.
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

