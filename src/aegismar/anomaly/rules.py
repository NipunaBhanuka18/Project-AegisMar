"""R1: explainable, ECDF-calibrated rule-based window scorer (ML-03 v1.1 section 5.2).

For every factor feature, the factor score is its empirical CDF on clean DEV-train windows of the
same motion state, ``s(x) = F_train(x)`` in [0, 1]. A factor group's score is the maximum of its
member feature scores; the composite score ``S`` is the maximum over groups and ``primary_factor``
is the arg-max group. Null features are skipped; a window with no non-null factor feature is not
scored (``S`` is NaN). The R1-lin variant is the equal-weight mean of the available group scores.

Implementation choices where ML-03 v1.1 leaves a detail open:

* ECDF convention: ``F(x) = #{train values <= x} / n`` (right-continuous), so a value equal to the
  training maximum scores 1.0 and a value below every training value scores 0.0.
* Calibration is per motion state (``moving``, ``stationary``, ``unknown``); a feature with no
  finite training value in a state yields a null factor score in that state.
* Ties in the arg-max are broken by the order of :data:`FACTOR_GROUPS` (ML-03 section 4.3 order).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pyarrow as pa
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

# ML-03 section 4.3: factor groups and their window features (ML-02 section 8.1).
FACTOR_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("SPEED_DISCONTINUITY", ("max_abs_delta_sog_kt", "max_abs_accel_ms2")),
    ("SPEED_POSITION_INCONSISTENCY", ("max_speed_disparity_kt", "max_dr_error_ratio")),
    ("COURSE_CHANGE", ("max_abs_rot_deg_s",)),
    ("LATERAL_DRIFT", ("p90_lateral_drift_deg",)),
    ("HEADING_REVERSAL", ("reversal_share",)),
    ("REPORTING_GAP", ("max_gap_ratio", "max_unexplained_gap_s")),
    ("TRAJECTORY_SHAPE", ("tortuosity",)),
    ("STATIONARY_DISPLACEMENT", ("stationary_net_displacement_m",)),
)
FACTOR_NAMES: tuple[str, ...] = tuple(name for name, _ in FACTOR_GROUPS)
FACTOR_FEATURES: tuple[str, ...] = tuple(c for _, cols in FACTOR_GROUPS for c in cols)


def _column(windows: pa.Table, name: str) -> FloatArray:
    return np.asarray(
        [math.nan if v is None else float(v) for v in windows.column(name).to_pylist()],
        dtype=np.float64,
    )


def _states(windows: pa.Table) -> NDArray[np.object_]:
    return np.asarray(windows.column("motion_state").to_pylist(), dtype=object)


def ecdf(train_sorted: FloatArray, x: FloatArray) -> FloatArray:
    """Right-continuous empirical CDF of ``train_sorted`` evaluated at ``x``; NaN stays NaN."""
    if train_sorted.size == 0:
        return np.full(x.shape, np.nan)
    ranks = np.searchsorted(train_sorted, np.nan_to_num(x, nan=0.0), side="right")
    out = ranks.astype(np.float64) / float(train_sorted.size)
    out[~np.isfinite(x)] = np.nan
    return out


@dataclass(frozen=True)
class RuleScores:
    """R1 output, aligned with the scored window table."""

    composite: FloatArray  # S = max over factor groups (NaN = not scored)
    linear: FloatArray  # R1-lin = mean over available factor groups
    primary_factor: tuple[str | None, ...]
    group_scores: dict[str, FloatArray]


class RuleScorer:
    """ECDF-calibrated max-composite rule scorer (R1)."""

    def __init__(self) -> None:
        self._tables: dict[str, dict[str, FloatArray]] = {}

    @property
    def is_fitted(self) -> bool:
        return bool(self._tables)

    def fit(self, train_windows: pa.Table) -> RuleScorer:
        """Calibrate on **clean DEV-train** windows only (ML-03 section 3.3)."""
        if train_windows.num_rows == 0:
            raise ValueError("cannot calibrate R1 on an empty window table")
        states = _states(train_windows)
        tables: dict[str, dict[str, FloatArray]] = {}
        for state in sorted(set(states.tolist())):
            mask = states == state
            tables[str(state)] = {}
            for feat in FACTOR_FEATURES:
                values = _column(train_windows, feat)[mask]
                tables[str(state)][feat] = np.sort(values[np.isfinite(values)])
        self._tables = tables
        return self

    def calibration_sizes(self) -> dict[str, dict[str, int]]:
        """Number of training values behind every ECDF (for the experiment record)."""
        return {s: {f: int(v.size) for f, v in t.items()} for s, t in self._tables.items()}

    def feature_scores(self, windows: pa.Table) -> dict[str, FloatArray]:
        """Per-feature ECDF scores for ``windows``, using each window's own motion state."""
        if not self.is_fitted:
            raise RuntimeError("RuleScorer.fit must be called first")
        states = _states(windows)
        out: dict[str, FloatArray] = {}
        for feat in FACTOR_FEATURES:
            x = _column(windows, feat)
            s = np.full(x.shape, np.nan)
            for state, table in self._tables.items():
                mask = states == state
                if mask.any():
                    s[mask] = ecdf(table[feat], x[mask])
            out[feat] = s
        return out

    def score(self, windows: pa.Table) -> RuleScores:
        feats = self.feature_scores(windows)
        n = windows.num_rows
        groups: dict[str, FloatArray] = {}
        for name, cols in FACTOR_GROUPS:
            stacked = np.vstack([feats[c] for c in cols])
            has = np.isfinite(stacked).any(axis=0)
            g = np.full(n, np.nan)
            g[has] = np.nanmax(stacked[:, has], axis=0)
            groups[name] = g
        matrix = np.vstack([groups[name] for name in FACTOR_NAMES])  # (n_groups, n)
        scored = np.isfinite(matrix).any(axis=0)
        composite = np.full(n, np.nan)
        linear = np.full(n, np.nan)
        primary: list[str | None] = [None] * n
        if scored.any():
            sub = matrix[:, scored]
            composite[scored] = np.nanmax(sub, axis=0)
            linear[scored] = np.nanmean(sub, axis=0)
            filled = np.where(np.isfinite(sub), sub, -np.inf)
            best = np.argmax(filled, axis=0)  # first maximum -> FACTOR_GROUPS order
            for j, w in enumerate(np.flatnonzero(scored)):
                primary[int(w)] = FACTOR_NAMES[int(best[j])]
        return RuleScores(composite, linear, tuple(primary), groups)


def primary_factor_from_groups(group_scores: Mapping[str, FloatArray]) -> tuple[str | None, ...]:
    """Arg-max factor group per window (used for post-hoc attribution of M1/M2)."""
    matrix = np.vstack([group_scores[name] for name in FACTOR_NAMES])
    out: list[str | None] = []
    for j in range(matrix.shape[1]):
        col = matrix[:, j]
        out.append(FACTOR_NAMES[int(np.nanargmax(col))] if np.isfinite(col).any() else None)
    return tuple(out)
