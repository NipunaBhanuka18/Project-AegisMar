# W3-02 Benchmark Protocol: BallTree Reference vs. H3 Candidate Acceleration

**Status:** Locked protocol. The full LA/LB run was executed on 2026-11-28 at `379ec16` (`status = "completed"`); results are reported separately in [w3-02-benchmark-results.md](w3-02-benchmark-results.md). This document contains no performance results.  
**Date:** 2026-11-25  
**Track:** A (Clustering & Platform)  
**Milestone:** W3-02 (Comparative H1 Benchmarking)  
**Harness:** [src/aegismar/clustering/benchmark.py](../../src/aegismar/clustering/benchmark.py), runner [experiments/clustering/w3_02_benchmark.py](../../experiments/clustering/w3_02_benchmark.py)

---

## 1. Objective

Test hypothesis H1: on the LA/LB San Pedro Bay dataset, the calibrated H3 candidate provider ([ADR-009](../02-architecture/decisions/ADR-009-planned-h3-candidate-acceleration.md)) changes the runtime of exact spatiotemporal neighborhood construction and ST-DBSCAN relative to the BallTree reference ([ADR-005](../02-architecture/decisions/ADR-005-balltree-haversine-neighbor-search.md)), **without changing any result**.

Correctness is a precondition, not a measured outcome. Every timed comparison is preceded by exact parity verification at the same scale. If parity fails, timing is not run.

---

## 2. Relationship to Existing Documents

This protocol implements [Milestone W3-02](../04-development/milestones.md) and refines [evaluation-protocol.md §2.1–§2.3](evaluation-protocol.md). Where those documents conflict or are underspecified, this protocol decides as follows. The source documents are left unchanged.

| Topic | Source text | Decision in this protocol | Reason |
|---|---|---|---|
| Scale tiers | §2.1: 10k / 50k / 100k / 500k (optional). Milestone: 10k / 50k / 100k / full LA/LB | **10,000 / 50,000 / 100,000 / full (143,116)**. 500k is **deferred** | The single-day LA/LB extract has 143,116 clustering-eligible rows; no 500k dataset exists yet |
| Total time | §2.3: `T_total = T_build + T_query + T_prune` (no clustering). Milestone: includes clustering | Report **both** `index_and_graph_time_s` (= build + query_and_prune) and `total_time_s` (= build + query_and_prune + clustering) | Satisfies both definitions without choosing one |
| Query vs. prune | §2.3 lists separate `T_query` and `T_prune` | Official trials time **`query_and_prune_time_s`** as one segment; the split is reported only in the separate Phase 4 diagnostics pass | Separating them requires per-point timers, which bias the measurement (§5) |
| Memory | §2.3: `tracemalloc` and `psutil` | **Separate** `tracemalloc` pass (Phase 3); **no `psutil`** | `psutil` is not a project dependency. Memory tracing during timed trials inflates timings |
| Seeds | §2.3: "deterministic seeds" | **No RNG seeds**: subsets are deterministic chronological prefixes and all algorithms are deterministic | There is no randomness to seed. Determinism is verified (nested-prefix check, repeat-trial result consistency) |
| Recall / precision | Milestone: neighbor recall/precision | Against the **brute-force oracle** on a 2,000-row prefix, and against **BallTree** at every scale | The oracle refuses N > 5,000 (`oracle.py`, ADR-008) |
| Repetitions | §2.3: 1 warm-up + 10 trials | Kept, with **counterbalanced paired** trials (§4.2) | Controls for order and drift effects within each comparison |

---

## 3. Input Dataset (Verified Provenance)

The benchmark input is the post-W2-01 regeneration **v1.1**. The historical v1.0 file is kept immutable and is not used.

| Property | Value | Evidence |
|---|---|---|
| Path | `data/processed/lalb_20250101_v1_1/cleaned_ais.parquet` | Regenerated 2026-11-25 at `main` `7d2d114`, `git_dirty=false` |
| Raw source SHA-256 | `42e4f766feb98b20e98124685137bcc2be16a20c06dda46e33f415f0b281eac8` | `manifest.json` `source_sha256`, recomputed independently |
| File SHA-256 | `bdde2581302270a9e2c99a1a7aa1819a0bd1a24fbf6384458cfd8a81229eaf48` | Matches the value reported in `ml-02-feature-spec.md` |
| Logical fingerprint (`aegismar-logical-v1`, [ADR-011](../02-architecture/decisions/ADR-011-dataset-provenance-and-content-fingerprinting.md)) | `d8a619f7d27314ae8418eff5da8e1c5c96004d038c2fce8f5ee868ed90fec2cf` | `aegismar fingerprint`; canonical order verified |
| Rows | 143,124 total; **143,116** after the default `QualityFilterPolicy` (8 `TIMESTAMP_POSITION_CONFLICT` rows excluded) | Row-level diff, 2026-11-25 |

**Equivalence to v1.0 for clustering inputs (verified):** v1.0 and v1.1 differ in exactly 12 rows, all in the derived kinematics columns (`prev_source_row`, `elapsed_seconds`, `distance_nm`, `implied_speed_knots`) of the 4 same-timestamp conflict groups. After the default quality filter, both versions yield 143,116 rows with byte-identical `(source_row, mmsi, timestamp_utc, latitude, longitude)` columns (SHA-256 of the Arrow IPC stream: `be3e7850008d9f8c5ca56ceb1e540e4776ce14aeb66db8687c6f831b5d71e5ea` for both). Clustering inputs are therefore identical, so the earlier v1.0 H3/BallTree parity evidence (13,188,256 edges, 0 fallbacks at resolution 8) was obtained on the same clustering input. Phase 1 re-verifies parity on v1.1 at the current code revision rather than relying on that evidence.

The harness re-verifies the file hash, logical fingerprint, row order, and sibling `manifest.json` agreement on every run and records them in the output.

---

## 4. Locked Configuration

| Parameter | Value |
|---|---|
| `eps_spatial_m` / `eps_temporal_s` / `min_samples` | 300.0 / 900.0 / 5 (`STDBSCANConfig` defaults) |
| Quality filter | `QualityFilterPolicy()`: exclude `TIMESTAMP_POSITION_CONFLICT` and `TIMESTAMP_METADATA_CONFLICT` |
| Scales | Chronological prefixes of the filtered, canonically sorted dataset: 10,000 / 50,000 / 100,000 / full |
| Primary H3 | Resolution 8, k-ring 1 (clearance 395 m ≥ 300 m) |
| Sensitivity H3 | Resolution 7, k-ring 1 (988 m); resolution 9, k-ring 2 (371 m) |
| H3 contract | `empirical_regional_calibrated` for all three; fallback enabled (default), pentagon fallback off (default) |
| Oracle prefix | First 2,000 filtered rows |
| Warm-up / trials | 1 warm-up per provider (excluded) + 10 measured paired trials per block and scale |

### 4.1 Four strictly separated phases

1. **Correctness (Phase 1).**
   - **Oracle check:** on the 2,000-row prefix, BallTree and H3 at resolutions 8, 7 and 9 are each compared with `BruteForceNeighborhoodOracle`.
   - **Scale parity:** at every scale, H3 at resolutions 8, 7 and 9 is compared with BallTree.
   - **Recorded per comparison:**
     - exact CSR graph match, neighbor recall and precision, missing and extra neighbors;
     - directed and undirected edge-count agreement;
     - Adjusted Rand Index (`sklearn.metrics.adjusted_rand_score`);
     - exact label and role identity;
     - cluster, core, border and noise counts;
     - H3 fallback count.
   - **Pass rule:** a comparison passes only if recall = precision = ARI = 1.0, the graph, labels, roles and counts are identical, and the H3 fallback count is 0.
   - **Abort rule:** if any comparison fails, or the nested-prefix check fails, `status = "parity_failed"` and Phases 2–4 are skipped.
2. **Official timed trials (Phase 2):** `detailed_timing=False`, `measure_memory=False`. There are three blocks with identical methodology: **primary** (BallTree vs. H3 r8) and **sensitivity** (BallTree vs. H3 r7, BallTree vs. H3 r9), each across all scales.
3. **Peak memory (Phase 3):** one isolated `tracemalloc` pass per provider (BallTree, H3 r7/r8/r9) per scale, with `detailed_timing=False`.
4. **Stage diagnostics (Phase 4):** one `detailed_timing=True` pass per provider per scale. It records the stage split: build, cell mapping, `grid_disk` precomputation, candidate retrieval, temporal filtering, distance filtering, candidates evaluated, and clustering. These timings carry instrumentation overhead and are **not** compared with Phase 2.

### 4.2 Counterbalanced paired trials

Within each (block, scale):
- Run the warm-up first (BallTree, then H3).
- For trial index `t = 0..9`, run BallTree then H3 when `t` is even, and H3 then BallTree when `t` is odd.
- Call `gc.collect()` immediately before every individual provider run. The garbage collector stays enabled during timing.
- Pair trial `t`'s BallTree and H3 timings for the paired statistics.

Every trial must report `detailed_timing == False` and an H3 `fallback_count` of 0. Its cluster, core, border and noise counts must equal the Phase 1 BallTree reference for that scale. A violation sets `status = "trial_integrity_failed"`.

---

## 5. Timing Definitions and Instrumentation Fairness

All timers use `time.perf_counter`. Each official provider run constructs a fresh provider and then calls `run_st_dbscan(..., measure_memory=False)`.

| Field | Definition |
|---|---|
| `build_time_s` | Provider constructor index build (`provider.build_time_seconds`). BallTree: tree construction. H3: cell mapping + bucket index + `grid_disk` precomputation |
| `query_and_prune_time_s` | Wall time of `build_neighborhood_graph()`: candidate retrieval + exact temporal filter + exact Haversine filter + CSR assembly |
| `clustering_time_s` | Core-first ST-DBSCAN labeling on the built graph |
| `index_and_graph_time_s` | `build_time_s + query_and_prune_time_s` |
| `total_time_s` | `build_time_s + query_and_prune_time_s + clustering_time_s` |

**Not timed:** Parquet loading, quality filtering, and canonical sorting (`load_clustering_dataset_from_parquet`). These are identical for both providers.

**`detailed_timing` toggle (fairness).** Before W3-02, H3 executed 6+ `perf_counter` calls per point inside its query loop and BallTree executed none. That inflated H3's own measured time.
- Both providers now accept `detailed_timing: bool = False`.
- With `False`, graph construction performs **zero** per-batch or per-point `perf_counter` calls in either provider. Only the coarse constructor build time is recorded. This is enforced by a unit test that counts `perf_counter` calls.
- With `True`, an instrumented twin of the query path records stage timers.
- Unit tests verify that both modes produce identical graphs, labels, roles, counts and fallback behaviour.
- Official trials are locked to `False`. `W302BenchmarkConfig` rejects `official_detailed_timing=True`.

---

## 6. Statistics

Statistics are descriptive only. They are reported per (block, scale, provider, metric) as:
- `n`, `mean`, `median`, `std` (`ddof=1`), `min`, `max`;
- the interquartile points `iqr_p25` and `iqr_p75`;
- a two-sided 95% Student-t confidence interval for the mean, `mean ± t(0.975, n−1)·s/√n`.

The critical values are exact for df = 1–30, verified against `scipy.stats.t.ppf` to 9 decimals; scipy is not a dependency. For df > 30 the normal value 1.959964 is used.

**Paired comparison** (BallTree vs. H3, matched trial index):
- paired difference `balltree − h3` in seconds: mean and 95% CI (positive means H3 is faster);
- per-trial speedup `balltree / h3`: mean, median and 95% CI (> 1 means H3 is faster);
- ratio-of-means speedup `mean(balltree) / mean(h3)`.

> **Interpretation limit.** Intervals describe run-to-run dispersion on one host, one dataset, and one parameter set. They do not establish statistical significance across hardware, operating systems, datasets, or parameters. Every result file carries this note (`statistical_interpretation_note`).

---

## 7. Reproduction

```bash
uv run python experiments/clustering/w3_02_benchmark.py \
    -i data/processed/lalb_20250101_v1_1/cleaned_ais.parquet \
    -o experiments/outputs/w3_02_benchmark_results.json
```

- **Defaults:** `--scales 10000 50000 100000 full --trials 10 --warmup 1 --oracle-rows 2000 --sensitivity-resolutions 7 9`.
- **Overwrite protection:** the runner refuses to replace an existing output unless `--overwrite` is passed.
- **Exit codes:**
  - `0`: completed;
  - `1`: usage, input or configuration error;
  - `2`: a correctness or trial-integrity check failed (the JSON is still written).
- **Output location:** `experiments/outputs/` is git-ignored, so results are never committed. Reported numbers must cite the output file's recorded provenance (dataset hashes, `git_commit_sha`, `git_dirty`, library versions, host).

**Output record:**
- `config`, including fixed official/memory/diagnostic settings and k-rings;
- `provenance`:
  - dataset hashes, fingerprint, filtering accounting and sibling-manifest agreement;
  - runtime and git state;
  - versions of numpy, scikit-learn, h3 and pyarrow;
  - platform, processor and CPU count;
- `scales`: per-scale row count, time span and unique vessels;
- `nested_prefix_verified`;
- `phase_1_correctness`;
- `phase_2_timed_trials`: raw trials, summaries and paired comparisons;
- `phase_3_peak_memory`;
- `phase_4_stage_diagnostics`.

---

## 8. Threats to Validity and Limitations

- **Single host and OS.** Results are specific to the recorded machine. Run-to-run noise from background processes is only partly controlled by counterbalancing and warm-up.
- **Garbage collection.** GC remains enabled during timing, and `gc.collect()` runs before each provider. Collection pauses inside a run are part of the measured cost.
- **Chronological prefixes.** Smaller scales cover the earliest hours of 2025-01-01, not random samples. Density and vessel mix may differ from the full day. Each scale's time span and vessel count are recorded.
- **Implementation level.** H3's per-point query loop is Python, while BallTree's `query_radius` is compiled per batch. Results compare these implementations as built, not the asymptotic merit of either index.
- **Memory.** `tracemalloc` captures Python-tracked allocations, including NumPy buffers. Native allocations that bypass the Python allocator are not captured, and RSS is not measured.
- **Calibration scope.** H3 parity holds for the calibrated configurations in §4 on this dataset. It is not a global completeness claim (ADR-009 Option B).
- **Fixed parameters.** One parameter set (300 m / 900 s / min_samples 5) is benchmarked. Sensitivity to ε and `min_samples` is out of scope.

---

## 9. Verification of the Harness

Unit tests in [tests/unit/test_benchmark.py](../../tests/unit/test_benchmark.py) cover:
- `detailed_timing` invariance for BallTree and for H3 at resolutions 7, 8 and 9, including the full-fallback path;
- the metrics contract in both modes;
- zero `perf_counter` calls on the official path;
- exact statistics on known inputs;
- the counterbalanced execution order;
- graph-comparison helpers, configuration validation and the nested-prefix check;
- an end-to-end mini benchmark on synthetic AIS data, covering provenance, exact parity, all four phases and the parity-failure abort;
- the runner's JSON output and overwrite protection.

The full LA/LB benchmark results are reported in [w3-02-benchmark-results.md](w3-02-benchmark-results.md).
