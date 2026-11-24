# Project Vision: AegisMar

> **Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**

**Document Version:** 2.2  
**Status:** Approved Platform Architecture Baseline  
**Last Updated:** 2026-11-22  
**Research Tracks & Collaboration:**  
- **Track A (Clustering & Platform Lead):** NipunaBhanuka18  
- **Track B (Vessel Behavior ML):** Kishakya *(Track Lead)*  

---

## 1. Executive Summary

Maritime transportation accounts for over 80% of global trade volume. Modern maritime operations rely fundamentally on the Automatic Identification System (AIS) for situational awareness, collision avoidance, and maritime domain monitoring. However, port authorities, maritime researchers, and domain analysts face an overwhelming deluge of high-frequency, noisy spatial telemetry that degrades the effectiveness of traditional analytical tools.

**Project AegisMar** is an undergraduate AI research and software engineering platform designed to deliver an explainable, computationally efficient, and scientifically reproducible maritime intelligence system. AegisMar bridges the gap between raw, imperfect AIS broadcasts and actionable maritime insights through a collaborative, multi-engine architecture addressing two central challenges:
1. **Computational efficiency and correctness in spatiotemporal traffic clustering** (evaluating H3 discrete hexagonal spatial partitioning against a geodesic Haversine BallTree baseline).
2. **Transparent, physically interpretable vessel behavior anomaly detection** (distinguishing ordinary operational density noise from genuine kinematic abnormalities using rule-based scoring and unsupervised learning).

---

## 2. Problem Statement & Operational Context

### 2.1 The Data Dilemma in Maritime Telemetry
- **Sheer Volume & Irregular Frequency**: AIS stations receive millions of messages daily. Broadcast rates fluctuate dynamically from 2 seconds (vessels underway altering course) to 3 minutes (vessels anchored or moored).
- **Sensor Corruption & Missing Sentinels**: Real-world AIS records frequently contain invalid coordinates, missing MMSI/IMO identifiers, dead-reckoning nulls $(0.0, 0.0)$, and special ITU/NMEA sentinel values (e.g., Speed Over Ground of `102.3` knots indicating unavailable data, Heading `511` indicating no heading sensor).
- **Spurious Outliers vs. High-Density Dwell**: Vessels dwelling in designated anchorage basins or holding lanes create hyper-dense clusters. Standard distance-based anomaly detectors frequently misclassify these legitimate operational clusters as anomalies while failing to detect subtle, low-density kinematic deviations in open transit lanes.

### 2.2 The Need for Explainable Maritime Analytics
Existing machine learning anomaly detection frameworks in the maritime literature frequently act as "black boxes." When an alert fires, port operators cannot determine whether the alert was triggered by sensor noise, GPS multipath errors, unexpected tidal drift, or deliberate transponder manipulation. AegisMar prioritizes explainable kinematic rule scoring alongside transparent spatiotemporal clustering.

---

## 3. Core Value Proposition

AegisMar delivers value across three analytical pillars:

1. **Scientifically Rigorous Spatiotemporal Clustering**:
   - Implements a verified **Haversine BallTree ST-DBSCAN** baseline algorithm.
   - Introduces an **H3-accelerated candidate generation** mechanism that reduces computational overhead while guaranteeing zero loss of eligible spatial neighbors ($\ge 99.9\%$ empirical recall verified against a brute-force oracle).
2. **True Vessel-Aware Anchorage Intelligence**:
   - Extracts vessel stay-points based on spatial displacement and temporal duration thresholds.
   - Incorporates spatial berth exclusions to distinguish vessels docked at berths from vessels waiting at anchor.
   - Computes anchorage utilization based on distinct vessel counts (`MMSI`) rather than raw ping counts, eliminating ping-rate bias.
3. **Multi-Factor Kinematic Anomaly Detection**:
   - Detects physically implausible velocity jumps ($> \Delta v_{\text{max}}$).
   - Identifies abnormal rate of turn ($\text{ROT}$) and course deviations without speed change (drifting).
   - Flags suspicious transponder outages (AIS gaps exceeding expected reporting intervals in active channels).
   - Provides human-interpretable score breakdowns for every detected incident.

---

## 4. Target Users & Stakeholders

| Stakeholder | Primary Need | AegisMar Capability |
|---|---|---|
| **Maritime Researchers** | Reproducible baselines and verifiable clustering performance. | Open-source Python modular monolith, deterministic benchmarks, and synthetic test oracles. |
| **Port Authorities & VTS Operators** | Accurate anchorage dwell times and berth congestion metrics. | Vessel-aware stay-point extraction and berth polygon exclusion. |
| **Maritime Domain Analysts** | Explainable alerts on abnormal vessel maneuvers and signal dropouts. | Trajectory-level kinematic scoring with transparent factor breakdown. |

---

## 5. Strategic Scope & Non-Goals

To maintain high research rigor and engineering quality during an eight-week solo development timeline (200 hours), AegisMar establishes strict operational boundaries:
- **Historical Analysis Focus**: AegisMar operates on historical AIS batches (e.g., NOAA AIS extracts in Parquet/DuckDB format). Real-time NMEA streaming and WebSocket replay are deferred.
- **Localhost Modular Monolith**: All processing, analytical querying, and map serving occur locally without cloud orchestration, Kubernetes, or distributed message queues.
- **Factual Anomaly Identification**: Anomalies represent physical and kinematic deviations from expected maritime behavior; AegisMar does not attempt unverified legal or military assertions regarding "hostile intent" or "dark fleet sanctions evasion."

---

## 6. Long-Term Vision Beyond the MVP

Following successful delivery and academic evaluation of the 8-week MVP, AegisMar envisions:
- Expanding H3-accelerated clustering across multi-port coastal corridors.
- Incorporating environmental co-variates (bathymetry, tidal currents, and weather) into the anomaly scoring engine.
- Packaging the analytical core into an offline-first containerized analysis appliance for coastal surveillance teams.

