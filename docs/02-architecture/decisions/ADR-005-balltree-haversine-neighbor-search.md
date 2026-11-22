# ADR-005: Scikit-Learn BallTree with Haversine Metric as Reference Neighbor Search Engine

**Status:** Accepted  
**Date:** 2026-11-18  
**Deciders:** NipunaBhanuka18 (Project Lead)  
**Technical Scope:** Spatial Indexing Subsystem & Scientific Baseline  

---

## 1. Context and Problem Statement

Spatiotemporal clustering (ST-DBSCAN) requires retrieving all spatial neighbors of an observation within a spatial radius $\varepsilon_{\text{spatial}}$ (e.g. 300 meters) on the surface of the Earth.

Naive pairwise distance computation has $O(N^2)$ time complexity, executing over 20 billion distance calculations on 143k records. We needed an established, mathematically verified spatial indexing engine to serve as the ground-truth **reference baseline** against which our proposed Uber H3 candidate indexing engine can be benchmarked.

---

## 2. Considered Alternatives

### Alternative A: Flat $O(N^2)$ Pairwise Distance Matrix
- **Concept:** Compute full $N \times N$ distance matrix via broadcasting.
- **Evaluation at Decision Time (2026-11-18):** Evaluated and rejected for production use. An array of $143{,}116 \times 143{,}116$ float64 values requires **163.8 GB of RAM**, causing an immediate out-of-memory crash. However, this brute-force approach was isolated as an independent test oracle for $N \le 5{,}000$ (see ADR-008).

### Alternative B: Projected Euclidean KD-Tree (UTM / Web Mercator)
- **Concept:** Project coordinates from WGS 84 (lat/lon) into a local 2D planar projection (e.g. UTM Zone 11N) and build a standard Euclidean `scikit-learn.neighbors.KDTree`.
- **Evaluation at Decision Time (2026-11-18):** Evaluated and rejected. Planar map projections introduce scale distortion that varies with latitude and distance from central meridians. At regional boundaries and high latitudes, Euclidean distances deviate from spherical geodesic ground truth, undermining scientific benchmarking rigor.

### Alternative C: SciPy cKDTree with 3D Geocentric Cartesian Coordinates ($X, Y, Z$) (Retrospective Alternative, 2026-11-18)
- **Concept:** Convert lat/lon/alt to 3D Earth-Centered Earth-Fixed (ECEF) coordinates and query via 3D chord length.
- **Evaluation on 2026-11-18:** Evaluated. While fast, 3D chord distance requires converting curved spherical distances $\varepsilon_{\text{spatial}}$ to linear 3D chord lengths ($2 R \sin(\theta/2)$). `scikit-learn` BallTree directly supports the exact Haversine metric natively on spherical radians without coordinate conversion approximations.

---

## 3. Decision

We will use **`scikit-learn.neighbors.BallTree`** configured with `metric='haversine'` as the official spatial indexing reference baseline (`BallTreeNeighborhoodProvider`).

Coordinates are converted to radians in `[latitude_rad, longitude_rad]` order. The search radius is converted to angular radians via $\varepsilon_{\text{rad}} = \varepsilon_{\text{spatial\_m}} / R_{\text{earth}}$, where $R_{\text{earth}} = 6{,}371{,}008.8\text{ meters}$ (the official WGS 84 mean spherical radius).

To prevent memory spikes during radius querying, queries are executed in vectorized chunks (`batch_size=2048`), and candidates undergo exact degree-difference Haversine pruning to prevent 1-ULP floating-point precision differences against the oracle.

---

## 4. Rationale

1. **Exact Spherical Geodesics**: The Haversine metric computes true spherical great-circle distances, avoiding planar projection distortions across all latitudes.
2. **Established Scientific Baseline**: `scikit-learn` BallTree is a mature, globally recognized metric tree implementation, providing an unassailable baseline for academic research papers.
3. **$O(N \log N)$ Average Query Complexity**: Enables evaluating 143k records on a laptop in ~13 seconds uninstrumented wall time without $N \times N$ memory allocation.
4. **Provider Protocol Decoupling**: Implemented behind the shared `NeighborhoodProvider` protocol, allowing the upcoming H3 engine to drop into the identical ST-DBSCAN core algorithm.

---

## 5. Consequences and Trade-offs

### Positive Consequences
- Absolute geographic accuracy: verified to achieve 100% neighbor recall against the independent brute-force oracle across synthetic, polar, and real fixtures.
- Memory bounded: CSR neighborhood graph representation avoids dense adjacency matrices.

### Negative Consequences / Trade-offs
- **Tree Construction Overhead**: BallTree requires rebuilding the metric tree if points change.
- **Query Performance at High Density**: When points cluster densely, BallTree query times increase as pruning bounding balls become less effective.
  - *Mitigation:* This is the exact research hypothesis motivating Track A's investigation into discrete hexagonal H3 candidate acceleration.

---

## 6. Implementation Status and Evidence Links

- **Status**: Implemented and verified in Milestone W2-01.
- **Source Code**: [src/aegismar/clustering/balltree_neighbors.py](../../../src/aegismar/clustering/balltree_neighbors.py)
- **Unit Tests**: [tests/unit/test_st_dbscan.py](../../../tests/unit/test_st_dbscan.py), [tests/unit/test_oracle.py](../../../tests/unit/test_oracle.py).
- **Recorded Baseline Run**: 143,116 analyzed observations queried in 13.34 s uninstrumented wall time (commit `3ece859`).

---

## 7. Known Limitations

- Haversine distance assumes a spherical Earth ($R = 6{,}371{,}008.8\text{ m}$), which has a maximum deviation of ~0.5% from the WGS 84 ellipsoidal geodesic (Vincenty/Karney) at extreme latitudes. Acceptable for maritime spatial clustering where $\varepsilon_{\text{spatial}} \le 1{,}000\text{ m}$.

---

## 8. Conditions for Revisiting

- Research requirement dictates sub-millimeter ellipsoidal geodesic precision (e.g., GeographicLib/Karney geodesics).
