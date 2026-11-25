# ML-03: Track B Evaluation Protocol (Baselines, Splits, Perturbations, Metrics)

> **Project AegisMar — Track B (Vessel Behavior ML & Anomaly Detection)**
> **Document Version:** 1.1 (DRAFT amendment — under review by Kishakya; v1.0 frozen 2026-11-23)
> **Milestone:** ML-03
> **Track Lead:** Kishakya
> **Date:** 2026-11-23 (v1.0); amended 2026-11-25 (v1.1 draft)
> **Builds on:** [ML-02 Feature Specification v1.0.1](ml-02-feature-spec.md); canonical dataset v1.1 ([evidence-register.md §2.1](evidence-register.md))

> [!IMPORTANT]
> **Frozen protocol.** Decisions D7–D14 were accepted by the Track B lead on 2026-11-23 (Section 12).
> **v1.1 draft:** Section 0 lists the proposed amendments (decisions D15–D18, marked **⚑ DECISION**
> until accepted). They are made **before any test-day inspection**, as Section 3.4 permits.
> This protocol was frozen **before any held-out test day was inspected** (Section 3.4). Any later
> change requires a new document version and is subject to the test-day firewall rules. This document
> contains no experimental results. All dataset numbers it cites come from executed ML-01 / ML-02
> scripts; arithmetic illustrations are labelled as such.

> [!NOTE]
> **Relationship to existing documents.** This protocol refines the Track B part of
> [evaluation-protocol.md §3](evaluation-protocol.md) and [vessel-behavior-ml.md §7–§9](vessel-behavior-ml.md).
> Where they conflict, Section 11 lists each conflict and its resolution. Those documents will be
> updated in the final documentation pass, not in this change.

---

## 0. Amendment Summary (v1.1)

### 0.1 Why the protocol is amended

While building the ML-05 perturbation harness, the v1.0 eligibility rules were applied to the D0
validation vessels (111 vessels, seed 1000) with the harness prototype. Measured injection counts:

| Configuration | Injections possible (v1.0 rules) |
|---|---|
| A1 / A2 (any magnitude) | 12 |
| B (any magnitude) | 10 |
| C1 / C2, G = 30 min | 7 |
| C1 / C2, G = 60 min | 4 (one of them produced no scorable window) |
| C1 / C2, G = 120 min | 0 |

Every configuration falls below the v1.0 threshold of 20 eligible injections (Section 4.2 notes), so
every result would be descriptive only. The limiting factor is the number of vessels with long, clean
moving stretches: relaxing the rules on D0 alone (several injections per segment, a 1.5 kt guard and a
±15 min margin) reached at most 41 / 29 / 8 injections (A1 / B / C2-60) from only 12–16 vessels.
2025-01-01 is also a public holiday, so a model trained on it alone would learn holiday behaviour,
while both test days are ordinary working days. These numbers were measured on 2026-11-25 with the
uncommitted harness prototype; ML-05 records the eligibility diagnostics reproducibly (Section 7).

### 0.2 Amendments

| ID | Change | Sections |
|---|---|---|
| D15 | Add a second development day, **D0B = 2025-01-08** (Wednesday, ordinary working day). Development set **DEV = D0 ∪ D0B**. | 3.1 |
| D16 | The vessel partition is computed **jointly over both development days**: one MMSI-grouped, stratified 70/30 split, so a vessel's data on both days belongs to the same partition. Replaces the single-day split of D8 (same strata, seed and fraction). Tuning sets are renamed **DEV-train / DEV-val**. | 3.2, 3.3, 3.5, 5, 6, 10 |
| D17 | Eligibility and density: SOG guard **1.5 kt** (ML-02 G1, was 2.0 kt); **several injections per eligible segment**, at least 60 min apart (was one per segment); C1/C2 require at least two further observations after the reappearance observation, so a window with ≥ 3 pairs can exist. The ±30 min clean margin is **kept**, so every positive window remains unambiguous. | 4.1 |
| D18 | Remove the G = 120 min configurations (no eligible site under v1.0); C sweeps use G ∈ {30, 60} min. | 4.2 |

### 0.3 Firewall compliance

As of this amendment, T1 and T2 have only been downloaded, sliced, ingested and integrity-checked (file
SHA-256, row and vessel counts, timestamp range), and checked by the metadata-only firewall guard. No
feature, distribution, plot or score from T1/T2 has been computed. The amendment is therefore a
pre-evaluation change, which Section 3.4 permits.

---

## 1. Purpose

ML-03 freezes, **before any model is trained**:

1. which data is used for fitting, tuning and testing, and how leakage is prevented;
2. how synthetic anomalies are injected and labelled;
3. which baselines and models are compared, with their configurations;
4. which metrics and statistical tests decide the hypotheses H-ML1 and H-ML2;
5. what every experiment must record.

Fixing these in advance prevents results-driven tuning. It is the main protection against
overstated claims.

---

## 2. Hypotheses Under Test

Restated from [vessel-behavior-ml.md §3](vessel-behavior-ml.md), with the operational decision rules
defined in Section 8.

- **H-ML1 (kinematics vs density noise):** the kinematic rule-based scorer (R1) achieves a higher
  window-level F1 than the ST-DBSCAN density-noise baseline (B0) on perturbed held-out data. The claimed
  margin is ≥ 15 percentage points.
- **H-ML2 (ML vs rules):** Isolation Forest (M1) achieves a higher PR-AUC than R1, while ≥ 90% of its true
  positives carry the correct primary factor.

Negative or null outcomes are reported with equal prominence (onboarding §9.4).

---

## 3. Data, Partitions and Leakage Control

### 3.1 Datasets

| Role | Date (UTC) | Day | Status | Rationale |
|---|---|---|---|---|
| **D0 — development** | 2025-01-01 | Wednesday (US public holiday) | Canonical v1.1 `lalb_20250101_v1_1/` (file SHA-256 `bdde2581…`, fingerprint `d8a619f7…`); profiled (ML-01) | Shared with Track A; all ML-02 design evidence comes from it. |
| **D0B — development** *(v1.1)* | 2025-01-08 | Wednesday | `lalb_20250108/`, ingested with the current pipeline (own manifest and fingerprint) | An ordinary working day one week after the holiday; adds vessels and non-holiday behaviour (Section 0.1). Not a test day, not a holiday. |
| **T1 — test** | 2025-01-14 | Tuesday | Downloaded, sliced, ingested; integrity-checked only (2026-11-23) | An ordinary working weekday, about 2 weeks later. |
| **T2 — test** | 2025-01-22 | Wednesday | Downloaded, sliced, ingested; integrity-checked only (2026-11-23) | **Same weekday as D0 but not a holiday.** This separates a holiday effect from a weekday effect. 2025-01-20 (a US federal holiday) is deliberately avoided. |

**Decision D7 (accepted):** test days T1 = 2025-01-14 and T2 = 2025-01-22.

**⚑ DECISION D15 (v1.1):** add development day D0B = 2025-01-08; DEV = D0 ∪ D0B.

All four days use the same bounding box (lat [33.5, 33.9], lon [-118.4, -118.0]), the same slicing
procedure (`scripts/slice_noaa_bbox.py`), and `aegismar ingest`. Each day is a separate dataset
directory (`data/processed/lalb_YYYYMMDD/`; D0 uses the canonical `lalb_20250101_v1_1/`) with its own
manifest and SHA-256. Features are extracted **per day** (outage windows and segments never span
days, ML-02 §6).

### 3.2 Vessel partition of the development set (DEV = D0 ∪ D0B)

- **Unit:** MMSI, **across both development days**. A vessel's trajectories on D0 and D0B belong to
  exactly one partition; the same MMSI is never in DEV-train on one day and DEV-val on the other.
- **Strata:** (vessel group as in ML-01) × (ever-moving: any SOG ≥ 1.5 kt on either day). A vessel's
  group comes from its first non-null `vessel_type` in time order across both days. Groups with fewer
  than 5 vessels are merged into `other` before stratifying.
- **Procedure (deterministic):** within each stratum, sort the MMSIs ascending, permute them with
  `numpy.random.default_rng(42)`, and assign the first `round(0.3 · n)` to **DEV-val**. The rest form
  **DEV-train**.
- **Size:** the realised counts per stratum and per day are reported by the ML-04 re-run on DEV.

**Decision D8 (accepted; amended by D16):** stratified 70/30 MMSI split with seed 42, the validation
part used as the tuning set.

**⚑ DECISION D16 (v1.1):** the split is computed jointly over both development days (replaces the
single-day D0 split).

### 3.3 What each partition may be used for

| Partition | Allowed use | Forbidden use |
|---|---|---|
| DEV-train | Fit scalers and imputers; fit the F10 expected-interval medians; calibrate the R1 factor ECDFs (Section 5.2); fit M1 and M2 | Threshold selection; any metric reported as a result |
| DEV-val (perturbed) | Select decision thresholds; tune the B0 grid (Section 5.1); choose between model variants | Fitting any model parameter |
| T1, T2 (clean and perturbed) | Final evaluation, **once** | Any tuning, threshold change or feature redesign |

### 3.4 Test-day firewall

1. Until the single final evaluation (Section 10, step 6), T1 and T2 may only be downloaded, sliced, ingested and
   integrity-checked (SHA-256, row count, vessel count, timestamp range). **No feature distribution,
   plot or score from T1/T2 may be inspected.**
2. After the final evaluation, any change to features, thresholds or models means the T1/T2 numbers
   can no longer serve as an unbiased test. Such a change must be documented, and a new untouched test
   day added.
3. **Clarification of ML-02 §10:** the planned re-check of D1–D3 on the held-out days is a
   *post-evaluation robustness report* (for example, are the cadence medians similar?). It is not a
   tuning step. If it shows that a parameter is unsuitable, rule 2 applies.

### 3.5 Test populations

- **Primary:** T1/T2 vessels whose MMSI is **not** in DEV-train (unseen vessels, unseen days).
- **Secondary:** all T1/T2 vessels (unseen days, possibly familiar vessels).

**Decision D9 (accepted):** the stricter unseen-vessel population is primary.

### 3.6 Removal of the within-day chronological split

The earlier proposals (hours 0–16 vs 16–24, or "Days 1–14 / 15–21") are replaced by the separate test
days. Within one day, a time split mixes up time-of-day effects. ML-01 found that moving vessels per
hour range from 2 to 47. Multi-week data is not available within the agreed scope.

**Second development day (v1.1).** D0B adds vessels and ordinary working-day behaviour to both
training and validation (Section 0.1). It does not replace the test days and is never used as one.

---

## 4. Synthetic Perturbation Framework

### 4.1 General rules

1. **Injection level.** Perturbations are applied to a copy of the canonical records *before*
   re-deriving the movement columns. The derived columns (`prev_source_row`, `elapsed_seconds`,
   `distance_nm`, `implied_speed_knots`, quality flags) are recomputed with the production cleaner
   `aegismar.ingestion.cleaner.process_and_clean_observations`. Perturbed data therefore follows exactly
   the same derivation as real data. A mapping from re-derived rows to original `source_row` values is
   kept, because the cleaner renumbers rows.
2. **Eligibility.** Injections target only **moving segments** (segments as in ML-02 G4) of DEV-val or
   test vessels. The target observation and every observation within ±30 min of it must:
   - have SOG ≥ 1.5 kt (ML-02 G1; v1.0 used 2.0 kt — amended by D17);
   - carry no pre-existing quality flag other than `MISSING_*`;
   - lie outside any feed-wide outage window (ML-02 §6).
   C1/C2 additionally require at least two further observations in the same segment after the
   reappearance observation, so that a window with ≥ 3 pairs containing it can exist (D17).
3. **Density.** Several injections per eligible segment are allowed in one perturbed copy (v1.0: one
   per segment — amended by D17). Injections in the same vessel are at least 60 min (2 × W) apart
   between their spans, so window labels never overlap.

**⚑ DECISION D17 (v1.1):** SOG guard 1.5 kt, several injections per segment ≥ 60 min apart, C
scorability requirement; the ±30 min clean margin is unchanged.
4. **One type and magnitude per copy.** Each perturbed copy of a dataset contains one perturbation
   type at one magnitude. This keeps the effects separable and the attribution unambiguous.
5. **Seeds.** Placement and random signs use `numpy.random.default_rng(seed)`:
   - headline configurations: 10 seeds `{1000, …, 1009}`;
   - severity sweeps: 3 seeds `{1000, 1001, 1002}`.
6. **Injection manifest.** Every copy writes `perturbations.json` with, per injection: id, type, magnitude
   parameters, MMSI, affected original `source_row`s, the pre- and post-perturbation field values, and the seed.

### 4.2 Perturbation types

| Type | What is modified | Severity sweep | **Headline config** | Expected factor(s) |
|---|---|---|---|---|
| **A1 — reported-speed spike** | `sog` of one observation += Δv (position unchanged) | Δv ∈ {5, 10, 15, 20, 25} kt | Δv = 20 kt | `SPEED_DISCONTINUITY`, `SPEED_POSITION_INCONSISTENCY` |
| **A2 — position jump** | One observation moved along its COG by Δv · Δtᵢ / 3600 NM (so the implied speed into it rises by about Δv) | Δv ∈ {5, 10, 15, 20, 25} kt | Δv = 20 kt | `SPEED_POSITION_INCONSISTENCY` |
| **B — lateral drift** | `heading` of K = 5 consecutive observations set to COG ± θ (sign random; wrapped to [0, 360)). Requires heading originally present. | θ ∈ {30, 45, 60, 85}° | θ = 85° | `LATERAL_DRIFT` |
| **C1 — reporting gap** | All observations in [t₀, t₀ + G] removed; positions afterwards unchanged | G ∈ {30, 60} min | — (sweep only) | `REPORTING_GAP` |
| **C2 — gap with displaced reappearance** | As C1, then every later observation in the same segment shifted D NM perpendicular to the COG at reappearance (side random) | G ∈ {30, 60} min at D = 1 NM; D ∈ {0.5, 2} NM at G = 60 min | G = 60 min, D = 1 NM | `REPORTING_GAP`, `SPEED_POSITION_INCONSISTENCY` |

Notes:
- Sweeps deliberately include magnitudes expected to be hard to detect (for example θ = 30°, Δv = 5 kt).
  The aim is a sensitivity curve, not only a pass/fail at one magnitude.
- B uses K = 5 observations. At the 70 s moving cadence (ML-01) that is about 6 min (arithmetic).
- C perturbations need long eligible segments. ML-05 reports how many injections were possible per
  configuration. Configurations with fewer than 20 eligible injections per evaluation dataset (DEV-val
  pooled over its two days; each test day separately) are reported as descriptive only.
- G = 120 min was removed in v1.1 (no eligible site on the D0 validation vessels under v1.0).

**⚑ DECISION D18 (v1.1):** C1/C2 sweeps use G ∈ {30, 60} min.
- **Physical realism caveat:** C2 shifts are not checked against the coastline and may move a track
  over land. This is accepted as a limitation of a controlled sensitivity benchmark (vessel-behavior-ml.md §8.4).

**Decision D10 (accepted):** perturbation types, sweeps and headline configurations as tabulated.

### 4.3 Factor groups (shared by R1, M1 attribution and the output contract)

| Factor | Window features (ML-02 §8.1) |
|---|---|
| `SPEED_DISCONTINUITY` | W2 `max_abs_delta_sog_kt`, W3 `max_abs_accel_ms2` |
| `SPEED_POSITION_INCONSISTENCY` | W4 `max_speed_disparity_kt`, W9 `max_dr_error_ratio` |
| `COURSE_CHANGE` | W5 `max_abs_rot_deg_s` |
| `LATERAL_DRIFT` | W6 `p90_lateral_drift_deg` |
| `HEADING_REVERSAL` | W7 `reversal_share` |
| `REPORTING_GAP` | W8 `max_gap_ratio`, `max_unexplained_gap_s` |
| `TRAJECTORY_SHAPE` | W10 `tortuosity` |
| `STATIONARY_DISPLACEMENT` | W11 (experimental; stationary windows only) |

### 4.4 Labels

- **Window label:** a window is positive if it contains any observation affected by an injection. For
  C1/C2 that means the first observation after the gap (the pair that spans it).
- **Event label:** an injection counts as *detected* if at least one window containing an affected
  observation is flagged.
- **Unknown label (masked):** windows that contain a **pre-existing** `IMPLIED_SPEED_VIOLATION`,
  `TIMESTAMP_POSITION_CONFLICT` or `TIMESTAMP_METADATA_CONFLICT` observation are excluded from metric
  computation, because their true status is unknown. They are listed separately for qualitative review
  as "naturally occurring candidate events". This resolves ML-02 decision D5.

**Decision D11 (accepted):** mask the pre-existing flagged windows as unknown.

---

## 5. Methods Compared

All methods score the same windows (ML-02 §8; 30 min long, 10 min step, segment-bounded).

### 5.1 B0 — ST-DBSCAN density-noise baseline

- Run `aegismar` BallTree ST-DBSCAN (`stdbscan-core-first-v1.0`, H3 parity verified in W3-01) on the full
  perturbed day (all vessels; density depends on everyone).
- **Window score:** the fraction of the window's observations labelled noise (−1).
- **Fairness:** B0 is tuned on DEV-val, just like the other methods, over ε_s ∈ {150, 300, 600} m ×
  MinPts ∈ {3, 5, 10}, with ε_t = 900 s. The value with the best DEV-val headline F1 is used on the test days.
  The W2-01 exploratory configuration (300 m, 900 s, 5) is one of the grid points.

### 5.2 R1 — Explainable rule-based scorer (calibrated)

- For each factor feature *x*, the **factor score** is its empirical CDF on clean DEV-train windows of the
  same motion state: *s(x) = F̂_train(x) ∈ [0, 1]*. Every feature in §4.3 is oriented so that a higher
  value is more abnormal, so no sign flips are needed.
- **Factor group score:** the maximum of its member feature scores.
- **Composite:** *S = max over factor groups*. **`primary_factor` = argmax.** Null features are skipped;
  a window with no non-null factor features is not scored.
- **Alert:** S ≥ θ_R1, with θ_R1 chosen on DEV-val (Section 6.3).
- **Why this replaces the fixed physical thresholds in vessel-behavior-ml.md §7.1:** ML-01 showed that the
  proposed acceleration scale (0.5 m/s²) is exceeded by about 4 of 142,731 pairs at this cadence, and that
  the drift distribution needs a reversal split (ML-02 C3, C7). Thresholds calibrated on data are
  reproducible and transparent, and each alert still says "this value is in the top x% of normal training
  behaviour for factor F".
- **Variant R1-lin (reported, not primary):** an equal-weight mean of the factor group scores, matching the
  proposal's linear combination.

**Decision D12 (accepted):** an ECDF-calibrated, max-composite R1 as the primary rule baseline.

### 5.3 M1 — Isolation Forest (primary ML model)

- **Input:** the window features W2–W10 plus missing-value indicators for W6 and W7 (heading is often
  missing; ML-02 C5). Moving windows only. Gap-only scoring of stationary windows is out of scope for M1.
- **Preprocessing (fit on DEV-train only):** median imputation, then `RobustScaler`.
- **Hyperparameters:** `n_estimators=300`, `max_samples="auto"`, `max_features=1.0`, `random_state=42`.
  The `contamination` value is irrelevant because scores are used directly.
- **Score:** `−score_samples(x)`, mapped to [0, 1] through its ECDF on DEV-train. This gives a
  **non-probabilistic** anomaly index (vessel-behavior-ml.md §7.2).
- **Attribution (post-hoc):** `primary_factor` is the factor group with the highest R1 factor score in
  that window. This is a documented limitation: Isolation Forest has no native attribution, so its
  explanation comes from the same calibrated feature percentiles.

### 5.4 M2 — Local Outlier Factor (secondary)

- `LocalOutlierFactor(n_neighbors=35, novelty=True)` on the same preprocessed inputs, with the same ECDF
  score mapping and the same attribution method. Reported as secondary. It is not part of a hypothesis test.

**Decision D13 (accepted):** M1 is primary and M2 secondary, with the hyperparameters above, and no
hyperparameter search on test data.

---

## 6. Metrics

### 6.1 Ranking (primary)
- **Window-level PR-AUC** (average precision) on the headline configurations. The positive prevalence is
  always reported next to it, because the PR-AUC of a random scorer equals the prevalence.
- ROC-AUC is secondary.

### 6.2 Detection
- **Event recall** per perturbation type and magnitude, giving sensitivity curves.
- **Precision, Recall, F1** at the DEV-val-selected threshold (Section 6.3).

### 6.3 Threshold selection (leakage fix)
- Each method's threshold maximises F1 on **DEV-val**, pooled across headline configurations and seeds.
  It is then **fixed** for T1/T2.
- The "optimal-F1 threshold" of evaluation-protocol §3.3 is reported on the test days only as a
  clearly labelled **oracle upper bound**, never as a result.

### 6.4 False alarms on clean data
- Flagged windows on the **unperturbed** test days, merged into incidents per vessel (overlapping flagged
  windows become one incident), reported as **incidents per 1,000 vessel-hours**. Vessel-hours = the sum
  over vessels of observed segment durations. Broken down by vessel group and motion state.

### 6.5 Attribution
- **Attribution accuracy:** among true-positive windows, the share whose `primary_factor` is in the
  expected set for the injected type (Section 4.2).

### 6.6 Reporting granularity
- Results are reported per test day (T1, T2) and pooled, for the primary and secondary populations,
  as mean ± standard deviation across seeds.

**Decision D14 (accepted):** window PR-AUC as the primary metric, DEV-val threshold selection, and 10/3 seeds.

---

## 7. Diagnostics That Must Be Reported

- The realised partition sizes (vessels and windows) per stratum and per day.
- The number of eligible and realised injections per configuration.
- The share of windows not scored because every factor feature is null (by transceiver class).
- Results stratified by transceiver class (A/B). Heading-dependent factors are null for about 91% of
  Class B rows (ML-02 C5).
- B0's selected grid point and its DEV-val F1 for every grid point.

---

## 8. Statistical Decision Rules

- **Resampling unit:** vessel (MMSI) — a **cluster bootstrap**, because windows of one vessel are correlated.
  B = 2,000 resamples, seed 42, paired (each resample is applied to all methods at once).
- **H-ML1:** Δ = F1(R1) − F1(B0) on the primary population, pooled over T1/T2 and the headline configs.
  - Reject H₀ (Δ ≤ 0) if the one-sided 95% bootstrap lower bound of Δ is > 0.
  - Claim the ≥ 15 pp margin only if that lower bound is ≥ 0.15.
- **H-ML2:** Δ = PR-AUC(M1) − PR-AUC(R1); the same procedure. The attribution criterion holds if the
  one-sided 95% lower bound of M1's attribution accuracy is ≥ 0.90.
- **Multiplicity:** Holm–Bonferroni across the two hypothesis tests at α = 0.05.
- **Power caveat:** with about 40 moving validation vessels per day and unseen-vessel filtering (Section 3.5),
  the confidence intervals may be wide. A non-significant result is reported as "not established", not as
  evidence of no difference.

---

## 9. Experiment Recording Standard

Each run writes to `experiments/outputs/anomaly/<experiment_id>/` (gitignored):

| File | Contents |
|---|---|
| `metadata.json` | experiment id; git commit and dirty flag; SHA-256 of each input dataset; partition seed and partition hash (SHA-256 of the sorted MMSI lists); perturbation seeds; ML-02 and ML-03 document versions; all hyperparameters and thresholds; library versions (python, numpy, pyarrow, scikit-learn); platform |
| `perturbations.json` | the injection manifest (Section 4.1, item 6) |
| `metrics.json` | every metric in Section 6, per day, population, configuration and seed; bootstrap CIs; prevalence |
| `predictions.parquet` | window id, MMSI, start/end, method, score, alert, primary_factor, label (positive / negative / unknown) |
| `models/` | fitted scaler, imputer, ECDF tables, `isolation_forest.joblib`, `lof.joblib` |

---

## 10. Execution Order (ML-04 → ML-05)

1. Download, slice and ingest T1/T2. Integrity check only (Section 3.4).
2. ML-04: implement `features.py` per ML-02 and pass its tests.
3. Ingest D0B, then build the DEV partition (both days) and record its hash.
4. ML-05: build the perturbation harness (`evaluation.py`), R1 (`rules.py`), and M1/M2 (`models.py`).
   Fit on DEV-train and tune on DEV-val.
5. **Freeze:** record all thresholds and grid choices in `metadata.json` and tag the commit.
6. Evaluate once on T1/T2 and produce the report, including negative findings.

---

## 11. Reconciliation With Existing Documents

| Existing statement | Location | Resolution in this protocol |
|---|---|---|
| Chronological split "Days 1–14 / Days 15–21" | evaluation-protocol §3.1 | Replaced by D0 + T1/T2 (§3.1, §3.6) |
| Within-day 16 h / 8 h split | vessel-behavior-ml §8.2 | Removed (§3.6) |
| Type A "> 20 kt" vs "+25 kt" | evaluation-protocol §3.2 / vessel-behavior-ml §8.4 | Sweep 5–25 kt with a 20 kt headline, split into A1/A2 (§4.2) |
| Type B "> 60° at > 2 kt" vs "85° at 12 kt" | same | Sweep 30–85° with an 85° headline; eligibility SOG ≥ 2 kt (§4.1–4.2) |
| Type C "30 min–4 h" vs "45–90 min" | same | Sweep 30–60 min (v1.1); 4 h and 120 min dropped because no eligible site exists on the development data (Section 0.1) |
| F1 at the "optimal threshold" | evaluation-protocol §3.3 | Threshold from DEV-val; the test-day optimum is labelled an oracle bound (§6.3) |
| Fixed physical rule thresholds (0.5 m/s², 45°, 1,800 s) | vessel-behavior-ml §7.1 | Replaced by ECDF calibration (§5.2); justified by ML-02 C3/C7/C8 |
| Untuned density-noise baseline | research-plan H2 / vessel-behavior-ml §7.3 | B0 tuned on DEV-val like every other method (§5.1) |

---

## 12. Design Decisions (Accepted)

All decisions below were accepted by the Track B lead (Kishakya) on 2026-11-23.

| # | Decision | Accepted choice |
|---|---|---|
| D7 | Test days | T1 = 2025-01-14 (Tue), T2 = 2025-01-22 (Wed) |
| D8 | Development split | Stratified (group × ever-moving) 70/30 by MMSI, seed 42; validation part for tuning (amended by D16) |
| D9 | Primary test population | Vessels not in DEV-train |
| D10 | Perturbations | Types A1, A2, B, C1, C2 with the sweeps and headlines in §4.2 |
| D11 | Pre-existing flagged windows | Masked as "unknown"; reviewed qualitatively |
| D12 | Rule baseline | ECDF-calibrated, max-composite R1 (R1-lin reported) |
| D13 | Models | M1 Isolation Forest (primary), M2 LOF (secondary), fixed hyperparameters |
| D14 | Metrics and seeds | Window PR-AUC primary; DEV-val threshold; 10 headline / 3 sweep seeds |
| D15 ⚑ | Extra development day *(v1.1, pending)* | D0B = 2025-01-08; DEV = D0 ∪ D0B |
| D16 ⚑ | Joint split *(v1.1, pending)* | One MMSI-grouped stratified split over both development days |
| D17 ⚑ | Eligibility and density *(v1.1, pending)* | SOG ≥ 1.5 kt; several injections per segment ≥ 60 min apart; C scorability; ±30 min margin kept |
| D18 ⚑ | Gap configurations *(v1.1, pending)* | G ∈ {30, 60} min (120 min removed) |

---

## 13. Known Limitations

1. Synthetic perturbations measure sensitivity to defined signatures. They do not measure real-world
   detection of maritime threats (vessel-behavior-ml §8.4).
2. A single region with four days of data (two development, two test) cannot support claims about
   other ports or seasons.
3. D0 is a public holiday. T2 is included specifically so that any difference between D0 and T2 can be described.
4. Isolation Forest / LOF attribution is post-hoc (§5.3), not intrinsic.
5. Kinematic signal quality is limited by the 70–180 s cadence and missing headings (ML-02 C1, C5).

---

## 14. Version History

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-11-23 | Initial draft. |
| 1.0 | 2026-11-23 | Decisions D7–D14 accepted by the Track B lead; protocol frozen before any test-day inspection. |
| 1.1 (draft) | 2026-11-25 | Amendments D15–D18 (Section 0): second development day, joint vessel split, relaxed eligibility and density, G = 120 min removed. Made before any test-day inspection. |
