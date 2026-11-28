# W3-02 Benchmark Results: BallTree Reference vs. H3 Candidate Acceleration

**Status:** Executed. Results of the locked [W3-02 Benchmark Protocol](w3-02-benchmark-protocol.md).  
**Run date:** 2026-11-28  
**Track:** A (Clustering & Platform)  
**Milestone:** W3-02 (Comparative H1 Benchmarking)  
**Result record:** `experiments/outputs/w3_02_benchmark_results.json` (git-ignored; schema `1.0`, `status = "completed"`)

All numbers in this report are copied from the result record. Timings are rounded to 4 decimal places, and memory is rounded to 0.1 MiB. Two figures are derived from recorded values and are labelled where they appear: the candidate-count ratios and the memory percentages.

> **Interpretation limit (from the result record).** Descriptive statistics only. Confidence intervals are two-sided 95% Student-t intervals over repeated runs on a single host and a single dataset. They describe run-to-run execution-time dispersion under these conditions and do not claim statistical significance across hardware, operating systems, datasets, or parameter settings.

---

## Summary

- **Correctness:** H3 at resolutions 7, 8 and 9 reproduced the BallTree reference exactly at every scale. Every check had an exact CSR graph match, recall and precision of 1.0, ARI 1.0, identical labels and roles, and 0 fallbacks. All four engines also matched the brute-force oracle on a 2,000-row prefix.
- **Runtime (primary configuration, H3 r8):** H3 is slower than BallTree on small prefixes and faster on the full day. By total time it is 0.773× at 10k, 0.908× at 50k, 1.004× at 100k (the 95% CI includes 1.0, so parity) and **1.150× at full scale**, where it takes 10.7867 s against BallTree's 12.4074 s. The paired saving is 1.6206 s [1.4917, 1.7496]. On index + graph time the per-trial speedup at full scale is **1.1543× [1.1411, 1.1676]**.
- **Sensitivity configurations:** r7 (k-ring 1) and r9 (k-ring 2) are slower than BallTree at every tested scale: 0.842× and 0.911× by total time at full scale.
- **Memory:** H3 r8's `tracemalloc` peak at full scale is 233.8 MiB, against BallTree's 225.8 MiB (+3.6%, derived). These are Python-tracked allocations only.
- **H1 outcome on this host and dataset:** the result is mixed. With exactness preserved, the calibrated r8 provider gives a measurable speedup only at the full one-day scale (143,116 rows). It is at parity at 100k and slower below that.

---

## 1. Run Provenance & Experimental Configuration

| Property | Value |
|---|---|
| Code revision | `379ec16b763b005ce40808d7bbfc28940a140d89`, `git_dirty: false` |
| Execution window (UTC) | `2026-11-28T11:19:02Z` → `2026-11-28T11:57:24Z` |
| Total wall time | 2301.3 s (`total_wall_time_s = 2301.3239550000008`; ≈ 38.4 min) |
| Dataset | Canonical v1.1, `data/processed/lalb_20250101_v1_1/cleaned_ais.parquet` |
| File SHA-256 | `bdde2581302270a9e2c99a1a7aa1819a0bd1a24fbf6384458cfd8a81229eaf48` |
| Logical fingerprint (`aegismar-logical-v1`) | `d8a619f7d27314ae8418eff5da8e1c5c96004d038c2fce8f5ee868ed90fec2cf` |
| Canonical order verified | `true` |
| Sibling `manifest.json` | `output_parquet_sha256_matches_file: true`, `content_fingerprint_matches_file: true`; manifest `git_commit_sha 7d2d114…`, `git_dirty: false`, `source_sha256 42e4f766…` |
| Row accounting | 143,124 Parquet rows → 143,116 after `QualityFilterPolicy()` (8 `TIMESTAMP_POSITION_CONFLICT` rows excluded) |
| Software | Python 3.11.9 (CPython), aegismar 0.1.0.dev1, numpy 2.4.6, scikit-learn 1.9.1, h3 4.5.1, pyarrow 26.0.1 |
| Host | `Windows-10-10.0.26300-SP0`, AMD64, `AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD`, 16 logical CPUs |

**Locked parameters.**
- **ST-DBSCAN:** `eps_spatial_m` 300 m, `eps_temporal_s` 900 s, `min_samples` 5, algorithm `stdbscan-core-first-v1.0`.
- **H3 configurations:** primary resolution 8 (k-ring 1); sensitivity resolutions 7 (k-ring 1) and 9 (k-ring 2).
- **Repetitions:** 1 warm-up per provider (excluded) and 10 measured trials per block and scale.
- **Official trials:** `detailed_timing = false`, `measure_memory = false`, timer `time.perf_counter`.
- **Garbage collection:** `gc.collect()` runs before each provider run, and GC stays enabled during timing.
- **Counterbalancing:** even trial index runs BallTree first; odd trial index runs H3 first.
- **Memory pass:** a separate `tracemalloc` pass (`measure_memory = true`, `detailed_timing = false`). `psutil` RSS is not measured.

**Scale subsets.** These are chronological prefixes of the filtered, canonically sorted dataset (`nested_prefix_verified: true`).

| Scale | Rows | UTC span (2025-01-01) | Unique vessels |
|---|---:|---|---:|
| 10k | 10,000 | 00:00:00 – 01:33:45 | 304 |
| 50k | 50,000 | 00:00:00 – 08:16:50 | 310 |
| 100k | 100,000 | 00:00:00 – 17:06:11 | 322 |
| full | 143,116 | 00:00:00 – 23:59:57 | 362 |

---

## 2. Phase 1 — Correctness Verification

`all_parity_checks_passed: true`.

Every comparison below also had 0 missing and 0 extra neighbours, identical labels and roles, and matching counts. The oracle rows compare all four engines against `BruteForceNeighborhoodOracle`. The parity rows compare each H3 resolution against BallTree.

| Check | Rows | Candidates | Exact graph | Recall | Precision | ARI | Directed edges | Undirected edges | Clusters / core / border / noise | H3 fallbacks | Passed |
|---|---:|---|---|---:|---:|---:|---:|---:|---|---:|---|
| Brute-force oracle | 2,000 | BallTree, H3 r8, H3 r7, H3 r9 | Yes | 1.0 | 1.0 | 1.0 | 101,432 | 49,716 | 66 / 1,863 / 54 / 83 | 0 | Yes |
| Parity vs BallTree @ 10k | 10,000 | H3 r8, H3 r7, H3 r9 | Yes | 1.0 | 1.0 | 1.0 | 767,660 | 378,830 | 66 / 9,242 / 137 / 621 | 0 | Yes |
| Parity vs BallTree @ 50k | 50,000 | H3 r8, H3 r7, H3 r9 | Yes | 1.0 | 1.0 | 1.0 | 4,315,932 | 2,132,966 | 140 / 47,211 / 455 / 2,334 | 0 | Yes |
| Parity vs BallTree @ 100k | 100,000 | H3 r8, H3 r7, H3 r9 | Yes | 1.0 | 1.0 | 1.0 | 9,316,524 | 4,608,262 | 208 / 96,210 / 559 / 3,231 | 0 | Yes |
| Parity vs BallTree @ full | 143,116 | H3 r8, H3 r7, H3 r9 | Yes | 1.0 | 1.0 | 1.0 | 13,188,256 | 6,522,570 | 241 / 136,276 / 934 / 5,906 | 0 | Yes |

At full scale, the counts and edge totals reproduce the W2-01 and W3-01B baselines (`CLM-CLU-04`, `CLM-CLU-06`) on canonical v1.1 at the current code revision.

---

## 3. Phase 2 — Official Timed Trials & Paired Comparisons

`all_trial_integrity_checks_passed: true`. Every block and scale satisfied three conditions:
- `all_trials_detailed_timing_false`
- `all_trials_fallback_free`
- `results_consistent_with_phase_1`

Timing tables show mean / median / sd [95% CI] in seconds. The metrics are defined in [protocol §5](w3-02-benchmark-protocol.md#5-timing-definitions-and-instrumentation-fairness):
- **Index + graph** = build + query and prune.
- **Total** = index + graph + clustering.

Paired tables show:
- the difference BallTree − H3 in seconds (positive means H3 is faster);
- the per-trial speedup BallTree / H3 (> 1 means H3 is faster);
- the ratio of means.

### 3.1 Headline speedup (total time, ratio of means; per-trial 95% CI)

| H3 configuration | 10k | 50k | 100k | full |
|---|---:|---:|---:|---:|
| **r8 (k-ring 1), primary** | 0.773× [0.760, 0.788] | 0.908× [0.856, 0.968] | 1.004× [0.994, 1.014] | **1.150× [1.137, 1.164]** |
| r7 (k-ring 1) | 0.606× [0.603, 0.609] | 0.680× [0.676, 0.683] | 0.757× [0.748, 0.767] | 0.842× [0.825, 0.860] |
| r9 (k-ring 2) | 0.605× [0.601, 0.610] | 0.675× [0.670, 0.680] | 0.812× [0.807, 0.818] | 0.911× [0.903, 0.919] |

**Interpretation.**
- **H3 r8 crosses over between 100k and full scale.**
  - It is 0.77× at 10k and 0.91× at 50k.
  - It reaches parity at 100k: 1.004×, with a per-trial 95% CI of [0.994, 1.014] that contains 1.0.
  - It is 1.15× faster at full scale: 10.79 s against 12.41 s total, a paired saving of about 1.62 s.
  - At full scale the index + graph speedup is 1.154× [1.141, 1.168], with ratio of means 1.1541.
- **The speedup comes from graph construction.** BallTree query and prune takes 12.0789 s and H3 r8 takes 10.3781 s. Index build favours BallTree at every scale. Clustering time is the same for both providers, as expected: they share the same core-first engine and produce identical graphs.
- **r7 and r9 lose to BallTree everywhere.** Their gap narrows with scale, reaching 0.842× and 0.911× at full scale, but neither overtakes BallTree within the tested range. Section 5 explains why.

### 3.2 Primary block: BallTree vs. H3 r8 (k-ring 1)

| Scale | Metric | BallTree (s) | H3 r8 (s) |
|---|---|---|---|
| 10k | Build | 0.0036 / 0.0035 / 0.0002 [0.0035, 0.0038] | 0.0131 / 0.0132 / 0.0003 [0.0129, 0.0134] |
| 10k | Query + prune | 0.4306 / 0.4264 / 0.0122 [0.4219, 0.4394] | 0.5531 / 0.5476 / 0.0238 [0.5361, 0.5701] |
| 10k | Clustering | 0.0159 / 0.0157 / 0.0007 [0.0154, 0.0164] | 0.0159 / 0.0157 / 0.0007 [0.0154, 0.0164] |
| 10k | Index + graph | 0.4342 / 0.4299 / 0.0123 [0.4254, 0.4431] | 0.5662 / 0.5603 / 0.0239 [0.5491, 0.5833] |
| 10k | Total | 0.4501 / 0.4457 / 0.0127 [0.4410, 0.4592] | 0.5821 / 0.5759 / 0.0244 [0.5646, 0.5995] |
| 50k | Build | 0.0234 / 0.0234 / 0.0001 [0.0233, 0.0235] | 0.0569 / 0.0563 / 0.0029 [0.0548, 0.0590] |
| 50k | Query + prune | 2.9557 / 2.8365 / 0.2259 [2.7941, 3.1173] | 3.2279 / 3.1382 / 0.2737 [3.0322, 3.4237] |
| 50k | Clustering | 0.0875 / 0.0858 / 0.0037 [0.0849, 0.0901] | 0.0911 / 0.0854 / 0.0184 [0.0779, 0.1042] |
| 50k | Index + graph | 2.9791 / 2.8597 / 0.2259 [2.8175, 3.1407] | 3.2848 / 3.1952 / 0.2763 [3.0872, 3.4825] |
| 50k | Total | 3.0666 / 2.9448 / 0.2284 [2.9032, 3.2300] | 3.3759 / 3.2807 / 0.2945 [3.1652, 3.5866] |
| 100k | Build | 0.0534 / 0.0517 / 0.0050 [0.0498, 0.0569] | 0.1068 / 0.1066 / 0.0012 [0.1060, 0.1077] |
| 100k | Query + prune | 7.0327 / 7.0131 / 0.0859 [6.9713, 7.0941] | 6.9464 / 6.9195 / 0.0888 [6.8829, 7.0099] |
| 100k | Clustering | 0.1798 / 0.1788 / 0.0026 [0.1779, 0.1817] | 0.1826 / 0.1814 / 0.0044 [0.1795, 0.1858] |
| 100k | Index + graph | 7.0861 / 7.0647 / 0.0904 [7.0214, 7.1507] | 7.0533 / 7.0261 / 0.0887 [6.9898, 7.1167] |
| 100k | Total | 7.2659 / 7.2435 / 0.0891 [7.2021, 7.3296] | 7.2359 / 7.2077 / 0.0902 [7.1713, 7.3004] |
| full | Build | 0.0737 / 0.0735 / 0.0008 [0.0731, 0.0743] | 0.1515 / 0.1517 / 0.0013 [0.1506, 0.1525] |
| full | Query + prune | 12.0789 / 12.0387 / 0.0886 [12.0155, 12.1422] | 10.3781 / 10.3754 / 0.1374 [10.2798, 10.4764] |
| full | Clustering | 0.2548 / 0.2542 / 0.0029 [0.2528, 0.2568] | 0.2571 / 0.2543 / 0.0079 [0.2514, 0.2627] |
| full | Index + graph | 12.1526 / 12.1132 / 0.0885 [12.0893, 12.2159] | 10.5297 / 10.5266 / 0.1377 [10.4311, 10.6282] |
| full | Total | 12.4074 / 12.3693 / 0.0892 [12.3436, 12.4712] | 10.7867 / 10.7887 / 0.1404 [10.6863, 10.8872] |

| Scale | Metric | Paired diff BallTree − H3, mean [95% CI] (s) | Per-trial speedup mean / median [95% CI] | Ratio of means |
|---|---|---|---|---:|
| 10k | Index + graph | −0.1319 [−0.1438, −0.1201] | 0.7675 / 0.7688 [0.7528, 0.7823] | 0.7670 |
| 10k | Total | −0.1319 [−0.1436, −0.1203] | 0.7739 / 0.7749 [0.7597, 0.7880] | 0.7733 |
| 50k | Index + graph | −0.3057 [−0.5114, −0.1001] | 0.9102 / 0.8914 [0.8541, 0.9663] | 0.9069 |
| 50k | Total | −0.3093 [−0.5242, −0.0944] | 0.9119 / 0.8942 [0.8556, 0.9683] | 0.9084 |
| 100k | Index + graph | 0.0328 [−0.0373, 0.1030] | 1.0047 / 1.0059 [0.9949, 1.0146] | 1.0047 |
| 100k | Total | 0.0300 [−0.0413, 0.1013] | 1.0042 / 1.0060 [0.9945, 1.0140] | 1.0041 |
| full | Index + graph | 1.6229 [1.4958, 1.7501] | 1.1543 / 1.1568 [1.1411, 1.1676] | 1.1541 |
| full | Total | 1.6206 [1.4917, 1.7496] | 1.1504 / 1.1529 [1.1373, 1.1636] | 1.1502 |

### 3.3 Sensitivity block: BallTree vs. H3 r7 (k-ring 1)

| Scale | Metric | BallTree (s) | H3 r7 (s) |
|---|---|---|---|
| 10k | Build | 0.0036 / 0.0035 / 0.0001 [0.0035, 0.0036] | 0.0113 / 0.0114 / 0.0002 [0.0112, 0.0114] |
| 10k | Query + prune | 0.4168 / 0.4170 / 0.0031 [0.4146, 0.4190] | 0.6924 / 0.6926 / 0.0043 [0.6893, 0.6955] |
| 10k | Clustering | 0.0158 / 0.0158 / 0.0004 [0.0154, 0.0161] | 0.0157 / 0.0157 / 0.0001 [0.0157, 0.0158] |
| 10k | Index + graph | 0.4204 / 0.4205 / 0.0031 [0.4181, 0.4226] | 0.7037 / 0.7040 / 0.0043 [0.7006, 0.7068] |
| 10k | Total | 0.4361 / 0.4359 / 0.0034 [0.4337, 0.4385] | 0.7194 / 0.7198 / 0.0043 [0.7163, 0.7225] |
| 50k | Build | 0.0233 / 0.0233 / 0.0002 [0.0232, 0.0234] | 0.0523 / 0.0525 / 0.0005 [0.0520, 0.0527] |
| 50k | Query + prune | 2.7077 / 2.7068 / 0.0189 [2.6942, 2.7213] | 4.0080 / 4.0074 / 0.0117 [3.9997, 4.0164] |
| 50k | Clustering | 0.0851 / 0.0852 / 0.0008 [0.0845, 0.0857] | 0.0840 / 0.0839 / 0.0003 [0.0838, 0.0842] |
| 50k | Index + graph | 2.7310 / 2.7300 / 0.0189 [2.7175, 2.7445] | 4.0603 / 4.0592 / 0.0116 [4.0520, 4.0687] |
| 50k | Total | 2.8161 / 2.8152 / 0.0193 [2.8022, 2.8299] | 4.1443 / 4.1429 / 0.0118 [4.1359, 4.1528] |
| 100k | Build | 0.0512 / 0.0509 / 0.0008 [0.0506, 0.0517] | 0.1003 / 0.1001 / 0.0010 [0.0995, 0.1010] |
| 100k | Query + prune | 6.8868 / 6.8862 / 0.0844 [6.8264, 6.9471] | 9.1143 / 9.1398 / 0.1016 [9.0417, 9.1870] |
| 100k | Clustering | 0.1754 / 0.1747 / 0.0019 [0.1740, 0.1767] | 0.1767 / 0.1758 / 0.0028 [0.1748, 0.1787] |
| 100k | Index + graph | 6.9380 / 6.9370 / 0.0845 [6.8775, 6.9984] | 9.2146 / 9.2390 / 0.1017 [9.1419, 9.2873] |
| 100k | Total | 7.1133 / 7.1127 / 0.0852 [7.0524, 7.1743] | 9.3914 / 9.4165 / 0.1027 [9.3179, 9.4648] |
| full | Build | 0.0731 / 0.0730 / 0.0009 [0.0725, 0.0737] | 0.1415 / 0.1411 / 0.0013 [0.1406, 0.1424] |
| full | Query + prune | 11.9947 / 11.9684 / 0.1628 [11.8783, 12.1112] | 14.2368 / 14.2903 / 0.3217 [14.0067, 14.4670] |
| full | Clustering | 0.2521 / 0.2518 / 0.0009 [0.2514, 0.2528] | 0.2535 / 0.2534 / 0.0028 [0.2515, 0.2555] |
| full | Index + graph | 12.0678 / 12.0424 / 0.1626 [11.9515, 12.1841] | 14.3783 / 14.4309 / 0.3211 [14.1486, 14.6081] |
| full | Total | 12.3199 / 12.2944 / 0.1623 [12.2038, 12.4360] | 14.6318 / 14.6856 / 0.3229 [14.4008, 14.8628] |

| Scale | Metric | Paired diff BallTree − H3, mean [95% CI] (s) | Per-trial speedup mean / median [95% CI] | Ratio of means |
|---|---|---|---|---:|
| 10k | Index + graph | −0.2833 [−0.2859, −0.2808] | 0.5974 / 0.5967 [0.5947, 0.6000] | 0.5974 |
| 10k | Total | −0.2833 [−0.2860, −0.2806] | 0.6062 / 0.6059 [0.6033, 0.6091] | 0.6062 |
| 50k | Index + graph | −1.3294 [−1.3456, −1.3131] | 0.6726 / 0.6722 [0.6689, 0.6763] | 0.6726 |
| 50k | Total | −1.3283 [−1.3449, −1.3116] | 0.6795 / 0.6790 [0.6758, 0.6832] | 0.6795 |
| 100k | Index + graph | −2.2767 [−2.3741, −2.1792] | 0.7530 / 0.7505 [0.7438, 0.7622] | 0.7529 |
| 100k | Total | −2.2780 [−2.3760, −2.1800] | 0.7575 / 0.7550 [0.7484, 0.7666] | 0.7574 |
| full | Index + graph | −2.3105 [−2.5922, −2.0288] | 0.8397 / 0.8337 [0.8224, 0.8571] | 0.8393 |
| full | Total | −2.3119 [−2.5949, −2.0289] | 0.8424 / 0.8363 [0.8253, 0.8596] | 0.8420 |

### 3.4 Sensitivity block: BallTree vs. H3 r9 (k-ring 2)

| Scale | Metric | BallTree (s) | H3 r9 (s) |
|---|---|---|---|
| 10k | Build | 0.0035 / 0.0035 / 0.0000 [0.0035, 0.0035] | 0.0224 / 0.0224 / 0.0002 [0.0223, 0.0226] |
| 10k | Query + prune | 0.4144 / 0.4139 / 0.0029 [0.4123, 0.4165] | 0.6784 / 0.6762 / 0.0082 [0.6726, 0.6842] |
| 10k | Clustering | 0.0158 / 0.0159 / 0.0002 [0.0157, 0.0160] | 0.0157 / 0.0156 / 0.0002 [0.0155, 0.0158] |
| 10k | Index + graph | 0.4179 / 0.4174 / 0.0029 [0.4159, 0.4200] | 0.7008 / 0.6984 / 0.0082 [0.6949, 0.7067] |
| 10k | Total | 0.4338 / 0.4334 / 0.0030 [0.4316, 0.4359] | 0.7165 / 0.7139 / 0.0083 [0.7105, 0.7225] |
| 50k | Build | 0.0233 / 0.0233 / 0.0003 [0.0231, 0.0235] | 0.0780 / 0.0779 / 0.0012 [0.0772, 0.0789] |
| 50k | Query + prune | 2.7049 / 2.6959 / 0.0331 [2.6812, 2.7286] | 4.0048 / 3.9964 / 0.0560 [3.9648, 4.0448] |
| 50k | Clustering | 0.0846 / 0.0845 / 0.0010 [0.0839, 0.0853] | 0.0853 / 0.0844 / 0.0019 [0.0839, 0.0867] |
| 50k | Index + graph | 2.7282 / 2.7192 / 0.0333 [2.7044, 2.7521] | 4.0828 / 4.0740 / 0.0568 [4.0422, 4.1235] |
| 50k | Total | 2.8129 / 2.8032 / 0.0338 [2.7887, 2.8371] | 4.1681 / 4.1591 / 0.0583 [4.1264, 4.2098] |
| 100k | Build | 0.0511 / 0.0512 / 0.0003 [0.0509, 0.0514] | 0.1346 / 0.1347 / 0.0012 [0.1337, 0.1355] |
| 100k | Query + prune | 6.8875 / 6.8809 / 0.0453 [6.8551, 6.9200] | 8.4458 / 8.4411 / 0.0596 [8.4032, 8.4884] |
| 100k | Clustering | 0.1752 / 0.1753 / 0.0009 [0.1746, 0.1759] | 0.1766 / 0.1764 / 0.0020 [0.1752, 0.1780] |
| 100k | Index + graph | 6.9387 / 6.9321 / 0.0455 [6.9061, 6.9712] | 8.5804 / 8.5743 / 0.0596 [8.5377, 8.6230] |
| 100k | Total | 7.1139 / 7.1080 / 0.0455 [7.0813, 7.1465] | 8.7569 / 8.7510 / 0.0608 [8.7134, 8.8004] |
| full | Build | 0.0729 / 0.0729 / 0.0006 [0.0725, 0.0734] | 0.1962 / 0.1954 / 0.0038 [0.1935, 0.1989] |
| full | Query + prune | 12.0035 / 12.0509 / 0.1333 [11.9081, 12.0988] | 13.0836 / 13.0810 / 0.0744 [13.0304, 13.1368] |
| full | Clustering | 0.2528 / 0.2524 / 0.0021 [0.2513, 0.2544] | 0.2551 / 0.2551 / 0.0022 [0.2535, 0.2567] |
| full | Index + graph | 12.0764 / 12.1243 / 0.1337 [11.9808, 12.1721] | 13.2798 / 13.2766 / 0.0729 [13.2277, 13.3320] |
| full | Total | 12.3293 / 12.3769 / 0.1348 [12.2328, 12.4257] | 13.5349 / 13.5310 / 0.0744 [13.4817, 13.5881] |

| Scale | Metric | Paired diff BallTree − H3, mean [95% CI] (s) | Per-trial speedup mean / median [95% CI] | Ratio of means |
|---|---|---|---|---:|
| 10k | Index + graph | −0.2829 [−0.2880, −0.2778] | 0.5964 / 0.5978 [0.5922, 0.6006] | 0.5963 |
| 10k | Total | −0.2827 [−0.2879, −0.2776] | 0.6055 / 0.6070 [0.6012, 0.6097] | 0.6054 |
| 50k | Index + graph | −1.3546 [−1.3843, −1.3249] | 0.6683 / 0.6678 [0.6632, 0.6733] | 0.6682 |
| 50k | Total | −1.3552 [−1.3856, −1.3249] | 0.6749 / 0.6743 [0.6699, 0.6799] | 0.6749 |
| 100k | Index + graph | −1.6417 [−1.6924, −1.5910] | 0.8087 / 0.8079 [0.8035, 0.8139] | 0.8087 |
| 100k | Total | −1.6430 [−1.6940, −1.5921] | 0.8124 / 0.8118 [0.8073, 0.8175] | 0.8124 |
| full | Index + graph | −1.2034 [−1.3095, −1.0972] | 0.9094 / 0.9136 [0.9016, 0.9172] | 0.9094 |
| full | Total | −1.2057 [−1.3127, −1.0986] | 0.9109 / 0.9152 [0.9032, 0.9187] | 0.9109 |

---

## 4. Phase 3 — Peak Memory (`tracemalloc`)

Peak `tracemalloc` memory in MiB. Each value comes from one isolated pass per provider and scale (`detailed_timing = false`), never mixed with the timed trials.

| Scale | Rows | BallTree | H3 r7 | H3 r8 | H3 r9 |
|---|---:|---:|---:|---:|---:|
| 10k | 10,000 | 13.6 | 14.0 | 14.2 | 14.7 |
| 50k | 50,000 | 74.5 | 77.1 | 77.4 | 78.8 |
| 100k | 100,000 | 159.3 | 164.4 | 164.7 | 166.5 |
| full | 143,116 | 225.8 | 233.3 | 233.8 | 236.9 |

At full scale the H3 peaks exceed BallTree by +3.3% (r7), +3.6% (r8) and +4.9% (r9). These percentages are derived from the recorded MiB values.

> **Scope of the memory measurement.** `tracemalloc` captures Python-tracked allocations, including NumPy buffers. It does **not** capture native C/C++/Cython allocations that bypass the Python allocator, such as scikit-learn's BallTree internals or the H3 C library. Process RSS (`psutil`) was not measured, because `psutil` is not a project dependency. These figures therefore do not cover total process memory.

---

## 5. Phase 4 — Stage Diagnostics & Mechanistic Explanation

> **Not comparable with Phase 2.** These are single `detailed_timing = true` passes, and the per-stage timers add overhead. They explain *where* time goes; Phase 2 is the authority on *how much*.

All times are in seconds. "—" means the stage does not exist for that provider. H3 fallback count is 0 in every run.

| Scale | Provider | Build | Cell mapping | Candidate precomp. | Candidate retrieval | Temporal filtering | Distance filtering | Candidates evaluated | Clustering | Occupied cells |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10k | BallTree | 0.004 | — | — | 0.120 | 0.053 | 0.222 | 2,549,460 | 0.015 | — |
| 10k | H3 r7 | 0.011 | 0.009 | 0.002 | 0.002 | 0.231 | 0.416 | 6,021,332 | 0.016 | 102 |
| 10k | H3 r8 | 0.013 | 0.009 | 0.005 | 0.002 | 0.200 | 0.299 | 2,567,218 | 0.016 | 296 |
| 10k | H3 r9 | 0.023 | 0.009 | 0.014 | 0.002 | 0.367 | 0.284 | 1,895,404 | 0.016 | 762 |
| 50k | BallTree | 0.024 | — | — | 0.906 | 0.531 | 1.196 | 67,849,586 | 0.085 | — |
| 50k | H3 r7 | 0.054 | 0.044 | 0.010 | 0.014 | 1.851 | 2.414 | 32,635,408 | 0.094 | 123 |
| 50k | H3 r8 | 0.058 | 0.044 | 0.013 | 0.013 | 1.370 | 1.657 | 13,963,936 | 0.088 | 455 |
| 50k | H3 r9 | 0.081 | 0.046 | 0.035 | 0.015 | 2.414 | 1.534 | 10,353,122 | 0.088 | 1506 |
| 100k | BallTree | 0.052 | — | — | 2.552 | 1.845 | 2.580 | 302,303,216 | 0.179 | — |
| 100k | H3 r7 | 0.102 | 0.086 | 0.016 | 0.028 | 5.004 | 4.878 | 65,492,824 | 0.192 | 137 |
| 100k | H3 r8 | 0.120 | 0.090 | 0.030 | 0.036 | 4.005 | 3.920 | 28,957,656 | 0.194 | 555 |
| 100k | H3 r9 | 0.148 | 0.094 | 0.054 | 0.036 | 5.515 | 3.251 | 21,544,668 | 0.179 | 1889 |
| **full** | BallTree | 0.073 | — | — | 5.671 | 3.792 | 4.022 | 602,195,852 | 0.365 | — |
| **full** | H3 r7 | 0.147 | 0.122 | 0.025 | 0.046 | 9.304 | 7.374 | 92,374,636 | 0.264 | 172 |
| **full** | H3 r8 | 0.152 | 0.123 | 0.029 | 0.038 | 5.766 | 4.903 | 41,015,702 | 0.260 | 798 |
| **full** | H3 r9 | 0.203 | 0.130 | 0.073 | 0.047 | 8.655 | 4.460 | 30,448,440 | 0.267 | 2937 |

Instrumented query and prune at full scale: BallTree 14.010 s, H3 r7 17.579 s, H3 r8 11.372 s, H3 r9 13.914 s.

> **What `candidates_evaluated` counts.** The two providers count at different pipeline stages, so the columns are not like-for-like.
> - **BallTree** counts the **spatial-only** candidates returned by `query_radius`: every point within 300 m at *any* time of day. This is counted *before* the exact temporal filter ([`balltree_neighbors.py`](../../src/aegismar/clustering/balltree_neighbors.py)).
> - **H3** counts candidates that have *already* passed the temporal window, via a binary search on each candidate cell's sorted timestamps. This is counted *before* the exact Haversine filter ([`h3_neighbors.py`](../../src/aegismar/clustering/h3_neighbors.py)).

### 5.1 Why the crossover occurs

**BallTree candidates grow with the whole day.** BallTree indexes only space. A vessel moored or anchored for many hours contributes every one of its own pings within 300 m as a candidate for every other ping, whatever the time gap. The spatial candidate stream therefore grows with the time span covered as well as with the row count. Going from 10k (1.6 h span) to full scale (24 h span), rows grow 14.3×, but BallTree's spatial candidates grow 236× (2.55 M → 602.2 M; ratios derived). BallTree then discards most of these in its vectorised temporal filter. The compiled `query_radius` retrieval (5.671 s) and the temporal filter (3.792 s) dominate its full-scale cost.

**H3 does not generate those candidates.** H3 r8 pre-buckets points by cell, with timestamps sorted within each cell. Each query binary-searches only the time window `[t − 900 s, t + 900 s]` inside the 7 cells of its k-ring 1 disk, so time-ineligible points are never produced. Over the same 10k → full range, its candidates grow only 16.0× (2.57 M → 41.0 M), and at full scale it evaluates 14.7× fewer candidates than BallTree's spatial stream (derived).

**The cost is a fixed per-point overhead.** H3 runs a Python-level loop for each point (the temporal-filtering stage: 5.766 s at full scale for r8). BallTree batches its queries in compiled code.
- **Small prefixes:** only a few hours are covered, so BallTree's candidate stream is small and the fixed Python overhead makes H3 slower (0.77× at 10k).
- **Around 100k (about 17 h):** the two effects balance (parity).
- **Full day:** BallTree's time-blind candidate explosion outweighs the overhead, and H3 r8 is faster (1.15×).

### 5.2 Why r7 and r9 lose to r8

- **r7 (k-ring 1, 172 coarse occupied cells at full scale).** Each query still visits 7 cells, but the cells are large, so many temporally eligible points lie far outside 300 m. Candidates rise to 92.4 M, 2.25× r8's 41.0 M (derived). Both the temporal stage (9.304 s) and the Haversine stage (7.374 s) get more expensive.
- **r9 (k-ring 2, 2,937 fine occupied cells at full scale).** The finer cells give the fewest candidates (30.4 M) and the cheapest Haversine stage among H3 configurations (4.460 s). But k-ring 2 visits 19 cells per query (1 + 6 + 12 for a hexagon) instead of 7. That means 19 binary-search pairs per point inside the Python loop, and the temporal stage rises to 8.655 s.
- **r8 (k-ring 1, 798 cells)** sits between the two failure modes: cells fine enough to keep candidates low, with a 7-cell disk that keeps the per-point loop short.

This explanation is consistent with the recorded stage timings and with the code. It is an interpretation of one host's measurements, not a separately tested causal claim.

---

## 6. Measurement Caveats & Threats to Validity

- **Single host and dataset; descriptive intervals.** The 95% Student-t intervals describe run-to-run dispersion on one Windows/AMD workstation, one dataset and one parameter set. They make no claim of significance across hardware, operating systems, datasets or parameters ([protocol §6, §8](w3-02-benchmark-protocol.md#8-threats-to-validity-and-limitations)).
- **Transient host slowdown at r8 @ 50k.** In the primary block at 50k, raw total times rose for a short stretch:
  - BallTree trials 6–8: 3.2967, 3.4084 and 3.4238 s, against 2.8253–2.9580 s in trials 0–5.
  - H3 trial 6: 4.2101 s, against 3.2471–3.3343 s otherwise.
  - Both providers were affected in the same window, which points to host interference rather than a provider effect.
  - This cell therefore has the widest dispersion in the run (sd 0.2284 s and 0.2945 s for total time). Its 95% CI for the paired speedup, [0.856, 0.968], still lies entirely below 1.0.
- **Mild execution-order drift.** Per-provider means differ slightly by run position. These figures are derived from the raw trials, comparing H3-first (odd) and BallTree-first (even) trials:
  - **Largest systematic effect:** at r7 full scale, H3 is about 4% slower when it runs second.
  - **r8 @ 50k:** +5.8%, but this is driven by the single H3 trial-6 outlier above.
  - **Elsewhere:** within ±2%.
  - Counterbalanced pairing gives each provider 5 first-position and 5 second-position runs per cell, which offsets this drift in the paired statistics. It does widen the r7 full-scale intervals.
- **Instrumented diagnostics.** In Phase 4, BallTree's full-scale clustering time (0.365 s) is higher than its Phase-2 mean (0.2548 s), while the other providers match their Phase-2 values. Phase 4 is a single instrumented pass and is not used for any comparison.
- **Chronological prefixes, not random samples.** The 10k/50k/100k subsets cover the first 1.6 h, 8.3 h and 17.1 h of 2025-01-01. The crossover is tied to the time span covered, so results at a given row count could differ for a random sample or a denser multi-day input.
- **Implementation level.** H3's per-point query loop runs in Python, while BallTree's `query_radius` is compiled and batched. The results compare these implementations as built, not the asymptotic merit of either index.
- **Scale ceiling.** The 500k tier of [evaluation-protocol.md §2.1](evaluation-protocol.md) is deferred, because no dataset of that size exists yet. Behaviour above 143,116 rows is untested.
- **Native memory not captured** by `tracemalloc` (see Section 4).
- **Fixed parameters.** Only 300 m / 900 s / MinPts 5 was benchmarked, and sensitivity to ε is out of scope. A different ε would change the calibrated k-rings and candidate volumes.

---

## 7. Reproduction

```bash
uv run python experiments/clustering/w3_02_benchmark.py \
    -i data/processed/lalb_20250101_v1_1/cleaned_ais.parquet \
    -o experiments/outputs/w3_02_benchmark_results.json
```

- **Run at:** commit `379ec16` with a clean working tree.
- **Defaults:** `--scales 10000 50000 100000 full --trials 10 --warmup 1 --oracle-rows 2000 --sensitivity-resolutions 7 9`.
- **Overwrite protection:** the runner refuses to replace an existing result unless `--overwrite` is passed.
- **Progress output:** printed once per phase, scale and block, not per trial. At full scale a single Phase-2 block can run silently for several minutes.
- **Results are host-specific.** A rerun on other hardware will give different absolute timings. Phase 1 correctness should be identical.
