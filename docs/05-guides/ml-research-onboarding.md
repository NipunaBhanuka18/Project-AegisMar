# ML Research Collaborator Onboarding Guide

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**  
> **Document Version:** 1.0  
> **Target Audience:** Kishakya (Incoming ML Research Collaborator) & Academic Collaborators  
> **Track:** Vessel Trajectory Feature Engineering & Behavior Anomaly Detection  
> **Platform Lead:** NipunaBhanuka18  
> **Date:** 2026-11-22  

---

Welcome to **Project AegisMar**! This guide is designed to get you up to speed quickly on the problem space, repository architecture, data contracts, and development practices.

As the proposed Machine Learning Research Collaborator, you will lead an independent, high-impact research track focusing on **vessel trajectory feature engineering and explainable behavioral anomaly detection**.

---

## 1. What AegisMar Is Solving

Commercial maritime shipping accounts for over 80% of world trade. Maritime Domain Awareness (MDA) systems collect millions of Automatic Identification System (AIS) transponder broadcasts every day. However, raw AIS data poses three fundamental problems:
1. **Computational Inefficiency**: Spatial density algorithms (like ST-DBSCAN) scale quadratically without specialized spatial partitioning.
2. **Data Quality Flaws**: Telemetry is riddled with missing sensor reports, dead-reckoning nulls $(0.0, 0.0)$, GPS multipath jitter, and sentinel values (e.g., speed of 102.3 kt, heading of 511°).
3. **Black-Box Alert Fatigue**: Standard outlier models flag vessels drifting with currents or waiting at anchor as anomalies, while failing to identify subtle kinematic deviations (e.g. sharp speed drops, unexpected course alterations, or dark transponder gaps) in high-traffic fairways. Furthermore, deep learning "black boxes" provide no physical justification that maritime operators can trust.

**AegisMar addresses this by building two complementary engines:**
- **Clustering Track (Lead: NipunaBhanuka18)**: Scalable spatiotemporal clustering comparing an Uber H3 discrete hexagonal grid index against a geodesic Haversine BallTree baseline to isolate anchorage basins and vessel dwell areas.
- **ML Anomaly Track (Proposed Lead: Kishakya)**: Trajectory-aware kinematic feature engineering and unsupervised anomaly detection (e.g. Rule-based + Isolation Forest / LOF) that outputs explainable physical justifications for every alert.

---

## 2. Current Completed Milestones

The repository has established a solid, verified data engineering and clustering foundation:
- **Milestone W1-01**: Clean Python 3.11.9 repository skeleton, `uv` packaging, strict `.gitignore`, complete documentation tree.
- **Milestone W1-02A**: NOAA 2025 AIS schema investigation, San Pedro Bay (Los Angeles / Long Beach) study region selection (143,156 raw pings, 362 vessels).
- **Milestone W1-02B**: Production AIS ingestion pipeline (`aegismar ingest`), sentinel coercion, coordinate bounds validation, full-record duplicate consolidation, and columnar `zstd` Parquet storage.
- **Milestone W2-01**: Ingestion corrections (strict integer MMSI sanitation, same-timestamp conflict preservation without fictitious zero-time movement, duplicate raw header rejection), reference Haversine `BallTree` ST-DBSCAN engine (`stdbscan-core-first-v1.0`), and independent brute-force $O(N^2)$ oracle (`BruteForceNeighborhoodOracle`). 52 automated tests passing with 95% total code coverage.
- **Milestone W2-CLOSE**: Public exploratory clustering visualization published in `README.md` (`docs/assets/w2-balltree-clustering.png`).

---

## 3. How to Clone and Install the Project

AegisMar uses **`uv`**, an extremely fast Python package and project manager.

### Prerequisites
- Python 3.11.9 (binary wheel compatibility for C-extensions)
- Git (>= 2.40)
- `uv` (>= 0.11.0; install via `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"` on Windows, or `curl -LsSf https://astral.sh/uv/install.sh | sh` on Linux/macOS)

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
# 1. Run all unit and oracle tests (currently 52 passing tests)
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

All 5 commands should exit with exit code `0`.

---

## 5. How Cleaned AIS Data Is Structured

Cleaned telemetry is stored in columnar Apache Parquet format at:
`data/processed/lalb_20250101/cleaned_ais.parquet`

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
uv run python -m aegismar ingest --input data/raw/sample_lalb_20250101.csv --output data/processed/lalb_20250101 --overwrite
```

### Option B: Downloading Directly from NOAA Marine Cadastre
```bash
# 1. Download official NOAA 2025-01-01 extract (192.8 MB compressed)
curl -o data/raw/ais-2025-01-01.csv.zst "https://noaaocm.blob.core.windows.net/ais/csv2/csv2025/ais-2025-01-01.csv.zst"

# 2. Decompress and slice San Pedro Bay bounding box (Lat: [33.5, 33.9], Lon: [-118.4, -118.0])
# (A lightweight Python snippet can slice this to data/raw/sample_lalb_20250101.csv)

# 3. Run the ingestion pipeline
uv run python -m aegismar ingest --input data/raw/sample_lalb_20250101.csv --output data/processed/lalb_20250101
```

The resulting `data/processed/lalb_20250101/cleaned_ais.parquet` will have 143,124 canonical rows and generate a cryptographic `manifest.json`.

---

## 7. Existing Modules Relevant to ML Research

You can import and reuse existing verified utilities:
- `src/aegismar/common/types.py`: `CanonicalPing` dataclass representing a single observation.
- `src/aegismar/common/constants.py`: Quality flags (`IMPLIED_SPEED_VIOLATION`, `TIMESTAMP_POSITION_CONFLICT`), maximum physical bounds.
- `src/aegismar/spatial/haversine.py`: Fast scalar and array-based Haversine geodesic distance functions:
  ```python
  from aegismar.spatial.haversine import haversine_distance_m, haversine_distance_nm

  dist_m = haversine_distance_m(lat1, lon1, lat2, lon2)
  ```
- `src/aegismar/clustering/types.py`: `load_clustering_dataset_from_parquet` for fast loading with canonical total order.

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

## 9. How to Create a Research Branch

Always branch off a clean, updated `main`:

```bash
git checkout main
git pull origin main
git checkout -b feat/ml-trajectory-features
```

Recommended branch naming conventions:
- `feat/ml-<feature-name>`: New ML capabilities (e.g. `feat/ml-isolation-forest`).
- `exp/ml-<experiment-name>`: Specific research experiments (e.g. `exp/ml-perturbation-study`).
- `docs/ml-<topic>`: Documentation and research notes (e.g. `docs/ml-feature-spec`).

---

## 10. How to Submit a Pull Request

1. Rerun quality gates locally:
   `uv run pytest -v && uv run ruff check . && uv run ruff format --check . && uv run mypy src tests`
2. Push your branch to GitHub:
   `git push -u origin feat/ml-trajectory-features`
3. Open a Pull Request on GitHub against `main`.
4. Fill out the lightweight AegisMar Pull Request template.
5. NipunaBhanuka18 will review and merge your PR.

---

## 11. How to Use an AI Coding Assistant Safely

If you use an AI coding assistant (like GitHub Copilot, Gemini, Claude, or ChatGPT):
1. **Never fabricate research results**: Never accept simulated runtimes, mock recall figures, or fake evaluation scores. All numbers in reports must come from actual execution logs.
2. **Review mathematical formulas**: Check geodesic and kinematic equations manually (e.g. ensuring angular differences wrap properly around $360^\circ$).
3. **Verify Git staging**: Before committing, always check `git status` to ensure virtualenv files, large CSV/Parquet files, or scratch scripts are not staged.
4. **Run quality gates locally**: Ensure Ruff, Mypy, and Pytest pass after every AI code suggestion.

---

## 12. How to Record Experiments and Evidence

All ML experiments must be deterministic and reproducible:
- **Random Seeds**: Always fix seeds (e.g., `random_state=42`).
- **Input Tracking**: Record the SHA-256 hash of the input Parquet file in your experiment metadata.
- **Structured JSON Logging**: Save experiment summaries to `experiments/outputs/anomaly/<exp_id>_metrics.json`.
- **Model Serialization**: Save trained models with `joblib` alongside configuration JSONs.

---

## 13. Protected Files: What Not to Modify Without Coordination

To ensure platform stability, do not edit the following files without prior discussion:
- `src/aegismar/clustering/*` (NipunaBhanuka18's clustering engine)
- `src/aegismar/ingestion/*` (canonical ingestion pipeline)
- `src/aegismar/spatial/*` (geodesic math and test oracle)
- `tests/unit/test_st_dbscan.py`, `tests/unit/test_oracle.py`, `tests/unit/test_ingestion.py`
- `pyproject.toml` (core dependency additions should be agreed upon before running `uv add`)
- `.python-version`

---

## 14. Known Scientific Limitations

Keep these real-world constraints in mind when designing your models:
1. **No Ground Truth for Malicious Behavior**: Public AIS feeds do not label "rogue" ships. Our primary quantitative evaluation relies on documented synthetic perturbations injected into clean trajectories.
2. **Terrestrial AIS Coverage Blind Spots**: Receiver antenna shielding or line-of-sight limits near port cranes can cause 15–30 minute gaps that are innocent coverage drops, not deliberate transponder blackouts.
3. **Low-Speed Gyro Drift**: At speeds under $1.0\text{ knot}$, GPS Course Over Ground (COG) swings erratically. Always guard drift angle calculations ($|\text{COG} - \text{Heading}|$) with a minimum speed check ($\text{SOG} > 1.5\text{ kt}$).
4. **Single-Day Scope**: The primary study sample spans 24 hours of San Pedro Bay traffic (143k pings). Models must not assume weeks of historical training data for individual ships.

---

## 15. First Suggested Research Tasks (ML Backlog)

Here is a recommended starting sequence for your research track (no fixed deadlines; proceed at your own pace):

- **ML-01: Literature & Schema Review**:
  - Read `docs/03-research/vessel-behavior-ml.md` (the research proposal).
  - Inspect `data/processed/lalb_20250101/cleaned_ais.parquet` schema and distributions.
  - Review key maritime anomaly literature (e.g., kinematic rules, trajectory windowing, Isolation Forests).
- **ML-02: Vessel Trajectory Feature Specification**:
  - Define exact mathematical formulas for kinematic acceleration, angular course change, drift angle, and gap duration.
  - Define windowing policy (sliding time window vs fixed ping count).
- **ML-03: Freeze Baseline Models and Evaluation Protocol**:
  - Define vessel-disjoint train/test split strategy (70/30 MMSI partition).
  - Specify synthetic perturbation parameter bounds (speed jumps, crabbing, coverage dropouts).
  - Define metrics: Precision, Recall, $F_1$, PR-AUC, and Factor Attribution Accuracy.
- **ML-04: Implement First Feature Engineering Experiment**:
  - Implement `src/aegismar/anomaly/features.py` with unit tests in `tests/unit/test_anomaly.py`.
  - Extract feature matrix for the 362 vessels in San Pedro Bay and generate a summary report.

Welcome aboard! Feel free to raise questions, suggest alternative modeling ideas, and adapt the proposal to match your research interests.
