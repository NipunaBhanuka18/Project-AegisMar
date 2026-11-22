# ADR-009: Uber H3 Discrete Hexagonal Grid as Correctness-Preserving Candidate Neighbor Generator

**Status:** Accepted (Planned Design for Milestone W3-01)  
**Date:** 2026-11-14 (Architecture Formalized: 2026-11-18)  
**Deciders:** NipunaBhanuka18 (Project Lead & Primary Researcher)  
**Technical Scope:** Spatial Candidate Indexing & Primary Research Contribution (RQ1)  

---

## 1. Context and Problem Statement

Metric tree structures such as `BallTree` achieve $O(N \log N)$ average query complexity, but tree construction latency and recursive tree traversals on dense clusters create performance bottlenecks on large AIS datasets.

Discrete Global Grid Systems (DGGS), specifically Uber's hierarchical hexagonal H3 grid, partition the Earth into regular hexagonal cells. Hexagonal cells have the unique geometric property that all immediate neighbor cells share identical centroid-to-centroid distances (unlike square grids where diagonal neighbors are $\sqrt{2}$ further than orthogonal neighbors).

We needed an indexing mechanism that leverages discrete $O(1)$ cell hashing to accelerate candidate neighbor generation while strictly guaranteeing zero loss of true spatial neighbors ($\text{Recall} = 1.0$) against geodesic ground truth.

---

## 2. Considered Alternatives

### Alternative A: Unpruned Discrete Grid Binning (Assigning points to static cell clusters)
- **Concept:** Map points to H3 cells and treat each cell or its 1-ring as an automatic cluster without distance verification.
- **Evaluation at Decision Time (2026-11-14):** Evaluated and rejected. Unpruned cell binning violates the mathematical definition of DBSCAN: two points on opposite sides of a cell boundary might be 1 meter apart but separated into different cells, or two points on opposite corners of a cell might be 1,000 meters apart but lumped together. It introduces severe boundary distortion.

### Alternative B: Geohash / Square Grid Quadtrees
- **Concept:** Spatial indexing using quadtrees or Morton-order Geohashes.
- **Evaluation at Decision Time (2026-11-14):** Evaluated and rejected. Square cells suffer from non-uniform neighbor distances (orthogonal vs. diagonal neighbors) and severe distortion at high latitudes, requiring complex anisotropic expansion buffers.

---

## 3. Decision

We will implement an **H3-accelerated candidate neighbor provider** (`H3NeighborhoodProvider`) that:
1. Maps observations to discrete H3 cells at resolution $R$ using `h3-py` (v4.x API).
2. Generates candidate neighbor sets using $k$-ring cell expansion ($k \ge 1$) around target cells.
3. Automatically computes resolution $R$ and expansion order $k$ such that the inscribed circle radius of the $k$-ring strictly circumscribes the spatial search radius $\varepsilon_{\text{spatial}}$:
   $$r_{\text{inscribed}}(R, k) \ge \varepsilon_{\text{spatial}}$$
4. Performs **exact geodesic Haversine distance filtering and integer-microsecond temporal filtering** on all returned candidate pairs before neighborhood admission.
5. Implements the shared `NeighborhoodProvider` protocol, enabling seamless injection into the existing deterministic `run_st_dbscan` core.

---

## 4. Rationale

1. **Correctness-Preserving Guarantee**: Because the $k$-ring strictly envelopes $\varepsilon_{\text{spatial}}$, no eligible spatial neighbor can exist outside the candidate cells. The subsequent exact Haversine filter eliminates false positives, guaranteeing mathematical equivalence to BallTree ($\text{Recall} = 1.0$).
2. **Computational Speedup (Hypothesis H1)**: H3 cell lookup is $O(1)$ integer hashing. Populating hash buckets is substantially faster than recursive metric tree construction, and candidate retrieval avoids deep tree traversals.
3. **Pluggable Architecture**: Plugs directly into `run_st_dbscan` without altering the deterministic core-first labeling policy or border point tie-breaking.

---

## 5. Consequences and Trade-offs

### Positive Consequences
- Enables formal empirical testing of Primary Research Hypothesis H1.
- Provides a clean scientific comparison: BallTree vs H3 across runtime, query latency, index build time, peak memory, and neighbor recall.

### Negative Consequences / Trade-offs
- **Candidate Over-Retrieval**: Hexagonal $k$-rings retrieve candidates in the corners of hexagons that fall outside the circular search radius $\varepsilon_{\text{spatial}}$ (precision $< 1.0$ prior to pruning).
  - *Mitigation:* The exact geodesic pruning step filters out non-qualifying points; benchmark measurements explicitly record candidate precision ($P_{\text{neighbor}}$) to quantify this trade-off.
- **Icosahedral Pentagon Distortion**: H3 contains 12 pentagonal cells per resolution across the globe.
  - *Mitigation:* Milestone W3-01 includes specific completeness unit tests targeting pentagonal distortion zones.

---

## 6. Implementation Status and Evidence Links

- **Status**: Planned for Milestone W3-01 and W3-02 (Week 3).
- **Protocol**: [docs/03-research/evaluation-protocol.md](../../03-research/evaluation-protocol.md)
- **Shared Provider Protocol**: [src/aegismar/clustering/types.py](../../../src/aegismar/clustering/types.py) (`NeighborhoodProvider`).

---

## 7. Known Limitations

- Not yet implemented in the codebase (scheduled for Week 3). Claims of measured performance remain hypotheses subject to empirical validation.

---

## 8. Conditions for Revisiting

- Benchmark results in Week 3 demonstrate that H3 indexing overhead exceeds BallTree query savings on real AIS datasets, failing to reject the null hypothesis $H_{1,0}$.
