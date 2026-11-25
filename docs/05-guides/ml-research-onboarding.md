# ML Research Collaborator Onboarding Guide

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**  
> **Document Version:** 1.2 (updated 2026-11-24 after ML-01–ML-03; see §14)  
> **Target Audience:** Kishakya (ML Research Collaborator, Track B Lead) & Academic Collaborators  
> **Track:** Track B — ML-Based Vessel Behavior Intelligence  
> **Platform Lead:** NipunaBhanuka18  
> **Date:** 2026-11-22  

---

Welcome to **Project AegisMar**! This guide is designed to get you up to speed quickly on the problem space, repository architecture, data contracts, and development practices.

As the Machine Learning Research Collaborator and Track B lead, you lead Track B: **vessel trajectory feature engineering, explainable behavioral anomaly scoring, and unsupervised machine learning models**.

---

## 1. Which Documents to Read First

To get oriented without feeling overwhelmed by documentation, read in this sequence:
1. **[docs/START-HERE.md](../START-HERE.md)**: Executive overview of the maritime problem, platform architecture, verified baselines, and reproduction steps.
2. **[docs/01-project/collaboration-plan.md](../01-project/collaboration-plan.md)**: Team structure, track leadership, module boundaries, and authorship principles.
3. **[docs/03-research/evidence-register.md](../03-research/evidence-register.md)**: The verifiable claims register distinguishing proven facts from hypotheses.
4. **[docs/03-research/vessel-behavior-ml.md](../03-research/vessel-behavior-ml.md)**: The formal ML research proposal (marked `PROPOSAL — NOT FINALIZED`).
5. **[docs/03-research/ml-02-feature-spec.md](../03-research/ml-02-feature-spec.md)**: The accepted Track B feature specification (v1.0). Where it differs from the proposal, it takes precedence.
6. **[docs/03-research/ml-03-evaluation-protocol.md](../03-research/ml-03-evaluation-protocol.md)**: The frozen Track B evaluation protocol (v1.0): splits, test days, perturbations, baselines, metrics.
7. **[CONTRIBUTING.md](../../CONTRIBUTING.md)**: Coding standards, branch conventions, and automated quality gates.

---

## 2. Distinguishing Specifications from Verified Behavior

As an AI research engineer, it is essential to distinguish between **what is currently implemented and verified** versus **what is planned or proposed**:
- **Implemented & Verified**:
  - Raw AIS CSV ingestion with dual schema adaptation (`aegismar ingest`).
  - Sentinel nullification, MMSI 9-digit sanitization, duplicate consolidation, and quality flagging.
  - Columnar `zstd` Parquet storage writer and cryptographic `manifest.json`.
  - Reference Haversine `BallTree` ST-DBSCAN clustering engine (`stdbscan-core-first-v1.0`).
  - Independent brute-force $O(N^2)$ geodesic test oracle (`BruteForceNeighborhoodOracle`).
  - Uber H3 candidate neighborhood provider (`H3NeighborhoodProvider`, Track A W3-01/W3-01B) with verified neighborhood parity against the BallTree reference on the LA/LB dataset.
  - Track B data tooling: ML-01 dataset profiling (`experiments/anomaly/ml01_profile_dataset.py`), ML-02 drift breakdown (`experiments/anomaly/ml02_drift_breakdown.py`), and the NOAA bounding-box slicer (`scripts/slice_noaa_bbox.py`).
  - 92 automated tests in `tests/` with 94% total code coverage (measured 2026-11-24 on `main` @ `c4b9344`).
- **Specified but Not Yet Implemented**:
  - Trajectory kinematic feature extraction — specified in [ML-02 v1.0](../03-research/ml-02-feature-spec.md); implementation is ML-04.
  - Rule-based scoring, Isolation Forest / LOF models and the perturbation harness — evaluation frozen in [ML-03 v1.0](../03-research/ml-03-evaluation-protocol.md); implementation is ML-05.
- **Planned / Hypothesized (Not Yet Implemented)**:
  - Comparative H1 benchmarking, BallTree vs. H3 (Track A, W3-02).
  - Vessel stay-point extraction and berth polygon exclusion (Track A, Week 4).
  - DuckDB analytical queries, FastAPI service and map dashboard (Track A, W5-01 to W7-01).

Always check [docs/03-research/evidence-register.md](../03-research/evidence-register.md) if you are unsure whether a capability is verified or proposed.

---

## 3. How to Clone and Install the Project

AegisMar uses **`uv`**, an extremely fast, modern Python package manager.

### Prerequisites
- Python 3.11.9 (binary wheel compatibility for C-extensions)
- Git (>= 2.40)
- `uv` (>= 0.11.0; install via `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"` on Windows, or `curl -LsSf https://astral.sh/uv/install.sh | sh` on Linux/macOS)
- **Editor / IDE**: You are free to use any editor or IDE of your choice (VS Code, Cursor, PyCharm, Neovim, terminal). The project has zero IDE dependencies or hardcoded editor configurations.

### Setup Commands
```bash
# 1. Clone repository
git clone https://github.com/NipunaBhanuka18/Project-AegisMar.git
cd Project-AegisMar

# 2. Synchronize environment with exact locked dependencies
uv sync --locked
```

`uv sync --locked` will automatically create a local virtual environment (`.venv`) and install all pinned packages (`numpy`, `scikit-learn`, `pyarrow`, `pytest`, `ruff`, `mypy`, `tzdata`).

---

## 4. How to Run Existing Tests & Quality Gates

Every change must pass our strict automated quality gates before opening a pull request:

```bash
# 1. Run all unit and oracle tests (92 passing tests as of 2026-11-24)
uv run pytest -v

# 2. Check code coverage
uv run pytest --cov=aegismar --cov-report=term-missing

# 3. Check linting rules
uv run ruff check .

# 4. Check formatting
uv run ruff format --check .

# 5. Run strict static type checking
uv run mypy src tests
```

To automatically format your code according to project rules, simply run:
```bash
uv run ruff format .
```

---

## 5. How Cleaned AIS Data Is Structured

Cleaned telemetry is stored in columnar Apache Parquet format at:
`data/processed/lalb_20250101_v1_1/cleaned_ais.parquet` (canonical v1.1; see [evidence-register.md §2.1](../03-research/evidence-register.md))

The dataset contains 19 standardized columns defined in `src/aegismar/ingestion/schema.py`:
1. `source_row` (`int64`): Original CSV row number for auditability.
2. `mmsi` (`string`): 9-digit zero-padded Maritime Mobile Service Identity.
3. `timestamp_utc` (`timestamp[us, UTC]`): UTC broadcast timestamp with microsecond resolution.
4. `latitude` (`float64`): WGS 84 latitude in decimal degrees $[-90.0, 90.0]$.
5. `longitude` (`float64`): WGS 84 longitude in decimal degrees $[-180.0, 180.0]$.
6. `sog` (`float32`, nullable): Speed Over Ground in knots. Sentinels (`102.3`) are nullified.
7. `cog` (`float32`, nullable): Course Over Ground in degrees $[0.0, 359.9]$. Sentinels (`360.0`) are nullified.
8. `heading` (`float32`, nullable): True heading $[0, 359]$ degrees. Sentinels (`511`) are nullified.
9. `nav_status` (`int8`, nullable): ITU navigational status (0–14). Status `15` is nullified.
10. `vessel_type` (`int16`, nullable): Numeric ship category (e.g. 70=Cargo, 80=Tanker).
11. `vessel_name` (`string`, nullable): Station license name.
12. `imo` (`string`, nullable): IMO number.
13. `call_sign` (`string`, nullable): Radio call sign.
14. `transceiver_class` (`string`, nullable): `'A'` (commercial SOLAS) or `'B'` (small craft).
15. `prev_source_row` (`int64`, nullable): Preceding valid observation row for this vessel.
16. `elapsed_seconds` (`float64`, nullable): Seconds elapsed since previous observation.
17. `distance_nm` (`float64`, nullable): Geodesic displacement in nautical miles.
18. `implied_speed_knots` (`float64`, nullable): $\Delta d / \Delta t$ in knots.
19. `quality_flags` (`list[string]`): Warnings (`TIMESTAMP_POSITION_CONFLICT`, `IMPLIED_SPEED_VIOLATION`, etc.).

---

## 6. How to Acquire or Reproduce Permitted Research Data

> [!WARNING]
> **Data Governance Policy**: Never commit raw AIS data (`data/raw/`) or processed Parquet partitions (`data/processed/`) to Git. The `.gitignore` file enforces this automatically.

If you do not have the local Parquet dataset, you can reproduce it in under 2 minutes:

### Option A: From Pre-extracted Regional Sample
If you have `data/raw/sample_lalb_20250101.csv`:
```bash
uv run python -m aegismar ingest --input data/raw/sample_lalb_20250101.csv --output data/processed/lalb_20250101_v1_1
```

### Option B: Downloading Directly from NOAA Marine Cadastre
```bash
# 1. Download official NOAA 2025-01-01 extract (202,190,247 bytes; SHA-256 36c07f4a...bdde53)
curl -fL -o data/raw/ais-2025-01-01.csv.zst "https://noaaocm.blob.core.windows.net/ais/csv2/csv2025/ais-2025-01-01.csv.zst"

# 2. Stream-decompress and slice the San Pedro Bay bounding box (no extra dependency; uses pyarrow)
uv run python scripts/slice_noaa_bbox.py data/raw/ais-2025-01-01.csv.zst data/raw/sample_lalb_20250101.csv --lat 33.5 33.9 --lon -118.4 -118.0

# 3. Run the ingestion pipeline
uv run python -m aegismar ingest --input data/raw/sample_lalb_20250101.csv --output data/processed/lalb_20250101_v1_1
```

Expected results (independently reproduced by the Track B lead on 2026-11-23; slicer re-verified 2026-11-24):
- Slicer: 7,337,208 nationwide rows scanned; 143,156 rows and 362 vessels kept; sample SHA-256 `42e4f766feb98b20e98124685137bcc2be16a20c06dda46e33f415f0b281eac8`.
- Ingestion: 143,124 canonical rows (32 duplicates consolidated, 8 timestamp-position conflicts) plus a cryptographic `manifest.json`. Always record the SHA-256 of the Parquet file you actually used in experiment metadata.

### Track B held-out test days (ML-03)
The same procedure (download → `scripts/slice_noaa_bbox.py` → `aegismar ingest`) is used for the two
held-out test days defined in [ML-03 §3.1](../03-research/ml-03-evaluation-protocol.md): 2025-01-14 →
`data/processed/lalb_20250114/` and 2025-01-22 → `data/processed/lalb_20250122/`. Follow the ML-03
**test-day firewall**: only integrity checks (hashes, row and vessel counts, time range) are allowed on
these days until the final evaluation.

---

## 7. Existing Modules Relevant to ML Research

You can import and reuse existing verified utilities:
- `src/aegismar/common/types.py`: `CanonicalPing` dataclass representing a single observation.
- `src/aegismar/common/constants.py`: Quality flags (`IMPLIED_SPEED_VIOLATION`, `TIMESTAMP_POSITION_CONFLICT`), maximum physical bounds.
- `src/aegismar/spatial/haversine.py`: Scalar Haversine geodesic distance functions (`haversine_distance_meters`, `haversine_distance_nm`) and a list-based pairwise helper (`haversine_vector_meters`):
  ```python
  from aegismar.spatial.haversine import haversine_distance_meters, haversine_distance_nm

  dist_m = haversine_distance_meters(lat1, lon1, lat2, lon2)
  ```
- `src/aegismar/clustering/types.py`: `load_clustering_dataset_from_parquet` loads the Parquet file and re-sorts it into the clustering canonical total order `(timestamp_utc, mmsi, latitude, longitude, source_row)`.
- **Row order on disk:** `cleaned_ais.parquet` itself is written in `(mmsi, timestamp_utc, source_row)` order by the ingestion cleaner. Track B code must not rely on file order; ML-02 §4.1 re-sorts each vessel by `(timestamp_utc, source_row)`.

---

## 8. Proposed Independent ML Work Boundaries

To prevent merge conflicts and allow you to iterate freely:
- **ML Source Code**: Create all your modules inside `src/aegismar/anomaly/`:
  - `src/aegismar/anomaly/features.py` (trajectory feature extraction)
  - `src/aegismar/anomaly/rules.py` (rule-based kinematic scoring)
  - `src/aegismar/anomaly/models.py` (Isolation Forest / LOF wrappers)
  - `src/aegismar/anomaly/evaluation.py` (metrics, perturbation injection)
- **ML Tests**: Place all your unit tests in `tests/unit/test_anomaly.py`.
- **Experiment Artifacts**: Save experiment outputs under `experiments/outputs/anomaly/` (gitignored).

---

## 9. How to Propose an Experiment & Document Settings

When conducting a new machine learning experiment:
1. **Define the Hypothesis**: What exact question is being tested (e.g. "Does incorporating rate of turn improve PR-AUC over acceleration alone?")?
2. **Deterministic Configuration**: Always fix random seeds (`random_state=42`) and record hyperparameters (window size $W$, contamination rate, tree count).
3. **Record Metadata**: Save an experiment JSON file in `experiments/outputs/anomaly/` recording:
   - Git commit SHA
   - Input dataset SHA-256 hash
   - Exact hyperparameters
   - Execution metrics (PR-AUC, ROC-AUC, $F_1$, confusion matrix)
4. **Recording Negative Findings**: In scientific research, **negative results are just as valuable as positive results**. If an Isolation Forest fails to outperform a simple velocity rule, or if adding Heading disparity creates too many false alarms, document this clearly in your experiment log! Transparent error analysis strengthens research credibility.

---

## 10. How to Use an AI Coding Assistant Safely

If you use an AI coding assistant (like GitHub Copilot, Gemini, Claude, or ChatGPT):
1. **Never accept simulated results**: Never allow an AI to generate mock benchmark runtimes, fake recall scores, or fabricated evaluation metrics. All numbers in reports must come from actual execution logs.
2. **Review mathematical formulas**: Check geodesic and kinematic equations manually (e.g. ensuring angular differences wrap properly around $360^\circ$).
3. **Verify Git staging**: Before committing, always check `git status` to ensure virtualenv files, large CSV/Parquet files, or scratch scripts are not staged.
4. **Run quality gates locally**: Ensure Ruff, Mypy, and Pytest pass after every AI code suggestion.

---

## 11. Protected Files & Shared Schema Changes

To ensure platform stability:
- **Protected Files**: Do not edit `src/aegismar/clustering/*`, `src/aegismar/ingestion/*`, or `src/aegismar/spatial/*` without prior discussion with NipunaBhanuka18.
- **Shared Schema Agreement**: Any changes to shared data structures—such as `pyproject.toml` dependencies, the 19-column canonical schema, or the `vessel_anomaly_v1` GeoJSON contract—require mutual discussion and agreement before merging.

---

## 12. Known Scientific Limitations

Keep these real-world constraints in mind when designing your models:
1. **No Ground Truth for Malicious Behavior**: Public AIS feeds do not label "rogue" ships. Our primary quantitative evaluation relies on documented synthetic perturbations injected into clean trajectories.
2. **Terrestrial AIS Coverage Blind Spots**: Receiver antenna shielding or line-of-sight limits near port cranes can cause 15–30 minute gaps that are innocent coverage drops, not deliberate transponder blackouts. ML-01 also found two **feed-wide** silences on 2025-01-01 (03:07:37–03:20:25 and 12:06:09–12:18:20 UTC) that account for 557 of 1,579 vessel gaps > 600 s; gap features must be outage-aware (ML-02 §6).
3. **Low-Speed Gyro Drift**: At speeds under $1.5\text{ knots}$, GPS Course Over Ground (COG) swings erratically. Always guard drift angle calculations ($|\text{COG} - \text{Heading}|$) with a minimum speed check ($\text{SOG} \ge 1.5\text{ kt}$; ML-02 guard G1).
4. **Limited Temporal Scope**: Development uses one day (2025-01-01, a public holiday; 143k pings). Evaluation adds two held-out days (2025-01-14 and 2025-01-22; ML-03 §3.1). Models must not assume weeks of historical training data for individual ships.
5. **Coarse Reporting Cadence**: The NOAA data arrives at roughly 70 s (moving Class A) to 180 s intervals, not raw 2–10 s AIS, so "instantaneous" rates are interval averages (ML-02 C1, C3).

---

## 13. First Suggested Research Tasks (ML Backlog)

Here is a recommended starting sequence for your research track (no fixed deadlines; proceed at your own pace):

- **ML-01: Literature & Schema Review** — *data profiling completed; literature review pending*:
  - [x] Inspect `cleaned_ais.parquet` schema and distributions (`experiments/anomaly/ml01_profile_dataset.py`).
  - [ ] Review key maritime anomaly literature (e.g., kinematic rules, trajectory windowing, Isolation Forests) and write summary notes.
- **ML-02: Vessel Trajectory Feature Specification** — *completed* ([v1.0](../03-research/ml-02-feature-spec.md)).
- **ML-03: Freeze Baseline Models and Evaluation Protocol** — *completed* ([v1.0](../03-research/ml-03-evaluation-protocol.md)); held-out days 2025-01-14 and 2025-01-22 downloaded, sliced, ingested and integrity-checked.
- **ML-04: Feature Engineering Module & Baseline Experiments** — *next*:
  - Implement `src/aegismar/anomaly/features.py` exactly as specified in ML-02, with the ML-02 §11 verification cases in `tests/unit/test_anomaly.py`.
  - Build the D0 vessel partition (ML-03 §3.2) and record its hash.
  - Extract features for the development day (2025-01-01) and log a reproducible experiment under `experiments/outputs/anomaly/`.
- **ML-05: Anomaly Model Evaluation & `vessel_anomaly_v1` Export**:
  - Perturbation harness, R1 rule scorer, Isolation Forest / LOF, and the single frozen test-day evaluation, all per ML-03.

Welcome aboard! Feel free to raise questions, suggest alternative modeling ideas, and adapt the proposal to match your research interests.

---

## 14. Version History

| Version | Date | Change |
|---|---|---|
| 1.1 | 2026-11-22 | Collaborator onboarding baseline. |
| 1.2 | 2026-11-24 | Corrected the Haversine import example (`haversine_distance_meters`); documented the on-disk row order; added the `scripts/slice_noaa_bbox.py` slicing step with verified expected results; updated implemented/planned status (H3 implemented; 92 tests, 94% coverage); linked ML-02/ML-03; added the held-out test days, outage and cadence limitations; updated the ML backlog status. |
