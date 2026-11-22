# ADR-001: Modular Monolith Architecture for Solo/Collaborative AI Research Platform

**Status:** Accepted  
**Date:** 2026-11-14 (Updated: 2026-11-22 for collaborative research track model)  
**Deciders:** NipunaBhanuka18 (Project Lead & Author); reviewed for collaboration with Kishakya  
**Technical Scope:** Entire System Architecture  

---

## 1. Context and Problem Statement

Project AegisMar is an undergraduate AI research and software engineering initiative designed to evaluate spatiotemporal clustering algorithms and trajectory behavior anomaly detection on maritime Automatic Identification System (AIS) telemetry. The project operates within bounded undergraduate capacity (~200 hours across an 8-week lifecycle baseline) and has expanded from a solo initiative into a collaboration between two researchers leading complementary technical workstreams.

We needed an architectural pattern that maximizes scientific rigor, engineering productivity, local reproducibility, and test execution speed, while completely avoiding operational and distributed infrastructure overhead that would jeopardize deliverability.

---

## 2. Considered Alternatives

### Alternative A: Distributed Microservices (Docker Compose / Kubernetes)
- **Concept:** Separate containerized services for Ingestion, Clustering, Anomaly Detection, Database, and Web API, communicating over gRPC or HTTP REST.
- **Evaluation at Decision Time (2026-11-14):** Evaluated and rejected. Transmitting hundreds of thousands of multi-dimensional AIS observations across network sockets incurs substantial serialization/deserialization and inter-process communication overhead compared to shared in-memory Arrow buffers. Debugging network failures, container networking, and distributed logging would consume developer hours needed for algorithmic correctness.

### Alternative B: Enterprise Spatial Database (PostgreSQL + PostGIS + Kafka)
- **Concept:** Streaming ingestion via Apache Kafka into PostgreSQL/PostGIS, executing queries via `ST_DWithin` and `ST_ClusterDBSCAN`.
- **Evaluation at Decision Time (2026-11-14):** Evaluated and rejected. PostGIS built-in DBSCAN operates as a black box, preventing fine-grained candidate generation instrumentation (which is the core research contribution of comparing H3 vs BallTree). External database dependencies create high reproducibility friction for academic evaluators.

### Alternative C: Multi-Repository Split (Retrospective Alternative, 2026-11-22)
- **Concept:** When collaboration was established, split the repository into two separate Git repositories: one for spatial clustering and one for ML anomaly detection.
- **Evaluation on 2026-11-22:** Considered and rejected. Splitting repositories would duplicate data engineering code, require complex cross-repo package publishing or submodules, create schema drift, and hinder joint end-to-end integration into the final FastAPI/map dashboard product.

---

## 3. Decision

We will construct Project AegisMar as a **Python-first Modular Monolith** coupled with **local columnar analytical storage (Apache Parquet + DuckDB)**.

All application logic—ingestion, spatial indexing, clustering, trajectory anomaly detection, analytical storage, and the thin read-only HTTP API—resides within a single unified codebase under `src/aegismar/`. Internal communication occurs via typed Python interfaces and structured dataclasses, with persistent analytical state flowing through local Parquet files.

---

## 4. Rationale

1. **Zero Infrastructure Friction**: Anyone can clone the repository, run `uv sync --locked`, and immediately execute tests, pipelines, and benchmarks without running Docker daemons or configuring database servers.
2. **Extreme Analytical Performance**: Utilizing in-memory PyArrow buffers and in-process DuckDB queries avoids inter-process serialization overhead and delivers sub-second analytical execution on local SSDs.
3. **Direct Research Instrumentation**: Algorithmic components have direct in-memory access to spatial candidate sets, geodesic oracles, and timing counters, enabling precise scientific measurement of indexing overhead, memory footprint, and neighborhood recall.
4. **Clean Cognitive Load**: Both researchers work in a shared, unified workspace with clear internal namespace boundaries (`aegismar.clustering` vs `aegismar.anomaly`).

---

## 5. Consequences and Trade-offs

### Positive Consequences
- Deterministic single-command setup via `uv`.
- Sub-second unit test execution (52 tests currently execute in <2.0 seconds).
- Shared utilities (`CanonicalPing`, geodesic Haversine distance, Parquet loader) are directly reusable without packaging overhead.

### Negative Consequences / Trade-offs
- **Single-Node Resource Limits**: System memory is bound to the host RAM.
  - *Mitigation:* The MVP targets regional coastal sectors (e.g., Los Angeles / Long Beach with ~143k pings), well within the memory capacity of a standard 16 GB workstation.
- **Monolithic Process Failure**: An unhandled exception halts a CLI command.
  - *Mitigation:* CLI pipeline commands are decoupled into standalone batch stages (`ingest`, `cluster`, future `anomalies`) saving intermediate Parquet artifacts to disk.

---

## 6. Implementation Status and Evidence Links

- **Status**: Implemented and verified in Milestones W1-01, W1-02B, and W2-01.
- **Source Code**: [src/aegismar/](../../../src/aegismar/)
- **Configuration**: [pyproject.toml](../../../pyproject.toml)
- **Verification Evidence**: Automated quality gates (52 unit tests, strict Mypy, Ruff) pass cleanly on Python 3.11.9.

---

## 7. Known Limitations

- Does not support distributed clustering across a cluster of nodes.
- High memory usage if attempting nationwide daily AIS datasets (7.3M pings) without chunked partition processing.

---

## 8. Conditions for Revisiting

- Dataset scale expands beyond 5,000,000 observations in a single analytical pass, exceeding single-node RAM.
- Multi-user concurrent write operations are required (the current MVP is strictly single-user, offline, and read-only).
