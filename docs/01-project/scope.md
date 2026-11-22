# Scope & Boundary Definition: AegisMar v2.1

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**

**Document Version:** 2.2  
**Status:** Controlled Scope Baseline & Collaborative Governance  
**Research Tracks & Capacity:**  
- **Track A (Clustering & Platform Lead):** NipunaBhanuka18 (20–30 hours/week, 200 total hours across 8 weeks)  
- **Track B (ML Anomaly Detection):** Kishakya *(proposed collaborator; independent schedule to be agreed)*  
**Lifecycle Baseline:** Eight-Week Research & Engineering MVP with Parallel ML Track  

---

## 1. Scope Governance Principles

To guarantee that Project AegisMar delivers both defensible research contributions and a functioning software engineering artifact, scope is governed across two complementary, decoupled tracks:

1. **Track A (Clustering & Data Platform Lead: NipunaBhanuka18)**: Governed by the intact eight-week solo roadmap (200 hours). Mandatory P1 deliverables focus on the AIS data engineering foundation, BallTree ST-DBSCAN reference engine, Uber H3 candidate optimization, and stay-point/anchorage intelligence.
2. **Track B (Vessel Behavior ML Track: Kishakya, *proposed*)**: Governed as an independent research track focusing on trajectory feature engineering, explainable rule-based scoring, and unsupervised anomaly detection (Isolation Forest / LOF). This track has its own flexible schedule (ML-01 to ML-04) and integrates into the platform strictly via defined data contracts without expanding the mandatory MVP scope of Track A.

All deliverables within each track remain prioritized under three strict tiers:
- **Mandatory (P1)**: Core deliverables required for the undergraduate research thesis, empirical validation, and functional MVP.
- **Conditional (P2)**: High-value secondary capabilities implemented if preceding deliverables meet quality gates ahead of schedule.
- **Deferred (Out of Scope)**: Capabilities exceeding the project constraints, documented to prevent scope creep.

---

## 2. Scope Categorization Matrix

| Component | Scope Tier | Category | Rationale & Success Condition |
|---|---|---|---|
| **AIS Validation & Profiling** | **Mandatory** | Ingestion | Required to prevent sensor sentinels from corrupting spatial clustering and anomaly scoring. |
| **Parquet / Columnar Storage** | **Mandatory** | Data Layer | High-performance, compressed, analytical file format enabling local out-of-core processing. |
| **Haversine BallTree Baseline** | **Mandatory** | Core Research | Ground-truth spatial indexing baseline needed to scientifically benchmark H3 acceleration. |
| **H3 Candidate Generation & Correctness Validation** | **Mandatory** | Core Research | Primary research contribution; must prove $\ge 99.9\%$ neighbor recall against brute force. |
| **Deterministic ST-DBSCAN Engine** | **Mandatory** | Core Research | Required to segment spatiotemporal traffic patterns into clusters and identify noise. |
| **Stay-Point & Anchorage Analysis** | **Mandatory** | Analytics | Extracts vessel stops; groups dwell areas into anchorages using unique vessel metrics. |
| **Berth Polygon Exclusion** | **Mandatory** | Analytics | Necessary to prevent docked terminal vessels from falsely inflating anchorage metrics. |
| **Kinematic Anomaly Scoring** | **Mandatory** | Analytics | Multi-factor rule-based trajectory scoring (speed jump, drift, transponder outage). |
| **Research Evaluation & Benchmarks** | **Mandatory** | Research | Rigorous evaluation measuring runtime, memory, recall, and F1 across dataset scales. |
| **Minimal Map & Incident Inspector** | **Mandatory** | Presentation | Essential for visual verification of clusters, anchorage polygons, and vessel anomalies. |
| **Reproducible Installation (`uv`)** | **Mandatory** | Engineering | Single-command deterministic setup ensuring anyone can verify the research. |
| **Isolation Forest Comparison** | **Conditional** | Analytics | Secondary research baseline comparing machine learning outlier detection to rule-based scoring. |
| **Advanced Incident Review Panel** | **Conditional** | Presentation | Deep-dive trajectory timeline inspector and sub-score drill-down in UI. |
| **Docker Compose Packaging** | **Conditional** | Deployment | Containerized single-node setup for non-Python environments (if time permits in Week 8). |
| **Live AIS Stream Ingestion (NMEA)** | **Deferred** | Ingestion | Real-time UDP/TCP decoding introduces unnecessary network complexity for historical research. |
| **Vessel Track Replay Engine** | **Deferred** | Presentation | Animated temporal playback adds significant frontend overhead without improving research outcomes. |
| **Deep Learning Models (LSTM, Transformers)** | **Deferred** | Analytics | Excessively compute-intensive; lacks physical explainability required for maritime operators. |
| **Global-Scale Monitoring** | **Deferred** | Infrastructure | MVP targets bounded candidate coastal sectors (e.g., Los Angeles / Long Beach or Delaware Bay). |
| **Sanctions & Legal Dark-Vessel Screening** | **Deferred** | Analytics | Requires commercial registry data; unsupported legal assertions must be avoided. |
| **Distributed Stack (PostGIS, Kafka, Spark, K8s)** | **Deferred** | Infrastructure | Violates lightweight modular monolith architecture; introduces severe operational drag. |
| **User Authentication & Cloud Deployment** | **Deferred** | Deployment | Unnecessary for a localhost research prototype and single-analyst workstation tool. |

---

## 3. Scope Change Control Policy

Under no circumstances will features from the **Deferred** category be promoted into the active sprint backlog. If a **Conditional** feature cannot be completed within its designated time window, it will be cleanly documented as future work without impacting the delivery of **Mandatory** milestones.

