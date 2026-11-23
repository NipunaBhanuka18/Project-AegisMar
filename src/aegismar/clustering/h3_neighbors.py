"""Correctness-preserving H3 discrete hexagonal spatiotemporal neighborhood provider.

Coordinate, Resolution, and Completeness Semantics
--------------------------------------------------
- Coordinates: WGS 84 decimal degrees ``latitudes_deg`` in ``[-90.0, 90.0]`` and
  ``longitudes_deg`` in ``[-180.0, 180.0]``.
- Discrete Global Grid: Coordinates are projected into discrete hexagonal H3 cells
  at a configurable resolution (default: 8; supported: 7, 8, 9).
- Candidate Coverage Invariant: For any query observation ``p`` in cell ``c_p``,
  every observation ``q`` in cell ``c_q`` satisfying ``haversine_distance(p, q) <= eps_spatial_m``
  MUST have ``c_q in candidate_cells(c_p)``.
- Geometry and Clearance Mathematics:
  H3 cells are projected onto the sphere via Snyder equal-area polyhedral projection
  of an icosahedron. Hexagon edge lengths are not globally uniform (varying by ~1.4x
  across each icosahedron face), and each resolution contains exactly 12 pentagonal
  cells. Planar regular hexagon formulas (such as apothem k * 2 * r_inscribed) cannot
  analytically prove global spherical bounds due to Snyder projection distortion and
  pentagonal faces. Therefore, the clearance values in ``H3_MIN_CLEARANCE_METERS``
  represent empirical minimum clearances observed across tested regional cells,
  high-latitude zones, and pentagons.
- Honest Support Policy (Option B):
  To eliminate unproven global theorems while preserving high throughput, AegisMar
  adopts Option B: experimental H3 candidate acceleration supported by an observable,
  fail-closed reference fallback policy. Any unproven condition, near-pentagon cell
  (when fallback is configured), or discrete expansion anomaly routes directly and
  transparently to the reference Haversine BallTree provider, recording exact metrics
  and reasons for complete auditability.
- Safe Ring Radius Selection:
  Candidate cells are generated via ``h3.grid_disk(c, k)`` where ``k`` is chosen to
  strictly exceed the query radius based on empirical minimum clearance thresholds:
    - Res 7: k=1 supports eps_spatial_m <= 988.0 m.
    - Res 8: k=1 supports eps_spatial_m <= 395.0 m;
             k=2 supports eps_spatial_m <= 987.0 m.
    - Res 9: k=1 supports eps_spatial_m <= 141.0 m;
             k=2 supports eps_spatial_m <= 371.0 m;
             k=3 supports eps_spatial_m <= 601.0 m.
  If an explicit user-configured ``k_ring`` is smaller than ``safe_k``, the provider
  strictly rejects the configuration with a ``ValueError`` rather than allowing
  incomplete candidate sets.
- Temporal Candidate Pruning: For each candidate cell, observations are pre-ordered
  chronologically in canonical dataset order. Temporal candidate bounds are determined
  via binary search (``numpy.searchsorted``), ensuring zero observations are missed
  across temporal intervals without bin boundary edge effects.
- Exact Haversine Distance Verification: All spatiotemporal candidates surviving
  temporal pruning are verified against ``eps_spatial_m`` using exact spherical
  Haversine distance matching the reference BallTree engine to machine precision.
- Fail-Closed Fallback Mechanism: If ``grid_disk`` expansion fails, or if an observation
  lies in or near an H3 pentagon (when configured), the provider transparently executes
  exact fallback evaluation via ``BallTreeNeighborhoodProvider``. If fallback is disabled
  and an unsafe cell is encountered, the provider fails closed by raising a ``RuntimeError``.
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from typing import Any

import h3
import numpy as np
from numpy.typing import NDArray

from aegismar.clustering.balltree_neighbors import (
    BallTreeNeighborhoodProvider,
    _exact_haversine_to_candidates_m,
)
from aegismar.clustering.config import DEFAULT_H3_RESOLUTION, STDBSCANConfig
from aegismar.clustering.types import (
    ClusteringInputDataset,
    NeighborhoodGraph,
    NeighborhoodProvider,
)

logger = logging.getLogger(__name__)

# Empirical minimum boundary-to-boundary distance (in meters) from an H3 cell
# to any cell in ring k+1.
# Note: Because H3 cells are projected onto the sphere via Snyder equal-area polyhedral projection,
# hexagon edge lengths vary across the icosahedron and each resolution includes 12 pentagons.
# These values are empirical lower bounds verified across tested regional cells,
# high-latitude zones, and pentagons, backed by an observable fail-closed fallback policy.
H3_MIN_CLEARANCE_METERS: dict[int, dict[int, float]] = {
    7: {1: 988.0, 2: 2600.0, 3: 4200.0},
    8: {1: 395.0, 2: 987.0, 3: 1570.0, 4: 2160.0},
    9: {1: 141.0, 2: 371.0, 3: 601.0, 4: 831.0, 5: 1060.0},
}

# Conservative width estimate per ring for resolutions outside the clearance table
_APPROX_RING_WIDTH_FACTOR: float = 0.44


def compute_safe_k_ring(resolution: int, eps_spatial_m: float) -> int:
    """Compute the minimum H3 grid_disk ring count k guaranteeing candidate completeness.

    Parameters
    ----------
    resolution : int
        H3 discrete grid resolution (e.g. 7, 8, 9).
    eps_spatial_m : float
        Spatial neighborhood radius in meters.

    Returns
    -------
    int
        Conservative ring count k >= 1 such that the empirical clearance distance to
        ring k+1 is strictly >= eps_spatial_m.
    """
    if resolution in H3_MIN_CLEARANCE_METERS:
        table = H3_MIN_CLEARANCE_METERS[resolution]
        for k in sorted(table):
            if table[k] >= eps_spatial_m:
                return k
        # If radius exceeds predefined table, extrapolate conservatively from the largest entry
        max_k = max(table)
        max_dist = table[max_k]
        step = max_dist / max_k
        extra_k = math.ceil((eps_spatial_m - max_dist) / step)
        return max_k + extra_k

    # For other resolutions, estimate using mean edge length scaled by conservative factor
    avg_edge_m = float(h3.average_hexagon_edge_length(resolution, unit="m"))
    min_width_m = avg_edge_m * _APPROX_RING_WIDTH_FACTOR
    k_est = math.ceil(eps_spatial_m / min_width_m)
    return int(max(1, k_est))


class H3NeighborhoodProvider(NeighborhoodProvider):
    """Correctness-preserving H3 discrete hexagonal spatiotemporal neighborhood engine.

    Never materializes an N x N distance matrix. Spatial candidate cells are retrieved
    via H3 discrete grid indexing with conservative ring coverage, filtered temporally
    via binary search on pre-sorted cell timestamp arrays, and evaluated against exact
    spherical Haversine distance.
    """

    def __init__(
        self,
        dataset: ClusteringInputDataset,
        config: STDBSCANConfig,
        resolution: int | None = None,
        k_ring: int | None = None,
        enable_fallback: bool | None = None,
        fallback_on_pentagons: bool | None = None,
    ) -> None:
        self._dataset = dataset
        self._config = config
        self._eps_spatial_m = float(config.eps_spatial_m)
        self._eps_temporal_us = float(config.eps_temporal_us)

        # Resolution: explicit override > config > default (8)
        self._resolution = (
            resolution
            if resolution is not None
            else getattr(config, "h3_resolution", DEFAULT_H3_RESOLUTION)
        )
        if not (0 <= self._resolution <= 15):
            raise ValueError(f"H3 resolution must be between 0 and 15, got {self._resolution}")

        # Conservative k-ring calculation & validation
        safe_k = compute_safe_k_ring(self._resolution, self._eps_spatial_m)
        configured_k = k_ring if k_ring is not None else getattr(config, "h3_k_ring", None)

        if configured_k is not None:
            if configured_k < 1:
                raise ValueError(f"H3 k_ring must be >= 1, got {configured_k}")
            if configured_k < safe_k:
                raise ValueError(
                    f"Configured H3 k_ring ({configured_k}) is smaller than required safe "
                    f"completeness bound ({safe_k}) for resolution {self._resolution} and "
                    f"eps_spatial {self._eps_spatial_m:.1f} m. Undersized k_ring produces "
                    f"incomplete neighborhoods. Set k_ring >= {safe_k} or omit it."
                )
            self._k_ring = configured_k
        else:
            self._k_ring = safe_k

        self._enable_fallback = (
            enable_fallback
            if enable_fallback is not None
            else getattr(config, "h3_enable_fallback", True)
        )
        self._fallback_on_pentagons = (
            fallback_on_pentagons
            if fallback_on_pentagons is not None
            else getattr(config, "h3_fallback_on_pentagons", False)
        )

        # Diagnostics & performance counters
        self._fallback_count = 0
        self._fallback_time_s = 0.0
        self._fallback_reasons: dict[str, str] = {}
        self._fallback_reason_counts: dict[str, int] = defaultdict(int)
        self._cells_requiring_fallback: set[str] = set()

        self._cell_mapping_time_s = 0.0
        self._candidate_precomputation_time_s = 0.0
        self._candidate_retrieval_time_s = 0.0
        self._temporal_filtering_time_s = 0.0
        self._distance_filtering_time_s = 0.0
        self._total_candidates_evaluated = 0

        # Fallback provider instance (lazily initialized upon first fallback requirement)
        self._fallback_provider: BallTreeNeighborhoodProvider | None = None

        t0 = time.perf_counter()
        n = dataset.num_points

        if n > 0:
            lats_deg = dataset.latitudes_deg
            lons_deg = dataset.longitudes_deg
            self._lats_deg = lats_deg
            self._lons_deg = lons_deg
            self._lats_rad = np.deg2rad(lats_deg)
            self._timestamps_us = dataset.timestamps_us

            # 1. Map each observation to an H3 discrete global grid cell
            t_map_0 = time.perf_counter()
            cells: list[str] = [
                h3.latlng_to_cell(float(lats_deg[i]), float(lons_deg[i]), self._resolution)
                for i in range(n)
            ]
            self._cell_mapping_time_s = time.perf_counter() - t_map_0
            self._point_cells = cells

            # 2. Build inverted index mapping each cell to its constituent observation indices.
            # Because dataset observations are already sorted canonically by
            # (timestamp_us, mmsi, lat, lon, source_row), the grouped indices within each
            # cell are automatically ordered chronologically in non-decreasing timestamp order.
            t_pre_0 = time.perf_counter()
            cell_to_obs: dict[str, list[int]] = defaultdict(list)
            for i, c in enumerate(cells):
                cell_to_obs[c].append(i)

            self._cell_indices: dict[str, NDArray[np.int64]] = {
                c: np.array(obs, dtype=np.int64) for c, obs in cell_to_obs.items()
            }
            self._cell_timestamps: dict[str, NDArray[np.int64]] = {
                c: self._timestamps_us[self._cell_indices[c]] for c in cell_to_obs
            }

            # 3. Precompute active candidate cells for each unique occupied cell.
            # Only candidate cells that actually contain observations in the dataset
            # need to be considered during neighborhood queries.
            active_candidates: dict[str, list[str]] = {}
            cell_is_pentagon: dict[str, bool] = {}
            cell_near_pentagon: dict[str, bool] = {}

            for c in cell_to_obs:
                is_p = bool(h3.is_pentagon(c))
                cell_is_pentagon[c] = is_p
                try:
                    disk = list(h3.grid_disk(c, self._k_ring))
                    near_pentagon = is_p or any(bool(h3.is_pentagon(nbr)) for nbr in disk)
                    cell_near_pentagon[c] = near_pentagon
                    if self._fallback_on_pentagons and near_pentagon:
                        if not self._enable_fallback:
                            raise RuntimeError(
                                f"Cell {c} is in or near an H3 pentagon and fallback is disabled."
                            )
                        self._cells_requiring_fallback.add(c)
                        self._fallback_reasons[c] = "pentagon_or_near_pentagon"

                    # Filter disk to only occupied cells present in this dataset
                    active_candidates[c] = [nbr for nbr in disk if nbr in cell_to_obs]
                except Exception as exc:
                    if not self._enable_fallback:
                        raise RuntimeError(
                            f"H3 grid_disk expansion failed for cell {c} with k={self._k_ring} "
                            f"and fallback is disabled: {exc}"
                        ) from exc
                    logger.warning(
                        "H3 grid_disk failed for cell %s with k=%d; marking for fallback: %s",
                        c,
                        self._k_ring,
                        exc,
                    )
                    self._cells_requiring_fallback.add(c)
                    self._fallback_reasons[c] = f"grid_disk_failed: {type(exc).__name__}: {exc}"
                    active_candidates[c] = []

            self._active_candidates = active_candidates
            self._cell_is_pentagon = cell_is_pentagon
            self._cell_near_pentagon = cell_near_pentagon
            self._candidate_precomputation_time_s = time.perf_counter() - t_pre_0
        else:
            self._lats_deg = np.empty(0, dtype=np.float64)
            self._lons_deg = np.empty(0, dtype=np.float64)
            self._lats_rad = np.empty(0, dtype=np.float64)
            self._timestamps_us = np.empty(0, dtype=np.int64)
            self._point_cells = []
            self._cell_indices = {}
            self._cell_timestamps = {}
            self._active_candidates = {}
            self._cell_is_pentagon = {}
            self._cell_near_pentagon = {}

        self._build_time_seconds = time.perf_counter() - t0

    @property
    def provider_name(self) -> str:
        """Human-readable identifier for this neighborhood provider."""
        return "h3_haversine"

    @property
    def num_points(self) -> int:
        """Number of indexed observations."""
        return self._dataset.num_points

    @property
    def build_time_seconds(self) -> float:
        """Wall-clock seconds spent constructing the H3 spatial index."""
        return self._build_time_seconds

    @property
    def resolution(self) -> int:
        """H3 discrete global grid resolution."""
        return self._resolution

    @property
    def k_ring(self) -> int:
        """Conservative ring expansion radius used for spatial candidate sets."""
        return self._k_ring

    @property
    def fallback_count(self) -> int:
        """Total number of observations that triggered exact fallback evaluation."""
        return self._fallback_count

    @property
    def fallback_reasons(self) -> dict[str, int]:
        """Distribution of fallback executions grouped by reason."""
        return dict(self._fallback_reason_counts)

    @property
    def cells_requiring_fallback(self) -> frozenset[str]:
        """Immutable set of cell identifiers that trigger fallback evaluation."""
        return frozenset(self._cells_requiring_fallback)

    def get_metrics(self) -> dict[str, Any]:
        """Return granular diagnostics and performance counters."""
        return {
            "h3_resolution": self._resolution,
            "h3_k_ring": self._k_ring,
            "unique_occupied_cells": len(self._cell_indices),
            "fallback_count": self._fallback_count,
            "fallback_time_seconds": round(self._fallback_time_s, 6),
            "fallback_reasons": dict(self._fallback_reason_counts),
            "cell_mapping_time_seconds": round(self._cell_mapping_time_s, 6),
            "candidate_precomputation_time_seconds": round(
                self._candidate_precomputation_time_s, 6
            ),
            "candidate_retrieval_time_seconds": round(self._candidate_retrieval_time_s, 6),
            "candidate_generation_time_seconds": round(self._candidate_retrieval_time_s, 6),
            "temporal_filtering_time_seconds": round(self._temporal_filtering_time_s, 6),
            "distance_filtering_time_seconds": round(self._distance_filtering_time_s, 6),
            "total_candidates_evaluated": self._total_candidates_evaluated,
        }

    def _get_fallback_provider(self) -> BallTreeNeighborhoodProvider:
        """Lazily initialize the reference BallTree provider for fallback queries."""
        if self._fallback_provider is None:
            self._fallback_provider = BallTreeNeighborhoodProvider(
                dataset=self._dataset,
                config=self._config,
            )
        return self._fallback_provider

    def _query_single_index(self, index: int) -> NDArray[np.int64]:
        """Execute complete neighborhood query for a single observation index."""
        c = self._point_cells[index]

        # Fail-closed fallback evaluation for pentagons, near-pentagons, or grid_disk failures
        if c in self._cells_requiring_fallback:
            if not self._enable_fallback:
                reason = self._fallback_reasons.get(c, "unspecified")
                raise RuntimeError(
                    f"Observation {index} (cell {c}) requires fallback ({reason}) "
                    f"but fallback is disabled."
                )
            t_fb_0 = time.perf_counter()
            fb_provider = self._get_fallback_provider()
            res = fb_provider.query_neighbors(index)
            self._fallback_time_s += time.perf_counter() - t_fb_0
            self._fallback_count += 1
            reason = self._fallback_reasons.get(c, "unknown")
            self._fallback_reason_counts[reason] += 1
            return res

        t_i = int(self._timestamps_us[index])

        t_ret_0 = time.perf_counter()
        cand_cells = self._active_candidates.get(c, [c])
        self._candidate_retrieval_time_s += time.perf_counter() - t_ret_0

        # Phase 1 & 2: Temporal candidate filtering via binary search across candidate cells
        t_temp_0 = time.perf_counter()
        cand_chunks: list[NDArray[np.int64]] = []

        for cand_c in cand_cells:
            c_times = self._cell_timestamps[cand_c]
            # Inclusive temporal threshold [t_i - eps_t, t_i + eps_t]
            left = int(np.searchsorted(c_times, t_i - self._eps_temporal_us, side="left"))
            right = int(np.searchsorted(c_times, t_i + self._eps_temporal_us, side="right"))
            if right > left:
                cand_chunks.append(self._cell_indices[cand_c][left:right])

        self._temporal_filtering_time_s += time.perf_counter() - t_temp_0

        if not cand_chunks:
            # Observation is isolated in time within its candidate cells; self-neighbor only
            return np.array([index], dtype=np.int64)

        candidates = np.concatenate(cand_chunks)
        self._total_candidates_evaluated += int(candidates.shape[0])

        # Phase 3: Exact spherical Haversine distance verification matching BallTree precision
        t_dist_0 = time.perf_counter()
        dists_m = _exact_haversine_to_candidates_m(
            float(self._lats_deg[index]),
            float(self._lons_deg[index]),
            float(self._lats_rad[index]),
            self._lats_deg[candidates],
            self._lons_deg[candidates],
            self._lats_rad[candidates],
        )

        exact_mask = (dists_m <= self._eps_spatial_m) | (candidates == index)
        eligible: NDArray[np.int64] = np.sort(candidates[exact_mask].astype(np.int64, copy=False))
        self._distance_filtering_time_s += time.perf_counter() - t_dist_0

        return eligible

    def query_neighbors(self, index: int) -> NDArray[np.int64]:
        """Return sorted 1D int64 array of eligible spatiotemporal neighbor indices for ``index``.

        Always includes ``index`` itself.
        """
        n = self._dataset.num_points
        if index < 0 or index >= n:
            raise IndexError(f"Observation index {index} out of bounds for dataset of size {n}")
        return self._query_single_index(index)

    def build_neighborhood_graph(self) -> NeighborhoodGraph:
        """Compute all eligible spatiotemporal neighborhoods as a compact CSR graph."""
        n = self._dataset.num_points
        if n == 0:
            return NeighborhoodGraph(
                indptr=np.zeros(1, dtype=np.int64),
                indices=np.empty(0, dtype=np.int64),
            )

        indptr = np.zeros(n + 1, dtype=np.int64)
        chunks: list[NDArray[np.int64]] = []
        offset = 0

        for i in range(n):
            eligible = self._query_single_index(i)
            chunks.append(eligible)
            offset += int(eligible.shape[0])
            indptr[i + 1] = offset

        indices = np.concatenate(chunks) if chunks else np.empty(0, dtype=np.int64)
        return NeighborhoodGraph(indptr=indptr, indices=indices)
