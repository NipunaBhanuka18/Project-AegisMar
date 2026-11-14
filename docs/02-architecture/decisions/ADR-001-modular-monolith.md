# ADR-001: Modular Monolith Architecture for 8-Week Solo Research MVP

**Status:** Accepted  
**Date:** 2026-11-14  
**Deciders:** Solo Undergraduate AI Engineer / Project AegisMar Author  
**Technical Scope:** Entire System Architecture  

---

## 1. Context and Problem Statement

Project AegisMar is an eight-week solo undergraduate research and software engineering initiative (planned for ~200 hours of development capacity). The project must deliver:
1. A scientifically correct, mathematically verified spatiotemporal clustering pipeline comparing H3 spatial indexing against a BallTree baseline.
2. A vessel-aware stay-point and anchorage analysis subsystem.
3. A lightweight trajectory anomaly detection engine.
4. An analytical storage and query layer.
5. A minimal web-based map interface.

Modern distributed architectures often advocate for microservices, message streaming backbones (e.g., Apache Kafka), and distributed spatial databases (e.g., PostgreSQL with PostGIS). We must decide on the architectural pattern that maximizes scientific rigor, engineering productivity, and reproducibility while completely avoiding infrastructure overhead that could jeopardize the 8-week delivery deadline.

---

## 2. Decision

We will build Project AegisMar as a **Python-first Modular Monolith** coupled with **in-process columnar analytical storage (Apache Parquet + DuckDB)**.

All application logic—ingestion, spatial indexing, clustering, anomaly detection, analytical storage, and the thin read-only HTTP API—will reside within a single codebase under `src/aegismar/`. The system will communicate internally via typed Python function calls and structured dataclasses, with persistent data flowing through local Parquet files.

---

## 3. Alternatives Considered and Rejected

### Alternative A: Distributed Microservices (Docker Compose / Kubernetes)
- **Concept:** Separate services for Ingestion Service, Clustering Service, Anomaly Service, Database Service, and Gateway API, communicating over gRPC or HTTP REST.
- **Reason for Rejection:**
  - Enormous operational overhead: managing multiple containers, service discovery, distributed logging, network serialization/deserialization latency, and multi-service deployment configurations.
  - Serialization bottleneck: Transmitting hundreds of thousands of multi-dimensional AIS trajectory records over network sockets between microservices incurs massive performance penalties compared to in-memory zero-copy Arrow memory buffers.
  - Incompatible with solo undergraduate capacity: debugging distributed systems and networking failures would consume precious hours needed for scientific clustering correctness and mathematical evaluation.

### Alternative B: Enterprise Spatial Database (PostgreSQL + PostGIS + Kafka)
- **Concept:** Ingest streaming AIS records into an Apache Kafka topic, consume into a PostgreSQL/PostGIS database, and execute spatial queries using PostGIS functions (`ST_DWithin`, `ST_ClusterDBSCAN`).
- **Reason for Rejection:**
  - Heavy external dependencies: Requires installing, maintaining, and migrating a local or remote PostgreSQL server and JVM-based Kafka broker.
  - Reduced algorithm controllability: Offloading clustering to PostGIS built-ins prevents fine-grained control and instrumentation of internal spatial neighbor candidate generation, which is the primary research contribution of this thesis (H3 vs BallTree neighbor candidate performance).
  - Reproducibility barrier: Reviewers or evaluators would have to configure external relational databases, credentials, and port mappings rather than simply running `uv sync && uv run pytest`.

---

## 4. Consequences and Trade-offs

### Positive Consequences
- **Zero Infrastructure Friction**: Developers and evaluators can clone the repository, run `uv sync`, and immediately execute tests, pipelines, and benchmarks without running Docker daemons or database servers.
- **Extreme Analytical Performance**: Utilizing in-memory PyArrow buffers and in-process DuckDB queries eliminates IPC serialization overhead and delivers sub-second analytical execution on local SSDs.
- **Direct Research Instrumentation**: Algorithmic components have direct in-memory access to spatial candidate sets, geodesic oracles, and timing counters, enabling precise scientific measurement of indexing overhead, memory footprint, and neighborhood recall.
- **Clean Cognitive Load**: The solo developer maintains full mental context of the codebase within a single IDE workspace.

### Negative Consequences / Trade-offs
- **Single-Node Resource Limits**: The system is bound to the RAM and CPU limits of the host machine (e.g., cannot automatically scale to a 10-node cluster).
  - *Mitigation:* The 8-week scope targets regional coastal sectors (e.g., Delaware Bay or Tampa Bay with 10k–500k pings), well within the memory capacity of a standard 16 GB workstation when utilizing columnar Parquet streaming.
- **Monolithic Process Failure**: A crash in one module during an end-to-end pipeline run halts the process.
  - *Mitigation:* The pipeline is broken into decoupled CLI stages that persist intermediate state to disk in Parquet format, allowing pipeline resumption without reprocessing.

---

## 5. Compliance and Review

This architectural decision is permanent for the 8-week MVP lifecycle. Any proposal to introduce external databases, message queues, or distributed services must be formally rejected under the approved project scope.

