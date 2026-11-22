# ADR-010: Decoupled Parallel Behavioral ML Workstream with Contract-Based Integration

**Status:** Accepted  
**Date:** 2026-11-22  
**Deciders:** NipunaBhanuka18 (Project Lead) & Kishakya (Proposed ML Collaborator, agreed in principle)  
**Technical Scope:** Collaborative System Architecture & Workstream Decoupling  

---

## 1. Context and Problem Statement

Project AegisMar expanded from a solo initiative into a collaborative research project between two AI undergraduate researchers:
- **NipunaBhanuka18**: Focusing on AIS data engineering, spatial indexing, BallTree/H3 clustering, and stay-point/anchorage intelligence (Track A).
- **Kishakya**: Focusing on vessel trajectory feature engineering, explainable rule-based anomaly scoring, and unsupervised machine learning models (Track B).

We needed an architectural pattern that allows Kishakya to iterate rapidly, conduct machine learning experiments, and evaluate candidate models without blocking or being blocked by Track A's clustering milestones, while ensuring seamless final integration into the shared DuckDB storage layer and FastAPI/web map product.

---

## 2. Considered Alternatives

### Alternative A: Monolithic Tight Coupling
- **Concept:** Force the trajectory anomaly engine to depend directly on spatial cluster outputs (e.g. running anomaly detection only on clustered anchorage points or embedding cluster labels into anomaly features).
- **Evaluation at Decision Time (2026-11-22):** Evaluated and rejected. Tightly coupling anomaly detection to clustering creates a sequential blocking dependency: Kishakya could not begin anomaly modeling until NipunaBhanuka18 finishes H3 and stay-point algorithms. Furthermore, behavioral anomalies occur predominantly on vessels *underway in open fairways*, not inside static dwell clusters.

### Alternative B: Disconnected Fork / Parallel Project
- **Concept:** Kishakya works on a completely separate repository with independent schemas and independent presentation tools.
- **Evaluation at Decision Time (2026-11-22):** Evaluated and rejected. Defeats the project's vision of an integrated maritime domain awareness platform. Duplicates data engineering effort and prevents joint presentation on the map inspector.

---

## 3. Decision

We establish a **Decoupled Parallel Workstream Architecture** governed by two strict versioned data contracts:

1. **Canonical Ingestion Input Contract**: Both tracks consume the identical cleaned Parquet dataset (`cleaned_ais.parquet`) adhering to the 19-column PyArrow schema. Track B reads trajectory observations directly from Parquet without waiting for clustering outputs.
2. **Provisional Vessel Anomaly Output Contract (`vessel_anomaly_v1`)**: Track B emits incident findings in a standardized GeoJSON FeatureCollection format (`incident_id`, `mmsi`, timestamps, observation source rows, model id/version, $[0.0, 1.0]$ non-probabilistic anomaly index, physical factor decomposition, and data quality context).
3. **Module Isolation**: Track B code resides exclusively under `src/aegismar/anomaly/`, tests in `tests/unit/test_anomaly.py`, and experiment outputs in `experiments/outputs/anomaly/`.
4. **Shared Serving Layer**: The in-process DuckDB storage layer (Week 6) and FastAPI service consume both cluster polygons and anomaly GeoJSON features via read-only file scans, presenting both on the shared map interface (Week 7).

---

## 4. Rationale

1. **Zero Blocker Dependency**: Both researchers can code, test, and run experiments simultaneously on their own branches (`feat/clu-...` vs `feat/ml-...`).
2. **Contract-Based Interoperability**: As long as the ML subsystem adheres to the input and output schemas, Kishakya has complete freedom to change model architectures (Isolation Forest vs LOF vs Autoencoders) without breaking the core platform.
3. **Preservation of Solo Baseline**: NipunaBhanuka18's 8-week clustering roadmap remains intact as the project's architectural backbone.

---

## 5. Consequences and Trade-offs

### Positive Consequences
- Maximum research autonomy for both collaborators.
- Clean Git history with minimal merge conflicts.
- Clear module ownership boundaries.

### Negative Consequences / Trade-offs
- **Output Schema Coordination Required**: Any change to `vessel_anomaly_v1` requires mutual discussion before modifying the downstream API or UI parsers.
  - *Mitigation:* Documented schema as provisional; schema changes require joint PR approval.

---

## 6. Implementation Status and Evidence Links

- **Status**: Architecture and contracts accepted; documentation baseline established in Milestone DOC-01.
- **Collaboration Plan**: [docs/01-project/collaboration-plan.md](../../01-project/collaboration-plan.md)
- **ML Research Proposal**: [docs/03-research/vessel-behavior-ml.md](../../03-research/vessel-behavior-ml.md)
- **Onboarding Guide**: [docs/05-guides/ml-research-onboarding.md](../../05-guides/ml-research-onboarding.md)

---

## 7. Known Limitations

- The ML anomaly model is not yet implemented; the `vessel_anomaly_v1` schema is provisional until Kishakya reviews and confirms trajectory windowing structures.

---

## 8. Conditions for Revisiting

- The two researchers agree on a structural revision to the anomaly output contract during Milestone ML-02.
