# ML-02: Vessel Trajectory Kinematic Feature Specification

> **Project AegisMar — Track B (Vessel Behavior ML & Anomaly Detection)**
> **Document Version:** 1.0 (Accepted by Track Lead)
> **Milestone:** ML-02
> **Track Lead:** Kishakya
> **Date:** 2026-11-23

> [!IMPORTANT]
> **Scope of this version.** This specification defines *features*, their exact formulas, validity
> guards and null rules. It does **not** set anomaly thresholds, rule weights or model hyperparameters;
> those belong to ML-03 (Baseline Models & Evaluation Protocol). Design decisions D1–D6 were accepted
> by the Track B lead on 2026-11-23 (Section 10). Changes to accepted features or guards require a
> new document version.
>
> **Evidence standard.** Every dataset statistic quoted here comes from an executed, reproducible
> script (Section 12). No numbers are estimated or simulated. Arithmetic illustrations are labelled as such.

---

## 1. Purpose and Scope

ML-02 turns the cleaned canonical AIS observations into a defined set of per-vessel kinematic,
geometric and reporting-interval features that ML-04 will implement in
`src/aegismar/anomaly/features.py`. The goals are:

1. Every feature has an exact formula, unit, input requirements, validity guard and null rule.
2. Every guard or design choice is justified by the ML-01 profile of the real dataset, not by assumption.
3. Features are computed per vessel only (no cross-vessel leakage), with one documented exception:
   feed-wide reception outages (Section 6), which describe the receiver network, not any vessel.

Out of scope: anomaly thresholds, rule weights, model choice, train/test splitting and perturbation
parameters (ML-03).

---

## 2. Data-Derived Constraints (ML-01 Findings)

Source dataset: `data/processed/lalb_20250101/cleaned_ais.parquet`, SHA-256
`bdde2581302270a9e2c99a1a7aa1819a0bd1a24fbf6384458cfd8a81229eaf48` (143,124 rows, 362 vessels,
2025-01-01 00:00:00 → 23:59:57 UTC).

| # | Finding | Evidence (profile key) | Consequence for features |
|---|---|---|---|
| C1 | The reporting cadence is coarse and regular, not raw AIS. 100% of intervals are whole seconds. The most common intervals are 180 s (26,305 pairs) and 70 s (15,020 pairs). When the previous ping is moving (SOG ≥ 1.5 kt) the median interval is 70 s (p95 92 s, p99 180 s). When it is stationary (SOG < 0.5 kt) the median is 179 s (p95 361 s). Class A median 71 s; Class B median 180 s. | `reporting_interval_s` | "Instantaneous" rates are really averages over 1–3 min. Acceleration and rate of turn are computed but must be read as interval-averaged. The expected interval depends on class and motion state (F10). |
| C2 | The dataset is mostly stationary. 90.0% of SOG values are < 0.5 kt and 76.8% are exactly 0. Only 135 of 362 vessels ever reach SOG ≥ 1.5 kt. | `sog_knots`, `split_feasibility` | Kinematic features apply only to moving observations. Stationary observations need their own features (F12). Scoring units need a motion state (Section 8). |
| C3 | Acceleration ≥ 0.5 m/s² (the proposal's Rule 1 scale) occurs in about 4 of 142,731 pairs (share 2.8 × 10⁻⁵). p99.9 of \|a\| is 0.081 m/s². | `kinematics_pairs` | Acceleration has low sensitivity at this cadence. Primary speed-discontinuity evidence should come from ΔSOG (F2) and speed disparity (F4). |
| C4 | Reported vs implied speed agree closely. The median \|implied − SOG\| is 0.026 kt and p99 is 1.32 kt. The maximum is 15,409.8 kt over all pairs but 1,140.9 kt when Δt ≥ 30 s. | `implied_vs_reported_speed_kt` | Speed disparity is a high-contrast feature. Very short Δt inflates it, so a minimum-Δt guard is needed (G3). |
| C5 | Heading is present in 63.0% of Class A rows and 8.8% of Class B rows. COG is present in 93.1% (A) and 63.3% (B). Class B is 223 of the 362 vessels. | `field_availability.by_class` | Drift features are null for most Class B traffic. Missing heading must be a null, never a zero. Feature availability is itself data-quality context. |
| C6 | At SOG ≥ 1.5 kt, the COG–heading disparity has median 3.0° and p95 108.1°. 5.9% of values exceed 45° (n = 7,230). The share > 45° is 13.6% at SOG ≥ 0.5 kt and 1.2% at SOG ≥ 5 kt. | `drift_cog_minus_heading` | The low-speed guard matters. 1.5 kt is adopted (G1), which also resolves the 0.5 vs 1.5 kt inconsistency in earlier documents. |
| C7 | Of the 429 disparities > 45° at SOG ≥ 1.5 kt, **342 are > 135° (near reversal)** from 29 vessels, with median SOG 2.9 kt. Tug/towing vessels contribute 281 of them and a single vessel contributes 134. Only **87 lie in 45–135°** (20 vessels). | `ml02_drift_breakdown` | Near-reversal and lateral drift are physically different. They are split into two features (F7, F8) so that reversal values do not dominate "drift". The cause of the reversals (astern movement, reversed heading configuration, tug operations) is **not established** by AIS alone. |
| C8 | Two **feed-wide silences**, when no vessel at all was received: 2025-01-01 03:07:37 → 03:20:25 and 12:06:09 → 12:18:20 UTC (union of sub-windows > 60 s). They account for **557 of 1,579** vessel gaps > 600 s. | `feed_wide_silences` | Gap features must separate receiver-network outages from vessel-specific gaps (Section 6, F10–F11). |
| C9 | Splitting at Δt > 1,800 s gives 468 segments (44 vessels split). At > 7,200 s it gives 386 segments (23 vessels split). 3 vessels have a single observation. | `segmentation`, `overview` | The segmentation threshold is set in G4. Single-observation vessels produce no pair features. |
| C10 | The 18 `IMPLIED_SPEED_VIOLATION` rows (implied speed > 50 kt) are positional jumps. 8 `TIMESTAMP_POSITION_CONFLICT` rows have no movement pointers. | `quality_flags` | Quality handling is defined in Section 4.3. |

---

## 3. Notation and Conventions

- Vessel trajectory: \(T_v = \langle p_1, \dots, p_N \rangle\) ordered by `(timestamp_utc, source_row)`.
- A **pair** \((p_j, p_i)\) links observation \(p_i\) to its predecessor \(p_j\). Here \(j\) is the row whose
  `source_row` equals \(p_i\).`prev_source_row`. That is the previous *unambiguous* observation of the same
  vessel, as assigned by ingestion.
- \(\Delta t_i\) = `elapsed_seconds` of \(p_i\) (seconds).
- Units: speed in knots (kt); distance in nautical miles (NM) or metres (m); angle in degrees (°); time in seconds (s).
  Conversion: 1 kt = 1852 / 3600 m/s = 0.514444… m/s.
- **Angular difference** (wrapped, unsigned), used for every angle comparison:
  $$\operatorname{angdiff}(a, b) = \left|\, ((a - b + 180) \bmod 360) - 180 \,\right| \in [0, 180]$$
  Example: angdiff(359°, 1°) = 2°, not 358°.
- **Signed angular difference**, used for turn direction:
  $$\operatorname{sangdiff}(a, b) = ((a - b + 180) \bmod 360) - 180 \in [-180, 180)$$
- **Null rule**: a feature is `null` (NaN) whenever any required input is null or any guard fails.
  Feature extraction **never imputes**. Imputation, if any, happens at model fitting time on the
  training partition only (ML-03).
- Earth radius \(R\) = 6,371,008.8 m. This is the same constant as `aegismar.spatial.haversine`; distances
  reuse `haversine_distance_meters` / `haversine_distance_nm`.

---

## 4. Input Contract and Pre-processing

### 4.1 Input
The 19-column canonical Parquet defined in `src/aegismar/ingestion/schema.py`. Feature code **must not
rely on file row order**. It re-sorts each vessel by `(timestamp_utc, source_row)`.

### 4.2 Pairing
Pairs are formed **only** through `prev_source_row`, reusing the ingestion values for `elapsed_seconds`,
`distance_nm` and `implied_speed_knots`. This keeps Track B consistent with the ingestion contract and
automatically skips same-timestamp conflict rows (their pointers are null by design).

### 4.3 Quality-flag handling

| Flag | Handling in feature extraction |
|---|---|
| `TIMESTAMP_POSITION_CONFLICT`, `TIMESTAMP_METADATA_CONFLICT` | Row kept for traceability. It produces no pair features (null pointers) and is excluded from window aggregates. Counted in `data_quality_context`. |
| `IMPLIED_SPEED_VIOLATION` | Row **kept**. Its features are computed normally, so the positional jump is visible in F4/F5. The flag is carried into `data_quality_context`. Whether these rows count as anomalies or as sensor artifacts in evaluation is deferred to ML-03 (D5). |
| `ZERO_ELAPSED_TIME` | Rate features are null (G2). |
| `MISSING_*`, `*_SENTINEL_NULLIFIED` | The field is null, so dependent features are null. Counted as availability context. |

---

## 5. Guards and Global Parameters

| ID | Parameter | Value | Justification |
|---|---|---|---|
| G1 | Moving-speed guard \(v_g\) | **1.5 kt** | C6: the share of disparity > 45° falls from 13.6% (≥ 0.5 kt) to 5.9% (≥ 1.5 kt) while keeping 7,230 drift-eligible rows (vs 5,663 at ≥ 5 kt). Consistent with onboarding §12.3. |
| G2 | Minimum Δt for any rate | Δt > 0 s | Avoid division by zero. |
| G3 | Minimum Δt for speed disparity | **30 s** | C4: removes the extreme inflation from very short intervals (max 15,409.8 → 1,140.9 kt) while keeping 142,510 of 142,742 pairs. |
| G4 | Segmentation threshold \(T_{seg}\) | **1,800 s** (D2) | Rates averaged over > 30 min at a 70–180 s cadence are not meaningful kinematics. 1,800 s is also the gap scale in the proposal's Rule 3. It gives 468 segments (C9). The pair that spans a break still receives gap features (F9–F11) but no rate features. |
| G5 | Maximum Δt for rate features \(T_{rate}\) | **600 s** (D3) | p99 of moving intervals is 180 s (C1). Rates over > 10 min mix several manoeuvres. Rate features (F3, F6) are null above this. |
| G6 | Feed-wide silence threshold \(S_{out}\) | **60 s** | C8: at about 1.66 messages/s on average, every silence > 60 s observed lies inside the two outage periods. |
| G7 | Outage merge tolerance | **180 s** | Silences separated by ≤ 180 s of activity merge into one outage window (one standard stationary interval). |
| G8 | Minimum net displacement for tortuosity | **0.05 NM** (≈ 93 m) | Below this, the straightness ratio is dominated by GPS jitter (stationary vessels). |

---

## 6. Feed-Wide Outage Detection

The outage table is derived **per dataset (per day)** from all observations:

1. Let \(U\) = sorted unique observation times (seconds) across *all* vessels.
2. A silence is any consecutive pair \((u_k, u_{k+1})\) in \(U\) with \(u_{k+1} - u_k > S_{out}\) (G6).
3. Merge silences separated by ≤ 180 s (G7) into outage windows \(O = \{[o^{s}_m, o^{e}_m]\}\).
4. For a vessel pair spanning \([t_j, t_i]\):
   $$\text{outage\_overlap\_s}_i = \sum_m \big|[t_j, t_i] \cap [o^{s}_m, o^{e}_m]\big|$$

**Leakage note.** The outage table uses every vessel's timestamps but **no labels and no kinematic values**.
It describes the receiver network, which an operator would also know. It is recomputed on whatever
dataset is being evaluated (including perturbed copies), never carried over from another day.

---

## 7. Point-Level (Pair) Features

All features below are attached to observation \(p_i\) and use its predecessor \(p_j\).

| ID | Name | Formula | Unit | Requires | Guards / null rule |
|---|---|---|---|---|---|
| F1 | `dt_s` | \(\Delta t_i\) | s | pair | null if no pair |
| F2 | `delta_sog_kt` | \(\text{SOG}_i - \text{SOG}_j\) (signed); `abs_delta_sog_kt` = \|·\| | kt | both SOG | null if either SOG null |
| F3 | `accel_ms2` | \(\dfrac{(\text{SOG}_i - \text{SOG}_j)\cdot 0.514444}{\Delta t_i}\) | m/s² | F2 | G2, G5. Interval-averaged (C1, C3). |
| F4 | `speed_disparity_kt` | \(\left\lvert v^{impl}_i - \tfrac{1}{2}(\text{SOG}_i + \text{SOG}_j)\right\rvert\), with \(v^{impl}_i\) = `implied_speed_knots` | kt | both SOG, implied | G3. Uses the mean of both reported speeds because implied speed is an average over the interval. |
| F5 | `implied_speed_kt` | `implied_speed_knots` (pass-through) | kt | pair | null if Δt = 0 |
| F6 | `rot_deg_s` | \(\dfrac{\operatorname{sangdiff}(\text{COG}_i, \text{COG}_j)}{\Delta t_i}\) (signed); `abs_rot_deg_s`; also `abs_delta_cog_deg` = angdiff | °/s, ° | both COG, both SOG | Both SOG ≥ \(v_g\) (G1); G2, G5 |
| F7 | `lateral_drift_deg` | \(d_i = \operatorname{angdiff}(\text{COG}_i, \text{HDG}_i)\) if \(d_i \le 135°\), else null | ° | COG, HDG, SOG at \(p_i\) | SOG\(_i\) ≥ \(v_g\) (G1). Single observation, no pair needed. |
| F8 | `course_heading_reversal` | 1 if \(d_i > 135°\), else 0 | binary | as F7 | as F7. Kept separate from drift (C7). Its physical cause is not established. |
| F9 | `gap_s` | \(\Delta t_i\), retained even when it exceeds \(T_{seg}\) | s | pair | null if no pair |
| F10 | `gap_ratio` | \(\Delta t_i \,/\, \tilde{\Delta t}_{c,s}\), where \(\tilde{\Delta t}_{c,s}\) is the median interval for transceiver class \(c\) and motion state \(s\) of \(p_j\) (moving: SOG ≥ \(v_g\); else stationary) | ratio | pair, class, SOG\(_j\) | The medians are **fitted on the training partition only** (ML-03). Null if class unknown. |
| F11 | `unexplained_gap_s` | \(\max(0,\ \Delta t_i - \text{outage\_overlap\_s}_i)\) | s | pair, outage table | — |
| F12 | `dr_error_nm` | Haversine distance between the actual \(p_i\) and the dead-reckoned position \(\hat{p}_i\) (below) | NM | SOG\(_j\), COG\(_j\), pair | null if COG\(_j\) or SOG\(_j\) null |
| F13 | `dr_error_ratio` | \(\dfrac{\text{dr\_error\_nm}_i}{\max(\text{SOG}_j \cdot \Delta t_i / 3600,\ 0.05)}\) | ratio | F12 | 0.05 NM floor as G8 |

**Dead-reckoned position** (spherical destination point): from \(p_j\) at latitude \(\varphi_1\), longitude
\(\lambda_1\), bearing \(\theta = \text{COG}_j\), angular distance \(\delta = (\text{SOG}_j \cdot \Delta t_i/3600 \cdot 1852)/R\):
$$\varphi_2 = \arcsin(\sin\varphi_1\cos\delta + \cos\varphi_1\sin\delta\cos\theta)$$
$$\lambda_2 = \lambda_1 + \operatorname{atan2}(\sin\theta\,\sin\delta\,\cos\varphi_1,\ \cos\delta - \sin\varphi_1\sin\varphi_2)$$
with \(\lambda_2\) normalised to \([-180°, 180°)\).

**Why F12/F13.** These features target the proposal's Type C perturbation: a reappearance *outside the
dead-reckoning envelope* after a gap. F11 says a gap happened; F12/F13 say whether the vessel ended up
somewhere its last reported motion cannot explain.

---

## 8. Scoring Unit, Windows and Motion State

**Scoring unit (D1): segment-bounded sliding time windows built on point features.**

- **Window:** length \(W\) = 30 min, step 10 min, never crossing a segment break (G4). A window needs
  ≥ 3 observations with pair features; otherwise it is not scored. At the observed 70–180 s cadence, a
  30-min window holds about 10–25 observations (arithmetic from C1, not a measured distribution).
- **Motion state:** a window is `moving` if the median SOG ≥ \(v_g\), otherwise `stationary`. Kinematic
  features (F2–F8) contribute only in `moving` windows. Gap features (F9–F13) contribute in both.
- **Why windows rather than single points:** the output contract (`vessel_anomaly_v1`) describes incidents
  with a start and end time, a LineString and `observation_source_rows`. That fits a window naturally.
- **Why point features underneath:** injected perturbations are often a single-point event. Window
  aggregates use `max` so that one extreme pair is not averaged away, and the arg-max pair gives the factor
  attribution (`primary_factor`) and its source row.
- **Incidents:** overlapping flagged windows of the same vessel merge into one incident (a rule for ML-05).

### 8.1 Window aggregates

| ID | Name | Definition |
|---|---|---|
| W1 | `n_obs`, `n_pairs` | counts in window |
| W2 | `max_abs_delta_sog_kt` | max of F2 (abs) |
| W3 | `max_abs_accel_ms2` | max of \|F3\| |
| W4 | `max_speed_disparity_kt` | max of F4 |
| W5 | `max_abs_rot_deg_s` | max of \|F6\| |
| W6 | `p90_lateral_drift_deg` | 90th percentile of F7 (null if < 3 values) |
| W7 | `reversal_share` | mean of F8 over eligible observations |
| W8 | `max_gap_ratio`, `max_unexplained_gap_s` | max of F10, F11 |
| W9 | `max_dr_error_ratio` | max of F13 |
| W10 | `tortuosity` | \(\sum \text{distance\_nm} \,/\, \text{haversine}(p_{first}, p_{last})\). Null if the net displacement < 0.05 NM (G8). |
| W11 | `stationary_net_displacement_m` | haversine(\(p_{first}, p_{last}\)) for `stationary` windows (candidate anchor-drag signal; **experimental**, D6 — to be evaluated in ML-04) |
| W12 | `heading_availability`, `cog_availability` | share of observations with a non-null field (data-quality context) |
| W13 | `median_sog_kt`, `motion_state` | context |

---

## 9. Implications Recorded for ML-03

These are not decisions of ML-02. They follow directly from the data and must be addressed when
thresholds and perturbations are frozen.

1. **The speed-jump perturbation vs an acceleration threshold.** *Arithmetic illustration:* a +25 kt jump
   = 12.86 m/s. Spread over a 70 s interval that is 0.18 m/s²; over 180 s it is 0.07 m/s². Both are below the
   proposal's \(a_{threshold} \approx 0.5\) m/s². Rule 1 should be re-based on F2/F4, or on F3 with thresholds
   calibrated to C3.
2. **Perturbation realism.** A perturbation that edits only the `sog` field shows up in F2/F4. One that
   moves positions shows up in F4/F5/F12. ML-03 must state which fields each perturbation type modifies.
3. **The drift perturbation (Type B: |COG − HDG| = 85° at 12 kt)** falls in the 45–135° band. That band is
   rare in clean data (87 rows, 20 vessels; C7), so F7 should separate it well. This is a hypothesis.
4. **Heading-dependent features are null for about 91% of Class B rows** (C5). Evaluation should report
   results per class, or limit drift perturbations to observations with heading available.
5. **Small moving population:** 135 vessels ever move at SOG ≥ 1.5 kt. This supports the agreed plan to add
   held-out days.

---

## 10. Design Decisions (Accepted)

All decisions below were accepted by the Track B lead (Kishakya) on 2026-11-23.

| # | Decision | Accepted choice |
|---|---|---|
| D1 | Scoring unit | Segment-bounded 30-min / 10-min-step windows over point features (Section 8) |
| D2 | \(T_{seg}\) | 1,800 s (G4) |
| D3 | \(T_{rate}\) | 600 s (G5) |
| D4 | Reversal handling | A separate feature F8, not merged into drift (F7) |
| D5 | `IMPLIED_SPEED_VIOLATION` rows | Kept as features; their label semantics are decided in ML-03 |
| D6 | W11 (stationary displacement) | Included as experimental and evaluated in ML-04 |

The parameter values in D1–D3 are justified by the ML-01 profile of a single day (2025-01-01). They
should be re-checked against the agreed held-out days once those are profiled, and any change recorded
as a new version of this document.

---

## 11. Verification Plan for ML-04 (`tests/unit/test_anomaly.py`)

Every case below uses a hand-built synthetic trajectory with a known answer:

1. `angdiff(359, 1) == 2`, `angdiff(0, 180) == 180`, `sangdiff(10, 350) == 20`, `sangdiff(350, 10) == -20`.
2. A straight constant-speed track gives F2 = 0, F3 = 0, F6 = 0, W10 ≈ 1.0, and F12 ≈ 0 within floating-point tolerance.
3. Dead-reckoning: due north from (0°, 0°) at 60 kt for 3,600 s gives \(\hat{p}\) ≈ (0.999325°, 0°) on the R = 6,371,008.8 m sphere (60 × 1852 m / R = 0.9993248° of arc; computed, not assumed to be exactly 1°).
4. Pairing skips `TIMESTAMP_POSITION_CONFLICT` rows. Rate features are null for Δt > \(T_{rate}\) and for Δt = 0.
5. Outage overlap: a gap fully inside an outage gives F11 = 0. A gap partly overlapping gives the exact residual.
6. Low-speed guard: a COG/heading disparity with SOG = 1.4 kt gives F7 = F8 = null.
7. Windows never span a segment break. A window with < 3 pairs is not produced.
8. Permutation invariance: shuffling input rows yields identical features.
9. No cross-vessel leakage: features of vessel A are unchanged when vessel B is removed (except the outage table, tested separately).

---

## 12. Reproducing the Evidence

```powershell
uv run python experiments/anomaly/ml01_profile_dataset.py `
  --input data/processed/lalb_20250101/cleaned_ais.parquet `
  --output experiments/outputs/anomaly/ml01_profile

uv run python experiments/anomaly/ml02_drift_breakdown.py `
  --input data/processed/lalb_20250101/cleaned_ais.parquet `
  --output experiments/outputs/anomaly/ml02_drift_breakdown
```

- `ml01_profile_dataset.py` is introduced on branch `feat/ml-01-data-profiling` (pending review).
- Both scripts record the input SHA-256 in their JSON output. Outputs are gitignored.
- Code baseline when this specification was written: commit `50408dc`.

---

## 13. Version History

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-11-23 | Initial draft from ML-01 profile and drift breakdown. |
| 1.0 | 2026-11-23 | Decisions D1–D6 accepted by the Track B lead; specification frozen for ML-03 / ML-04. |
