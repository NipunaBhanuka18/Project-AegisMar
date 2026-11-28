# Research Evidence Register & Verification Matrix

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**  
> **Document Version:** 1.2  
> **Lifecycle Status:** Active Evidence Baseline  
> **Maintained By:** NipunaBhanuka18 (Project Lead) & Kishakya (Track B Lead)  
> **Last Reconciled:** 2026-11-28 (W3-02 benchmark added; v1.1 dataset reconciliation of 2026-11-25 unchanged)  

---

## 1. Purpose and Evidentiary Standard

This document establishes the official **Research Evidence Register** for Project AegisMar. To maintain absolute academic and scientific integrity, every technical claim, benchmark measurement, algorithmic property, and empirical observation in the project must be traceable to concrete, auditable evidence.

### Evidence Classification Hierarchy
Every claim in this register is categorized under one of six strict evidentiary categories:
1. **Implemented and Code-Inspected**: Verified by manual code review and static analysis of production source files in `src/`.
2. **Tested by Automated Checks**: Formally verified by deterministic unit tests or oracle tests in `tests/` (executed and verified locally via `uv run pytest`).
3. **Experimentally Observed**: Directly measured in an executed experiment with logged JSON artifacts and execution parameters.
4. **Independently Reproduced**: Re-executed and verified independently across separate environments or repeated runs.
5. **Reported by Development Assistant**: Recorded in historical completion reports but not yet independently re-measured in multi-trial runs.
6. **Planned or Hypothesized**: Theoretical expectations, research hypotheses (H1, H2), or planned capabilities not yet implemented.

### Claim Accounting & Evidentiary Category Totals

The register currently tracks **22 formal claims** classified across the evidentiary hierarchy:

| Evidentiary Category | Claim Count | Active Claim Identifiers |
|---|---|---|
| **1. Implemented and Code-Inspected** | 0 | *(Baseline modules covered under Category 2 checks)* |
| **2. Tested by Automated Checks** | 12 | `CLM-ING-01`, `CLM-ING-02`, `CLM-ING-03`, `CLM-ING-04`, `CLM-ING-05`, `CLM-SPA-01`, `CLM-SPA-02`, `CLM-CLU-01`, `CLM-CLU-02`, `CLM-CLU-03`, `CLM-CLU-06`, `CLM-ANO-05` |
| **3. Experimentally Observed** | 7 | `CLM-ING-06`, `CLM-ING-08`, `CLM-CLU-04`, `CLM-CLU-07`, `CLM-ANO-02`, `CLM-ANO-03`, `CLM-ANO-04` |
| **4. Independently Reproduced** | 1 | `CLM-ING-07` |
| **5. Reported by Development Assistant** | 1 | `CLM-CLU-05` |
| **6. Planned or Hypothesized** | 1 | `CLM-ANO-01` |
| **Total Tracked Claims** | **22** | |

> [!CAUTION]
> **Scientific Integrity Guardrails**:
> - Passing automated unit tests verify software correctness against defined mathematical assertions; they do **not** prove operational maritime domain validity.
> - Code coverage percentages (e.g. 95%) measure line execution in tests; they do **not** measure model accuracy or detection precision.
> - A single performance run is an initial exploratory observation; it is **not** a statistically generalized multi-trial benchmark.
> - Density clusters discovered by ST-DBSCAN are raw spatiotemporal groupings; they are **not** validated commercial anchorages.
> - Local experiment output files (`experiments/outputs/*`) are intentionally excluded from Git tracking by `.gitignore` to keep the repository lightweight. This document specifies exact commands to reproduce any local artifact.

---

## 2. Dataset Accounting & Provenance Reconciliation

Before evaluating algorithmic claims, the data pipeline accounting from raw bytes to cluster assignments is reconciled below:

```text
  Raw Source Extract (sample_lalb_20250101.csv)
  └─ 143,156 raw CSV rows (362 unique MMSIs)
       │
       ▼ [Ingestion Pipeline: aegismar ingest]
       ├─ Exact Duplicates Dropped:           32 rows
       ├─ Hard-Invalid Coordinates Dropped:    0 rows
       ├─ Timestamp Conflicts Flagged:         8 rows (TIMESTAMP_POSITION_CONFLICT, preserved)
       └─ Teleportation Speeds Flagged:       18 rows (IMPLIED_SPEED_VIOLATION, preserved)
       │
  Cleaned Canonical Dataset (cleaned_ais.parquet, zstd-compressed)
  └─ 143,124 output rows (362 unique MMSIs, 19 canonical columns)
       │
       ▼ [Clustering Quality Filter Policy: QualityFilterPolicy(exclude_timestamp_conflicts=True)]
       ├─ Excluded Rows:                       8 rows (TIMESTAMP_POSITION_CONFLICT excluded)
       │
  Filtered Clustering Input (ClusteringInputDataset)
  └─ 143,116 analyzed observations
       │
       ▼ [BallTree ST-DBSCAN: eps_spatial=300m, eps_temporal=900s, MinPts=5]
       ├─ Core Points:                   136,276 observations (95.22%)
       ├─ Border Points:                     934 observations ( 0.65%)
       ├─ Noise Points:                    5,906 observations ( 4.13%)
       ├─ Accounting Verification:       136,276 + 934 + 5,906 = 143,116 (Exact 100% Match)
       └─ Discovered Density Clusters:       241 exploratory clusters (spanning berths, anchorages, and channels)
            │
            ▼ [Static Map Preview Export: clusters_preview.geojson]
            └─ Visualized Preview Subset:  5,000 observations (subsampled strictly for map rendering responsiveness)
```

### 2.1 Canonical Dataset Versions (reconciled 2026-11-25)

Two cleaned versions of the 2025-01-01 LA/LB dataset exist. They are identified by file SHA-256 **and** by the
writer-independent logical content fingerprint (`aegismar-logical-v1`, ADR-011), never by path alone.

| Version | Status | Path convention | File SHA-256 | Logical fingerprint | Produced by | Used by |
|---|---|---|---|---|---|---|
| **v1.0** | Historical, immutable | `data/processed/lalb_20250101/` | `4a7ca719dc2a3d9959cc4166edff773ca09156d8d914e54d0ab5f851ece5e88b` | `570b0fb09182720fc476b4b712c0d599bed3ed34491aad4946719fab965a1473` | `aegismar ingest` at `1b573ad` (W1-02B, before the W2-01 cleaner hardening) | W2-01 clustering baseline and W3-01/W3-01B H3 parity (`CLM-CLU-04`, `CLM-CLU-06`) |
| **v1.1** | **Canonical** for Track A (from W3-02) and Track B | `data/processed/lalb_20250101_v1_1/` | `bdde2581302270a9e2c99a1a7aa1819a0bd1a24fbf6384458cfd8a81229eaf48` | `d8a619f7d27314ae8418eff5da8e1c5c96004d038c2fce8f5ee868ed90fec2cf` | `aegismar ingest` at current `main` (W2-01 hardened cleaner) | W3-02 benchmark; Track B ML-01 to ML-05 |

- **Difference:** exactly 12 rows, only in the derived columns `prev_source_row`, `elapsed_seconds`, `distance_nm`
  and `implied_speed_knots` (`CLM-ING-08`). All positions, timestamps, kinematic fields and quality flags are identical.
- **Clustering equivalence:** after the default `QualityFilterPolicy`, both versions give bit-identical clustering inputs
  (143,116 rows), so the W2-01 and W3-01/W3-01B clustering and parity results apply unchanged to v1.1.
- **Track B must use v1.1:** ML-02 §4.2 relies on conflict rows having null predecessor pointers, which only v1.1 provides.
- **Workstation note:** on the Track B workstation, `data/processed/lalb_20250101/` was regenerated on 2026-11-23 (before
  the `_v1_1` path convention) and therefore holds v1.1 bytes. Always confirm a local file with `aegismar fingerprint`.
- **Reproduce:** `uv run python scripts/slice_noaa_bbox.py data/raw/ais-2025-01-01.csv.zst data/raw/sample_lalb_20250101.csv --lat 33.5 33.9 --lon -118.4 -118.0`,
  then `uv run python -m aegismar ingest -i data/raw/sample_lalb_20250101.csv -o data/processed/lalb_20250101_v1_1`,
  then `uv run python -m aegismar fingerprint -i data/processed/lalb_20250101_v1_1/cleaned_ais.parquet`.

---

## 3. Evidence Register Matrix

| Claim ID | Category | Claim Statement | Dataset & Target | Version / Config | Evidence Artifact / Code | Verification Status | Known Limitations |
|---|---|---|---|---|---|---|---|
| **CLM-ING-01** | Tested by Automated Checks | Dual schema adapter parses both NOAA 2025 (`snake_case`) and legacy (`PascalCase`) CSV formats, standardizing to 19 canonical columns. | Synthetic fixtures | `v0.1.0.dev1` | `src/aegismar/ingestion/schema.py`<br>`tests/unit/test_ingestion.py` (`test_01`, `test_02`) | **Verified** (Tests pass) | Schema must contain required fields (`mmsi`, `timestamp_utc`, `latitude`, `longitude`). |
| **CLM-ING-02** | Tested by Automated Checks | Ambiguous headers and duplicate raw columns mapping to the same canonical target are strictly rejected via `SchemaAdapterError`. | Synthetic fixtures | `v0.1.0.dev1` | `src/aegismar/ingestion/schema.py`<br>`tests/unit/test_ingestion.py` (`test_20`) | **Verified** (Tests pass) | Custom unmapped headers are ignored. |
| **CLM-ING-03** | Tested by Automated Checks | MMSI sanitation accepts only valid integer-format identifiers, zero-padding to 9 characters, and strictly rejects malformed decimals/floats. | Synthetic fixtures | `v0.1.0.dev1` | `src/aegismar/ingestion/cleaner.py`<br>`tests/unit/test_ingestion.py` (`test_04`, `test_05`, `test_17`) | **Verified** (Tests pass) | Rejects non-conforming test IDs. |
| **CLM-ING-04** | Tested by Automated Checks | International sentinels (`SOG 102.3`, `COG 360.0`, `HDG 511`, `Status 15`) and 2025 nulls are coerced to explicit typed nulls without dropping coordinates. | Synthetic fixtures | `v0.1.0.dev1` | `src/aegismar/ingestion/cleaner.py`<br>`tests/unit/test_ingestion.py` (`test_06`) | **Verified** (Tests pass) | Null values must be handled by downstream consumers. |
| **CLM-ING-05** | Tested by Automated Checks | Exact duplicate rows are consolidated (`EXACT_DUPLICATE`), while same-timestamp differing positions are preserved with `TIMESTAMP_POSITION_CONFLICT` and zero fictitious movement. | Synthetic fixtures | `v0.1.0.dev1` | `src/aegismar/ingestion/cleaner.py`<br>`tests/unit/test_ingestion.py` (`test_09`, `test_10`, `test_18`, `test_19`) | **Verified** (Tests pass) | Preserves conflicts for analytical inspection. |
| **CLM-ING-06** | Experimentally Observed | Ingestion of real San Pedro Bay sample converts 143,156 input records into 143,124 output rows in 7.19 s (~19,900 rec/s), identifying 362 vessels, 32 duplicates, and 18 speed violations ($>50\text{ kt}$). | `sample_lalb_20250101.csv`<br>(SHA-256: `42e4f766...`) | Commit `1b573ad`<br>(hardened `3ece859`) | `data/processed/lalb_20250101/manifest.json`<br>`data/processed/lalb_20250101/cleaned_ais.parquet` | **Verified on Local Disk** (Manifest confirmed) | In-memory batch ingestion; requires host RAM proportional to CSV size. |
| **CLM-ING-07** | Independently Reproduced | Both cleaned-dataset versions are byte-for-byte reproducible on a second workstation: ingestion at `1b573ad` reproduces v1.0 (`4a7ca719...`), ingestion at current `main` reproduces v1.1 (`bdde2581...`), and `scripts/slice_noaa_bbox.py` reproduces the regional sample (`42e4f766...`) from the NOAA extract. | `ais-2025-01-01.csv.zst` (SHA-256 `36c07f4a...`) → `sample_lalb_20250101.csv` | Commits `1b573ad`, `95b7e50`, `c468fd1` | `scripts/slice_noaa_bbox.py`; `aegismar ingest`; `aegismar fingerprint`; development log 2026-11-25 | **Verified** (identical file SHA-256 on two workstations) | Byte identity depends on the PyArrow writer (26.0.1); the logical fingerprint is the writer-independent identity (ADR-011). |
| **CLM-ING-08** | Experimentally Observed | v1.0 and v1.1 differ in exactly 12 rows of the derived columns `prev_source_row`, `elapsed_seconds`, `distance_nm`, `implied_speed_knots`: the 8 `TIMESTAMP_POSITION_CONFLICT` rows (v1.0 fictitious links, v1.1 null) and the 4 following rows (re-linked to the last unambiguous observation). After the default quality filter both yield bit-identical clustering inputs (143,116 rows: source rows, MMSIs, timestamps, latitudes, longitudes). | v1.0 vs v1.1 `cleaned_ais.parquet` | `QualityFilterPolicy()` default | Row-level diff and `load_clustering_dataset_from_parquet` comparison (2026-11-25) | **Verified** (executed comparison) | Equivalence covers clustering inputs only; Track B features use the derived columns and require v1.1. |
| **CLM-SPA-01** | Tested by Automated Checks | Haversine distance implementation computes exact spherical great-circle distances across standard coordinates, high latitudes, and anti-meridian dateline crossings ($\pm 180^\circ$). | Synthetic & extreme coordinates | `v0.1.0.dev1` | `src/aegismar/spatial/haversine.py`<br>`tests/unit/test_st_dbscan.py` (`test_10`, `test_11`) | **Verified** (Tests pass) | Assumes spherical Earth ($R=6{,}371{,}008.8\text{ m}$); max ~0.5% deviation from WGS 84 ellipsoid. |
| **CLM-SPA-02** | Tested by Automated Checks | Independent $O(N^2)$ brute-force test oracle calculates exact scalar Haversine distances independently of scikit-learn, with an automated $N \le 5{,}000$ safety cap. | Synthetic fixtures | `v0.1.0.dev1` | `src/aegismar/spatial/oracle.py`<br>`tests/unit/test_oracle.py` (7 tests) | **Verified** (Tests pass) | Capped at $N \le 5{,}000$ to prevent quadratic execution lockup. |
| **CLM-CLU-01** | Tested by Automated Checks | `BallTreeNeighborhoodProvider` matches brute-force oracle neighbor sets 100% across randomized datasets, extreme boundaries, and a 1,000-row real LA/LB subset. | Randomized & real 1k subset | `v0.1.0.dev1` | `src/aegismar/clustering/balltree_neighbors.py`<br>`tests/unit/test_oracle.py` (`test_12`, `test_oracle_matches_balltree...`) | **Verified** (Tests pass) | Tests neighborhood candidate retrieval; does not measure traffic semantics. |
| **CLM-CLU-02** | Tested by Automated Checks | Core-first ST-DBSCAN (`stdbscan-core-first-v1.0`) produces identical cluster assignments regardless of input row permutation (input permutation invariance on tested runtime). | Synthetic permutation fixtures | Policy `v1.0` | `src/aegismar/clustering/st_dbscan.py`<br>`tests/unit/test_st_dbscan.py` (`test_13`) | **Verified** (Tests pass) | Requires canonical sorting pass prior to clustering; verified deterministic within tested Python runtime. |
| **CLM-CLU-03** | Tested by Automated Checks | Non-core points reachable from multiple core components are deterministically attached to the nearest core component via lexicographical tie-breaker tuple `(dist, |dt|, cluster_id, core_idx)`. | Multi-core boundary fixtures | Policy `v1.0` | `src/aegismar/clustering/st_dbscan.py`<br>`tests/unit/test_st_dbscan.py` (`test_09`) | **Verified** (Tests pass) | Tie-breaking is geometric and temporal; not hydrodynamic. |
| **CLM-CLU-04** | Experimentally Observed | Exploratory BallTree ST-DBSCAN run on 143,116 analyzed LA/LB rows partitions observations into 241 spatiotemporal density clusters (136,276 core, 934 border, 5,906 noise). | `cleaned_ais.parquet` historical v1.0<br>(SHA-256: `4a7ca719...`; clustering inputs identical to canonical v1.1, §2.1) | $\varepsilon_s=300\text{m}$, $\Delta T=900\text{s}$, $\text{MinPts}=5$ | `experiments/outputs/w2_01_lalb_balltree/clustering_summary.json` | **Verified on Local Disk** (Summary JSON verified) | Clusters represent raw density groups; they are **NOT** 241 confirmed anchorages. |
| **CLM-CLU-05** | Reported by Development Assistant | Exploratory BallTree ST-DBSCAN recorded 13.680 s uninstrumented wall time (0.077 s build, 13.341 s query, 0.262 s clustering) in development log; instrumented run recorded 38.014 s wall time with 225.83 MB peak heap in summary JSON. | `cleaned_ais.parquet` | Commit `3ece859` | `experiments/outputs/w2_01_lalb_balltree/clustering_summary.json`<br>`docs/04-development/development-log.md` | **Recorded in Log; Not Multi-Trial Benchmark** | Measured on a single workstation run; uninstrumented timing reported in dev log, instrumented timing in summary JSON; not a multi-trial benchmark. |
| **CLM-CLU-06** | Tested by Automated Checks | Uber H3 candidate generation with empirical clearance lower bounds on calibrated resolutions (7, 8, 9), exact Haversine/temporal pruning, and fail-closed BallTree fallback for unsupported or anomalous configurations (Option B) achieves 100% recall (0 missing neighbors) against the brute-force oracle across 32 unit test fixture categories and 100% bit-for-bit CSR graph parity (13,188,256 / 13,188,256 edges, identical `indptr` and `indices`) against the BallTree reference on 143,116 real LA/LB observations (`cleaned_ais.parquet` historical v1.0, SHA-256: `4a7ca719...`, verified via `aegismar verify-parity`; clustering inputs bit-identical to canonical v1.1, §2.1). | Synthetic fixtures & `cleaned_ais.parquet` | Calibrated Res 7–9, Option B | `src/aegismar/clustering/h3_neighbors.py`<br>`tests/unit/test_h3_neighbors.py` (32 fixtures)<br>`experiments/outputs/w3_01_lalb_h3/clustering_summary.json` | **Verified** (Automated checks & real LA/LB parity pass) | Proves neighborhood candidate completeness and clustering equivalence under Option B contract on calibrated domain; formal comparative speedup benchmarking belongs to W3-02 ($H_{1,A}$). |
| **CLM-CLU-07** | Experimentally Observed | W3-02 multi-trial benchmark (1 warm-up + 10 counterbalanced paired trials per block and scale, `detailed_timing=False`): H3 at resolutions 7, 8 and 9 reproduces BallTree exactly at 10k / 50k / 100k / full (143,116 rows). Every check gives an exact CSR graph match, recall = precision = ARI = 1.0, 13,188,256 directed edges at full scale and 0 fallbacks; the 2,000-row brute-force oracle check also passes. H3 r8 total-time speedup (BallTree / H3, ratio of means): 0.773× (10k), 0.908× (50k), 1.004× (100k; per-trial 95% CI [0.994, 1.014]) and **1.150×** at full scale (12.4074 s vs 10.7867 s; paired saving 1.6206 s [1.4917, 1.7496]; index + graph per-trial speedup 1.1543× [1.1411, 1.1676]). r7 (0.842×) and r9 (0.911×) remain slower than BallTree at full scale. Full-scale `tracemalloc` peak: BallTree 225.8 MiB, H3 r8 233.8 MiB. | Canonical v1.1 `cleaned_ais.parquet` (SHA-256 `bdde2581...`, fingerprint `d8a619f7...`) | Commit `379ec16` (`git_dirty=false`); 300 m / 900 s / MinPts 5; h3 4.5.1, scikit-learn 1.9.1, numpy 2.4.6 | [w3-02-benchmark-protocol.md](w3-02-benchmark-protocol.md); [w3-02-benchmark-results.md](w3-02-benchmark-results.md); `experiments/outputs/w3_02_benchmark_results.json` | **Verified on Local Disk** (result JSON `status = "completed"`, all parity and trial-integrity checks passed) | Single host (Windows, AMD, 16 logical CPUs), single dataset and parameter set; descriptive 95% t-intervals only; chronological prefixes; `tracemalloc` excludes native memory and RSS is not measured; 500k scale deferred. |
| **CLM-ANO-01** | Planned / Hypothesized | Multi-factor kinematic trajectory anomaly scoring will achieve at least 15 percentage points higher $F_1$ than ST-DBSCAN spatial density noise ($H_{2,A}$). | Held-out trajectory partitions (test days 2025-01-14, 2025-01-22) | Rule-based (R1) vs. density noise (B0); IF (M1) | `docs/03-research/vessel-behavior-ml.md`<br>`docs/03-research/ml-03-evaluation-protocol.md` (frozen decision rules, §8) | **Unverified Hypothesis** (Planned ML track) | Anomaly models are **not yet implemented**; the evaluation protocol and statistical decision rules are frozen in ML-03 v1.0; hypotheses remain subject to experiment. |
| **CLM-ANO-02** | Experimentally Observed | On the canonical development day, reporting cadence is coarse: the most common intervals are 180 s (26,305 pairs) and 70 s (15,020 pairs), with a median of 70 s when the preceding ping is moving (SOG ≥ 1.5 kt). 90.0% of SOG values are < 0.5 kt; 135 of 362 vessels ever reach SOG ≥ 1.5 kt; heading is present in 63.0% of Class A and 8.8% of Class B rows. | v1.1 (`bdde2581...`) | ML-01 profile | `experiments/anomaly/ml01_profile_dataset.py` → `experiments/outputs/anomaly/ml01_profile/profile.json` | **Verified on Local Disk** | Single day (a public holiday); descriptive only. |
| **CLM-ANO-03** | Experimentally Observed | Two feed-wide reception silences (no observation from any vessel) occur on 2025-01-01, 03:07:37–03:20:25 and 12:06:09–12:18:20 UTC, spanned by 557 of the 1,579 vessel reporting gaps > 600 s. | v1.1 | Silence > 60 s, merge ≤ 180 s (ML-02 G6/G7) | `ml01_profile_dataset.py`; `aegismar.anomaly.features.detect_outage_windows`; `tests/unit/test_anomaly.py` (real-data check) | **Verified** | Property of the receiver network on this day; cause not established. |
| **CLM-ANO-04** | Experimentally Observed | Of 429 COG–heading disparities > 45° at SOG ≥ 1.5 kt, 342 are near-reversals (> 135°; 29 vessels, 281 rows from tug/towing vessels) and 87 are lateral drift (45–135°; 20 vessels). | v1.1 | SOG guard 1.5 kt | `experiments/anomaly/ml02_drift_breakdown.py` | **Verified on Local Disk** | The physical cause of the reversals is not established from AIS alone. |
| **CLM-ANO-05** | Tested by Automated Checks | The ML-04 feature extractor implements ML-02 v1.0 (angular wrapping, dead reckoning, rate guards, conflict-row skipping, outage-aware gaps, segment-bounded windows, permutation invariance, no cross-vessel leakage), and the test-day firewall refuses held-out days using Parquet metadata only. | Synthetic fixtures (plus a real-data outage/segment check when data is present) | ML-02 v1.0 / ML-03 v1.0 | `src/aegismar/anomaly/`; `tests/unit/test_anomaly.py` (34 tests) | **Verified** (Tests pass) | Software correctness only; says nothing about detection performance. |

---

## 4. Reconciled Technical Facts vs. Common Misinterpretations

To avoid confusion in academic papers, thesis defenses, or documentation reviews, the following factual boundaries are formally recorded:

### 1. "241 Clusters" vs. "241 Anchorages"
- **Factual Reality**: The exploratory ST-DBSCAN run discovered **241 spatiotemporal density clusters** ($\varepsilon_{\text{spatial}} = 300\text{ m}, \Delta T_{\text{temporal}} = 900\text{ s}, \text{MinPts} = 5$).
- **What they actually represent**: These clusters include container vessels moored alongside inner terminal wharves, tugboats working harbor channels, slow-moving vessels in entrance fairways, and vessels anchored in outer commercial anchorages.
- **Why they are not anchorages**: True anchorage identification requires **stay-point extraction** ($\Delta D_{\text{max}} \le 500\text{ m}$ for $\Delta T_{\text{min}} \ge 30\text{ min}$) and **berth polygon exclusion** to remove berthed vessels (scheduled for Milestone W4-01).

### 2. "100% Oracle Match" vs. "Maritime Detection Accuracy"
- **Factual Reality**: Automated test `test_oracle_matches_balltree_across_dateline_and_high_latitude` and randomized checks achieved 100% neighbor recall and label identity against the brute-force oracle.
- **What this proves**: This proves that the BallTree spatial index algorithm correctly retrieves all mathematically eligible neighbors within 300 meters and 900 seconds without software indexing omissions.
- **What this does NOT prove**: This does **not** prove that AegisMar detects maritime anomalies or vessel behaviors with 100% accuracy. Algorithm indexing verification is completely distinct from domain classification accuracy.

### 3. "Single Execution Timing" vs. "Benchmarking"
- **Factual Reality**: The W2-01 exploratory run executed in 13.680 s uninstrumented wall time (38.014 s under `tracemalloc`).
- **What this proves**: Demonstrates that running ST-DBSCAN over 143,116 records completes comfortably in tens of seconds on a standard laptop without crashing or exhausting 16 GB RAM.
- **What this does NOT prove**: A single execution run is subject to CPU thermal throttling, OS background processes, and cache warmups. Formal comparative benchmarking (evaluating $H1$) requires multi-trial repetitions (10+ runs) with recorded variance.
- **Status (2026-11-28)**: The multi-trial W3-02 benchmark has been executed (`CLM-CLU-07`, [w3-02-benchmark-results.md](w3-02-benchmark-results.md)). Its official uninstrumented BallTree full-scale total is 12.4074 s (mean of 10 trials). This replaces the single-run 13.680 s figure for comparative purposes; the W2-01 figure remains a historical record (`CLM-CLU-05`).

---

## 5. How to Reproduce Current Evidence Artifacts

Because raw and processed AIS datasets and experiment output directories are excluded from Git tracking via `.gitignore`, any researcher can reproduce the current baseline using the following deterministic sequence:

```powershell
# 1. Synchronize the exact locked Python environment
uv sync --locked

# 2. Verify all unit, oracle, and CLI regression tests (183 as of 2026-11-28; CI gate: coverage >= 85%)
uv run pytest --cov=aegismar --cov-fail-under=85 -v

# 3. Check code formatting, linting, and strict static types
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests

# 4. Reproduce the canonical v1.1 Parquet dataset from the regional sample.
#    Never pass --overwrite: data/processed/lalb_20250101/ (v1.0) and
#    data/processed/lalb_20250101_v1_1/ (v1.1) are immutable (§2.1). Without
#    --overwrite, ingestion refuses to replace an existing Parquet or manifest.
uv run python -m aegismar ingest `
  --input data/raw/sample_lalb_20250101.csv `
  --output data/processed/lalb_20250101_v1_1
uv run python -m aegismar fingerprint -i data/processed/lalb_20250101_v1_1/cleaned_ais.parquet

# 5. Reproduce the exploratory BallTree ST-DBSCAN clustering run
#    (clustering inputs of v1.0 and v1.1 are bit-identical, §2.1)
uv run python -m aegismar cluster `
  --input data/processed/lalb_20250101_v1_1/cleaned_ais.parquet `
  --output experiments/outputs/w2_01_lalb_balltree `
  --eps-spatial-m 300 `
  --eps-temporal-s 900 `
  --min-samples 5 `
  --overwrite

# 6. Verify summary JSON artifact metrics
Get-Content experiments/outputs/w2_01_lalb_balltree/clustering_summary.json

# 7. Reproduce the W3-02 benchmark (CLM-CLU-07; about 38 min on the reference host)
uv run python experiments/clustering/w3_02_benchmark.py `
  -i data/processed/lalb_20250101_v1_1/cleaned_ais.parquet `
  -o experiments/outputs/w3_02_benchmark_results.json
```
