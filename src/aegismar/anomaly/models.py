"""M1 Isolation Forest, M2 LOF and the B0 density-noise baseline (ML-03 v1.1 sections 5.1-5.4).

M1/M2 score **moving** windows only. Inputs are the window features W2-W10 plus missing-value
indicators for W6 (``p90_lateral_drift_deg``) and W7 (``reversal_share``). Median imputation and
``RobustScaler`` are fitted on clean DEV-train moving windows only. The raw anomaly score
``-score_samples(x)`` is mapped to [0, 1] through its ECDF on the training reference, giving a
non-probabilistic anomaly index. Attribution is post-hoc: the R1 arg-max factor group.

Implementation choices where ML-03 v1.1 leaves a detail open:

* M1's ECDF reference is ``-score_samples`` on the training windows. For M2 (``novelty=True``),
  scikit-learn's ``score_samples`` must not be applied to the training data itself, so the
  reference is the training LOF score ``-negative_outlier_factor_``.
* B0's window score is the fraction of the window's clustering-analysed observations labelled
  noise (-1). Observations excluded by the clustering quality filter are not counted; a window
  with none is not scored.
* B0 depends only on clustering inputs (positions, timestamps, conflict flags). When those are
  identical for two tables, the clean clustering result may be reused
  (:func:`clustering_inputs_equal` checks this exactly).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pyarrow as pa
from numpy.typing import NDArray
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import RobustScaler

from aegismar.anomaly.features import MOTION_MOVING
from aegismar.anomaly.rules import ecdf
from aegismar.clustering.config import STDBSCANConfig
from aegismar.clustering.st_dbscan import run_balltree_st_dbscan
from aegismar.clustering.types import (
    NOISE_CLUSTER_ID,
    ClusteringInputDataset,
    ObservationRecord,
    build_clustering_dataset,
)

FloatArray = NDArray[np.float64]

MODEL_FEATURES: tuple[str, ...] = (  # W2-W10
    "max_abs_delta_sog_kt",
    "max_abs_accel_ms2",
    "max_speed_disparity_kt",
    "max_abs_rot_deg_s",
    "p90_lateral_drift_deg",
    "reversal_share",
    "max_gap_ratio",
    "max_unexplained_gap_s",
    "max_dr_error_ratio",
    "tortuosity",
)
MISSING_INDICATOR_FEATURES: tuple[str, ...] = ("p90_lateral_drift_deg", "reversal_share")
MODEL_RANDOM_STATE: int = 42
IF_N_ESTIMATORS: int = 300
LOF_N_NEIGHBORS: int = 35

B0_EPS_TEMPORAL_S: float = 900.0
B0_GRID: tuple[tuple[float, int], ...] = tuple(
    (eps, mp) for eps in (150.0, 300.0, 600.0) for mp in (3, 5, 10)
)  # (eps_spatial_m, min_samples), ML-03 section 5.1


# --------------------------------------------------------------------------- M1 / M2
def design_matrix(windows: pa.Table) -> tuple[FloatArray, NDArray[np.bool_]]:
    """Raw model inputs (NaN = missing) and the moving-window mask."""
    cols = [
        np.asarray(
            [math.nan if v is None else float(v) for v in windows.column(c).to_pylist()],
            dtype=np.float64,
        )
        for c in MODEL_FEATURES
    ]
    x = np.column_stack(cols) if cols else np.empty((windows.num_rows, 0))
    moving = np.asarray(
        [s == MOTION_MOVING for s in windows.column("motion_state").to_pylist()], dtype=bool
    )
    return x, moving


def _with_indicators(x: FloatArray) -> FloatArray:
    idx = [MODEL_FEATURES.index(c) for c in MISSING_INDICATOR_FEATURES]
    indicators = (~np.isfinite(x[:, idx])).astype(np.float64)
    return np.hstack([x, indicators])


@dataclass
class WindowModel:
    """M1 (``isolation_forest``) or M2 (``lof``) anomaly index for moving windows."""

    kind: str
    imputer: Any = None
    scaler: Any = None
    estimator: Any = None
    reference: FloatArray | None = None  # sorted training raw scores for the ECDF

    def __post_init__(self) -> None:
        if self.kind not in ("isolation_forest", "lof"):
            raise ValueError(f"unknown model kind {self.kind!r}")

    def _transform(self, x: FloatArray) -> FloatArray:
        out = self.scaler.transform(self.imputer.transform(_with_indicators(x)))
        return np.asarray(out, dtype=np.float64)

    def fit(self, train_windows: pa.Table) -> WindowModel:
        """Fit on clean DEV-train **moving** windows only (ML-03 sections 3.3 and 5.3)."""
        x, moving = design_matrix(train_windows)
        x = x[moving]
        if x.shape[0] < LOF_N_NEIGHBORS + 1:
            raise ValueError(f"need more than {LOF_N_NEIGHBORS} moving training windows")
        self.imputer = SimpleImputer(strategy="median", keep_empty_features=True)
        self.scaler = RobustScaler()
        z = np.asarray(
            self.scaler.fit_transform(self.imputer.fit_transform(_with_indicators(x))),
            dtype=np.float64,
        )
        if self.kind == "isolation_forest":
            self.estimator = IsolationForest(
                n_estimators=IF_N_ESTIMATORS,
                max_samples="auto",
                max_features=1.0,
                random_state=MODEL_RANDOM_STATE,
            ).fit(z)
            raw = -np.asarray(self.estimator.score_samples(z), dtype=np.float64)
        else:
            self.estimator = LocalOutlierFactor(n_neighbors=LOF_N_NEIGHBORS, novelty=True).fit(z)
            raw = -np.asarray(self.estimator.negative_outlier_factor_, dtype=np.float64)
        self.reference = np.sort(raw)
        return self

    def raw_scores(self, windows: pa.Table) -> FloatArray:
        """``-score_samples`` for moving windows; NaN for all other windows."""
        if self.estimator is None:
            raise RuntimeError("WindowModel.fit must be called first")
        x, moving = design_matrix(windows)
        out = np.full(windows.num_rows, np.nan)
        if moving.any():
            z = self._transform(x[moving])
            out[moving] = -np.asarray(self.estimator.score_samples(z), dtype=np.float64)
        return out

    def score(self, windows: pa.Table) -> FloatArray:
        """Non-probabilistic anomaly index in [0, 1] (training-reference ECDF)."""
        assert self.reference is not None
        return ecdf(self.reference, self.raw_scores(windows))


# --------------------------------------------------------------------------- B0
def clustering_records(table: pa.Table) -> list[ObservationRecord]:
    cols = table.select(
        ["source_row", "mmsi", "timestamp_utc", "latitude", "longitude", "quality_flags"]
    ).to_pylist()
    return [
        ObservationRecord(
            source_row=int(r["source_row"]),
            mmsi=str(r["mmsi"]),
            timestamp_utc=_as_datetime(r["timestamp_utc"]),
            latitude=float(r["latitude"]),
            longitude=float(r["longitude"]),
            quality_flags=tuple(r["quality_flags"] or ()),
        )
        for r in cols
    ]


def _as_datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"timestamp_utc must be a datetime, got {type(value).__name__}")
    return value


def clustering_inputs_equal(a: ClusteringInputDataset, b: ClusteringInputDataset) -> bool:
    """Exact equality of everything ST-DBSCAN reads (row ids, vessels, times, positions)."""
    return (
        a.mmsis == b.mmsis
        and np.array_equal(a.source_rows, b.source_rows)
        and np.array_equal(a.timestamps_us, b.timestamps_us)
        and np.array_equal(a.latitudes_deg.view(np.int64), b.latitudes_deg.view(np.int64))
        and np.array_equal(a.longitudes_deg.view(np.int64), b.longitudes_deg.view(np.int64))
    )


@dataclass(frozen=True)
class NoiseLabels:
    """Per-source-row ST-DBSCAN noise flags for one dataset and one B0 grid point."""

    eps_spatial_m: float
    min_samples: int
    noise_rows: frozenset[int]
    analyzed_rows: frozenset[int]


def run_noise_baseline(
    dataset: ClusteringInputDataset, eps_spatial_m: float, min_samples: int
) -> NoiseLabels:
    """Run BallTree ST-DBSCAN (ML-03 B0) and return which analysed rows are noise."""
    config = STDBSCANConfig(
        eps_spatial_m=eps_spatial_m, eps_temporal_s=B0_EPS_TEMPORAL_S, min_samples=min_samples
    )
    result = run_balltree_st_dbscan(dataset, config)
    rows = dataset.source_rows
    noise = rows[result.labels == NOISE_CLUSTER_ID]
    return NoiseLabels(
        eps_spatial_m,
        min_samples,
        frozenset(int(r) for r in noise),
        frozenset(int(r) for r in rows),
    )


def b0_window_scores(windows: pa.Table, labels: NoiseLabels) -> FloatArray:
    """Fraction of each window's clustering-analysed observations labelled noise."""
    out = np.full(windows.num_rows, np.nan)
    for w, rows in enumerate(windows.column("source_rows").to_pylist()):
        analysed = [r for r in rows if r in labels.analyzed_rows]
        if analysed:
            out[w] = sum(r in labels.noise_rows for r in analysed) / len(analysed)
    return out


def build_dataset(table: pa.Table) -> ClusteringInputDataset:
    """Clustering input with the default quality filter (conflict rows excluded)."""
    return build_clustering_dataset(clustering_records(table))


def noise_labels_for_grid(
    dataset: ClusteringInputDataset, grid: Iterable[tuple[float, int]] = B0_GRID
) -> list[NoiseLabels]:
    return [run_noise_baseline(dataset, eps, mp) for eps, mp in grid]


def grid_points(grid: Sequence[tuple[float, int]] = B0_GRID) -> list[str]:
    return [f"eps{eps:g}m_minpts{mp}" for eps, mp in grid]
