"""Core data structures, input loaders, and provider protocol for ST-DBSCAN clustering."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray

from aegismar.clustering.config import QualityFilterPolicy, STDBSCANConfig

# Point role classifications
POINT_ROLE_CORE: str = "core"
POINT_ROLE_BORDER: str = "border"
POINT_ROLE_NOISE: str = "noise"
NOISE_CLUSTER_ID: int = -1

_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=UTC)


def datetime_to_epoch_us(dt: datetime) -> int:
    """Convert a datetime to exact integer Unix epoch microseconds (UTC)."""
    utc_dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    delta = utc_dt - _EPOCH_UTC
    return (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds


def epoch_us_to_datetime(epoch_us: int) -> datetime:
    """Convert integer Unix epoch microseconds back into a UTC-aware datetime."""
    seconds, micros = divmod(int(epoch_us), 1_000_000)
    return datetime.fromtimestamp(seconds, tz=UTC).replace(microsecond=micros)


@dataclass(frozen=True, slots=True)
class ObservationRecord:
    """Lightweight canonical observation record for programmatic/synthetic clustering inputs."""

    source_row: int
    mmsi: str
    timestamp_utc: datetime
    latitude: float
    longitude: float
    quality_flags: tuple[str, ...] = ()


@dataclass(slots=True)
class ClusteringInputDataset:
    """Deterministically sorted, quality-filtered observations ready for ST-DBSCAN.

    All parallel arrays share the same canonical total ordering:
    ``(timestamp_us, mmsi, latitude_deg, longitude_deg, source_row)``.
    This total order guarantees input-row permutation invariance across runs.
    """

    source_rows: NDArray[np.int64]
    mmsis: tuple[str, ...]
    timestamps_us: NDArray[np.int64]
    latitudes_deg: NDArray[np.float64]
    longitudes_deg: NDArray[np.float64]
    total_input_count: int
    excluded_count: int
    excluded_breakdown: dict[str, int]

    @property
    def num_points(self) -> int:
        """Number of eligible observations analyzed by clustering."""
        return int(self.source_rows.shape[0])

    @property
    def timestamps_s(self) -> NDArray[np.float64]:
        """UTC epoch timestamps in floating-point seconds."""
        return self.timestamps_us.astype(np.float64) / 1_000_000.0


@dataclass(slots=True)
class NeighborhoodGraph:
    """Compact CSR representation of eligible spatiotemporal neighborhoods.

    For observation ``i``, its sorted eligible neighbor indices (always including ``i``)
    are given by ``indices[indptr[i] : indptr[i + 1]]``.
    """

    indptr: NDArray[np.int64]
    indices: NDArray[np.int64]

    @property
    def num_points(self) -> int:
        """Number of observations represented in the graph."""
        return max(0, int(self.indptr.shape[0]) - 1)

    @property
    def total_edges(self) -> int:
        """Total directed neighborhood entries across all observations."""
        return int(self.indices.shape[0])

    def degree(self, index: int) -> int:
        """Return neighborhood cardinality (including self) for observation ``index``."""
        return int(self.indptr[index + 1] - self.indptr[index])

    def neighbors_of(self, index: int) -> NDArray[np.int64]:
        """Return sorted 1D int64 view of eligible neighbor indices for ``index``."""
        start = int(self.indptr[index])
        end = int(self.indptr[index + 1])
        return self.indices[start:end]


class NeighborhoodProvider(Protocol):
    """Injectable neighborhood lookup interface shared by BallTree, H3, and Oracle."""

    @property
    def provider_name(self) -> str:
        """Human-readable identifier for this neighborhood provider."""
        ...

    @property
    def num_points(self) -> int:
        """Number of indexed observations."""
        ...

    @property
    def build_time_seconds(self) -> float:
        """Wall-clock seconds spent constructing the spatial index."""
        ...

    def query_neighbors(self, index: int) -> NDArray[np.int64]:
        """Return sorted 1D int64 array of eligible neighbor indices (including ``index``)."""
        ...

    def build_neighborhood_graph(self) -> NeighborhoodGraph:
        """Compute complete eligible neighborhoods in compact CSR form without an NxN matrix."""
        ...


@dataclass(slots=True)
class STDBSCANResult:
    """Complete deterministic output and accounting summary of an ST-DBSCAN run."""

    dataset: ClusteringInputDataset
    config: STDBSCANConfig
    provider_name: str
    labels: NDArray[np.int64]
    roles: tuple[str, ...]
    num_clusters: int
    core_count: int
    border_count: int
    noise_count: int
    cluster_member_counts: dict[int, int]
    build_time_seconds: float
    query_time_seconds: float
    clustering_time_seconds: float
    total_time_seconds: float
    peak_tracemalloc_bytes: int

    def summary_dict(self) -> dict[str, Any]:
        """Return JSON-serializable summary of clustering configuration, counts, and timings."""
        return {
            "provider_name": self.provider_name,
            "config": self.config.to_dict(),
            "input_summary": {
                "total_input_count": self.dataset.total_input_count,
                "analyzed_count": self.dataset.num_points,
                "excluded_count": self.dataset.excluded_count,
                "excluded_breakdown": self.dataset.excluded_breakdown,
            },
            "clustering_summary": {
                "num_clusters": self.num_clusters,
                "core_count": self.core_count,
                "border_count": self.border_count,
                "noise_count": self.noise_count,
                "accounting_check_passed": (
                    self.core_count + self.border_count + self.noise_count
                    == self.dataset.num_points
                ),
                "largest_clusters": dict(
                    sorted(self.cluster_member_counts.items(), key=lambda x: (-x[1], x[0]))[:20]
                ),
            },
            "performance": {
                "build_time_seconds": round(self.build_time_seconds, 6),
                "query_time_seconds": round(self.query_time_seconds, 6),
                "clustering_time_seconds": round(self.clustering_time_seconds, 6),
                "total_time_seconds": round(self.total_time_seconds, 6),
                "peak_tracemalloc_mb": round(self.peak_tracemalloc_bytes / (1024 * 1024), 3),
            },
        }


def _sort_and_pack_dataset(
    source_rows: list[int],
    mmsis: list[str],
    timestamps_us: list[int],
    latitudes: list[float],
    longitudes: list[float],
    total_input_count: int,
    excluded_count: int,
    excluded_breakdown: dict[str, int],
) -> ClusteringInputDataset:
    """Sort observations into canonical total order and pack into typed NumPy arrays."""
    n = len(source_rows)
    if n == 0:
        return ClusteringInputDataset(
            source_rows=np.empty(0, dtype=np.int64),
            mmsis=(),
            timestamps_us=np.empty(0, dtype=np.int64),
            latitudes_deg=np.empty(0, dtype=np.float64),
            longitudes_deg=np.empty(0, dtype=np.float64),
            total_input_count=total_input_count,
            excluded_count=excluded_count,
            excluded_breakdown=excluded_breakdown,
        )

    order = sorted(
        range(n),
        key=lambda i: (
            timestamps_us[i],
            mmsis[i],
            latitudes[i],
            longitudes[i],
            source_rows[i],
        ),
    )

    return ClusteringInputDataset(
        source_rows=np.array([source_rows[i] for i in order], dtype=np.int64),
        mmsis=tuple(mmsis[i] for i in order),
        timestamps_us=np.array([timestamps_us[i] for i in order], dtype=np.int64),
        latitudes_deg=np.array([latitudes[i] for i in order], dtype=np.float64),
        longitudes_deg=np.array([longitudes[i] for i in order], dtype=np.float64),
        total_input_count=total_input_count,
        excluded_count=excluded_count,
        excluded_breakdown=excluded_breakdown,
    )


def build_clustering_dataset(
    records: Sequence[ObservationRecord],
    quality_filter: QualityFilterPolicy | None = None,
) -> ClusteringInputDataset:
    """Apply quality filtering and deterministic sorting to programmatic observation records."""
    policy = quality_filter if quality_filter is not None else QualityFilterPolicy()
    excluded_flags = policy.effective_excluded_flags()

    source_rows: list[int] = []
    mmsis: list[str] = []
    timestamps_us: list[int] = []
    latitudes: list[float] = []
    longitudes: list[float] = []
    excluded_count = 0
    excluded_counter: Counter[str] = Counter()

    for rec in records:
        matched_flags = [f for f in rec.quality_flags if f in excluded_flags]
        if matched_flags:
            excluded_count += 1
            for flag in matched_flags:
                excluded_counter[flag] += 1
            continue

        source_rows.append(int(rec.source_row))
        mmsis.append(rec.mmsi)
        timestamps_us.append(datetime_to_epoch_us(rec.timestamp_utc))
        latitudes.append(float(rec.latitude))
        longitudes.append(float(rec.longitude))

    return _sort_and_pack_dataset(
        source_rows=source_rows,
        mmsis=mmsis,
        timestamps_us=timestamps_us,
        latitudes=latitudes,
        longitudes=longitudes,
        total_input_count=len(records),
        excluded_count=excluded_count,
        excluded_breakdown=dict(excluded_counter),
    )


def load_clustering_dataset_from_parquet(
    parquet_path: Path | str,
    quality_filter: QualityFilterPolicy | None = None,
    max_rows: int | None = None,
) -> ClusteringInputDataset:
    """Load canonical AIS observations from Parquet with quality filtering and stable sorting.

    Reads only the columns required for ST-DBSCAN clustering
    (``source_row``, ``mmsi``, ``timestamp_utc``, ``latitude``, ``longitude``,
    ``quality_flags``), leaving the Parquet file strictly unchanged on disk.

    Parameters
    ----------
    parquet_path : Path | str
        Path to a canonical cleaned AIS Parquet file.
    quality_filter : QualityFilterPolicy | None
        Deterministic exclusion policy for quality-flagged rows. Defaults to
        ``QualityFilterPolicy()`` (excluding same-timestamp conflicts).
    max_rows : int | None
        Optional deterministic cap applied after quality filtering and canonical
        sorting (takes the first ``max_rows`` in canonical chronological order).
    """
    path = Path(parquet_path)
    if not path.is_file():
        raise FileNotFoundError(f"Canonical AIS Parquet file does not exist: {path}")

    if max_rows is not None and (isinstance(max_rows, bool) or max_rows < 0):
        raise ValueError(f"max_rows must be a non-negative integer or None, got {max_rows!r}")

    policy = quality_filter if quality_filter is not None else QualityFilterPolicy()
    excluded_flags = policy.effective_excluded_flags()

    required_cols = [
        "source_row",
        "mmsi",
        "timestamp_utc",
        "latitude",
        "longitude",
        "quality_flags",
    ]
    table = pq.read_table(str(path), columns=required_cols)
    total_input_count = int(table.num_rows)

    if total_input_count == 0:
        return _sort_and_pack_dataset([], [], [], [], [], 0, 0, {})

    raw_source_rows: list[int] = table.column("source_row").to_pylist()
    raw_mmsis: list[str] = table.column("mmsi").to_pylist()
    # Cast timestamp[us, tz=UTC] directly to int64 microseconds without Python datetime overhead
    ts_us_col = table.column("timestamp_utc").cast(pa.int64())
    raw_timestamps_us: list[int] = ts_us_col.to_pylist()
    raw_lats: list[float] = table.column("latitude").to_pylist()
    raw_lons: list[float] = table.column("longitude").to_pylist()
    raw_flags: list[list[str]] = table.column("quality_flags").to_pylist()

    source_rows: list[int] = []
    mmsis: list[str] = []
    timestamps_us: list[int] = []
    latitudes: list[float] = []
    longitudes: list[float] = []
    excluded_count = 0
    excluded_counter: Counter[str] = Counter()

    for idx in range(total_input_count):
        row_flags = raw_flags[idx] or []
        matched = [f for f in row_flags if f in excluded_flags]
        if matched:
            excluded_count += 1
            for flag in matched:
                excluded_counter[flag] += 1
            continue

        source_rows.append(int(raw_source_rows[idx]))
        mmsis.append(str(raw_mmsis[idx]))
        timestamps_us.append(int(raw_timestamps_us[idx]))
        latitudes.append(float(raw_lats[idx]))
        longitudes.append(float(raw_lons[idx]))

    dataset = _sort_and_pack_dataset(
        source_rows=source_rows,
        mmsis=mmsis,
        timestamps_us=timestamps_us,
        latitudes=latitudes,
        longitudes=longitudes,
        total_input_count=total_input_count,
        excluded_count=excluded_count,
        excluded_breakdown=dict(excluded_counter),
    )

    if max_rows is not None and dataset.num_points > max_rows:
        return ClusteringInputDataset(
            source_rows=dataset.source_rows[:max_rows].copy(),
            mmsis=dataset.mmsis[:max_rows],
            timestamps_us=dataset.timestamps_us[:max_rows].copy(),
            latitudes_deg=dataset.latitudes_deg[:max_rows].copy(),
            longitudes_deg=dataset.longitudes_deg[:max_rows].copy(),
            total_input_count=dataset.total_input_count,
            excluded_count=dataset.excluded_count,
            excluded_breakdown=dataset.excluded_breakdown,
        )

    return dataset
