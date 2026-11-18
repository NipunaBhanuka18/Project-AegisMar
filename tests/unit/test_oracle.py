"""Independent brute-force oracle verification tests for BallTree ST-DBSCAN (Fixture 12)."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from aegismar.clustering.balltree_neighbors import BallTreeNeighborhoodProvider
from aegismar.clustering.config import STDBSCANConfig
from aegismar.clustering.st_dbscan import run_st_dbscan
from aegismar.clustering.types import ObservationRecord, build_clustering_dataset
from aegismar.spatial.oracle import (
    BruteForceNeighborhoodOracle,
    verify_provider_against_oracle,
)

BASE_TIME = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)


def _generate_random_coastal_dataset(
    seed: int,
    n_points: int,
    center_lat: float = 33.74,
    center_lon: float = -118.20,
    spatial_spread_deg: float = 0.015,
    time_span_s: int = 3600,
) -> list[ObservationRecord]:
    """Generate a deterministic multi-cluster + noise synthetic dataset."""
    rng = random.Random(seed)
    # Create 4 random dense centers + uniform background noise
    centers = [
        (
            center_lat + rng.uniform(-spatial_spread_deg, spatial_spread_deg),
            center_lon + rng.uniform(-spatial_spread_deg, spatial_spread_deg),
            rng.randint(0, time_span_s),
        )
        for _ in range(4)
    ]

    records: list[ObservationRecord] = []
    for i in range(n_points):
        if rng.random() < 0.75:
            c_lat, c_lon, c_t = rng.choice(centers)
            lat = max(-89.9, min(89.9, c_lat + rng.gauss(0.0, 0.0018)))
            lon = c_lon + rng.gauss(0.0, 0.0018)
            # Wrap longitude cleanly into [-180, 180]
            if lon > 180.0:
                lon -= 360.0
            elif lon < -180.0:
                lon += 360.0
            t_offset = max(0.0, c_t + rng.gauss(0.0, 450.0))
        else:
            lat = max(
                -89.9, min(89.9, center_lat + rng.uniform(-spatial_spread_deg, spatial_spread_deg))
            )
            lon = center_lon + rng.uniform(-spatial_spread_deg, spatial_spread_deg)
            if lon > 180.0:
                lon -= 360.0
            elif lon < -180.0:
                lon += 360.0
            t_offset = rng.uniform(0.0, float(time_span_s))

        records.append(
            ObservationRecord(
                source_row=i + 1,
                mmsi=f"36600{i % 25:04d}",
                timestamp_utc=BASE_TIME + timedelta(seconds=t_offset),
                latitude=lat,
                longitude=lon,
            )
        )
    return records


@pytest.mark.parametrize(
    ("seed", "n_points", "eps_spatial_m", "eps_temporal_s", "min_samples"),
    [
        (101, 120, 300.0, 900.0, 5),
        (202, 150, 200.0, 600.0, 3),
        (303, 180, 500.0, 1200.0, 6),
        (404, 100, 150.0, 300.0, 4),
    ],
)
def test_12_randomized_datasets_match_bruteforce_oracle(
    seed: int,
    n_points: int,
    eps_spatial_m: float,
    eps_temporal_s: float,
    min_samples: int,
) -> None:
    """Fixture 12: BallTree matches independent O(N^2) oracle on neighbors, roles, and labels."""
    records = _generate_random_coastal_dataset(seed=seed, n_points=n_points)
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(
        eps_spatial_m=eps_spatial_m,
        eps_temporal_s=eps_temporal_s,
        min_samples=min_samples,
    )

    provider = BallTreeNeighborhoodProvider(ds, cfg, query_batch_size=32)
    report = verify_provider_against_oracle(ds, cfg, provider)

    assert report.num_points == n_points
    assert report.missing_neighbor_count == 0
    assert report.extra_neighbor_count == 0
    assert report.neighbor_recall == 1.0
    assert report.neighbor_precision == 1.0
    assert report.exact_neighborhood_match is True
    assert report.exact_role_match is True
    assert report.exact_label_match is True

    # Also verify point-by-point query_neighbors matches oracle query_neighbors
    oracle = BruteForceNeighborhoodOracle(ds, cfg)
    for idx in range(min(25, n_points)):
        assert np.array_equal(provider.query_neighbors(idx), oracle.query_neighbors(idx))


def test_oracle_matches_balltree_across_dateline_and_high_latitude() -> None:
    """Oracle and BallTree agree 100% on randomized dateline and Arctic scenarios."""
    for seed, lat, lon in [(505, 0.0, 179.995), (606, 82.0, 15.0)]:
        records = _generate_random_coastal_dataset(
            seed=seed,
            n_points=100,
            center_lat=lat,
            center_lon=lon,
            spatial_spread_deg=0.01,
        )
        ds = build_clustering_dataset(records)
        cfg = STDBSCANConfig(eps_spatial_m=400.0, eps_temporal_s=900.0, min_samples=4)
        provider = BallTreeNeighborhoodProvider(ds, cfg)
        report = verify_provider_against_oracle(ds, cfg, provider)
        assert report.exact_neighborhood_match is True
        assert report.exact_role_match is True
        assert report.exact_label_match is True


def test_oracle_refuses_large_dataset_guard() -> None:
    """Brute-force oracle must refuse O(N^2) execution above its safety limit."""
    records = _generate_random_coastal_dataset(seed=707, n_points=50)
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=5)

    with pytest.raises(ValueError, match="refuses O\\(N\\^2\\) execution"):
        BruteForceNeighborhoodOracle(ds, cfg, max_points=25)


def test_oracle_directly_injectable_into_st_dbscan() -> None:
    """Verify run_st_dbscan works identically with BruteForceNeighborhoodOracle injected."""
    records = _generate_random_coastal_dataset(seed=808, n_points=60)
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=4)

    oracle = BruteForceNeighborhoodOracle(ds, cfg)
    bt = BallTreeNeighborhoodProvider(ds, cfg)

    res_oracle = run_st_dbscan(ds, cfg, oracle)
    res_bt = run_st_dbscan(ds, cfg, bt)

    assert res_oracle.provider_name == "brute_force_oracle"
    assert res_bt.provider_name == "balltree_haversine"
    assert res_oracle.core_count + res_oracle.border_count + res_oracle.noise_count == 60
    assert np.array_equal(res_oracle.labels, res_bt.labels)
    assert res_oracle.roles == res_bt.roles
    assert res_oracle.cluster_member_counts == res_bt.cluster_member_counts
