# ML Research Collaborator Onboarding Guide

> **Project AegisMar: Explainable Maritime Traffic Intelligence & Vessel Behavior Anomaly Detection Platform**  
> **Document Version:** 1.1  
> **Target Audience:** Kishakya (Incoming ML Research Collaborator) & Academic Collaborators  
> **Track:** Track B — ML-Based Vessel Behavior Intelligence  
> **Platform Lead:** NipunaBhanuka18  
> **Date:** 2026-11-22  

---

Welcome to **Project AegisMar**! This guide is designed to get you up to speed quickly on the problem space, repository architecture, data contracts, and development practices.

As the proposed Machine Learning Research Collaborator, you will lead Track B: **vessel trajectory feature engineering, explainable behavioral anomaly scoring, and unsupervised machine learning models**.

---

## 1. Which Documents to Read First

To get oriented without feeling overwhelmed by documentation, read in this sequence:
1. **[docs/START-HERE.md](../START-HERE.md)**: Executive overview of the maritime problem, platform architecture, verified baselines, and reproduction steps.
2. **[docs/01-project/collaboration-plan.md](../01-project/collaboration-plan.md)**: Team structure, track leadership, module boundaries, and authorship principles.
3. **[docs/03-research/evidence-register.md](../03-research/evidence-register.md)**: The verifiable claims register distinguishing proven facts from hypotheses.
4. **[docs/03-research/vessel-behavior-ml.md](../03-research/vessel-behavior-ml.md)**: The formal ML research proposal (marked `PROPOSAL — NOT FINALIZED`).
5. **[CONTRIBUTING.md](../../CONTRIBUTING.md)**: Coding standards, branch conventions, and automated quality gates.

---

## 2. Distinguishing Specifications from Verified Behavior

As an AI research engineer, it is essential to distinguish between **what is currently implemented and verified** versus **what is planned or proposed**:
- **Implemented & Verified**:
  - Raw AIS CSV ingestion with dual schema adaptation (`aegismar ingest`).
  - Sentinel nullification, MMSI 9-digit sanitization, duplicate consolidation, and quality flagging.
  - Columnar `zstd` Parquet storage writer and cryptographic `manifest.json`.
  - Reference Haversine `BallTree` ST-DBSCAN clustering engine (`stdbscan-core-first-v1.0`).
  - Independent brute-force $O(N^2)$ geodesic test oracle (`BruteForceNeighborhoodOracle`).
  - 52 automated tests in `tests/` with 95% total code coverage.
- **Planned / Hypothesized (Not Yet Implemented)**:
  - Uber H3 candidate neighbor optimization (Track A, Week 3).
  - Vessel stay-point extraction and berth polygon exclusion (Track A, Week 4).
  - Trajectory kinematic feature engineering (Track B, Milestone ML-02/ML-04).
  - Rule-based kinematic anomaly scoring and Isolation Forest models (Track B).
  - DuckDB analytical queries and FastAPI map service (Weeks 6–7).

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

To automatically format your code according to project rules, simply run:
```bash
uv run ruff format .
```

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
2. **Terrestrial AIS Coverage Blind Spots**: Receiver antenna shielding or line-of-sight limits near port cranes can cause 15–30 minute gaps that are innocent coverage drops, not deliberate transponder blackouts.
3. **Low-Speed Gyro Drift**: At speeds under $1.5\text{ knots}$, GPS Course Over Ground (COG) swings erratically. Always guard drift angle calculations ($|\text{COG} - \text{Heading}|$) with a minimum speed check ($\text{SOG} > 1.5\text{ kt}$).
4. **Single-Day Scope**: The primary study sample spans 24 hours of San Pedro Bay traffic (143k pings). Models must not assume weeks of historical training data for individual ships.

---

## 13. First Suggested Research Tasks (ML Backlog)

Here is a recommended starting sequence for your research track (no fixed deadlines; proceed at your own pace):

- **ML-01: Literature & Schema Review**:
  - Read `docs/03-research/vessel-behavior-ml.md` (the research proposal).
  - Inspect `data/processed/lalb_20250101/cleaned_ais.parquet` schema and distributions.
  - Review key maritime anomaly literature (e.g., kinematic rules, trajectory windowing, Isolation Forests).
- **ML-02: Vessel Trajectory Feature Specification**:
  - Define exact mathematical formulas for kinematic acceleration, angular course change, drift angle, and gap duration.
  - Define windowing policy (sliding time window vs fixed ping count).
- **ML-03: Freeze Baseline Models and Evaluation Protocol**:
  - Define vessel-disjoint train/test split strategy (70/30 MMSI partition with vessel-type stratification).
  - Specify synthetic perturbation parameter bounds (speed jumps, crabbing, coverage dropouts).
  - Define metrics: Precision, Recall, $F_1$, PR-AUC, and Factor Attribution Accuracy.
- **ML-04: Implement First Feature Engineering Experiment**:
  - Implement `src/aegismar/anomaly/features.py` with unit tests in `tests/unit/test_anomaly.py`.
  - Extract feature matrix for the 362 vessels in San Pedro Bay and generate a summary report.

Welcome aboard! Feel free to raise questions, suggest alternative modeling ideas, and adapt the proposal to match your research interests.
