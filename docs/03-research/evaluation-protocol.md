# Scientific Evaluation Protocol (Draft)

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**

**Document Version:** 2.1 (Draft)  
**Status:** Controlled Draft Protocol  
**Author:** Solo AI Undergraduate Engineer  
**Scope:** Experimental Benchmark Execution & Quality Assurance  

---

## 1. Protocol Objective

This protocol establishes the scientific testing procedures, data partitioning rules, metric definitions, and verification standards for evaluating Project AegisMar. It ensures that all claims regarding algorithmic speedup, spatial neighborhood correctness, and anomaly detection performance are statistically sound, reproducible, and free of data leakage.

> [!IMPORTANT]
> This document specifies experimental procedures and metric definitions. It contains zero fabricated benchmark results or simulated measurements. Actual empirical observations will be recorded strictly during Milestone Week 8 benchmark runs.

---

## 2. Spatial Indexing & Clustering Evaluation Protocol

### 2.1 Benchmark Dataset Scales
Experiments will evaluate four standardized dataset scales derived from cleaned historical AIS partitions:
1. **Scale S (10,000 pings)**: Rapid verification, parameter sweeps, and unit-level oracle checks.
2. **Scale M (50,000 pings)**: Intermediate density, representing single-day port approach traffic.
3. **Scale L (100,000 pings)**: Primary scientific benchmark scale, representing multi-day coastal traffic.
4. **Scale XL (500,000 pings)** *(Optional/Stress)*: Upper bound stress test for single-workstation memory and runtime limits.

### 2.2 Independent Spatial Oracle & Correctness Verification
To prevent circular reasoning between spatial indexing data structures:
- A standalone, isolated brute-force oracle (`aegismar.spatial.oracle.BruteForceNeighborhoodOracle`, implemented in W2-01 with a default safety cap of $N \le 5{,}000$ to prevent accidental $O(N^2)$ runs on full 143k+ datasets) calculates exact scalar Haversine distances independently of `scikit-learn`/`BallTree`:
  $$d_{\text{haversine}}(p, q) = 2 R_{\text{earth}} \arcsin \left( \sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos \phi_p \cos \phi_q \sin^2\left(\frac{\Delta \lambda}{2}\right)} \right)$$
- The brute-force oracle defines ground-truth spatiotemporal neighbor sets:
  $$N_{\text{oracle}}(p) = \{ q \in D \mid d_{\text{haversine}}(p, q) \le \varepsilon_{\text{spatial}} \;\land\; |t_p - t_q| \le \Delta T_{\text{temporal}} \}$$
- Both the `BallTreeNeighborhoodProvider` (verified in W2-01) and the `H3NeighborhoodProvider` (hardened in W3-01A) are injected into the same deterministic core-first `run_st_dbscan` engine and compared against the oracle across neighborhoods, core/border/noise roles, and final cluster labels.
- In Milestone W3-01A, the H3 engine was hardened under **Option B (Experimental H3 Candidate Acceleration with Observable, Fail-Closed Reference Fallback)**:
  - Candidates are generated via empirical minimum clearance bounds (`compute_safe_k_ring`) evaluated across tested regional cells, high-latitude zones, and pentagons.
  - Undersized user-configured $k$-rings are strictly rejected with `ValueError`.
  - Discrete expansion failures (`grid_disk`) and near-pentagon encounters route to BallTree fallback (with recorded `fallback_reasons`) or raise `RuntimeError` if fallback is disabled. Silent self-cell downgrades are eliminated.
  - The H3 engine achieved $\text{Recall} = 1.0$ (zero missing neighbors) across all 27 unit test fixture categories (including cell boundaries $\delta \le 10\text{ m}$, sub-meter vertex pairs, pentagons, near-pentagons, high latitudes, dateline crossings, and multi-region coordinates) and bit-for-bit identical CSR neighborhood graphs (13,188,256 edges, identical `indptr` and `indices`) on all 143,116 real LA/LB observations against the BallTree reference. Formal comparative performance benchmarking across dataset scales is scheduled for Milestone W3-02.

### 2.3 Benchmark Timing & Memory Procedure
- **Warmup**: 1 warmup pass prior to timing collection to ensure JIT/cache stabilization.
- **Repetitions**: 10 independent trials per dataset scale with deterministic seeds.
- **Measurement Segments**:
  1. **Index Build Time ($T_{\text{build}}$)**: Time to construct BallTree vs. time to compute H3 cell hashes and populate hash buckets.
  2. **Query Latency ($T_{\text{query}}$)**: Time to execute neighborhood candidate queries for all points.
  3. **Exact Pruning Latency ($T_{\text{prune}}$)**: Geodesic distance verification on retrieved candidates.
  4. **Total Algorithm Execution Time ($T_{\text{total}} = T_{\text{build}} + T_{\text{query}} + T_{\text{prune}}$)**.
  5. **Peak Memory Footprint ($\text{RAM}_{\text{peak}}$)**: Measured via Python `tracemalloc` and OS process monitoring (`psutil`).

---

## 3. Trajectory Anomaly Detection Evaluation Protocol

### 3.1 Data Partitioning & Leakage Prevention
To prevent information leakage between historical trajectory baselines and anomaly evaluations:
1. **Chronological Holdout**: The dataset is split chronologically into an initial baseline observation window (e.g., Days 1–14) and an evaluation window (e.g., Days 15–21).
2. **Vessel-Disjoint Holdout**: For machine learning baselines (Isolation Forest), unique vessels (`MMSI`) are strictly segregated into Train and Test partitions ($70\% / 30\%$). No vessel seen in the training partition may appear in the test partition.

### 3.2 Controlled Trajectory Perturbation Methodology
Because authentic maritime incidents in public AIS lack standardized binary labels, evaluation relies on a dual-track strategy:
1. **Unperturbed In-Domain Validation**: Evaluating false positive alarm rates on clean, verified merchant trajectories.
2. **Documented Synthetic Perturbations**: Injecting physically plausible behavioral deviations into held-out clean trajectories with recorded perturbation parameters:
   - **Type A (Kinematic Speed Discontinuity)**: Injecting sudden speed jumps exceeding vessel physical capabilities ($> 20\text{ kt}$ instantaneous delta).
   - **Type B (Abnormal Drifting & Yaw)**: Inducing heading/course divergence ($|COG - HDG| > 60^\circ$ at speed $> 2\text{ kt}$) simulating unpowered drift or towing.
   - **Type C (Coverage Gap / Transponder Manipulation)**: Simulating transponder blackout intervals ($\Delta t \in [30\text{ min}, 4\text{ hours}]$) inside active fairways followed by discontinuous reappearance.

### 3.3 Anomaly Evaluation Metrics
- **Binary Classification Metrics**: Precision ($P$), Recall ($R$), and $F_1$-score evaluated at optimal $F_1$ decision threshold:
  $$F_1 = 2 \cdot \frac{P \cdot R}{P + R}$$
- **Ranking Quality**: Precision-Recall Area Under the Curve (PR-AUC) across continuous score thresholds.
- **Incident-Level Review Metrics**: Rate of false alarms per 1,000 vessel-hours of operational traffic.
- **Explainability Score**: Percentage of flagged anomalies whose primary contributing factor accurately identifies the injected perturbation type.

---

## 4. Experiment Recording & Reproducibility Standard

Every experiment executed by the AegisMar test harness must emit a structured JSON metadata block containing:
- Timestamp (UTC ISO 8601).
- Experiment identifier (e.g., `EXP-CLU-20261114-01`).
- Input dataset path and SHA-256 checksum.
- Exact parameter configuration (e.g., $\varepsilon_{\text{spatial}}$, $\varepsilon_{\text{temporal}}$, $\text{min\_samples}$, H3 resolution $R$, $k$-ring order).
- Random seeds (e.g., `random_seed: 42`).
- Host environment details (Python version, OS, CPU model, RAM).
- Complete measurement array (runtimes, memory readings, recall scores).

