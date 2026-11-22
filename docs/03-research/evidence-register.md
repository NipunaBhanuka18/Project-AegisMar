# Research Evidence Register & Verification Matrix

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**  
> **Document Version:** 1.0  
> **Lifecycle Status:** Active Evidence Baseline  
> **Maintained By:** NipunaBhanuka18 (Project Lead) & Kishakya (Proposed ML Collaborator)  
> **Last Reconciled:** 2026-11-22  

---

## 1. Purpose and Evidentiary Standard

This document establishes the official **Research Evidence Register** for Project AegisMar. To maintain absolute academic and scientific integrity, every technical claim, benchmark measurement, algorithmic property, and empirical observation in the project must be traceable to concrete, auditable evidence.

### Evidence Classification Hierarchy
Every claim in this register is categorized under one of six strict evidentiary categories:
1. **Implemented and Code-Inspected**: Verified by manual code review and static analysis of production source files in `src/`.
2. **Tested by Automated Checks**: Formally verified by deterministic unit tests or oracle tests in `tests/` passing in CI/CD.
3. **Experimentally Observed**: Directly measured in an executed experiment with logged JSON artifacts and execution parameters.
4. **Independently Reproduced**: Re-executed and verified independently across separate environments or repeated runs.
5. **Reported by Development Assistant**: Recorded in historical completion reports but not yet independently re-measured in multi-trial runs.
6. **Planned or Hypothesized**: Theoretical expectations, research hypotheses (H1, H2), or planned capabilities not yet implemented.

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
  Cleaned Canonical Dataset (cleaned_ais.parquet)
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
| **CLM-SPA-01** | Tested by Automated Checks | Haversine distance implementation computes exact spherical great-circle distances across standard coordinates, high latitudes, and anti-meridian dateline crossings ($\pm 180^\circ$). | Synthetic & extreme coordinates | `v0.1.0.dev1` | `src/aegismar/spatial/haversine.py`<br>`tests/unit/test_st_dbscan.py` (`test_10`, `test_11`) | **Verified** (Tests pass) | Assumes spherical Earth ($R=6{,}371{,}008.8\text{ m}$); max ~0.5% deviation from WGS 84 ellipsoid. |
| **CLM-SPA-02** | Tested by Automated Checks | Independent $O(N^2)$ brute-force test oracle calculates exact scalar Haversine distances independently of scikit-learn, with an automated $N \le 5{,}000$ safety cap. | Synthetic fixtures | `v0.1.0.dev1` | `src/aegismar/spatial/oracle.py`<br>`tests/unit/test_oracle.py` (7 tests) | **Verified** (Tests pass) | Capped at $N \le 5{,}000$ to prevent quadratic execution lockup. |
| **CLM-CLU-01** | Tested by Automated Checks | `BallTreeNeighborhoodProvider` matches brute-force oracle neighbor sets 100% across randomized datasets, extreme boundaries, and a 1,000-row real LA/LB subset. | Randomized & real 1k subset | `v0.1.0.dev1` | `src/aegismar/clustering/balltree_neighbors.py`<br>`tests/unit/test_oracle.py` (`test_12`, `test_oracle_matches_balltree...`) | **Verified** (Tests pass) | Tests neighborhood candidate retrieval; does not measure traffic semantics. |
| **CLM-CLU-02** | Tested by Automated Checks | Core-first ST-DBSCAN (`stdbscan-core-first-v1.0`) produces bit-for-bit identical cluster assignments regardless of input row permutation (permutation invariance). | Synthetic permutation fixtures | Policy `v1.0` | `src/aegismar/clustering/st_dbscan.py`<br>`tests/unit/test_st_dbscan.py` (`test_13`) | **Verified** (Tests pass) | Requires canonical sorting pass prior to clustering. |
| **CLM-CLU-03** | Tested by Automated Checks | Non-core points reachable from multiple core components are deterministically attached to the nearest core component via lexicographical tie-breaker tuple `(dist, |dt|, cluster_id, core_idx)`. | Multi-core boundary fixtures | Policy `v1.0` | `src/aegismar/clustering/st_dbscan.py`<br>`tests/unit/test_st_dbscan.py` (`test_09`) | **Verified** (Tests pass) | Tie-breaking is geometric and temporal; not hydrodynamic. |
| **CLM-CLU-04** | Experimentally Observed | Exploratory BallTree ST-DBSCAN run on 143,116 analyzed LA/LB rows partitions observations into 241 spatiotemporal density clusters (136,276 core, 934 border, 5,906 noise). | `cleaned_ais.parquet`<br>(SHA-256: `4a7ca719...`) | $\varepsilon_s=300\text{m}$, $\Delta T=900\text{s}$, $\text{MinPts}=5$ | `experiments/outputs/w2_01_lalb_balltree/clustering_summary.json` | **Verified on Local Disk** (Summary JSON verified) | Clusters represent raw density groups; they are **NOT** 241 confirmed anchorages. |
| **CLM-CLU-05** | Reported by Development Assistant | Exploratory BallTree ST-DBSCAN run recorded 13.680 s uninstrumented wall time (0.077 s build, 13.341 s query, 0.262 s clustering), and 38.014 s wall time with 225.83 MB peak heap under `tracemalloc`. | `cleaned_ais.parquet` | Commit `3ece859` | `experiments/outputs/w2_01_lalb_balltree/clustering_summary.json` | **Recorded in Log; Not Multi-Trial Benchmark** | Measured on a single workstation run; not a statistically validated multi-trial benchmark. |
| **CLM-CLU-06** | Planned / Hypothesized | H3 hexagonal candidate indexing with exact Haversine pruning will achieve a statistically significant speedup over BallTree on datasets $\ge 50\text{k}$ rows with 100% recall ($H_{1,A}$). | Future benchmark datasets | Resolution $R$, $k$-ring | `docs/03-research/research-plan.md` | **Unverified Hypothesis** (Planned for Week 3) | H3 candidate engine is **not yet implemented**; performance claims are hypotheses. |
| **CLM-ANO-01** | Planned / Hypothesized | Multi-factor kinematic trajectory anomaly scoring will achieve at least 15 percentage points higher $F_1$ than ST-DBSCAN spatial density noise ($H_{2,A}$). | Held-out trajectory partitions | Rule-based vs. IF | `docs/03-research/vessel-behavior-ml.md` | **Unverified Hypothesis** (Planned ML track) | Anomaly models are **not yet implemented**; hypotheses remain subject to experiment. |

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
- **What this does NOT prove**: A single execution run is subject to CPU thermal throttling, OS background processes, and cache warmups. Formal comparative benchmarking (evaluating $H1$) requires multi-trial repetitions (10+ runs) with recorded variance, planned for Milestone W3-02 and Week 8.

---

## 5. How to Reproduce Current Evidence Artifacts

Because raw and processed AIS datasets and experiment output directories are excluded from Git tracking via `.gitignore`, any researcher can reproduce the current baseline using the following deterministic sequence:

```powershell
# 1. Synchronize the exact locked Python environment
uv sync --locked

# 2. Verify all 52 unit, oracle, and CLI regression tests
uv run pytest -v

# 3. Check code formatting, linting, and strict static types
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests

# 4. Reproduce the canonical Parquet dataset from the regional sample
uv run python -m aegismar ingest `
  --input data/raw/sample_lalb_20250101.csv `
  --output data/processed/lalb_20250101 `
  --overwrite

# 5. Reproduce the exploratory BallTree ST-DBSCAN clustering run
uv run python -m aegismar cluster `
  --input data/processed/lalb_20250101/cleaned_ais.parquet `
  --output experiments/outputs/w2_01_lalb_balltree `
  --eps-spatial-m 300 `
  --eps-temporal-s 900 `
  --min-samples 5 `
  --overwrite

# 6. Verify summary JSON artifact metrics
Get-Content experiments/outputs/w2_01_lalb_balltree/clustering_summary.json
```
