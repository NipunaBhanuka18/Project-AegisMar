# ADR-006: Strict Dual-Threshold Spatiotemporal Neighborhood Semantics in Integer Microseconds

**Status:** Accepted  
**Date:** 2026-11-18  
**Deciders:** NipunaBhanuka18 (Project Lead)  
**Technical Scope:** ST-DBSCAN Clustering Core & Metric Foundations  

---

## 1. Context and Problem Statement

Maritime vessels move dynamically across both space and time. A density cluster representing an anchorage or holding area must capture vessels that are co-located in space *and* temporally co-present.

Two points separated by 50 meters but recorded 6 months apart do not belong to the same physical spatiotemporal traffic cluster. We needed a mathematically rigorous, floating-point-safe definition of spatiotemporal neighborhood inclusion.

---

## 2. Considered Alternatives

### Alternative A: 3D Normalized Euclidean Metric Space $(x, y, \alpha \cdot t)$
- **Concept:** Normalize latitude, longitude, and timestamp into a single 3D metric space scaled by an arbitrary velocity constant $\alpha$ (e.g. converting seconds to pseudo-meters) and run standard 3D DBSCAN.
- **Evaluation at Decision Time (2026-11-18):** Evaluated and rejected. Coupling space and time into a single distance metric $d_{3D} = \sqrt{\Delta s^2 + (\alpha \Delta t)^2} \le \varepsilon$ creates severe physical distortion: a pair with zero spatial distance can admit hours of temporal difference, while a pair with large spatial distance permits only seconds of temporal difference. It lacks interpretable physical units and distorts maritime dwell boundaries.

### Alternative B: Epanechnikov Kernel Density Estimation (KDE)
- **Concept:** Continuous spatiotemporal density estimation using temporal kernel windows.
- **Evaluation at Decision Time (2026-11-18):** Evaluated and rejected. High computational complexity ($O(N^2)$ evaluation on continuous grids) and sensitive bandwidth parameters that fail to separate distinct discrete anchorage basins.

---

## 3. Decision

We define spatiotemporal neighborhood inclusion strictly as the **simultaneous intersection of two independent physical thresholds**:

$$N_{\varepsilon_{\text{spatial}}, \Delta T_{\text{temporal}}}(p) = \left\{ q \in D \;\middle|\; d_{\text{haversine}}(p, q) \le \varepsilon_{\text{spatial}} \;\land\; |t_p - t_q| \le \Delta T_{\text{temporal}} \right\}$$

Where:
- Spatial distance $d_{\text{haversine}}(p, q)$ is evaluated in exact geodesic meters on the sphere.
- Temporal distance $|t_p - t_q|$ is evaluated in **exact integer UTC epoch microseconds** (`int64`), completely avoiding floating-point roundoff errors inherent in converting seconds or days to floats.

Self-inclusion is reflexive: $p \in N(p)$ always.

---

## 4. Rationale

1. **Physical Interpretability**: Maritime analysts understand exactly what `eps_spatial_m=300.0` and `eps_temporal_s=900.0` mean (vessels within 300 meters and 15 minutes of each other).
2. **Numerical Determinism**: Evaluating $|t_p - t_q| \le \Delta T \times 1{,}000{,}000$ in 64-bit integer microseconds guarantees bit-for-bit identical temporal neighborhood evaluations across platforms and compilers.
3. **Optimized Spatial-First Pruning**: Enables spatial candidate generation (BallTree or H3) to prune >99% of non-neighbors before evaluating the cheap scalar temporal check.

---

## 5. Consequences and Trade-offs

### Positive Consequences
- Zero temporal leakage: points outside the temporal window are never grouped into the same core neighborhood.
- Platform-agnostic repeatability: 100% agreement between BallTree, H3, and the brute-force oracle.

### Negative Consequences / Trade-offs
- **Fixed Window Granularity**: Does not dynamically adapt temporal windows based on vessel speed.
  - *Mitigation:* Vessel-aware stay-point extraction (Milestone W4-01) handles velocity-adaptive dwell filtering prior to anchorage clustering.

---

## 6. Implementation Status and Evidence Links

- **Status**: Implemented and verified in Milestone W2-01.
- **Source Code**: [src/aegismar/clustering/config.py](../../../src/aegismar/clustering/config.py), [src/aegismar/clustering/balltree_neighbors.py](../../../src/aegismar/clustering/balltree_neighbors.py)
- **Unit Tests**: [tests/unit/test_st_dbscan.py](../../../tests/unit/test_st_dbscan.py) (`test_03`, `test_04`, `test_05`).

---

## 7. Known Limitations

- Requires two explicit hyperparameters ($\varepsilon_{\text{spatial}}$, $\Delta T_{\text{temporal}}$) rather than a single parameter.

---

## 8. Conditions for Revisiting

- A formal maritime standard defines an alternative non-Cartesian spatiotemporal clustering metric.
