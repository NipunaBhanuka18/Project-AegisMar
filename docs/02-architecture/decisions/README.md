# Architecture Decision Records (ADRs)

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**

This directory contains the formal Architecture Decision Records (ADRs) documenting critical design choices, considered alternatives, evidence bases, and known tradeoffs for Project AegisMar.

Each record adheres to an evidence-backed format specifying the decision context, genuine historical or retrospective alternatives, rationales, implementation statuses, verification evidence, known limitations, and conditions that would justify revisiting the decision.

---

## Architectural Decision Register

| ADR ID | Title | Status | Date | Primary Scope | Implementation Status |
|---|---|---|---|---|---|
| [ADR-001](ADR-001-modular-monolith.md) | Modular Monolith Architecture for Solo/Collaborative AI Research Platform | **Accepted** | 2026-11-14 (updated 2026-11-22) | System Architecture | Implemented & Verified |
| [ADR-002](ADR-002-historical-ais-data-source.md) | Historical AIS Batch Telemetry as Primary Research Data Source | **Accepted** | 2026-11-14 | Ingestion & Research | Implemented & Verified |
| [ADR-003](ADR-003-canonical-schema-and-quality-flags.md) | Canonical PyArrow Schema with Explicit Quality Flags & Sentinel Nullification | **Accepted** | 2026-11-14 (hardened 2026-11-18) | Data Model | Implemented & Verified |
| [ADR-004](ADR-004-parquet-columnar-storage.md) | Apache Parquet Columnar Storage with Manifest Verification | **Accepted** | 2026-11-14 | Storage Layer | Implemented & Verified |
| [ADR-005](ADR-005-balltree-haversine-neighbor-search.md) | Scikit-Learn BallTree with Haversine Metric as Reference Neighbor Search Engine | **Accepted** | 2026-11-18 | Spatial Indexing | Implemented & Verified |
| [ADR-006](ADR-006-spatiotemporal-neighborhood-semantics.md) | Strict Dual-Threshold Spatiotemporal Neighborhood Semantics in Integer Microseconds | **Accepted** | 2026-11-18 | Clustering Core | Implemented & Verified |
| [ADR-007](ADR-007-deterministic-core-first-st-dbscan.md) | Deterministic Core-First Labeling Policy for ST-DBSCAN (`stdbscan-core-first-v1.0`) | **Accepted** | 2026-11-18 | Clustering Algorithm | Implemented & Verified |
| [ADR-008](ADR-008-independent-brute-force-test-oracle.md) | Independent $O(N^2)$ Brute-Force Geodesic Test Oracle for Verification | **Accepted** | 2026-11-18 | Quality Assurance | Implemented & Verified |
| [ADR-009](ADR-009-planned-h3-candidate-acceleration.md) | Uber H3 Discrete Hexagonal Grid as Correctness-Preserving Candidate Neighbor Generator | **Accepted (Planned)** | 2026-11-14 | Research Engine | Planned (Week 3) |
| [ADR-010](ADR-010-separate-integrated-behavioral-ml-workstream.md) | Decoupled Parallel Behavioral ML Workstream with Contract-Based Integration | **Accepted** | 2026-11-22 | Collaboration Architecture | Architecture Accepted |
| [ADR-011](ADR-011-dataset-provenance-and-content-fingerprinting.md) | Dataset Provenance via Authoritative Manifest and Versioned Logical Content Fingerprints (`aegismar-logical-v1`) | **Accepted** | 2026-11-25 | Data Layer & Provenance | Implemented (W3-02A, pending review) |
