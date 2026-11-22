# ADR-008: Independent $O(N^2)$ Brute-Force Geodesic Test Oracle for Verification

**Status:** Accepted  
**Date:** 2026-11-18  
**Deciders:** NipunaBhanuka18 (Project Lead)  
**Technical Scope:** Quality Assurance, Mathematical Verification & Scientific Rigor  

---

## 1. Context and Problem Statement

When evaluating novel or accelerated spatial indexing structures (such as Uber H3 hexagonal candidate indexing), there is a grave risk of **circular validation**: verifying an algorithm against another complex indexing library (e.g. comparing H3 to a BallTree that might itself harbor coordinate wrapping bugs or edge-case floating-point precision errors).

To scientifically defend claims of "zero lost neighbors" ($\text{Recall} = 1.0$), we needed an incontrovertible, standalone mathematical authority decoupled from third-party metric trees.

---

## 2. Considered Alternatives

### Alternative A: Cross-Validating BallTree against KDTree
- **Concept:** Compare `scikit-learn.neighbors.BallTree` against `KDTree`.
- **Evaluation at Decision Time (2026-11-18):** Evaluated and rejected. Both use metric tree partitioning and both can share algorithmic assumptions; KDTree does not support the spherical Haversine metric, introducing projection distortion.

### Alternative B: Validating only on Manual Synthetic Fixtures
- **Concept:** Write 5–10 small hand-calculated test cases.
- **Evaluation at Decision Time (2026-11-18):** Evaluated and rejected as sole verification. Small hand-crafted tests miss subtle edge cases such as anti-meridian dateline crossings ($\pm 180^\circ$), polar convergence, and 1-ULP floating-point rounding discrepancies on boundary conditions.

---

## 3. Decision

We construct an **isolated, standalone $O(N^2)$ brute-force test oracle**:
`aegismar.spatial.oracle.BruteForceNeighborhoodOracle`.

The oracle:
1. Is mathematically decoupled from `scikit-learn`, `BallTree`, `h3`, or any indexing structure.
2. Computes pairwise spherical great-circle distances via scalar trigonometry using the raw Haversine formula.
3. Evaluates all $N \times (N - 1) / 2$ pairs exhaustively.
4. Enforces an explicit safety guard ($N \le 5{,}000$) to prevent accidental quadratic memory or CPU lockup if invoked on massive production datasets.
5. Implements the shared `NeighborhoodProvider` protocol, allowing it to be injected directly into `run_st_dbscan` to produce ground-truth cluster labels and roles.

---

## 4. Rationale

1. **Unassailable Ground Truth**: An exhaustive pairwise comparison has no indexing trees, no bounding boxes, and no heuristic pruning; if BallTree or H3 misses a neighbor that the oracle finds, the index has a proven bug.
2. **Defensive Debugging**: During Milestone W2-01, the oracle detected a 1-ULP IEEE-754 discrepancy between vectorized degree differences and scalar degree differences, allowing us to align production code for bit-for-bit mathematical identity.
3. **Automated Continuous Verification**: Runs automatically in `pytest` across randomized datasets, high latitudes, dateline crossings, and a 1,000-row real LA/LB subset.

---

## 5. Consequences and Trade-offs

### Positive Consequences
- Guarantees that passing automated tests represent verified mathematical ground truth.
- Provides immediate debugging confidence when implementing the upcoming Week 3 H3 candidate indexing engine.

### Negative Consequences / Trade-offs
- **$O(N^2)$ Execution Limit**: The oracle cannot execute on the full 143k LA/LB dataset (would take ~40 minutes).
  - *Mitigation:* The oracle is capped at $N \le 5{,}000$ and verified against real-data slices (e.g. 1,000 rows in <0.3 s).

---

## 6. Implementation Status and Evidence Links

- **Status**: Implemented and verified in Milestone W2-01.
- **Source Code**: [src/aegismar/spatial/oracle.py](../../../src/aegismar/spatial/oracle.py)
- **Unit Tests**: [tests/unit/test_oracle.py](../../../tests/unit/test_oracle.py) (7 randomized and edge-case tests, 100% passing).

---

## 7. Known Limitations

- Verifies algorithmic neighbor discovery correctness; does **not** prove operational maritime anomaly detection accuracy (which requires maritime domain evaluation).

---

## 8. Conditions for Revisiting

- None.
