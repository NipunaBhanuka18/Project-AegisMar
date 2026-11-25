"""Haversine BallTree spatiotemporal neighborhood provider for reference ST-DBSCAN.

Coordinate and unit conventions
-------------------------------
- Input coordinates in ``ClusteringInputDataset`` are WGS 84 decimal degrees:
  ``latitudes_deg`` in ``[-90.0, 90.0]`` and ``longitudes_deg`` in ``[-180.0, 180.0]``.
- ``scikit-learn.neighbors.BallTree`` with ``metric="haversine"`` requires a
  2D float64 matrix of shape ``(N, 2)`` in **radians**, ordered as
  ``[latitude_rad, longitude_rad]``.
- Spatial search radius ``eps_spatial_m`` (meters) is converted to radians via
  ``eps_spatial_rad = eps_spatial_m / EARTH_RADIUS_METERS`` with
  ``EARTH_RADIUS_METERS = 6371008.8``.
- Temporal distances are evaluated exactly in integer UTC microseconds
  ``|t_i_us - t_j_us| <= eps_temporal_s * 1_000_000``.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.neighbors import BallTree

from aegismar.clustering.config import STDBSCANConfig
from aegismar.clustering.types import ClusteringInputDataset, NeighborhoodGraph
from aegismar.spatial.haversine import EARTH_RADIUS_METERS

# Tiny radian guard (~6.4 micrometers) applied ONLY to the BallTree candidate
# pre-query so 1-ULP floating-point rounding never drops a true boundary point
# prior to exact Haversine pruning against `eps_spatial_m`.
BALLTREE_QUERY_GUARD_RAD: float = 1e-12

# Default batch size for chunked BallTree radius queries to bound transient RAM
DEFAULT_QUERY_BATCH_SIZE: int = 2048


def _exact_haversine_to_candidates_m(
    lat_i_deg: float,
    lon_i_deg: float,
    lat_i_rad: float,
    cand_lats_deg: NDArray[np.float64],
    cand_lons_deg: NDArray[np.float64],
    cand_lats_rad: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Compute exact spherical Haversine distances in meters from point i to candidates.

    Computes ``deg2rad(lat2 - lat1)`` and ``deg2rad(lon2 - lon1)`` directly from
    degrees to match scalar ``haversine_distance_meters`` to machine precision.
    """
    dphi = np.deg2rad(cand_lats_deg - lat_i_deg)
    dlambda = np.deg2rad(cand_lons_deg - lon_i_deg)
    sin_half_dphi = np.sin(0.5 * dphi)
    sin_half_dlambda = np.sin(0.5 * dlambda)
    a = (sin_half_dphi * sin_half_dphi) + (
        math.cos(lat_i_rad) * np.cos(cand_lats_rad) * (sin_half_dlambda * sin_half_dlambda)
    )
    clamped_a = np.clip(a, 0.0, 1.0)
    c = 2.0 * np.arctan2(np.sqrt(clamped_a), np.sqrt(1.0 - clamped_a))
    result: NDArray[np.float64] = EARTH_RADIUS_METERS * c
    return result


class BallTreeNeighborhoodProvider:
    """Reference spatiotemporal neighborhood engine backed by scikit-learn Haversine BallTree.

    Never materializes an ``N x N`` pairwise distance matrix. Queries execute in
    bounded batches against the BallTree, apply exact temporal filtering first,
    and verify exact spherical Haversine distance ``<= eps_spatial_m`` on the
    surviving candidates.

    Timing instrumentation
    ----------------------
    ``build_time_seconds`` (whole tree construction) is always recorded. When
    ``detailed_timing=False`` (default, used for official benchmark trials),
    ``build_neighborhood_graph`` performs zero per-batch or per-point
    ``perf_counter`` calls. When ``detailed_timing=True``, candidate retrieval
    (``query_radius``), temporal filtering, and distance filtering are timed
    separately and candidates are counted. Neighborhood results are identical
    in both modes.
    """

    def __init__(
        self,
        dataset: ClusteringInputDataset,
        config: STDBSCANConfig,
        leaf_size: int = 40,
        query_batch_size: int = DEFAULT_QUERY_BATCH_SIZE,
        detailed_timing: bool = False,
    ) -> None:
        if isinstance(leaf_size, bool) or leaf_size < 1:
            raise ValueError(f"leaf_size must be an integer >= 1, got {leaf_size!r}")
        if isinstance(query_batch_size, bool) or query_batch_size < 1:
            raise ValueError(f"query_batch_size must be an integer >= 1, got {query_batch_size!r}")
        if not isinstance(detailed_timing, bool):
            raise ValueError(f"detailed_timing must be a boolean, got {detailed_timing!r}")

        self._detailed_timing = detailed_timing
        self._candidate_retrieval_time_s = 0.0
        self._temporal_filtering_time_s = 0.0
        self._distance_filtering_time_s = 0.0
        self._candidates_evaluated = 0

        self._dataset = dataset
        self._config = config
        self._leaf_size = leaf_size
        self._query_batch_size = query_batch_size

        self._eps_spatial_m: float = float(config.eps_spatial_m)
        self._eps_temporal_us: float = config.eps_temporal_us
        self._query_radius_rad: float = min(
            math.pi, config.eps_spatial_rad + BALLTREE_QUERY_GUARD_RAD
        )

        t0 = time.perf_counter()
        n = dataset.num_points
        if n > 0:
            lats_rad = np.deg2rad(dataset.latitudes_deg)
            lons_rad = np.deg2rad(dataset.longitudes_deg)
            self._lats_rad: NDArray[np.float64] = lats_rad
            self._lons_rad: NDArray[np.float64] = lons_rad
            # BallTree(metric="haversine") requires [lat_rad, lon_rad] column order
            self._coords_rad: NDArray[np.float64] = np.column_stack((lats_rad, lons_rad))
            self._tree: BallTree | None = BallTree(
                self._coords_rad,
                leaf_size=leaf_size,
                metric="haversine",
            )
        else:
            self._lats_rad = np.empty(0, dtype=np.float64)
            self._lons_rad = np.empty(0, dtype=np.float64)
            self._coords_rad = np.empty((0, 2), dtype=np.float64)
            self._tree = None

        self._build_time_seconds: float = time.perf_counter() - t0

    @property
    def provider_name(self) -> str:
        """Identifier for this neighborhood provider."""
        return "balltree_haversine"

    @property
    def num_points(self) -> int:
        """Number of indexed observations."""
        return self._dataset.num_points

    @property
    def build_time_seconds(self) -> float:
        """Wall-clock seconds spent building the BallTree."""
        return self._build_time_seconds

    @property
    def detailed_timing(self) -> bool:
        """Whether per-stage timers are recorded during neighborhood queries."""
        return self._detailed_timing

    def get_metrics(self) -> dict[str, Any]:
        """Return coarse build time and (if ``detailed_timing``) stage timers.

        Stage timers and ``candidates_evaluated`` are ``None`` when
        ``detailed_timing=False`` because they are not measured.
        """
        detailed = self._detailed_timing
        return {
            "provider": "balltree",
            "detailed_timing": detailed,
            "build_time_s": round(self._build_time_seconds, 6),
            "candidate_retrieval_time_s": (
                round(self._candidate_retrieval_time_s, 6) if detailed else None
            ),
            "temporal_filtering_time_s": (
                round(self._temporal_filtering_time_s, 6) if detailed else None
            ),
            "distance_filtering_time_s": (
                round(self._distance_filtering_time_s, 6) if detailed else None
            ),
            "candidates_evaluated": self._candidates_evaluated if detailed else None,
            "leaf_size": self._leaf_size,
            "query_batch_size": self._query_batch_size,
        }

    def _filter_candidates_timed(
        self, index: int, spatial_candidates: NDArray[np.int64]
    ) -> NDArray[np.int64]:
        """Instrumented twin of ``_filter_candidates`` (identical results, stage timers)."""
        self._candidates_evaluated += int(spatial_candidates.size)
        if spatial_candidates.size == 0:
            return np.array([index], dtype=np.int64)

        timestamps_us = self._dataset.timestamps_us
        t_i = timestamps_us[index]

        t_temp_0 = time.perf_counter()
        dt_us = np.abs(timestamps_us[spatial_candidates] - t_i)
        time_mask = dt_us <= self._eps_temporal_us
        time_cands = spatial_candidates[time_mask]
        self._temporal_filtering_time_s += time.perf_counter() - t_temp_0

        if time_cands.size == 0:
            return np.array([index], dtype=np.int64)

        t_dist_0 = time.perf_counter()
        dists_m = _exact_haversine_to_candidates_m(
            float(self._dataset.latitudes_deg[index]),
            float(self._dataset.longitudes_deg[index]),
            float(self._lats_rad[index]),
            self._dataset.latitudes_deg[time_cands],
            self._dataset.longitudes_deg[time_cands],
            self._lats_rad[time_cands],
        )
        exact_mask = (dists_m <= self._eps_spatial_m) | (time_cands == index)
        eligible: NDArray[np.int64] = np.sort(time_cands[exact_mask].astype(np.int64, copy=False))
        self._distance_filtering_time_s += time.perf_counter() - t_dist_0
        return eligible

    def _filter_candidates(
        self, index: int, spatial_candidates: NDArray[np.int64]
    ) -> NDArray[np.int64]:
        """Apply exact temporal and exact Haversine spatial filters to BallTree candidates."""
        if spatial_candidates.size == 0:
            return np.array([index], dtype=np.int64)

        timestamps_us = self._dataset.timestamps_us
        t_i = timestamps_us[index]

        # 1. Exact temporal threshold filter (fast integer subtraction)
        dt_us = np.abs(timestamps_us[spatial_candidates] - t_i)
        time_mask = dt_us <= self._eps_temporal_us
        time_cands = spatial_candidates[time_mask]

        if time_cands.size == 0:
            return np.array([index], dtype=np.int64)

        # 2. Exact Haversine geodesic distance verification against eps_spatial_m
        dists_m = _exact_haversine_to_candidates_m(
            float(self._dataset.latitudes_deg[index]),
            float(self._dataset.longitudes_deg[index]),
            float(self._lats_rad[index]),
            self._dataset.latitudes_deg[time_cands],
            self._dataset.longitudes_deg[time_cands],
            self._lats_rad[time_cands],
        )
        exact_mask = (dists_m <= self._eps_spatial_m) | (time_cands == index)
        eligible: NDArray[np.int64] = np.sort(time_cands[exact_mask].astype(np.int64, copy=False))
        return eligible

    def query_neighbors(self, index: int) -> NDArray[np.int64]:
        """Return sorted 1D int64 array of eligible spatiotemporal neighbor indices for ``index``.

        Always includes ``index`` itself.
        """
        n = self._dataset.num_points
        if index < 0 or index >= n:
            raise IndexError(f"Observation index {index} out of bounds for dataset of size {n}")
        assert self._tree is not None

        raw_result = self._tree.query_radius(
            self._coords_rad[index : index + 1],
            r=self._query_radius_rad,
            return_distance=False,
        )
        candidates = np.asarray(raw_result[0], dtype=np.int64)
        if self._detailed_timing:
            return self._filter_candidates_timed(index, candidates)
        return self._filter_candidates(index, candidates)

    def build_neighborhood_graph(self) -> NeighborhoodGraph:
        """Compute all eligible spatiotemporal neighborhoods in chunked batches as a CSR graph."""
        n = self._dataset.num_points
        if n == 0:
            return NeighborhoodGraph(
                indptr=np.zeros(1, dtype=np.int64),
                indices=np.empty(0, dtype=np.int64),
            )
        assert self._tree is not None

        indptr = np.zeros(n + 1, dtype=np.int64)
        neighbor_chunks: list[NDArray[np.int64]] = []
        running_offset = 0

        # Select the filter once so the official (untimed) path pays no per-point toggle cost.
        detailed = self._detailed_timing
        filter_candidates: Callable[[int, NDArray[np.int64]], NDArray[np.int64]] = (
            self._filter_candidates_timed if detailed else self._filter_candidates
        )

        for batch_start in range(0, n, self._query_batch_size):
            batch_end = min(n, batch_start + self._query_batch_size)
            if detailed:
                t_ret_0 = time.perf_counter()
            batch_raw = self._tree.query_radius(
                self._coords_rad[batch_start:batch_end],
                r=self._query_radius_rad,
                return_distance=False,
            )
            if detailed:
                self._candidate_retrieval_time_s += time.perf_counter() - t_ret_0
            for local_offset, raw_cands in enumerate(batch_raw):
                idx = batch_start + local_offset
                candidates = np.asarray(raw_cands, dtype=np.int64)
                eligible = filter_candidates(idx, candidates)
                neighbor_chunks.append(eligible)
                running_offset += int(eligible.shape[0])
                indptr[idx + 1] = running_offset

        indices = (
            np.concatenate(neighbor_chunks) if neighbor_chunks else np.empty(0, dtype=np.int64)
        )
        return NeighborhoodGraph(indptr=indptr, indices=indices)
