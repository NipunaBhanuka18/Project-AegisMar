# Business Requirements Specification (BRS)

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**

**Document Version:** 2.1 (Draft)  
**Lifecycle Status:** Controlled Draft (MVP Planning)  
**Author:** Solo AI Undergraduate Engineer  
**Baseline Allocation:** 200 Development Hours (8 Weeks)  
**Target Delivery:** Localhost Analytical Research MVP  

---

## 1. Purpose and Scope

This Business Requirements Specification (BRS) defines the operational, analytical, and research requirements for Project AegisMar. The system is designed to provide maritime analysts and researchers with a reproducible, explainable, and computationally optimized platform for discovering traffic patterns, validating anchorage utilization, and detecting trajectory-level vessel behavior anomalies from historical AIS data.

The scope covers:
- Offline ingestion, quality validation, and Parquet storage of raw AIS telemetry.
- Spatiotemporal clustering of vessel traffic using both a baseline spatial index and an accelerated hexagonal grid candidate generator.
- Vessel-aware anchorage identification incorporating berth exclusion zones.
- Kinematic trajectory anomaly detection with explainable multi-factor scoring.
- Localhost analytical querying (via DuckDB) and geospatial visualization (via read-only FastAPI and web map).

---

## 2. Stakeholders & User Personas

| Role | Operational Context | Primary Goal |
|---|---|---|
| **Maritime Domain Researcher** | Academic / defense laboratory investigating spatiotemporal clustering algorithms. | Validate computational speedup and neighborhood recall of H3-accelerated ST-DBSCAN versus geodesic BallTree baselines. |
| **Port Operations Analyst** | Port authority managing commercial anchorages, channel safety, and berth turnaround. | Quantify vessel waiting times, identify anchorage overcapacity, and separate anchored vessels from berthed vessels. |
| **Maritime Safety & Security Analyst** | Coast guard or monitoring center auditing maritime traffic compliance. | Review suspicious kinematic anomalies (drifting, excessive speed, unexpected AIS dropouts) with transparent, physical explanations. |

---

## 3. High-Level Business Objectives

- **BO-01: Correctness-Preserving Algorithmic Acceleration**: Demonstrate that discrete spatial partitioning (Uber H3) accelerates spatiotemporal density clustering without compromising the analytical correctness of neighbor discovery compared to geodesic metric tree baselines.
- **BO-02: Actionable Anchorage Intelligence**: Replace simplistic ping-density heatmaps with vessel-aware stay-point tracking and berth-delineated anchorage analytics.
- **BO-03: Explainable Anomaly Identification**: Provide clear physical justification for trajectory anomalies, reducing analyst alert fatigue caused by sensor artifacts and normal vessel maneuvers.
- **BO-04: Software & Research Reproducibility**: Ensure all data pipelines, benchmarks, and mathematical assertions can be executed and verified deterministically on standard local hardware.

---

## 4. Traceable Business Requirements

### 4.1 Ingestion & Data Integrity Requirements
- **BR-ING-01 (Data Immutability)**: The platform shall preserve all raw source AIS datasets in a read-only state. All cleaning, sentinel transformations, and derived calculations must be stored separately in columnar Parquet format.
- **BR-ING-02 (Sentinel & Missing Value Handling)**: The platform shall explicitly identify, mask, or coerce international standard AIS sentinel values (e.g., SOG 102.3 kt, Heading 511°, Navigational Status 15) to prevent calculation distortion.
- **BR-ING-03 (Kinematic Sanity Checking)**: The platform shall flag and filter telemetry records exhibiting physically implausible implied speeds between consecutive pings ($v_{\text{implied}} > 50\text{ knots}$ for commercial merchant vessels).

### 4.2 Spatiotemporal Clustering Requirements
- **BR-CLU-01 (Reference Baseline Architecture)**: The platform shall implement a reference ST-DBSCAN clustering engine utilizing a scikit-learn `BallTree` with the Haversine distance metric for spatial indexing.
- **BR-CLU-02 (Independent Correctness Oracle)**: An independent, exact brute-force geodesic distance comparator shall serve as the ground-truth test oracle to formally verify spatial neighbor retrieval.
- **BR-CLU-03 (H3 Neighbor Completeness)**: The H3-accelerated candidate generation mechanism shall guarantee that no candidate point within spatial search radius $\varepsilon_{\text{spatial}}$ is omitted from neighborhood expansion ($\text{Recall} \ge 99.9\%$).
- **BR-CLU-04 (Deterministic Point Classification)**: The ST-DBSCAN implementation must produce deterministic assignments of core, border, and noise points across identical runs with fixed seeds and sorted inputs.

### 4.3 Anchorage & Stay-Point Intelligence Requirements
- **BR-ANC-01 (Stay-Point Extraction)**: The platform shall extract stay-points by grouping contiguous temporal observations for an individual vessel where spatial displacement remains below $\Delta D_{\text{max}}$ for a duration exceeding $\Delta T_{\text{min}}$.
- **BR-ANC-02 (Berth Exclusion)**: Anchorage analytics must cross-reference stay-points against port berth and terminal polygons, excluding berthed or docked vessels from anchorage statistics.
- **BR-ANC-03 (Unique-Vessel Dwell Metrics)**: Anchorage utilization shall be reported primarily by unique vessel counts (`MMSI`) and dwell hours rather than raw ping counts, preventing sampling frequency bias.

### 4.4 Vessel Behavior Anomaly Requirements
- **BR-ANO-01 (Distinction of Density Noise from Threat)**: The system shall not classify unclustered spatial density noise as a security or behavioral anomaly. Spatial outliers must be evaluated on trajectory kinematics.
- **BR-ANO-02 (Explainable Kinematic Scoring)**: The platform shall score trajectory segments across explicit physical dimensions: velocity discontinuities, abnormal turns/drifting, transponder gap duration, and spatial exclusion zone infringement.
- **BR-ANO-03 (Evaluation Integrity)**: Anomaly detection algorithms must be evaluated on held-out vessel trajectories using documented, physically plausible perturbations to prevent data leakage.

### 4.5 Serving & Presentation Requirements
- **BR-SRV-01 (Localhost Read-Only Service)**: Precomputed analytical results, cluster boundaries, anchorage summaries, and anomaly incidents shall be served via a lightweight, read-only FastAPI HTTP service on localhost.
- **BR-SRV-02 (Geospatial Inspection UI)**: The system shall provide a minimal map-based browser dashboard allowing analysts to inspect vessel trajectories, cluster polygons, and anomaly evidence.

---

## 5. Non-Functional Requirements & Provisional Targets

- **NFR-REL-01 (Reproducibility)**: Every benchmark and experiment shall record input dataset hashes, parameter configurations, random seeds, and host hardware environment.
- **NFR-PERF-01 (Provisional Ingestion Memory & Throughput)**: The current MVP ingestion pipeline is an **in-memory batch processor** that materializes CSV rows and cleaned `CanonicalPing` objects in Python lists prior to Arrow/Parquet serialization (not bounded-memory streaming). It operates comfortably on regional daily extracts (~100k–500k pings) on standard consumer workstations; true bounded-memory streaming is deferred outside the MVP scope.
- **NFR-PERF-02 (Scalability Thresholds)**: Benchmark evaluations shall explicitly evaluate dataset scales of 10k, 50k, 100k, and optionally 500k records, measuring runtime, peak memory, and indexing overhead.
- **NFR-SEC-01 (Local Execution)**: The MVP shall operate entirely offline on localhost without requiring internet egress, external database connections, or cloud service credentials.

---

## 6. Business Rules & Operational Constraints

1. **Rule 1 (AIS Quality Precedence)**: Unvalidated AIS pings shall never enter clustering or anomaly evaluation pipelines.
2. **Rule 2 (Vessel Disjointness)**: Test and training splits for anomaly models must be vessel-disjoint (`MMSI` partitioned) and chronological to reflect real-world deployment.
3. **Rule 3 (Port Perimeter Priority)**: A stay-point inside a terminal or dock polygon shall always be classified as `BERTHED` regardless of speed or status report.
4. **Rule 4 (No False Intent Claims)**: An AIS transponder gap shall be labelled as `SIGNAL_GAP` or `POTENTIAL_COVERAGE_LOSS` with duration and location, never as "verified clandestine operations."

---

## 7. Out-of-Scope Scope Exclusions

The following capabilities are explicitly deferred or excluded from the 8-week MVP:
- Real-time live AIS streaming (NMEA over TCP/UDP/Serial) or live playback servers.
- Distributed data platforms (PostgreSQL, PostGIS, Apache Kafka, Apache Spark, Kubernetes).
- Deep learning architectures (LSTMs, Transformers, Graph Neural Networks).
- Multi-user authentication, authorization, or role-based access control (RBAC).
- Global-scale real-time monitoring.
- Automated maritime sanction enforcement or dark-vessel legal verification.

---

## 8. Acceptance Criteria

- [ ] All business requirements map directly to functional requirements in the SRS.
- [ ] Research hypotheses and evaluation protocols are formally defined and reproducible.
- [ ] Ingestion masks sentinels without loss of valid trajectory coordinates.
- [ ] ST-DBSCAN produces identical cluster labels between deterministic runs.
- [ ] H3 candidate search yields zero missing neighbors against the brute-force oracle.
- [ ] Anchorage statistics report unique vessel dwell hours with berth polygons excluded.
- [ ] Read-only API and web dashboard operate reliably on standard localhost.

