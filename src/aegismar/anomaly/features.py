"""Track B trajectory feature extraction, implementing ML-02 v1.0.

Specification: ``docs/03-research/ml-02-feature-spec.md`` (v1.0). Identifiers in this module
(F1-F13 pair features, W1-W13 window aggregates, guards G1-G8) refer to that document.

Implementation choices where ML-02 v1.0 leaves a detail open (documented, not new design):

* **Window alignment.** For each segment with first/last observation times ``t0``/``tl``, windows
  are half-open ``[t0 + k*step, t0 + k*step + W)``. If ``tl - t0 < W`` there is one window
  (``k = 0``); otherwise ``k = 0 .. floor((tl - t0 - W) / step) + 1``, which guarantees the last
  observation is covered.
* **Pair spanning a segment break.** ML-02 G4 removes only *rate* features from such a pair
  (they are already null through G5). ``delta_sog_kt`` (F2) and ``speed_disparity_kt`` (F4) are
  not rates and are therefore computed, which keeps the C2 "displaced reappearance" signal visible.
* **Motion state with no SOG.** A window whose observations all lack SOG has
  ``motion_state = "unknown"``; kinematic aggregates (W2-W7) are null, as for stationary windows.
* **Conflict rows.** ``TIMESTAMP_*_CONFLICT`` rows get no pair features, no segment and are not
  window members; they are counted per window in ``n_conflict_rows`` (data-quality context).

Feature extraction never imputes: a feature is NaN whenever an input is missing or a guard fails.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
from numpy.typing import NDArray

from aegismar.common.constants import (
    FLAG_IMPLIED_SPEED_VIOLATION,
    FLAG_TIMESTAMP_METADATA_CONFLICT,
    FLAG_TIMESTAMP_POSITION_CONFLICT,
    METERS_PER_NAUTICAL_MILE,
    SECONDS_PER_HOUR,
)
from aegismar.spatial.haversine import EARTH_RADIUS_METERS

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
BoolArray = NDArray[np.bool_]

FEATURE_SPEC_VERSION: str = "ml-02-v1.0"

# Guards and parameters (ML-02 section 5 and section 8)
MOVING_SOG_KT: float = 1.5  # G1
MIN_DISPARITY_DT_S: float = 30.0  # G3
SEGMENT_GAP_S: float = 1800.0  # G4 (D2)
MAX_RATE_DT_S: float = 600.0  # G5 (D3)
OUTAGE_MIN_SILENCE_S: float = 60.0  # G6
OUTAGE_MERGE_TOLERANCE_S: float = 180.0  # G7
MIN_NET_DISPLACEMENT_NM: float = 0.05  # G8
REVERSAL_THRESHOLD_DEG: float = 135.0  # F7 / F8 split
WINDOW_LENGTH_S: float = 1800.0  # D1
WINDOW_STEP_S: float = 600.0  # D1
MIN_WINDOW_PAIRS: int = 3  # ML-02 section 8
MIN_DRIFT_VALUES_FOR_P90: int = 3  # W6

KNOT_TO_MS: float = METERS_PER_NAUTICAL_MILE / SECONDS_PER_HOUR

MOTION_MOVING: str = "moving"
MOTION_STATIONARY: str = "stationary"
MOTION_UNKNOWN: str = "unknown"

PAIR_FEATURE_COLUMNS: tuple[str, ...] = (
    "dt_s",  # F1
    "delta_sog_kt",  # F2 (signed)
    "abs_delta_sog_kt",  # F2
    "accel_ms2",  # F3
    "speed_disparity_kt",  # F4
    "implied_speed_kt",  # F5
    "rot_deg_s",  # F6 (signed)
    "abs_rot_deg_s",  # F6
    "abs_delta_cog_deg",  # F6
    "lateral_drift_deg",  # F7
    "course_heading_reversal",  # F8
    "gap_s",  # F9
    "gap_ratio",  # F10
    "outage_overlap_s",  # section 6
    "unexplained_gap_s",  # F11
    "dr_error_nm",  # F12
    "dr_error_ratio",  # F13
)

WINDOW_FEATURE_COLUMNS: tuple[str, ...] = (
    "max_abs_delta_sog_kt",  # W2
    "max_abs_accel_ms2",  # W3
    "max_speed_disparity_kt",  # W4
    "max_abs_rot_deg_s",  # W5
    "p90_lateral_drift_deg",  # W6
    "reversal_share",  # W7
    "max_gap_ratio",  # W8
    "max_unexplained_gap_s",  # W8
    "max_dr_error_ratio",  # W9
    "tortuosity",  # W10
    "stationary_net_displacement_m",  # W11 (experimental, D6)
    "heading_availability",  # W12
    "cog_availability",  # W12
    "median_sog_kt",  # W13
)

ExpectedIntervals = Mapping[tuple[str, str], float]


# --------------------------------------------------------------------------- geometry
def angdiff(a: FloatArray | float, b: FloatArray | float) -> FloatArray:
    """Unsigned wrapped angular difference in degrees, in [0, 180] (ML-02 section 3)."""
    return np.abs(np.mod(np.asarray(a, dtype=np.float64) - b + 180.0, 360.0) - 180.0)


def sangdiff(a: FloatArray | float, b: FloatArray | float) -> FloatArray:
    """Signed wrapped angular difference ``a - b`` in degrees, in [-180, 180)."""
    return np.mod(np.asarray(a, dtype=np.float64) - b + 180.0, 360.0) - 180.0


def haversine_m(
    lat1: FloatArray, lon1: FloatArray, lat2: FloatArray, lon2: FloatArray
) -> FloatArray:
    """Vectorised great-circle distance in metres.

    Same formula, clamping and Earth radius as ``aegismar.spatial.haversine``.
    """
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    sin_dphi = np.sin(np.radians(np.asarray(lat2) - lat1) / 2.0)
    sin_dlam = np.sin(np.radians(np.asarray(lon2) - lon1) / 2.0)
    a = sin_dphi * sin_dphi + np.cos(phi1) * np.cos(phi2) * (sin_dlam * sin_dlam)
    a = np.clip(a, 0.0, 1.0)
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return np.asarray(EARTH_RADIUS_METERS * c, dtype=np.float64)


def destination_point(
    lat: FloatArray, lon: FloatArray, bearing_deg: FloatArray, distance_m: FloatArray
) -> tuple[FloatArray, FloatArray]:
    """Spherical destination point (ML-02 section 7), longitude normalised to [-180, 180)."""
    phi1 = np.radians(lat)
    lam1 = np.radians(lon)
    theta = np.radians(bearing_deg)
    delta = np.asarray(distance_m, dtype=np.float64) / EARTH_RADIUS_METERS
    sin_phi2 = np.sin(phi1) * np.cos(delta) + np.cos(phi1) * np.sin(delta) * np.cos(theta)
    phi2 = np.arcsin(np.clip(sin_phi2, -1.0, 1.0))
    lam2 = lam1 + np.arctan2(
        np.sin(theta) * np.sin(delta) * np.cos(phi1),
        np.cos(delta) - np.sin(phi1) * np.sin(phi2),
    )
    lon2 = np.mod(np.degrees(lam2) + 180.0, 360.0) - 180.0
    return np.asarray(np.degrees(phi2), dtype=np.float64), np.asarray(lon2, dtype=np.float64)


# --------------------------------------------------------------------------- outages
def detect_outage_windows(
    timestamps_s: Iterable[float] | FloatArray,
    min_silence_s: float = OUTAGE_MIN_SILENCE_S,
    merge_tolerance_s: float = OUTAGE_MERGE_TOLERANCE_S,
) -> list[tuple[float, float]]:
    """Feed-wide silence windows (ML-02 section 6, G6/G7) from all observation times."""
    u = np.unique(np.asarray(list(timestamps_s), dtype=np.float64))
    if u.size < 2:
        return []
    gaps = np.diff(u)
    idx = np.flatnonzero(gaps > min_silence_s)
    windows: list[tuple[float, float]] = []
    for i in idx:
        start, end = float(u[i]), float(u[i + 1])
        if windows and start - windows[-1][1] <= merge_tolerance_s:
            windows[-1] = (windows[-1][0], end)
        else:
            windows.append((start, end))
    return windows


def outage_overlap_s(
    start_s: FloatArray, end_s: FloatArray, windows: Iterable[tuple[float, float]]
) -> FloatArray:
    """Total overlap in seconds of each interval ``[start, end]`` with the outage windows."""
    start = np.asarray(start_s, dtype=np.float64)
    end = np.asarray(end_s, dtype=np.float64)
    total = np.zeros(start.shape, dtype=np.float64)
    for o_start, o_end in windows:
        total += np.clip(np.minimum(end, o_end) - np.maximum(start, o_start), 0.0, None)
    return np.where(np.isfinite(start) & np.isfinite(end), total, np.nan)


# --------------------------------------------------------------------------- observations
@dataclass(frozen=True)
class Observations:
    """Canonical observations sorted by ``(mmsi, timestamp_utc, source_row)`` with predecessors."""

    mmsi: NDArray[np.object_]
    vessel_code: IntArray
    timestamp_us: IntArray
    source_row: IntArray
    latitude: FloatArray
    longitude: FloatArray
    sog: FloatArray
    cog: FloatArray
    heading: FloatArray
    transceiver_class: NDArray[np.object_]
    elapsed_s: FloatArray
    distance_nm: FloatArray
    implied_speed_kt: FloatArray
    is_conflict: BoolArray
    has_implied_speed_violation: BoolArray
    prev_idx: IntArray

    @property
    def size(self) -> int:
        return int(self.source_row.size)

    @property
    def timestamp_s(self) -> FloatArray:
        return self.timestamp_us.astype(np.float64) / 1e6


def _to_float(col: pa.ChunkedArray) -> FloatArray:
    return np.asarray(
        pc.fill_null(pc.cast(col, pa.float64()), float("nan")).to_numpy(), dtype=np.float64
    )


def prepare_observations(table: pa.Table) -> Observations:
    """Sort canonical rows per vessel and resolve ``prev_source_row`` pointers (ML-02 4.1-4.2)."""
    mmsi_raw = np.asarray(table.column("mmsi").to_pylist(), dtype=object)
    uniq, codes = np.unique(mmsi_raw, return_inverse=True)
    ts = np.asarray(pc.cast(table.column("timestamp_utc"), pa.int64()).to_numpy(), dtype=np.int64)
    src = np.asarray(table.column("source_row").to_numpy(), dtype=np.int64)
    order = np.lexsort((src, ts, codes))

    flags = table.column("quality_flags").to_pylist()
    conflict = np.asarray(
        [
            bool(f)
            and (FLAG_TIMESTAMP_POSITION_CONFLICT in f or FLAG_TIMESTAMP_METADATA_CONFLICT in f)
            for f in flags
        ],
        dtype=bool,
    )
    isv = np.asarray([bool(f) and FLAG_IMPLIED_SPEED_VIOLATION in f for f in flags], dtype=bool)
    tclass = np.asarray(
        [c if c is not None else "" for c in table.column("transceiver_class").to_pylist()],
        dtype=object,
    )

    src_sorted = src[order]
    codes_sorted = codes[order].astype(np.int64)
    prev_src = _to_float(table.column("prev_source_row"))[order]

    if np.unique(src_sorted).size != src_sorted.size:
        raise ValueError("source_row values must be unique")
    position = {int(s): i for i, s in enumerate(src_sorted)}
    prev_idx = np.full(src_sorted.size, -1, dtype=np.int64)
    for i in np.flatnonzero(np.isfinite(prev_src)):
        j = position.get(int(prev_src[i]))
        if j is None:
            raise ValueError(f"prev_source_row {int(prev_src[i])} not found in dataset")
        if codes_sorted[j] != codes_sorted[i]:
            raise ValueError("prev_source_row points to a different vessel")
        prev_idx[i] = j

    return Observations(
        mmsi=uniq[codes_sorted],
        vessel_code=codes_sorted,
        timestamp_us=ts[order],
        source_row=src_sorted,
        latitude=_to_float(table.column("latitude"))[order],
        longitude=_to_float(table.column("longitude"))[order],
        sog=_to_float(table.column("sog"))[order],
        cog=_to_float(table.column("cog"))[order],
        heading=_to_float(table.column("heading"))[order],
        transceiver_class=tclass[order],
        elapsed_s=_to_float(table.column("elapsed_seconds"))[order],
        distance_nm=_to_float(table.column("distance_nm"))[order],
        implied_speed_kt=_to_float(table.column("implied_speed_knots"))[order],
        is_conflict=conflict[order],
        has_implied_speed_violation=isv[order],
        prev_idx=prev_idx,
    )


# --------------------------------------------------------------------------- pair features
def _motion_state_of(sog: FloatArray) -> NDArray[np.object_]:
    state = np.full(sog.size, "", dtype=object)
    state[np.isfinite(sog) & (sog >= MOVING_SOG_KT)] = MOTION_MOVING
    state[np.isfinite(sog) & (sog < MOVING_SOG_KT)] = MOTION_STATIONARY
    return state


def fit_expected_intervals(
    obs: Observations, train_mmsis: Iterable[str]
) -> dict[tuple[str, str], float]:
    """F10 medians per (transceiver class, motion state of ``p_j``), from training vessels only."""
    train = set(train_mmsis)
    has_pair = obs.prev_idx >= 0
    in_train = np.asarray([m in train for m in obs.mmsi], dtype=bool)
    sel = np.flatnonzero(has_pair & in_train & np.isfinite(obs.elapsed_s) & (obs.elapsed_s > 0))
    j = obs.prev_idx[sel]
    cls = obs.transceiver_class[j]
    state = _motion_state_of(obs.sog[j])
    out: dict[tuple[str, str], float] = {}
    for key in sorted({(str(c), str(s)) for c, s in zip(cls, state, strict=True)}):
        if not key[0] or not key[1]:
            continue
        mask = (cls == key[0]) & (state == key[1])
        out[key] = float(np.median(obs.elapsed_s[sel][mask]))
    return out


def compute_pair_features(
    obs: Observations,
    outages: Iterable[tuple[float, float]],
    expected_intervals: ExpectedIntervals | None = None,
) -> dict[str, FloatArray]:
    """Compute F1-F13 for every observation (aligned with ``obs``)."""
    n = obs.size
    nan = np.full(n, np.nan)
    has_pair = obs.prev_idx >= 0
    j = np.where(has_pair, obs.prev_idx, 0)

    def from_prev(values: FloatArray) -> FloatArray:
        return np.where(has_pair, values[j], np.nan)

    dt = np.where(has_pair, obs.elapsed_s, np.nan)
    sog_i, sog_j = obs.sog, from_prev(obs.sog)
    cog_i, cog_j = obs.cog, from_prev(obs.cog)
    rate_ok = np.isfinite(dt) & (dt > 0) & (dt <= MAX_RATE_DT_S)  # G2, G5

    delta_sog = sog_i - sog_j  # NaN propagates when either SOG is null
    with np.errstate(divide="ignore", invalid="ignore"):
        accel = np.where(rate_ok, delta_sog * KNOT_TO_MS / dt, np.nan)

    implied = np.where(has_pair & np.isfinite(dt) & (dt > 0), obs.implied_speed_kt, np.nan)
    disparity = np.where(
        np.isfinite(dt) & (dt >= MIN_DISPARITY_DT_S),
        np.abs(implied - 0.5 * (sog_i + sog_j)),
        np.nan,
    )

    rot_ok = rate_ok & (sog_i >= MOVING_SOG_KT) & (sog_j >= MOVING_SOG_KT)  # NaN SOG -> False
    signed_dcog = np.where(rot_ok, sangdiff(cog_i, cog_j), np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        rot = signed_dcog / dt
    abs_dcog = np.where(rot_ok, angdiff(cog_i, cog_j), np.nan)

    drift_ok = np.isfinite(obs.cog) & np.isfinite(obs.heading) & (obs.sog >= MOVING_SOG_KT)
    disparity_ch = np.where(drift_ok, angdiff(obs.cog, obs.heading), np.nan)
    lateral = np.where(drift_ok & (disparity_ch <= REVERSAL_THRESHOLD_DEG), disparity_ch, np.nan)
    reversal = np.where(drift_ok, (disparity_ch > REVERSAL_THRESHOLD_DEG).astype(float), np.nan)

    gap_ratio = nan.copy()
    if expected_intervals:
        cls_j = np.where(has_pair, obs.transceiver_class[j], "")
        state_j = np.where(has_pair, _motion_state_of(obs.sog)[j], "")
        for (cls, state), median in expected_intervals.items():
            if median > 0:
                mask = has_pair & (cls_j == cls) & (state_j == state)
                gap_ratio[mask] = dt[mask] / median

    t_i = obs.timestamp_s
    t_j = from_prev(t_i)
    overlap = np.where(has_pair, outage_overlap_s(t_j, t_i, outages), np.nan)
    unexplained = np.where(has_pair, np.maximum(0.0, dt - overlap), np.nan)

    dr_ok = has_pair & np.isfinite(sog_j) & np.isfinite(cog_j) & np.isfinite(dt)
    travelled_nm = np.where(dr_ok, sog_j * dt / SECONDS_PER_HOUR, np.nan)
    dr_lat, dr_lon = destination_point(
        np.where(dr_ok, from_prev(obs.latitude), 0.0),
        np.where(dr_ok, from_prev(obs.longitude), 0.0),
        np.where(dr_ok, cog_j, 0.0),
        np.where(dr_ok, travelled_nm * METERS_PER_NAUTICAL_MILE, 0.0),
    )
    dr_err_nm = np.where(
        dr_ok,
        haversine_m(dr_lat, dr_lon, obs.latitude, obs.longitude) / METERS_PER_NAUTICAL_MILE,
        np.nan,
    )
    dr_ratio = dr_err_nm / np.maximum(travelled_nm, MIN_NET_DISPLACEMENT_NM)

    return {
        "dt_s": dt,
        "delta_sog_kt": delta_sog,
        "abs_delta_sog_kt": np.abs(delta_sog),
        "accel_ms2": accel,
        "speed_disparity_kt": disparity,
        "implied_speed_kt": implied,
        "rot_deg_s": rot,
        "abs_rot_deg_s": np.abs(rot),
        "abs_delta_cog_deg": abs_dcog,
        "lateral_drift_deg": lateral,
        "course_heading_reversal": reversal,
        "gap_s": dt.copy(),
        "gap_ratio": gap_ratio,
        "outage_overlap_s": overlap,
        "unexplained_gap_s": unexplained,
        "dr_error_nm": dr_err_nm,
        "dr_error_ratio": dr_ratio,
    }


# --------------------------------------------------------------------------- segments & windows
def assign_segments(obs: Observations, segment_gap_s: float = SEGMENT_GAP_S) -> IntArray:
    """Global segment id per observation (G4); conflict rows get -1."""
    seg = np.full(obs.size, -1, dtype=np.int64)
    valid = np.flatnonzero(~obs.is_conflict)
    if valid.size == 0:
        return seg
    codes = obs.vessel_code[valid]
    new_vessel = np.ones(valid.size, dtype=bool)
    new_vessel[1:] = codes[1:] != codes[:-1]
    gap = obs.elapsed_s[valid]
    brk = new_vessel | (np.isfinite(gap) & (gap > segment_gap_s))
    seg[valid] = np.cumsum(brk) - 1
    return seg


def window_starts(t0: float, t_last: float) -> FloatArray:
    """Window start times for one segment (see module docstring)."""
    span = t_last - t0
    if span < WINDOW_LENGTH_S:
        return np.asarray([t0], dtype=np.float64)
    k_max = math.floor((span - WINDOW_LENGTH_S) / WINDOW_STEP_S) + 1
    return t0 + WINDOW_STEP_S * np.arange(k_max + 1, dtype=np.float64)


def _nanmax(x: FloatArray) -> float:
    x = x[np.isfinite(x)]
    return float(x.max()) if x.size else math.nan


def _nanmean(x: FloatArray) -> float:
    x = x[np.isfinite(x)]
    return float(x.mean()) if x.size else math.nan


def build_windows(
    obs: Observations, pairs: Mapping[str, FloatArray], segments: IntArray
) -> pa.Table:
    """Window aggregates W1-W13 for every segment-bounded 30-min / 10-min-step window."""
    ts = obs.timestamp_s
    rows: dict[str, list[object]] = {
        k: []
        for k in (
            "mmsi",
            "segment_id",
            "window_start_us",
            "window_end_us",
            "n_obs",
            "n_pairs",
            "motion_state",
            "n_implied_speed_violation",
            "n_conflict_rows",
            "source_rows",
            *WINDOW_FEATURE_COLUMNS,
        )
    }

    conflict_times: dict[int, FloatArray] = {}
    for code in np.unique(obs.vessel_code[obs.is_conflict]):
        conflict_times[int(code)] = np.sort(ts[obs.is_conflict & (obs.vessel_code == code)])

    valid = segments >= 0
    seg_ids, seg_first = np.unique(segments[valid], return_index=True)
    valid_idx = np.flatnonzero(valid)
    bounds = list(seg_first) + [valid_idx.size]
    for s_pos, seg_id in enumerate(seg_ids):
        idx = valid_idx[bounds[s_pos] : bounds[s_pos + 1]]
        t = ts[idx]
        code = int(obs.vessel_code[idx[0]])
        c_times = conflict_times.get(code, np.empty(0))
        for start in window_starts(float(t[0]), float(t[-1])):
            end = start + WINDOW_LENGTH_S
            lo = int(np.searchsorted(t, start, side="left"))
            hi = int(np.searchsorted(t, end, side="left"))
            w = idx[lo:hi]
            n_pairs = int((obs.prev_idx[w] >= 0).sum())
            if n_pairs < MIN_WINDOW_PAIRS:
                continue
            _append_window(rows, obs, pairs, w, int(seg_id), start, end, n_pairs, c_times)

    return pa.table(
        {
            "mmsi": pa.array(rows["mmsi"], type=pa.string()),
            "segment_id": pa.array(rows["segment_id"], type=pa.int64()),
            "window_start_utc": pa.array(
                rows["window_start_us"], type=pa.timestamp("us", tz="UTC")
            ),
            "window_end_utc": pa.array(rows["window_end_us"], type=pa.timestamp("us", tz="UTC")),
            "n_obs": pa.array(rows["n_obs"], type=pa.int64()),
            "n_pairs": pa.array(rows["n_pairs"], type=pa.int64()),
            "motion_state": pa.array(rows["motion_state"], type=pa.string()),
            "n_implied_speed_violation": pa.array(
                rows["n_implied_speed_violation"], type=pa.int64()
            ),
            "n_conflict_rows": pa.array(rows["n_conflict_rows"], type=pa.int64()),
            "source_rows": pa.array(rows["source_rows"], type=pa.list_(pa.int64())),
            **{
                c: pa.array(rows[c], type=pa.float64(), from_pandas=True)
                for c in WINDOW_FEATURE_COLUMNS
            },
        }
    )


def _append_window(
    rows: dict[str, list[object]],
    obs: Observations,
    pairs: Mapping[str, FloatArray],
    w: IntArray,
    seg_id: int,
    start: float,
    end: float,
    n_pairs: int,
    conflict_times: FloatArray,
) -> None:
    sog = obs.sog[w]
    finite_sog = sog[np.isfinite(sog)]
    median_sog = float(np.median(finite_sog)) if finite_sog.size else math.nan
    if not finite_sog.size:
        state = MOTION_UNKNOWN
    elif median_sog >= MOVING_SOG_KT:
        state = MOTION_MOVING
    else:
        state = MOTION_STATIONARY
    moving = state == MOTION_MOVING

    drift = pairs["lateral_drift_deg"][w]
    drift = drift[np.isfinite(drift)]
    first, last = int(w[0]), int(w[-1])
    net_m = float(
        haversine_m(
            obs.latitude[first : first + 1],
            obs.longitude[first : first + 1],
            obs.latitude[last : last + 1],
            obs.longitude[last : last + 1],
        )[0]
    )
    net_nm = net_m / METERS_PER_NAUTICAL_MILE
    path_nm = float(np.nansum(obs.distance_nm[w[1:]])) if w.size > 1 else 0.0

    values: dict[str, float] = {
        "max_abs_delta_sog_kt": _nanmax(pairs["abs_delta_sog_kt"][w]) if moving else math.nan,
        "max_abs_accel_ms2": _nanmax(np.abs(pairs["accel_ms2"][w])) if moving else math.nan,
        "max_speed_disparity_kt": _nanmax(pairs["speed_disparity_kt"][w]) if moving else math.nan,
        "max_abs_rot_deg_s": _nanmax(pairs["abs_rot_deg_s"][w]) if moving else math.nan,
        "p90_lateral_drift_deg": (
            float(np.percentile(drift, 90))
            if moving and drift.size >= MIN_DRIFT_VALUES_FOR_P90
            else math.nan
        ),
        "reversal_share": _nanmean(pairs["course_heading_reversal"][w]) if moving else math.nan,
        "max_gap_ratio": _nanmax(pairs["gap_ratio"][w]),
        "max_unexplained_gap_s": _nanmax(pairs["unexplained_gap_s"][w]),
        "max_dr_error_ratio": _nanmax(pairs["dr_error_ratio"][w]),
        "tortuosity": path_nm / net_nm if net_nm >= MIN_NET_DISPLACEMENT_NM else math.nan,
        "stationary_net_displacement_m": net_m if state == MOTION_STATIONARY else math.nan,
        "heading_availability": float(np.isfinite(obs.heading[w]).mean()),
        "cog_availability": float(np.isfinite(obs.cog[w]).mean()),
        "median_sog_kt": median_sog,
    }

    rows["mmsi"].append(str(obs.mmsi[first]))
    rows["segment_id"].append(seg_id)
    rows["window_start_us"].append(int(round(start * 1e6)))
    rows["window_end_us"].append(int(round(end * 1e6)))
    rows["n_obs"].append(int(w.size))
    rows["n_pairs"].append(n_pairs)
    rows["motion_state"].append(state)
    rows["n_implied_speed_violation"].append(int(obs.has_implied_speed_violation[w].sum()))
    rows["n_conflict_rows"].append(
        int(
            np.searchsorted(conflict_times, end, side="left")
            - np.searchsorted(conflict_times, start, side="left")
        )
    )
    rows["source_rows"].append([int(s) for s in obs.source_row[w]])
    for key, value in values.items():
        rows[key].append(value)


# --------------------------------------------------------------------------- orchestration
@dataclass(frozen=True)
class FeatureResult:
    """Pair-level and window-level features for one dataset."""

    observations: Observations
    outages: list[tuple[float, float]]
    pair_features: dict[str, FloatArray]
    segments: IntArray
    windows: pa.Table

    def pair_table(self) -> pa.Table:
        """Pair features as an Arrow table keyed by MMSI, source row and timestamp."""
        obs = self.observations
        return pa.table(
            {
                "mmsi": pa.array(obs.mmsi.tolist(), type=pa.string()),
                "source_row": pa.array(obs.source_row, type=pa.int64()),
                "timestamp_utc": pa.array(obs.timestamp_us, type=pa.timestamp("us", tz="UTC")),
                "segment_id": pa.array(self.segments, type=pa.int64()),
                "is_conflict": pa.array(obs.is_conflict, type=pa.bool_()),
                **{
                    c: pa.array(self.pair_features[c], type=pa.float64(), from_pandas=True)
                    for c in PAIR_FEATURE_COLUMNS
                },
            }
        )


def extract_features(
    table: pa.Table,
    expected_intervals: ExpectedIntervals | None = None,
    outages: Iterable[tuple[float, float]] | None = None,
) -> FeatureResult:
    """Run the full ML-02 extraction on one canonical dataset.

    ``outages`` defaults to the feed-wide silences detected on ``table`` itself (ML-02 section 6).
    ``expected_intervals`` (F10) must come from :func:`fit_expected_intervals` on the training
    partition; when omitted, ``gap_ratio`` is null.
    """
    obs = prepare_observations(table)
    outage_list = list(outages) if outages is not None else detect_outage_windows(obs.timestamp_s)
    pairs = compute_pair_features(obs, outage_list, expected_intervals)
    segments = assign_segments(obs)
    windows = build_windows(obs, pairs, segments)
    return FeatureResult(obs, outage_list, pairs, segments, windows)
