# Collaborative Research & Engineering Plan

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**  
> **Document Version:** 1.1  
> **Lifecycle Status:** Active Collaboration & Governance Baseline  
> **Research Team:**  
> - **NipunaBhanuka18**: Project Lead & Geospatial Clustering Track Lead  
> - **Kishakya**: Proposed ML Research Collaborator *(participation, schedule, and attribution pending review)*  
> **Date:** 2026-11-22  

---

## 1. Collaboration Purpose and Context

Project AegisMar originated as an independent undergraduate research and software engineering initiative by its original author, NipunaBhanuka18. The project has since expanded into a collaborative research partnership between two fellow AI undergraduate researchers.

The core philosophy of this collaboration is:
- **One Team**: Two researchers collaborating on one joint research and engineering initiative.
- **One Integrated Product**: A single, cohesive maritime domain awareness platform delivering clustering, anchorage intelligence, and trajectory anomaly detection through an integrated FastAPI service and web map.
- **Two Complementary Lead Areas**: NipunaBhanuka18 leads spatial clustering and platform data engineering; Kishakya leads trajectory feature engineering and behavioral machine learning.
- **Shared Architecture & Integration**: Both researchers co-design and agree on shared data schemas, analytical contracts, and platform architecture.
- **Flexible Development Pace**: Communication happens whenever helpful without bureaucratic drag (no compulsory daily stand-ups, no artificial timesheet reporting, and no forced synchronized hours).

---

## 2. Research Tracks & Researcher Responsibilities

```mermaid
flowchart TD
    subgraph TrackA ["Track A: Maritime Traffic & Anchorage Intelligence (Lead: NipunaBhanuka18)"]
        Ingest["AIS Ingestion & Data Quality Engine"]
        BallTree["BallTree Reference ST-DBSCAN Engine"]
        H3["H3 Hexagonal Acceleration Engine"]
        StayPoint["Stay-Point & Anchorage Intelligence"]
        H1Eval["Comparative H1 Benchmarks (Recall/Runtime)"]
    end

    subgraph TrackB ["Track B: Vessel Behavior ML (Proposed Lead: Kishakya)"]
        TrajFeat["Vessel Trajectory Feature Engineering"]
        RuleScorer["Rule-Based Kinematic Baseline"]
        IsoForest["Unsupervised Isolation Forest / LOF"]
        Perturb["Synthetic Perturbation Evaluation Harness"]
        H2Eval["Explainable Anomaly Benchmarks (PR-AUC/F1)"]
    end

    subgraph Platform ["Shared Platform Integration & Presentation"]
        ParquetContract[("Canonical Parquet Contract")]
        AnomalyContract[("Vessel Anomaly Contract (GeoJSON, Provisional)")]
        DuckDBStore[("DuckDB Analytical Query Layer")]
        FastAPI["Read-Only FastAPI Service"]
        WebMap["Geospatial Dashboard (Leaflet)"]
    end

    Ingest --> ParquetContract
    ParquetContract --> BallTree
    ParquetContract --> H3
    ParquetContract --> TrajFeat
    H3 --> StayPoint
    StayPoint --> DuckDBStore
    TrajFeat --> RuleScorer
    TrajFeat --> IsoForest
    RuleScorer --> AnomalyContract
    IsoForest --> AnomalyContract
    AnomalyContract --> DuckDBStore
    DuckDBStore --> FastAPI
    FastAPI --> WebMap
```

### Track A: Maritime Traffic and Anchorage Intelligence
- **Track Lead**: NipunaBhanuka18
- **Core Responsibilities**:
  - AIS data engineering pipeline (`aegismar.ingestion`) and Parquet storage management.
  - Geodesic spatial indexing foundation (`aegismar.spatial`) and independent test oracles (`oracle.py`).
  - Reference Haversine `BallTree` ST-DBSCAN clustering engine (`aegismar.clustering.balltree_neighbors`).
  - Uber H3 candidate generation optimization (`aegismar.clustering.h3_neighbors`) and comparative H1 benchmarks.
  - Stay-point extraction and berth polygon exclusion (`aegismar.staypoint`).
  - Shared analytical storage (DuckDB) and read-only FastAPI service integration (`aegismar.api`).
  - Primary platform architecture maintenance and CI/CD quality enforcement.

### Track B: ML-Based Vessel Behavior Intelligence
- **Proposed Track Lead**: Kishakya *(participation pending review)*
- **Core Responsibilities**:
  - Trajectory windowing and kinematic feature extraction (`aegismar.anomaly.features`).
  - Transparent rule-based kinematic anomaly scoring (`aegismar.anomaly.rules`).
  - Unsupervised machine learning models: Isolation Forest, LOF, and alternative baselines (`aegismar.anomaly.models`).
  - Controlled synthetic perturbation generation and leakage-free evaluation harness (`aegismar.anomaly.evaluation`).
  - Explainable anomaly incident output generation adhering to the provisional `vessel_anomaly_v1` GeoJSON contract.
  - Scientific analysis, error analysis, and research documentation for the ML track ([vessel-behavior-ml.md](../03-research/vessel-behavior-ml.md)).

---

## 3. Scope Boundaries & Roadmap Independence

To ensure neither researcher blocks the other:
1. **Intact 8-Week Clustering Roadmap**: NipunaBhanuka18's original 8-week development roadmap for Track A remains intact as the historical and engineering baseline.
2. **Independent ML Schedule**: Track B operates on an independent schedule with its own proposed milestone sequence (ML-01 to ML-04). Deadlines and milestones will be agreed upon collaboratively to fit Kishakya's availability.
3. **No Mandatory Scope Creep**: The core deliverables of the platform remain protected. ML capabilities integrate through well-defined contracts without introducing hard dependencies into the clustering pipeline.
4. **Decoupled Module Namespaces**: Track A operates in `aegismar.clustering`, `aegismar.spatial`, and `aegismar.staypoint`. Track B operates strictly within `aegismar.anomaly`.

---

## 4. Integration Contracts

Interoperability between the two tracks is governed by two versioned contracts:

### 4.1 Ingestion Contract (Input to ML Track)
- **Source**: `data/processed/<dataset_id>/cleaned_ais.parquet`
- **Schema**: 19 canonical fields defined in `src/aegismar/ingestion/schema.py`
- **Guarantee**: Sorted in canonical total order `(timestamp_utc, mmsi, latitude, longitude, source_row)`. Quality flags provided for each ping.

### 4.2 Anomaly Output Contract (Input to Serving Layer)
- **Specification**: `vessel_anomaly_v1` GeoJSON FeatureCollection (Provisional baseline).
- **Schema includes**: `incident_id`, `mmsi`, `start_timestamp_utc`, `end_timestamp_utc`, `observation_source_rows`, `model_id`, `model_version`, `anomaly_score` $\in [0.0, 1.0]$, `score_semantics` (non-probabilistic index), `primary_factor`, `factor_contributions`, `data_quality_context`.
- **Presentation**: Ingested by the DuckDB query layer and served via `GET /api/v1/anomalies` without requiring runtime model execution.

---

## 5. Collaboration Workflows & Quality Standards

- **Branching**: All work happens on topic branches (`feat/ml-...`, `feat/clu-...`) branched off `main`.
- **Quality Gates**: Every pull request must pass all 5 gates (`pytest`, coverage $\ge 90\%$, `ruff check`, `ruff format`, strict `mypy`).
- **Data Protection**: Strict prohibition against committing raw AIS files, Parquet datasets, or local experiment outputs.
- **Review Policy**: Pull requests touching shared files (`pyproject.toml`, storage layer, API schemas) require mutual review and approval. Track-specific PRs are reviewed collaboratively.
- **Conflict Resolution**: Disagreements regarding platform architecture, dependencies, or shared schemas will be resolved through written design discussions referencing verifiable evidence and project requirements.

---

## 6. Academic Attribution & Authorship Principles

1. **Equal Intellectual Respect**: Both researchers are treated as primary academic contributors to the AegisMar initiative.
2. **Publication Co-Authorship**: Any research paper, conference submission, or technical thesis derived from Project AegisMar will include both researchers as co-authors, with lead authorship on specific papers reflecting track leadership (e.g., spatial clustering paper led by NipunaBhanuka18; anomaly detection paper led by Kishakya).
3. **Transparent Contribution Tracking**: Git commit histories, development logs, and the [Research Evidence Register](../03-research/evidence-register.md) will accurately document individual contributions.
4. **Prospective Status**: Kishakya's name is noted as the proposed collaborator. Her formal attribution and participation will be updated upon her review and acceptance of this plan.
