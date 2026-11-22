# ADR-002: Historical AIS Batch Telemetry as Primary Research Data Source

**Status:** Accepted  
**Date:** 2026-11-14  
**Deciders:** NipunaBhanuka18 (Project Lead)  
**Technical Scope:** Ingestion Subsystem & Research Scope  

---

## 1. Context and Problem Statement

Maritime domain intelligence research requires realistic spatial vessel telemetry. We evaluated whether Project AegisMar should consume live real-time AIS streams (e.g., NMEA over TCP/UDP or commercial WebSocket feeds) or operate on standardized historical batch extracts (e.g., NOAA Marine Cadastre AIS).

The research objective requires deterministic algorithmic benchmarking of spatiotemporal clustering and trajectory anomaly detection. Live streaming introduces network volatility, missing data irreproducibility, and complex socket-handling dependencies.

---

## 2. Considered Alternatives

### Alternative A: Live Real-Time NMEA AIS Streaming
- **Concept:** Connect to live AIS receiver streams via TCP/UDP sockets (e.g., AISHub, MarineTraffic API, or local RTL-SDR receiver), parse raw NMEA sentences dynamically, and perform online anomaly detection.
- **Evaluation at Decision Time (2026-11-14):** Evaluated and rejected. Live streaming introduces network dropouts, non-repeatable telemetry sequences, commercial API rate limits or subscription costs, and requires heavy stateful streaming engines (Kafka/Flink). It directly conflicts with the primary research requirement of reproducible, identical benchmark runs across algorithm implementations.

### Alternative B: Synthetic Maritime Trajectory Simulators (Retrospective Alternative, 2026-11-14)
- **Concept:** Generate completely synthetic vessel trajectories using kinematic agent simulators.
- **Evaluation at Decision Time:** Evaluated and rejected as primary data source. Fully synthetic traffic lacks the subtle real-world sensor artifacts, GPS multipath jitter, high-density holding patterns, and authentic maritime behavior needed to validate practical domain utility.

---

## 3. Decision

We will utilize **authoritative historical daily AIS batch extracts from the NOAA Marine Cadastre** (specifically 2025+ daily extracts in `.csv.zst` format) as the primary research and development data source.

Specific study regions (e.g., San Pedro Bay, Los Angeles / Long Beach, CA) are extracted via bounded geographic bounding boxes into standardized regional CSV samples for processing.

---

## 4. Rationale

1. **Academic Reproducibility**: Historical batches are immutable. Anyone can download the identical 24-hour extract from NOAA Azure Blob storage, verify its cryptographic hash, and reproduce benchmark results bit-for-bit.
2. **Authentic Sensor Noise**: Real NOAA AIS telemetry contains genuine GPS jitter, transmitter sentinel values (`102.3`, `511`, `15`), variable broadcast frequencies, and real traffic density distributions.
3. **Zero Network Dependency during Execution**: The complete analytical pipeline runs offline on local storage without internet egress or API keys.
4. **Public Domain Licensing**: NOAA AIS data is in the public domain (U.S. Government Work / CC0 equivalent), allowing unrestricted academic research and artifact publication.

---

## 5. Consequences and Trade-offs

### Positive Consequences
- Deterministic, repeatable test and benchmark executions.
- Cryptographic traceability from raw bytes to cleaned Parquet (`manifest.json` SHA-256 recording).
- Complete isolation from external network failures or API rate limits.

### Negative Consequences / Trade-offs
- **No Real-Time Operational Alerting**: The MVP cannot alert on vessels currently underway in live waters.
  - *Mitigation:* The batch architecture establishes the mathematical and algorithmic foundation; real-time streaming wrappers can be built around the core engine in post-MVP work.
- **Static Temporal Scope**: Initial experiments evaluate single-day slices (e.g., 2025-01-01).
  - *Mitigation:* Multi-day concatenation is supported by the ingestion pipeline schema.

---

## 6. Implementation Status and Evidence Links

- **Status**: Implemented and verified in Milestone W1-02A and W1-02B.
- **Documentation**: [docs/03-research/datasets.md](../../03-research/datasets.md)
- **Raw Artifacts**: `data/raw/ais-2025-01-01.csv.zst` (SHA-256 `36c07f4abad24f86fdd2ae8722b5a1d9422f3a223efc3482a568665275bdde53`), `sample_lalb_20250101.csv` (143,156 raw records).
- **Validation Manifest**: `data/processed/lalb_20250101/manifest.json`.

---

## 7. Known Limitations

- Historical AIS does not provide ground-truth coast guard enforcement labels for illicit vessel behavior; behavioral anomalies must be evaluated via physical kinematic laws and controlled synthetic perturbation injection.

---

## 8. Conditions for Revisiting

- Post-MVP extension to coastal monitoring stations requiring live NMEA 0183/2000 serial stream decoding.
