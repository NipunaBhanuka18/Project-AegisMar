# ADR-009: Uber H3 Discrete Hexagonal Grid as Correctness-Preserving Candidate Neighbor Generator

**Status:** Finalized & Verified (Milestone W3-01B)  
**Date:** 2026-11-14 (Architecture Formalized: 2026-11-18; Implemented: 2026-11-22; Hardened: 2026-11-23; Finalized: 2026-11-23)  
**Deciders:** NipunaBhanuka18 (Project Lead & Primary Researcher)  
**Technical Scope:** Spatial Candidate Indexing & Primary Research Contribution (RQ1)  

---

## 1. Context and Problem Statement

Metric tree structures such as `BallTree` achieve $O(N \log N)$ average query complexity, but tree construction latency and recursive tree traversals on dense clusters create performance bottlenecks on large AIS datasets.

Discrete Global Grid Systems (DGGS), specifically Uber's hierarchical hexagonal H3 grid, partition the Earth into discrete hexagonal cells using an icosahedral Snyder equal-area projection. In an idealized planar regular hexagon grid, immediate neighbors share identical centroid-to-centroid distances (unlike square grids where diagonal neighbors are $\sqrt{2}$ further than orthogonal neighbors).

However, on a spherical planetary manifold:
1. **Snyder Projection Distortion**: Hexagon edge lengths are not uniform across the globe; edge lengths and cell areas vary by approximately $1.4\times$ across each icosahedral face.
2. **Pentagonal Distortions**: Each resolution contains exactly 12 pentagonal cells (icosahedron vertices) where 5 rather than 6 cells meet, causing localized topological distortion.
3. **Planar vs. Spherical Geometry**: Idealized regular planar hexagon apothem formulas ($k \cdot 2 r_{\text{inscribed}} = k \sqrt{3} s$) do not constitute an analytical mathematical proof of global spherical bounds across arbitrary coordinates.

We required an indexing mechanism that leverages discrete $O(1)$ cell hashing to accelerate candidate neighbor generation while guaranteeing zero loss of true spatial neighbors ($\text{Recall} = 1.0$) against geodesic ground truth without relying on unproven global theorems.

---

## 2. Considered Alternatives

### Alternative A: Unpruned Discrete Grid Binning (Assigning points to static cell clusters)
- **Concept:** Map points to H3 cells and treat each cell or its 1-ring as an automatic cluster without distance verification.
- **Evaluation at Decision Time (2026-11-14):** Evaluated and rejected. Unpruned cell binning violates the mathematical definition of DBSCAN: two points on opposite sides of a cell boundary might be 1 meter apart but separated into different cells, or two points on opposite corners of a cell might be 1,000 meters apart but lumped together. It introduces severe boundary distortion.

### Alternative B: Geohash / Square Grid Quadtrees
- **Concept:** Spatial indexing using quadtrees or Morton-order Geohashes.
- **Evaluation at Decision Time (2026-11-14):** Evaluated and rejected. Square cells suffer from non-uniform neighbor distances (orthogonal vs. diagonal neighbors) and severe distortion at high latitudes, requiring complex anisotropic expansion buffers.

### Alternative C: Unconditional Global Mathematical Guarantee (Pure Hexagonal Analytical Bounds)
- **Concept:** Claim that planar apothem formulas analytically prove global completeness for all spherical cells.
- **Evaluation at Audit Time (W3-01A/B):** Evaluated and rejected. Snyder projection distortion, edge length variances, and icosahedral pentagons invalidate claims of closed-form global regular-hexagon proofs on the sphere.

---

## 3. Decision

We adopt **Option B: Empirical H3 Candidate Acceleration with Observable, Fail-Closed Reference Fallback**:

1. **Discrete Projection**: Map observations to discrete H3 cells at resolution $R$ using `h3-py` (v4.x API).
2. **Empirical Clearance Bounds on Calibrated Resolutions**:
   - Determine required ring expansion $k \ge 1$ via `compute_safe_k_ring(R, \varepsilon_s)` using conservative clearance lookup tables (`H3_MIN_CLEARANCE_METERS`) empirically verified across tested regional cells, high-latitude coordinates, and pentagons:
     - **Resolution 7 ($k=1$):** clearance $\ge 988.0\text{ m}$ (supports $\varepsilon_s \le 988\text{ m}$; max table: $4200.0\text{ m}$ at $k=3$)
     - **Resolution 8 ($k=1$):** clearance $\ge 395.0\text{ m}$ (supports $\varepsilon_s \le 395\text{ m}$; max table: $2160.0\text{ m}$ at $k=4$)
     - **Resolution 9 ($k=1$):** clearance $\ge 141.0\text{ m}$; $k=2$ clearance $\ge 371.0\text{ m}$ (supports $\varepsilon_s \le 371\text{ m}$; max table: $1060.0\text{ m}$ at $k=5$)
3. **Unsupported Configuration Policy**:
   - When an uncalibrated resolution or a search radius exceeding empirical tables is supplied:
     - **Default strict mode (`allow_uncalibrated=False`)**: if fallback is disabled, raises `ValueError`; if fallback is enabled, routes all observations to reference `BallTree` fallback with clear warnings and metadata (`completeness_contract = "full_balltree_fallback"`).
     - **Explicit experimental opt-in (`allow_uncalibrated=True`)**: estimates $k$-ring order via average edge approximations, logs clear warnings, and marks metadata (`completeness_contract = "experimental_uncalibrated"`).
4. **Strict Parameter Validation (Fail-Closed)**:
   - If a caller explicitly configures `k_ring < safe_k`, `H3NeighborhoodProvider` raises a `ValueError` rather than allowing candidate omissions.
5. **Precise Fallback Triggers vs. Omission Detection**:
   - The provider does **not** claim real-time automatic detection of omitted candidates outside the candidate disk; runtime exactness is preserved by safe ring radii or explicit fallback routing.
   - Fallback to `BallTreeNeighborhoodProvider` is triggered strictly by:
     1. **H3 API Exceptions**: Unexpected errors during `h3.grid_disk(c, k)` expansion mark cells for fallback or fail closed with `RuntimeError` if fallback is disabled.
     2. **Pentagon-Related Fallback**: When `fallback_on_pentagons=True` is enabled, pentagons and near-pentagon hexagons route to BallTree fallback (or fail closed with `RuntimeError` if fallback is disabled).
     3. **Unsupported Configuration Fallback**: When an uncalibrated resolution or excessive radius is provided with `enable_fallback=True`.
6. **Exact Pruning**: Perform exact geodesic Haversine distance filtering and integer-microsecond temporal filtering on all candidates surviving discrete expansion, matching BallTree precision to machine epsilon.
7. **Dataset-Scoped Parity Verification**: Provide an explicit offline verification tool (`verify_dataset_h3_balltree_parity` and CLI `verify-parity`) confirming 100% bit-for-bit graph parity (`indptr` and `indices`) on specific datasets.

---

## 4. Clearance Mathematics and Geometry Audit

During Milestones W3-01A and W3-01B, an in-depth audit of the clearance geometry resolved the following distinctions:

| Geometric Concept | Planar Hexagon Idealization | Actual H3 Spherical Reality | Operational Impact |
|:---|:---|:---|:---|
| **Edge Length** | Constant edge length $s$ globally. | `average_hexagon_edge_length` is an aggregated global average. Actual edge lengths vary by $\sim 1.4\times$ across each icosahedron face. | Clearance thresholds must use empirical minima across faces, not average edge lengths. |
| **Cell Clearances** | Inscribed circle apothem $r_{\text{in}} = \frac{\sqrt{3}}{2} s$. Minimum distance to ring $k+1$ is $2 k r_{\text{in}}$. | Snyder projection distorts cell interior angles and edge curvatures on the sphere. | Minimum clearance to ring $k+1$ is bounded by inter-vertex and inter-edge distances across adjoining cells. |
| **Pentagonal Faces** | Excluded (grid assumed infinite planar hexagon tessellation). | 12 pentagonal cells exist at each resolution at icosahedron vertices. Cells adjacent to pentagons share 5 rather than 6 neighbors. | Near-pentagon cells are detected via `grid_disk(c, k)` and routed to BallTree fallback when configured. |
| **Scientific Support Policy** | Claims unconditional theoretical guarantee. | Option B: High-throughput empirical candidate generation supported by transparent, fail-closed fallback for unproven boundary cases. | Eliminates unproven claims; provides defensible, audit-proof scientific methodology. |

---

## 5. Consequences and Trade-offs

### Positive Consequences
- **Zero Candidate Omission Guarantee on Calibrated Domains**: Empirical clearance thresholds plus fail-closed fallback ensure $\text{Recall} = 1.0$ against geodesic ground truth on tested regional AIS data.
- **Fail-Closed Reliability**: Accidental under-configuration, uncalibrated resolutions, or discrete grid failures cannot silently corrupt research clustering results.
- **Computational Speedup (Hypothesis H1)**: H3 candidate precomputation and $O(\log M_{\text{cell}})$ temporal search achieve a **1.34x graph query speedup** on 143,116 real observations while maintaining 100% bit-for-bit graph parity.
- **Dataset-Scoped Verifiability**: Any researcher can independently verify full graph parity using `aegismar verify-parity`.

### Negative Consequences / Trade-offs
- **Candidate Over-Retrieval**: Hexagonal disks retrieve candidates in corners outside the spherical search circle (precision $< 1.0$ prior to pruning).
  - *Mitigation:* Exact Haversine pruning eliminates false positives; benchmark measurements explicitly record candidate counts and timing breakdown.
- **Fallback Overhead**: Fallback queries require initializing and querying `BallTreeNeighborhoodProvider`.
  - *Mitigation:* Fallback provider is initialized lazily; on the authentic LA/LB dataset, fallback count was exactly 0.

---

## 6. Implementation Status and Evidence Links

- **Status**: Finalized and verified in Milestone W3-01B; formal multi-trial benchmarking in W3-02.
- **Provider Implementation**: [src/aegismar/clustering/h3_neighbors.py](../../../src/aegismar/clustering/h3_neighbors.py) (`H3NeighborhoodProvider`, `compute_safe_k_ring`, `verify_dataset_h3_balltree_parity`).
- **Engine Integration**: [src/aegismar/clustering/st_dbscan.py](../../../src/aegismar/clustering/st_dbscan.py) (`run_h3_st_dbscan`), [src/aegismar/clustering/config.py](../../../src/aegismar/clustering/config.py) (`STDBSCANConfig`), [src/aegismar/cli.py](../../../src/aegismar/cli.py) (`cluster`, `verify-parity`).
- **Automated Verification Suite**: [tests/unit/test_h3_neighbors.py](../../../tests/unit/test_h3_neighbors.py) (32 fixture categories, 39 total test cases, covering boundaries, vertices, pentagons, near-pentagons, undersized rings, uncalibrated resolutions, radii limits, experimental opt-in, and multi-region parity).
- **Dataset-Specific Empirical Baseline Parity**:
  - Full CSR neighborhood graph parity verified on authentic NOAA San Pedro Bay dataset ([data/processed/lalb_20250101/cleaned_ais.parquet](../../../data/processed/lalb_20250101/cleaned_ais.parquet), SHA-256: `4a7ca719dc2a3d9959cc4166edff773ca09156d8d914e54d0ab5f851ece5e88b`):
    - Analyzed observations: 143,116 records (8 timestamp conflicts excluded by policy).
    - `indptr match: True` (100.0000% degree identity).
    - `indices match: True` (100.0000% neighbor identity across all 13,188,256 edges).
    - `clusters_match: True`, `roles_match: True`, `labels_match: True` (241 clusters, 136,276 core, 934 border, 5,906 noise).
    - `fallback_count: 0`.
- **Shared Provider Protocol**: [src/aegismar/clustering/types.py](../../../src/aegismar/clustering/types.py) (`NeighborhoodProvider`).

---

## 7. Known Limitations

- Verification confirms 100% mathematical correctness ($\text{Recall} = 1.0$) and exact clustering equivalence against the BallTree reference on the calibrated San Pedro Bay dataset. Formal multi-trial comparative benchmarking across scales (10k, 50k, 100k, full LA/LB) evaluating Hypothesis H1 runtime and memory speedup belongs to Milestone W3-02.

---

## 8. Conditions for Revisiting

- Benchmark results in Week 3 demonstrate that H3 indexing overhead exceeds BallTree query savings on real AIS datasets, failing to reject the null hypothesis $H_{1,0}$.
