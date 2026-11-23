"""H3 discrete hexagonal spatiotemporal neighborhood candidate provider.

Correctness Contract and Empirical Support Policy
-------------------------------------------------
- Coordinates: WGS 84 decimal degrees ``latitudes_deg`` in ``[-90.0, 90.0]`` and
  ``longitudes_deg`` in ``[-180.0, 180.0]``.
- Discrete Global Grid: Coordinates are projected into discrete hexagonal H3 cells
  at a configurable resolution (calibrated: 7, 8, 9; default: 8).
- Geometry and Clearance Mathematics:
  H3 partitions the Earth using Snyder equal-area polyhedral projection of an
  icosahedron. Hexagon edge lengths are not uniform (varying by ~1.4x across each
  icosahedral face), and each resolution contains exactly 12 pentagonal cells where
  5 cells meet. Planar regular hexagon formulas (such as apothem k * 2 * r_inscribed)
  do not analytically prove global spherical completeness across arbitrary coordinates.
  Therefore, the clearance values in ``H3_MIN_CLEARANCE_METERS`` represent empirical
  minimum clearances observed across tested regional cells, high-latitude zones, and
  pentagons.
- Empirical Support Policy (Option B):
  AegisMar does not claim an unproven global analytical completeness theorem for H3.
  Instead, correctness is preserved through a two-tier contract:
    1. Calibrated Regional Candidate Search: For calibrated resolutions (7, 8, 9) and
       search radii within documented empirical clearance tables, ``compute_safe_k_ring``
       selects conservative ring coverage k. All candidates surviving discrete expansion
       undergo exact spherical Haversine distance verification matching BallTree precision.
    2. Fail-Closed Fallback Architecture: For uncalibrated resolutions, search radii
       exceeding empirical tables, discrete API failures (e.g. ``grid_disk`` errors),
       or configured pentagon encounters, the provider falls closed. If fallback is
       enabled (default), queries route transparently to the reference
       ``BallTreeNeighborhoodProvider``. If fallback is disabled, the provider fails
       closed immediately with a ``ValueError`` or ``RuntimeError``.
- Unsupported Configurations:
  Uncalibrated resolutions or radii exceeding empirical tables are strictly rejected
  unless explicit experimental opt-in (``allow_uncalibrated=True``) is granted. In
  experimental mode, ring estimation is approximate, clear warnings are logged, and
  diagnostics flag ``completeness_contract = "experimental_uncalibrated"``.
- Fallback Triggers vs. Omission Detection:
  The provider does NOT possess runtime oracle knowledge of candidates omitted outside
  a chosen ring. Fallback is triggered explicitly by:
    a) H3 API exceptions during ``grid_disk`` expansion.
    b) Pentagon or near-pentagon cell encounters (when ``fallback_on_pentagons=True``).
    c) Unsupported/uncalibrated configurations (when fallback is enabled).
- Dataset-Specific Parity Verification:
  Complete mathematical equivalence to the BallTree reference is verified offline
  per-dataset via ``verify_dataset_h3_balltree_parity``, comparing full CSR neighborhood
  graphs (``indptr`` and ``indices``) bit-for-bit.
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import h3
import numpy as np
from numpy.typing import NDArray

from aegismar.clustering.balltree_neighbors import (
    BallTreeNeighborhoodProvider,
    _exact_haversine_to_candidates_m,
)
from aegismar.clustering.config import (
    DEFAULT_H3_RESOLUTION,
    SUPPORTED_CALIBRATED_H3_RESOLUTIONS,
    STDBSCANConfig,
)
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

# Conservative width estimate per ring for experimental estimation outside clearance tables
_APPROX_RING_WIDTH_FACTOR: float = 0.44


def compute_safe_k_ring(
    resolution: int,
    eps_spatial_m: float,
    allow_uncalibrated: bool = False,
) -> int:
    """Compute the minimum H3 grid_disk ring count k based on empirical clearance tables.

    Parameters
    ----------
    resolution : int
        H3 discrete grid resolution (e.g. 7, 8, 9).
    eps_spatial_m : float
        Spatial neighborhood radius in meters.
    allow_uncalibrated : bool, optional
        If True, allow approximate estimation for uncalibrated resolutions or radii
        exceeding documented empirical clearance tables. Defaults to False (strict mode).

    Returns
    -------
    int
        Ring count k >= 1 such that the empirical clearance distance to
        ring k+1 is >= eps_spatial_m.

    Raises
    ------
    ValueError
        If resolution is uncalibrated or eps_spatial_m exceeds documented clearance tables
        and allow_uncalibrated is False.
    """
    if resolution in H3_MIN_CLEARANCE_METERS:
        table = H3_MIN_CLEARANCE_METERS[resolution]
        for k in sorted(table):
            if table[k] >= eps_spatial_m:
                return k

        max_k = max(table)
        max_dist = table[max_k]
        if not allow_uncalibrated:
            raise ValueError(
                f"Requested eps_spatial_m ({eps_spatial_m:.1f} m) exceeds maximum empirically "
                f"calibrated clearance ({max_dist:.1f} m) for H3 resolution {resolution}. "
                f"Set allow_uncalibrated=True to extrapolate ring order experimentally "
                f"without empirical completeness guarantees."
            )

        # Explicit uncalibrated extrapolation:
        step = max_dist / max_k
        extra_k = math.ceil((eps_spatial_m - max_dist) / step)
        return max_k + extra_k

    if not allow_uncalibrated:
        raise ValueError(
            f"H3 resolution {resolution} has no empirically calibrated clearance table "
            f"(calibrated resolutions: {tuple(sorted(H3_MIN_CLEARANCE_METERS))}). "
            f"Set allow_uncalibrated=True to estimate ring order experimentally "
            f"without empirical completeness guarantees."
        )

    # Explicit uncalibrated approximation:
    avg_edge_m = float(h3.average_hexagon_edge_length(resolution, unit="m"))
    min_width_m = avg_edge_m * _APPROX_RING_WIDTH_FACTOR
    k_est = math.ceil(eps_spatial_m / min_width_m)
    return int(max(1, k_est))


class H3NeighborhoodProvider(NeighborhoodProvider):
    """H3 discrete hexagonal spatiotemporal neighborhood provider with fail-closed fallback.

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
        allow_uncalibrated: bool | None = None,
    ) -> None:
        self._dataset = dataset
        self._config = config
        self._eps_spatial_m = float(config.eps_spatial_m)
        self._eps_temporal_us = float(config.eps_temporal_us)

        # Resolution resolution: explicit override > config > default (8)
        self._resolution = (
            resolution
            if resolution is not None
            else getattr(config, "h3_resolution", DEFAULT_H3_RESOLUTION)
        )
        if not (0 <= self._resolution <= 15):
            raise ValueError(f"H3 resolution must be between 0 and 15, got {self._resolution}")

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
        self._allow_uncalibrated = (
            allow_uncalibrated
            if allow_uncalibrated is not None
            else getattr(config, "h3_allow_uncalibrated", False)
        )

        # Calibration & safe k-ring determination
        self._all_fallback = False
        self._unsupported_reason: str | None = None
        configured_k = k_ring if k_ring is not None else getattr(config, "h3_k_ring", None)

        try:
            safe_k = compute_safe_k_ring(
                self._resolution,
                self._eps_spatial_m,
                allow_uncalibrated=self._allow_uncalibrated,
            )
        except ValueError as exc:
            if not self._enable_fallback:
                raise ValueError(
                    f"Unsupported H3 configuration and fallback is disabled: {exc}"
                ) from exc
            logger.warning(
                "Unsupported H3 configuration (%s); routing all queries to BallTree fallback.",
                exc,
            )
            self._all_fallback = True
            self._unsupported_reason = f"unsupported_configuration: {exc}"
            safe_k = 1

        if not self._all_fallback:
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
        else:
            self._k_ring = configured_k if configured_k is not None else 1

        # Establish contract metadata
        if self._all_fallback:
            self._is_calibrated = False
            self._completeness_contract = "full_balltree_fallback"
        elif self._allow_uncalibrated and (
            self._resolution not in SUPPORTED_CALIBRATED_H3_RESOLUTIONS
            or self._eps_spatial_m > max(H3_MIN_CLEARANCE_METERS[self._resolution].values())
        ):
            self._is_calibrated = False
            self._completeness_contract = "experimental_uncalibrated"
            logger.warning(
                "H3 provider operating in experimental uncalibrated mode (resolution %d, "
                "eps_spatial %.1f m). No empirical completeness guarantee is established.",
                self._resolution,
                self._eps_spatial_m,
            )
        else:
            self._is_calibrated = True
            self._completeness_contract = "empirical_regional_calibrated"

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

        if n > 0 and not self._all_fallback:
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
        elif n > 0 and self._all_fallback:
            # All observations will route directly to BallTree fallback
            self._lats_deg = dataset.latitudes_deg
            self._lons_deg = dataset.longitudes_deg
            self._lats_rad = np.deg2rad(dataset.latitudes_deg)
            self._timestamps_us = dataset.timestamps_us
            self._point_cells = ["fallback"] * n
            self._cell_indices = {}
            self._cell_timestamps = {}
            self._active_candidates = {}
            self._cell_is_pentagon = {}
            self._cell_near_pentagon = {}
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
        """Ring expansion radius used for spatial candidate sets."""
        return self._k_ring

    @property
    def is_calibrated(self) -> bool:
        """Whether this provider operates within empirically calibrated bounds."""
        return self._is_calibrated

    @property
    def completeness_contract(self) -> str:
        """Classification of the active completeness contract."""
        return self._completeness_contract

    @property
    def allow_uncalibrated(self) -> bool:
        """Whether experimental uncalibrated configurations are permitted."""
        return self._allow_uncalibrated

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
        """Return granular diagnostics, contract status, and performance counters."""
        return {
            "h3_resolution": self._resolution,
            "h3_k_ring": self._k_ring,
            "is_calibrated": self._is_calibrated,
            "completeness_contract": self._completeness_contract,
            "h3_allow_uncalibrated": self._allow_uncalibrated,
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
        if self._all_fallback:
            t_fb_0 = time.perf_counter()
            fb_provider = self._get_fallback_provider()
            res = fb_provider.query_neighbors(index)
            self._fallback_time_s += time.perf_counter() - t_fb_0
            self._fallback_count += 1
            reason = self._unsupported_reason or "unsupported_configuration"
            self._fallback_reason_counts[reason] += 1
            return res

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


@dataclass(frozen=True, slots=True)
class ParityVerificationResult:
    """Detailed results of bit-for-bit neighborhood and clustering parity verification."""

    dataset_sha256: str
    num_points: int
    eps_spatial_m: float
    eps_temporal_s: float
    min_samples: int
    h3_resolution: int
    h3_k_ring: int
    csr_indptr_match: bool
    csr_indices_match: bool
    total_edges_balltree: int
    total_edges_h3: int
    clusters_match: bool
    roles_match: bool
    labels_match: bool
    balltree_build_time_s: float
    balltree_query_time_s: float
    h3_build_time_s: float
    h3_query_time_s: float
    graph_query_speedup: float
    h3_metrics: dict[str, Any]

    @property
    def is_perfect_parity(self) -> bool:
        """Return True if all graph edges, roles, and cluster labels match 100% exactly."""
        return (
            self.csr_indptr_match
            and self.csr_indices_match
            and self.clusters_match
            and self.roles_match
            and self.labels_match
        )


def verify_dataset_h3_balltree_parity(
    dataset: ClusteringInputDataset,
    config: STDBSCANConfig,
    resolution: int | None = None,
    k_ring: int | None = None,
    dataset_sha256: str = "unspecified",
) -> ParityVerificationResult:
    """Verify bit-for-bit CSR graph and clustering parity between BallTree and H3 on a dataset."""
    from aegismar.clustering.st_dbscan import run_st_dbscan

    # 1. Build BallTree graph
    t0 = time.perf_counter()
    bt_prov = BallTreeNeighborhoodProvider(dataset=dataset, config=config)
    bt_build_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    bt_graph = bt_prov.build_neighborhood_graph()
    bt_query_s = time.perf_counter() - t0

    # 2. Build H3 graph
    t0 = time.perf_counter()
    h3_prov = H3NeighborhoodProvider(
        dataset=dataset,
        config=config,
        resolution=resolution,
        k_ring=k_ring,
    )
    h3_build_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    h3_graph = h3_prov.build_neighborhood_graph()
    h3_query_s = time.perf_counter() - t0

    # 3. Graph comparisons
    indptr_match = bool(np.array_equal(bt_graph.indptr, h3_graph.indptr))
    indices_match = bool(np.array_equal(bt_graph.indices, h3_graph.indices))

    # 4. Clustering executions
    bt_res = run_st_dbscan(dataset=dataset, config=config, provider=bt_prov)
    h3_res = run_st_dbscan(dataset=dataset, config=config, provider=h3_prov)

    clusters_match = bool(bt_res.num_clusters == h3_res.num_clusters)
    roles_match = bool(bt_res.roles == h3_res.roles)
    labels_match = bool(np.array_equal(bt_res.labels, h3_res.labels))

    speedup = bt_query_s / max(h3_query_s, 1e-9)

    return ParityVerificationResult(
        dataset_sha256=dataset_sha256,
        num_points=dataset.num_points,
        eps_spatial_m=float(config.eps_spatial_m),
        eps_temporal_s=float(config.eps_temporal_s),
        min_samples=config.min_samples,
        h3_resolution=h3_prov.resolution,
        h3_k_ring=h3_prov.k_ring,
        csr_indptr_match=indptr_match,
        csr_indices_match=indices_match,
        total_edges_balltree=bt_graph.total_edges,
        total_edges_h3=h3_graph.total_edges,
        clusters_match=clusters_match,
        roles_match=roles_match,
        labels_match=labels_match,
        balltree_build_time_s=round(bt_build_s, 6),
        balltree_query_time_s=round(bt_query_s, 6),
        h3_build_time_s=round(h3_build_s, 6),
        h3_query_time_s=round(h3_query_s, 6),
        graph_query_speedup=round(speedup, 2),
        h3_metrics=h3_prov.get_metrics(),
    )
