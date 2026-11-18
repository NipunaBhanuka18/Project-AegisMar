"""Independent O(N^2) brute-force geodesic-temporal test oracle for spatial verification.

This module intentionally implements its own standalone spherical Haversine formula
using Python's standard ``math`` library without importing or reusing ``BallTree``,
``scikit-learn``, or vectorized indexing code. It exists strictly to verify
correctness of spatial neighborhood providers on small test datasets (default
guard: ``N <= 5000``).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from aegismar.clustering.config import STDBSCANConfig
from aegismar.clustering.st_dbscan import run_st_dbscan
from aegismar.clustering.types import (
    ClusteringInputDataset,
    NeighborhoodGraph,
    NeighborhoodProvider,
)

# Mean spherical Earth radius (IUGG / WGS 84 mean radius in meters)
ORACLE_EARTH_RADIUS_METERS: float = 6371008.8

# Safety guard preventing accidental O(N^2) execution on full 100k+ AIS datasets
DEFAULT_MAX_ORACLE_POINTS: int = 5000


def _standalone_haversine_meters(
    lat1_deg: float,
    lon1_deg: float,
    lat2_deg: float,
    lon2_deg: float,
) -> float:
    """Standalone scalar spherical Haversine distance in meters (independent of spatial indexes)."""
    if lat1_deg == lat2_deg and lon1_deg == lon2_deg:
        return 0.0

    phi1 = math.radians(lat1_deg)
    phi2 = math.radians(lat2_deg)
    dphi = math.radians(lat2_deg - lat1_deg)
    dlambda = math.radians(lon2_deg - lon1_deg)

    sin_dphi = math.sin(0.5 * dphi)
    sin_dlambda = math.sin(0.5 * dlambda)

    hav = (sin_dphi * sin_dphi) + (math.cos(phi1) * math.cos(phi2) * sin_dlambda * sin_dlambda)
    clamped = 0.0 if hav < 0.0 else (1.0 if hav > 1.0 else hav)
    central_angle = 2.0 * math.atan2(math.sqrt(clamped), math.sqrt(1.0 - clamped))
    return ORACLE_EARTH_RADIUS_METERS * central_angle


class BruteForceNeighborhoodOracle:
    """Independent O(N^2) brute-force spatiotemporal neighborhood oracle.

    Implements the ``NeighborhoodProvider`` protocol so it can be directly injected
    into ``run_st_dbscan`` for end-to-end oracle comparison against ``BallTree``
    (and ``H3`` in Week 3).
    """

    def __init__(
        self,
        dataset: ClusteringInputDataset,
        config: STDBSCANConfig,
        max_points: int = DEFAULT_MAX_ORACLE_POINTS,
    ) -> None:
        if dataset.num_points > max_points:
            raise ValueError(
                f"BruteForceNeighborhoodOracle refuses O(N^2) execution on {dataset.num_points} "
                f"points (safety limit: {max_points}). Use a small subset for oracle verification."
            )

        self._dataset = dataset
        self._config = config
        self._eps_spatial_m = float(config.eps_spatial_m)
        self._eps_temporal_us = config.eps_temporal_us
        t0 = time.perf_counter()
        self._build_time_seconds = time.perf_counter() - t0

    @property
    def provider_name(self) -> str:
        """Identifier for the brute-force oracle provider."""
        return "brute_force_oracle"

    @property
    def num_points(self) -> int:
        """Number of observations in the test dataset."""
        return self._dataset.num_points

    @property
    def build_time_seconds(self) -> float:
        """Oracle has no spatial index build phase."""
        return self._build_time_seconds

    def query_neighbors(self, index: int) -> NDArray[np.int64]:
        """Exhaustively scan all N points and return sorted eligible neighbors of ``index``."""
        n = self._dataset.num_points
        if index < 0 or index >= n:
            raise IndexError(f"Observation index {index} out of bounds for dataset of size {n}")

        lats = self._dataset.latitudes_deg
        lons = self._dataset.longitudes_deg
        ts_us = self._dataset.timestamps_us

        lat_i = float(lats[index])
        lon_i = float(lons[index])
        t_i = int(ts_us[index])

        eligible: list[int] = []
        for j in range(n):
            if j == index:
                eligible.append(j)
                continue
            if abs(t_i - int(ts_us[j])) > self._eps_temporal_us:
                continue
            dist_m = _standalone_haversine_meters(lat_i, lon_i, float(lats[j]), float(lons[j]))
            if dist_m <= self._eps_spatial_m:
                eligible.append(j)

        return np.array(eligible, dtype=np.int64)

    def build_neighborhood_graph(self) -> NeighborhoodGraph:
        """Exhaustively compute all N neighborhoods in CSR format."""
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
            nbrs = self.query_neighbors(i)
            chunks.append(nbrs)
            offset += int(nbrs.shape[0])
            indptr[i + 1] = offset

        indices = np.concatenate(chunks) if chunks else np.empty(0, dtype=np.int64)
        return NeighborhoodGraph(indptr=indptr, indices=indices)


@dataclass(frozen=True, slots=True)
class OracleVerificationReport:
    """Detailed correctness comparison between a candidate provider and the brute-force oracle."""

    provider_name: str
    num_points: int
    total_oracle_edges: int
    total_provider_edges: int
    missing_neighbor_count: int
    extra_neighbor_count: int
    neighbor_recall: float
    neighbor_precision: float
    exact_neighborhood_match: bool
    exact_role_match: bool
    exact_label_match: bool


def verify_provider_against_oracle(
    dataset: ClusteringInputDataset,
    config: STDBSCANConfig,
    provider: NeighborhoodProvider,
    max_oracle_points: int = DEFAULT_MAX_ORACLE_POINTS,
) -> OracleVerificationReport:
    """Compare a neighborhood provider against the independent brute-force oracle.

    Verifies:
    1. Every observation's complete eligible neighbor set (zero missing, zero extra).
    2. Core / border / noise role classifications under the same deterministic policy.
    3. Final cluster IDs under the same deterministic policy.
    """
    oracle = BruteForceNeighborhoodOracle(
        dataset=dataset,
        config=config,
        max_points=max_oracle_points,
    )

    oracle_graph = oracle.build_neighborhood_graph()
    provider_graph = provider.build_neighborhood_graph()

    n = dataset.num_points
    missing = 0
    extra = 0
    matched = 0

    for i in range(n):
        o_set = set(oracle_graph.neighbors_of(i).tolist())
        p_set = set(provider_graph.neighbors_of(i).tolist())
        matched += len(o_set & p_set)
        missing += len(o_set - p_set)
        extra += len(p_set - o_set)

    total_o = oracle_graph.total_edges
    total_p = provider_graph.total_edges
    recall = 1.0 if total_o == 0 else matched / total_o
    precision = 1.0 if total_p == 0 else matched / total_p

    oracle_res = run_st_dbscan(dataset=dataset, config=config, provider=oracle)
    provider_res = run_st_dbscan(dataset=dataset, config=config, provider=provider)

    exact_roles = oracle_res.roles == provider_res.roles
    exact_labels = bool(np.array_equal(oracle_res.labels, provider_res.labels))

    return OracleVerificationReport(
        provider_name=provider.provider_name,
        num_points=n,
        total_oracle_edges=total_o,
        total_provider_edges=total_p,
        missing_neighbor_count=missing,
        extra_neighbor_count=extra,
        neighbor_recall=recall,
        neighbor_precision=precision,
        exact_neighborhood_match=(missing == 0 and extra == 0),
        exact_role_match=exact_roles,
        exact_label_match=exact_labels,
    )
