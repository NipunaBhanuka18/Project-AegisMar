# Project AegisMar

> **Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3119/)
[![Project Status: Pre-Alpha MVP](https://img.shields.io/badge/status-pre--alpha%20MVP-blue.svg)](#2-current-status)
[![License: Pending](https://img.shields.io/badge/license-pending-lightgrey.svg)](#14-license-attribution)

---

## 1. Project Overview

**Project AegisMar** is an eight-week solo undergraduate research and software engineering initiative designed to build a scientifically rigorous, reproducible maritime Automatic Identification System (AIS) analytics MVP.

The project investigates scalable spatiotemporal clustering and kinematic trajectory anomaly detection to extract explainable maritime traffic intelligence—specifically addressing port congestion, anchorage dwell analysis, and irregular vessel behaviors.

---

<a id="current-status"></a>
## 2. Current Status

- **Phase**: Milestone **W2-01: Ingestion Corrections & BallTree ST-DBSCAN Reference Engine (Completed)**.
- **State**: Validated in-memory AIS ingestion pipeline (`zstd` Parquet + manifest), hardened MMSI/conflict/schema checks, reference Haversine `BallTree` ST-DBSCAN (`stdbscan-core-first-v1.0`), independent $O(N^2)$ brute-force oracle, and exploratory LA/LB baseline completed and verified (52 unit/oracle tests, 95% coverage).
- **Codebase Implementation**: Pre-alpha (`0.1.0.dev1`). Uber H3 candidate optimization, comparative H1 benchmarks, stay-point/anchorage analytics, anomaly detection, DuckDB/FastAPI, and web UI are planned for Weeks 3–8 (H3 is **not yet implemented**).

---

## 3. Maritime Problem Statement

Maritime domain awareness (MDA) relies heavily on global AIS transponder broadcasts. However, real-world AIS data poses severe analytical bottlenecks:
1. **High Volume & Velocity**: Billions of spatial pings overwhelm naive quadratic spatial algorithms.
2. **Data Quality Flaws**: Pervasive missing records, dead-reckoning nulls, GPS drift, and sentinel values (e.g., SOG 102.3 kt, heading 511°, status 15).
3. **Density Noise vs. Malicious Anomalies**: Vessels lingering in holding areas or drifting with tidal currents generate dense clusters that naive detectors misclassify as anomalous, while actual kinematic deviations (e.g., sudden dark transponder gaps, abnormal loitering outside designated anchorages) are obscured.
4. **Lack of Explainability**: "Black box" anomaly detection fails maritime operators who require transparent, physical justifications for alerts.

---

## 4. Research Objectives

### Primary Research Objective (RQ1)
Investigate the measured runtime, query latency, and memory performance of an **H3-accelerated Spatiotemporal DBSCAN (ST-DBSCAN)** candidate-generation engine compared against a reference **Haversine BallTree** baseline. The objective requires verifying whether discrete hexagonal partitioning achieves measurable indexing and query efficiency while guaranteeing 100% eligible-neighbor recall on defined correctness tests (acknowledging that this performance and full correctness guarantee have not yet been empirically achieved and remain subject to experimental validation).

### Secondary Research Objective (RQ2)
Evaluate whether a **lightweight, trajectory-aware rule-based scoring engine** (augmented conditionally with Isolation Forest) can reliably surface kinematic anomalies (drift, loitering, speed discontinuities) with significantly lower false-positive rates than point-density outlier baselines.

---

## 5. Planned MVP Features

- **Validated AIS Ingestion**: Deterministic Parquet-based ingestion with explicit sentinel masking, coordinate bounds validation, and chronological trajectory sorting.
- **Dual Spatiotemporal Clustering Engines**:
  - *Baseline*: `scikit-learn` BallTree utilizing exact haversine metric.
  - *Candidate-Accelerated*: Uber H3 discrete global grid index with correctness-preserving neighbor expansion.
- **Vessel-Aware Anchorage Analytics**: Stay-point extraction, port berth exclusion, and true unique-vessel dwell tracking (distinguishing vessel count from raw ping density).
- **Explainable Anomaly Scoring**: Multi-factor kinematic scoring (speed jump, turn-rate anomalies, dark transponder gaps, anchorage boundary violations).
- **Read-Only API & Map Inspector**: Lightweight FastAPI service delivering precomputed GeoJSON layers to an interactive Leaflet/MapLibre browser dashboard.

---

## 6. High-Level Architecture

AegisMar is designed as a **Python-first modular monolith** prioritizing scientific correctness, local execution, and reproducibility without distributed systems overhead:

```mermaid
flowchart TD
    subgraph Data ["Data Layer (Local Storage)"]
        Raw["Raw AIS (CSV/Parquet)"] --> Ingest["Ingestion & Quality Engine"]
        Ingest --> CleanParquet[("Cleaned Parquet Partitions")]
    end

    subgraph Core ["Core Analytics Engine (Modular Monolith)"]
        CleanParquet --> TrajPrep["Trajectory Assembly"]
        TrajPrep --> ClusterBaseline["BallTree ST-DBSCAN (Baseline)"]
        TrajPrep --> ClusterH3["H3 ST-DBSCAN (Candidate Accelerated)"]
        ClusterH3 --> StayPoint["Stay-Point & Anchorage Engine"]
        TrajPrep --> AnomalyEng["Kinematic Anomaly Detector"]
    end

    subgraph Serving ["Serving & Presentation Layer"]
        StayPoint --> DuckDBStore[("DuckDB / GeoJSON Store")]
        AnomalyEng --> DuckDBStore
        DuckDBStore --> FastAPISvc["Read-Only FastAPI Service"]
        FastAPISvc --> MapDashboard["Geospatial Map Dashboard"]
    end
```

---

## 7. Technology Stack

| Component | Current Status | Planned Technology | Selection Justification |
|---|---|---|---|
| **Runtime** | Python 3.11.9 | Python 3.11.9 | Binary wheel compatibility on Windows for C-extensions (`h3`, `scikit-learn`). |
| **Package Manager**| `uv` (0.11.x) | `uv` | High performance, reproducible dependency locking (`uv.lock`), PEP 621 compliant. |
| **Build Backend** | `hatchling` | `hatchling` | Standard, modern PEP 517 build backend. |
| **Quality Gates** | `ruff`, `mypy`, `pytest` | `ruff`, `mypy`, `pytest` | Sub-second linting/formatting, strict static typing, rigorous unit testing. |
| **Data Engine** | Implemented (`pyarrow`); `duckdb` planned (W6) | `duckdb`, `pyarrow` | Columnar Parquet I/O (`zstd`) implemented via PyArrow; in-process DuckDB planned for W6. |
| **Spatial Indexing**| BallTree Implemented (W2-01); H3 Planned (W3) | `numpy`, `scikit-learn`, `h3` (4.x) | Haversine `BallTree` reference baseline verified; Uber H3 deferred to Week 3. |
| **Web Service** | *Planned (W6)* | `fastapi`, `uvicorn` | Lightweight, asynchronous, typed, read-only HTTP endpoints serving GeoJSON. |
| **Geospatial UI** | *Planned (W7)* | Vanilla JS + Leaflet / MapLibre | Zero-build-step interactive geospatial visualization. |

---

## 8. Eight-Week Development Roadmap

The project is structured around an estimated 200 hours (25 h/week) across 8 milestone weeks:

- **Week 1**: Repository initialization, doc tree, AIS data ingestion, and sentinel masking.
- **Week 2**: Ingestion hardening, Haversine `BallTree` reference ST-DBSCAN, and independent brute-force oracle verification.
- **Week 3**: Uber H3 candidate optimization, boundary/pentagon completeness testing, and comparative H1 benchmarks.
- **Week 4**: Vessel-aware stay-point extraction and anchorage dwell analysis (with berth exclusion).
- **Week 5**: Trajectory anomaly detection engine (rule-based kinematics and optional Isolation Forest).
- **Week 6**: Analytical storage integration (DuckDB/Parquet) and read-only FastAPI service.
- **Week 7**: Geospatial dashboard implementation and end-to-end analytical validation.
- **Week 8**: Performance benchmarking, reproducibility report, and research paper completion.

---

## 9. Current Milestones & Progress

| Milestone | Title | Target Week | Status |
|---|---|---|---|
| **W1-01** | Repository Initialization & Documentation Foundation | Week 1 | **Completed** |
| **W1-02A**| NOAA AIS Dataset Selection & Schema Investigation | Week 1 | **Completed** |
| **W1-02B**| AIS Ingestion, Data Quality & Parquet Storage | Week 1 | **Completed** |
| **W2-01** | Ingestion Corrections, BallTree ST-DBSCAN & Brute-Force Oracle | Week 2 | **Completed** |
| **W3-01** | H3 Candidate Optimization & Completeness Verification | Week 3 | Planned |
| **W3-02** | Comparative H1 Benchmarking (BallTree vs. H3) | Week 3 | Planned |
| **W4-01** | Stay-Point Extraction & Anchorage Dwell Identification | Week 4 | Planned |
| **W5-01** | Kinematic Anomaly Scoring & Evaluation Engine | Week 5 | Planned |
| **W6-01** | DuckDB Analytical Query Layer & Read-Only API | Week 6 | Planned |
| **W7-01** | Geospatial Incident Dashboard & End-to-End Demo | Week 7 | Planned |
| **W8-01** | Benchmark Execution, Reproducibility & Research Report | Week 8 | Planned |

---

## 10. Environment Setup & CLI Usage

### Prerequisites
- Windows 10/11 (or Linux/macOS)
- Git (>= 2.40)
- Python 3.11.9
- `uv` (>= 0.11.0)

### Quickstart Setup
```powershell
# Clone repository
git clone https://github.com/NipunaBhanuka18/Project-AegisMar.git
cd "Project-AegisMar"

# Synchronize virtual environment with locked dependencies
uv sync --locked

# Run test suite and static quality gates
uv run pytest -v
uv run pytest --cov=aegismar --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

### AIS Data Ingestion & Reference Clustering CLI
```powershell
# Ingest raw/regional AIS CSV into canonical Parquet storage (in-memory batch pipeline)
uv run python -m aegismar ingest --input data/raw/sample_lalb_20250101.csv --output data/processed/lalb_20250101

# Ingest with custom implied speed threshold (knots) and overwrite permission
uv run python -m aegismar ingest -i data/raw/sample_lalb_20250101.csv -o data/processed/lalb_20250101 -s 50.0 --overwrite

# Run reference Haversine BallTree ST-DBSCAN on cleaned AIS Parquet
uv run python -m aegismar cluster --input data/processed/lalb_20250101/cleaned_ais.parquet --output experiments/outputs/w2_01_lalb_balltree --eps-spatial-m 300 --eps-temporal-s 900 --min-samples 5 --overwrite
```

---

## 11. Research Methodology Overview

1. **Independent Verification Oracle**: A brute-force $O(N^2)$ geodesic distance comparator serves as the ground-truth test oracle in automated unit testing.
2. **Correctness Guarantee**: H3 candidate neighbor sets must prove zero false negatives against the BallTree reference ($\text{Recall} = 1.0$).
3. **Vessel-Aware Metrics**: Anchorage utilization and dwell times are computed per unique vessel (`MMSI`), avoiding raw ping density bias.
4. **Leakage-Free Anomaly Evaluation**: Trajectory anomaly detectors are evaluated using chronological and vessel-disjoint splits with physically plausible synthetic perturbations.

---

## 12. Documentation Index

The repository maintains comprehensive, verified technical documentation:

- **Project Definition & Requirements**:
  - [Project Vision](docs/01-project/vision.md)
  - [Business Requirements Specification (BRS Draft v2.1)](docs/01-project/brs.md)
  - [Software Requirements Specification (SRS Draft v2.1)](docs/01-project/srs.md)
  - [Scope & Boundary Definition](docs/01-project/scope.md)
  - [Eight-Week Roadmap](docs/01-project/roadmap.md)
- **Architecture & Technical Decisions**:
  - [System Architecture](docs/02-architecture/system-architecture.md)
  - [ADR-001: Modular Monolith vs. Distributed Microservices](docs/02-architecture/decisions/ADR-001-modular-monolith.md)
- **Research & Evaluation**:
  - [Research Plan & Hypotheses](docs/03-research/research-plan.md)
  - [Scientific Evaluation Protocol](docs/03-research/evaluation-protocol.md)
  - [Dataset Management & Quality Protocol](docs/03-research/datasets.md)
- **Development & Verification**:
  - [Milestone Schedule & Tracking](docs/04-development/milestones.md)
  - [Development Log](docs/04-development/development-log.md)
  - [Testing & Quality Assurance Strategy](docs/04-development/testing-strategy.md)
- **Guides**:
  - [Installation & Environment Setup Guide](docs/05-guides/installation.md)
- **Release History**:
  - [Project Changelog](CHANGELOG.md)

---

## 13. Scope Exclusions & Known Limitations

To ensure successful delivery within the 8-week solo developer capacity, the following features are strictly out-of-scope for the MVP:
- **No Real-Time Streaming or Replay**: Real-time NMEA stream ingestion or playback servers are excluded.
- **No Complex Distributed Infrastructure**: No PostgreSQL/PostGIS, Apache Kafka, Kubernetes, or microservices.
- **No Authentication / Authorization**: The MVP is designed strictly as a localhost single-user tool.
- **No Unverifiable Dark-Vessel Guarantees**: AIS signal gaps are flagged as kinematic/transponder gaps; no unverified claims of "hostile intent" or "sanction evasion" will be made.

---

<a id="license-and-attribution"></a>
## 14. License & Attribution

- **License**: Pending formal selection. All rights currently reserved.
- **Author**: Solo Undergraduate AI Researcher & Software Engineer.
- **Academic Context**: Undergraduate AI Research & Engineering Capstone Project.

