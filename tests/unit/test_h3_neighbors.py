"""Comprehensive correctness and completeness verification tests for H3 neighborhood provider.

Covers all 27 required and adversarial test fixture categories:
 1. Same-cell neighbors.
 2. Adjacent-cell neighbors.
 3. Eligible points separated by more than one H3 ring (e.g. resolution 9 with k=2).
 4. Points on opposite sides of an H3 cell boundary.
 5. Points exactly at the spatial threshold.
 6. Points exactly at the temporal threshold.
 7. Temporal-bin boundary crossing and inclusive windowing.
 8. Dense single-cell observations.
 9. Sparse isolated observations.
10. H3 pentagons and nearby cells (including pentagon fallback).
11. High-latitude coordinates.
12. Antimeridian crossing (+/- 180 deg).
13. Multiple H3 resolutions (7, 8, 9).
14. Randomized global observations compared against independent brute-force oracle.
15. Input permutation invariance.
16. Repeated-run determinism.
17. Empty inputs (N = 0).
18. Invalid configuration detection.
19. Data-quality filtering compatibility.
20. Fallback correctness and diagnostic logging.
21. Undersized k-ring rejection.
22. Forced grid_disk failure triggers fallback.
23. Forced grid_disk failure raises when fallback is disabled.
24. Near-pentagon hexagon fallback.
25. Cell vertex and boundary adversarial pairs.
26. Multi-region oracle parity (Equator, English Channel, Arctic).
27. Spatial radii near clearance boundaries (k-ring transitions).
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import h3
import numpy as np
import pytest

from aegismar.clustering.balltree_neighbors import BallTreeNeighborhoodProvider
from aegismar.clustering.config import (
    QualityFilterPolicy,
    STDBSCANConfig,
)
from aegismar.clustering.h3_neighbors import H3NeighborhoodProvider, compute_safe_k_ring
from aegismar.clustering.st_dbscan import run_h3_st_dbscan, run_st_dbscan
from aegismar.clustering.types import (
    ClusteringInputDataset,
    ObservationRecord,
    build_clustering_dataset,
)
from aegismar.common.constants import FLAG_TIMESTAMP_POSITION_CONFLICT
from aegismar.spatial.oracle import (
    OracleVerificationReport,
    verify_provider_against_oracle,
)

BASE_TIME = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)


def _assert_oracle_parity(report: OracleVerificationReport) -> None:
    """Assert mandatory correctness invariants against the brute-force oracle."""
    assert report.missing_neighbor_count == 0, (
        f"Missing neighbors detected: {report.missing_neighbor_count}"
    )
    assert report.extra_neighbor_count == 0, (
        f"Extra neighbors detected: {report.extra_neighbor_count}"
    )
    assert report.exact_neighborhood_match is True
    assert report.exact_role_match is True
    assert report.exact_label_match is True


def _assert_h3_balltree_parity(
    dataset: ClusteringInputDataset,
    config: STDBSCANConfig,
    h3_provider: H3NeighborhoodProvider,
    bt_provider: BallTreeNeighborhoodProvider,
) -> None:
    """Assert 100% exact parity between H3 and BallTree on identical inputs."""
    h3_graph = h3_provider.build_neighborhood_graph()
    bt_graph = bt_provider.build_neighborhood_graph()

    assert h3_graph.num_points == bt_graph.num_points
    assert h3_graph.total_edges == bt_graph.total_edges, (
        f"Edge count mismatch: H3={h3_graph.total_edges}, BT={bt_graph.total_edges}"
    )

    n = dataset.num_points
    for i in range(n):
        h3_nbrs = h3_graph.neighbors_of(i)
        bt_nbrs = bt_graph.neighbors_of(i)
        np.testing.assert_array_equal(
            h3_nbrs,
            bt_nbrs,
            err_msg=f"Neighborhood mismatch at index {i}",
        )

    h3_res = run_st_dbscan(dataset, config, h3_provider)
    bt_res = run_st_dbscan(dataset, config, bt_provider)

    assert h3_res.num_clusters == bt_res.num_clusters
    assert h3_res.core_count == bt_res.core_count
    assert h3_res.border_count == bt_res.border_count
    assert h3_res.noise_count == bt_res.noise_count
    assert h3_res.roles == bt_res.roles
    np.testing.assert_array_equal(h3_res.labels, bt_res.labels)


# ---------------------------------------------------------------------------
# Fixture 1: Same-cell neighbors
# ---------------------------------------------------------------------------
def test_01_same_cell_neighbors() -> None:
    """Fixture 1: Observations co-located within the same H3 cell are correctly identified."""
    center_lat, center_lon = 33.7400, -118.2700
    records = [
        ObservationRecord(1, "111111111", BASE_TIME, center_lat, center_lon),
        ObservationRecord(
            2,
            "222222222",
            BASE_TIME + timedelta(seconds=60),
            center_lat + 0.0002,
            center_lon + 0.0002,
        ),
        ObservationRecord(
            3,
            "333333333",
            BASE_TIME + timedelta(seconds=120),
            center_lat - 0.0002,
            center_lon - 0.0002,
        ),
        ObservationRecord(
            4,
            "444444444",
            BASE_TIME + timedelta(seconds=180),
            center_lat + 0.0001,
            center_lon - 0.0001,
        ),
        ObservationRecord(
            5,
            "555555555",
            BASE_TIME + timedelta(seconds=240),
            center_lat - 0.0001,
            center_lon + 0.0001,
        ),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=3)
    prov = H3NeighborhoodProvider(ds, cfg, resolution=8)
    report = verify_provider_against_oracle(ds, cfg, prov)
    _assert_oracle_parity(report)


# ---------------------------------------------------------------------------
# Fixture 2: Adjacent-cell neighbors
# ---------------------------------------------------------------------------
def test_02_adjacent_cell_neighbors() -> None:
    """Fixture 2: Observations in adjacent 1-ring H3 cells are correctly retrieved."""
    # Find two adjacent cell centers at resolution 8
    c1 = h3.latlng_to_cell(33.7400, -118.2700, 8)
    disk = list(h3.grid_disk(c1, 1))
    c2 = disk[1]  # Adjacent neighbor cell
    lat1, lon1 = h3.cell_to_latlng(c1)
    lat2, lon2 = h3.cell_to_latlng(c2)

    records = [
        ObservationRecord(1, "111111111", BASE_TIME, lat1, lon1),
        ObservationRecord(2, "222222222", BASE_TIME + timedelta(seconds=100), lat2, lon2),
    ]
    ds = build_clustering_dataset(records)
    dist_m = h3.great_circle_distance((lat1, lon1), (lat2, lon2), unit="m")
    cfg = STDBSCANConfig(eps_spatial_m=dist_m + 50.0, eps_temporal_s=900.0, min_samples=2)
    prov = H3NeighborhoodProvider(ds, cfg, resolution=8)
    report = verify_provider_against_oracle(ds, cfg, prov)
    _assert_oracle_parity(report)
    assert report.total_provider_edges == 4  # Both mutually see each other (2 + 2)


# ---------------------------------------------------------------------------
# Fixture 3: Multi-ring neighbors (resolution 9 with k=2)
# ---------------------------------------------------------------------------
def test_03_multi_ring_candidate_completeness() -> None:
    """Fixture 3: At resolution 9 with eps_spatial=300m, k=2 rings are required and complete."""
    center_lat, center_lon = 33.7400, -118.2700
    # Two points ~250m apart (which spans across ring 1 into ring 2 at resolution 9)
    # 0.0022 deg latitude is ~244 m
    records = [
        ObservationRecord(1, "111111111", BASE_TIME, center_lat, center_lon),
        ObservationRecord(
            2, "222222222", BASE_TIME + timedelta(seconds=60), center_lat + 0.0022, center_lon
        ),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=2)

    # Safe k-ring for res 9 with 300m must be >= 2
    safe_k = compute_safe_k_ring(9, 300.0)
    assert safe_k >= 2

    prov = H3NeighborhoodProvider(ds, cfg, resolution=9)
    assert prov.k_ring >= 2
    report = verify_provider_against_oracle(ds, cfg, prov)
    _assert_oracle_parity(report)


# ---------------------------------------------------------------------------
# Fixture 4: Opposite sides of a cell boundary
# ---------------------------------------------------------------------------
def test_04_opposite_sides_of_cell_boundary() -> None:
    """Fixture 4: Observations placed 5 meters apart on opposite sides of an H3 cell boundary."""
    c = h3.latlng_to_cell(33.7400, -118.2700, 8)
    boundary = h3.cell_to_boundary(c)
    # Take middle of first edge
    p1 = boundary[0]
    p2 = boundary[1]
    edge_mid_lat = 0.5 * (p1[0] + p2[0])
    edge_mid_lon = 0.5 * (p1[1] + p2[1])

    # Offset by +/- 0.00003 deg (~3.3 meters) perpendicular to boundary
    pt_inside = (edge_mid_lat - 0.00003, edge_mid_lon)
    pt_outside = (edge_mid_lat + 0.00003, edge_mid_lon)

    records = [
        ObservationRecord(1, "111111111", BASE_TIME, pt_inside[0], pt_inside[1]),
        ObservationRecord(
            2, "222222222", BASE_TIME + timedelta(seconds=30), pt_outside[0], pt_outside[1]
        ),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=50.0, eps_temporal_s=900.0, min_samples=2)
    prov = H3NeighborhoodProvider(ds, cfg, resolution=8)
    report = verify_provider_against_oracle(ds, cfg, prov)
    _assert_oracle_parity(report)


# ---------------------------------------------------------------------------
# Fixture 5: Points exactly at the spatial threshold
# ---------------------------------------------------------------------------
def test_05_points_exactly_at_spatial_threshold() -> None:
    """Fixture 5: Points placed exactly at eps_spatial_m boundary are inclusive."""
    center_lat, center_lon = 33.7400, -118.2700
    eps_m = 300.0
    # Great-circle displacement along meridian: dlat = eps_m / R * (180 / pi)
    dlat_deg = (eps_m / 6371008.8) * (180.0 / 3.141592653589793)

    records = [
        ObservationRecord(1, "111111111", BASE_TIME, center_lat, center_lon),
        ObservationRecord(2, "222222222", BASE_TIME, center_lat + dlat_deg, center_lon),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=eps_m, eps_temporal_s=900.0, min_samples=2)
    h3_prov = H3NeighborhoodProvider(ds, cfg, resolution=8)
    bt_prov = BallTreeNeighborhoodProvider(ds, cfg)
    _assert_h3_balltree_parity(ds, cfg, h3_prov, bt_prov)


# ---------------------------------------------------------------------------
# Fixture 6: Points exactly at the temporal threshold
# ---------------------------------------------------------------------------
def test_06_points_exactly_at_temporal_threshold() -> None:
    """Fixture 6: Points separated by exactly eps_temporal_s are inclusive."""
    center_lat, center_lon = 33.7400, -118.2700
    records = [
        ObservationRecord(1, "111111111", BASE_TIME, center_lat, center_lon),
        ObservationRecord(
            2, "222222222", BASE_TIME + timedelta(seconds=900), center_lat, center_lon
        ),
        ObservationRecord(
            3, "333333333", BASE_TIME + timedelta(seconds=901), center_lat, center_lon
        ),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=2)
    h3_prov = H3NeighborhoodProvider(ds, cfg, resolution=8)
    report = verify_provider_against_oracle(ds, cfg, h3_prov)
    _assert_oracle_parity(report)
    # Point 1 sees point 2 (dt=900s), but not point 3 (dt=901s)
    nbrs_1 = h3_prov.query_neighbors(0)
    assert 1 in nbrs_1
    assert 2 not in nbrs_1


# ---------------------------------------------------------------------------
# Fixture 7: Temporal-bin boundary crossing and inclusive windowing
# ---------------------------------------------------------------------------
def test_07_temporal_window_traversal() -> None:
    """Fixture 7: Multiple observations spanning wide temporal intervals across bins."""
    center_lat, center_lon = 33.7400, -118.2700
    records = [
        ObservationRecord(
            i + 1, f"36600000{i}", BASE_TIME + timedelta(minutes=i * 5), center_lat, center_lon
        )
        for i in range(12)  # Spans 0 to 55 minutes (at 15-min eps_temporal, sliding window moves)
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=3)
    h3_prov = H3NeighborhoodProvider(ds, cfg, resolution=8)
    report = verify_provider_against_oracle(ds, cfg, h3_prov)
    _assert_oracle_parity(report)


# ---------------------------------------------------------------------------
# Fixture 8: Dense single-cell observations
# ---------------------------------------------------------------------------
def test_08_dense_single_cell_observations() -> None:
    """Fixture 8: Dense cluster of 60 points packed into one H3 cell."""
    center_lat, center_lon = 33.7400, -118.2700
    rng = random.Random(42)
    records = [
        ObservationRecord(
            i + 1,
            f"3660000{i:02d}",
            BASE_TIME + timedelta(seconds=rng.randint(0, 600)),
            center_lat + rng.uniform(-0.0005, 0.0005),
            center_lon + rng.uniform(-0.0005, 0.0005),
        )
        for i in range(60)
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=5)
    h3_prov = H3NeighborhoodProvider(ds, cfg, resolution=8)
    report = verify_provider_against_oracle(ds, cfg, h3_prov)
    _assert_oracle_parity(report)


# ---------------------------------------------------------------------------
# Fixture 9: Sparse isolated observations (all noise)
# ---------------------------------------------------------------------------
def test_09_sparse_isolated_observations() -> None:
    """Fixture 9: Observations spaced far apart in space/time classify 100% as noise."""
    records = [
        ObservationRecord(1, "111111111", BASE_TIME, 33.0, -118.0),
        ObservationRecord(2, "222222222", BASE_TIME, 34.0, -118.0),
        ObservationRecord(3, "333333333", BASE_TIME, 35.0, -118.0),
        ObservationRecord(4, "444444444", BASE_TIME, 36.0, -118.0),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=2)
    h3_prov = H3NeighborhoodProvider(ds, cfg, resolution=8)
    report = verify_provider_against_oracle(ds, cfg, h3_prov)
    _assert_oracle_parity(report)
    res = run_st_dbscan(ds, cfg, h3_prov)
    assert res.num_clusters == 0
    assert res.noise_count == 4
    assert res.core_count == 0


# ---------------------------------------------------------------------------
# Fixture 10: H3 pentagons and nearby cells
# ---------------------------------------------------------------------------
def test_10_pentagon_neighborhood_completeness() -> None:
    """Fixture 10: Observations located directly in and around H3 pentagon cells."""
    pentagons = list(h3.get_pentagons(8))
    p = pentagons[0]  # e.g. 64.7°N, 10.5°E in Norway
    lat_p, lon_p = h3.cell_to_latlng(p)

    records = [
        ObservationRecord(1, "111111111", BASE_TIME, lat_p, lon_p),
        ObservationRecord(
            2, "222222222", BASE_TIME + timedelta(seconds=60), lat_p + 0.0005, lon_p + 0.0005
        ),
        ObservationRecord(
            3, "333333333", BASE_TIME + timedelta(seconds=120), lat_p - 0.0005, lon_p - 0.0005
        ),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=2)

    # Test with standard H3 pentagon indexing
    h3_prov = H3NeighborhoodProvider(ds, cfg, resolution=8, fallback_on_pentagons=False)
    bt_prov = BallTreeNeighborhoodProvider(ds, cfg)
    _assert_h3_balltree_parity(ds, cfg, h3_prov, bt_prov)

    # Test with explicit pentagon fallback enabled
    h3_fb = H3NeighborhoodProvider(ds, cfg, resolution=8, fallback_on_pentagons=True)
    _assert_h3_balltree_parity(ds, cfg, h3_fb, bt_prov)
    assert h3_fb.fallback_count > 0


# ---------------------------------------------------------------------------
# Fixture 11: High-latitude coordinates
# ---------------------------------------------------------------------------
def test_11_high_latitude_coordinates() -> None:
    """Fixture 11: Polar observations at 85°N where meridians converge tightly."""
    high_lat = 85.0
    records = [
        ObservationRecord(1, "111111111", BASE_TIME, high_lat, 0.0),
        ObservationRecord(2, "222222222", BASE_TIME + timedelta(seconds=30), high_lat, 0.05),
        ObservationRecord(3, "333333333", BASE_TIME + timedelta(seconds=60), high_lat + 0.001, 0.0),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=500.0, eps_temporal_s=900.0, min_samples=2)
    h3_prov = H3NeighborhoodProvider(ds, cfg, resolution=8)
    report = verify_provider_against_oracle(ds, cfg, h3_prov)
    _assert_oracle_parity(report)


# ---------------------------------------------------------------------------
# Fixture 12: Antimeridian crossing (+/- 180 deg)
# ---------------------------------------------------------------------------
def test_12_antimeridian_crossing() -> None:
    """Fixture 12: Observations straddling the 180° meridian in the Pacific."""
    records = [
        ObservationRecord(1, "111111111", BASE_TIME, 0.0, 179.999),
        ObservationRecord(2, "222222222", BASE_TIME + timedelta(seconds=30), 0.0, -179.999),
        ObservationRecord(3, "333333333", BASE_TIME + timedelta(seconds=60), 0.001, 179.999),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=2)
    h3_prov = H3NeighborhoodProvider(ds, cfg, resolution=8)
    report = verify_provider_against_oracle(ds, cfg, h3_prov)
    _assert_oracle_parity(report)
    bt_prov = BallTreeNeighborhoodProvider(ds, cfg)
    _assert_h3_balltree_parity(ds, cfg, h3_prov, bt_prov)


# ---------------------------------------------------------------------------
# Fixture 13: Multiple H3 resolutions (7, 8, 9)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("res", [7, 8, 9])
def test_13_multiple_h3_resolutions(res: int) -> None:
    """Fixture 13: H3 provider yields 100% oracle match across resolutions 7, 8, and 9."""
    center_lat, center_lon = 33.7400, -118.2700
    rng = random.Random(123)
    records = [
        ObservationRecord(
            i + 1,
            f"3660000{i}",
            BASE_TIME + timedelta(seconds=rng.randint(0, 600)),
            center_lat + rng.uniform(-0.001, 0.001),
            center_lon + rng.uniform(-0.001, 0.001),
        )
        for i in range(25)
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=3)
    prov = H3NeighborhoodProvider(ds, cfg, resolution=res)
    report = verify_provider_against_oracle(ds, cfg, prov)
    _assert_oracle_parity(report)


# ---------------------------------------------------------------------------
# Fixture 14: Randomized global observations compared against oracle
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("seed", "n_points", "eps_spatial_m", "eps_temporal_s", "min_samples"),
    [
        (101, 120, 300.0, 900.0, 5),
        (202, 150, 200.0, 600.0, 3),
        (303, 180, 500.0, 1200.0, 6),
        (404, 100, 150.0, 300.0, 4),
    ],
)
def test_14_randomized_datasets_match_oracle(
    seed: int,
    n_points: int,
    eps_spatial_m: float,
    eps_temporal_s: float,
    min_samples: int,
) -> None:
    """Fixture 14: Multi-cluster randomized datasets match independent oracle 100%."""
    rng = random.Random(seed)
    center_lat, center_lon = 33.74, -118.20
    centers = [
        (
            center_lat + rng.uniform(-0.015, 0.015),
            center_lon + rng.uniform(-0.015, 0.015),
            rng.randint(0, 3600),
        )
        for _ in range(4)
    ]
    records: list[ObservationRecord] = []
    for i in range(n_points):
        if rng.random() < 0.75:
            c_lat, c_lon, c_t = rng.choice(centers)
            lat = max(-89.9, min(89.9, c_lat + rng.gauss(0.0, 0.0018)))
            lon = c_lon + rng.gauss(0.0, 0.0018)
            t_offset = max(0.0, c_t + rng.gauss(0.0, 450.0))
        else:
            lat = max(-89.9, min(89.9, center_lat + rng.uniform(-0.015, 0.015)))
            lon = center_lon + rng.uniform(-0.015, 0.015)
            t_offset = rng.uniform(0.0, 3600.0)

        records.append(
            ObservationRecord(
                source_row=i + 1,
                mmsi=f"36600{i % 25:04d}",
                timestamp_utc=BASE_TIME + timedelta(seconds=t_offset),
                latitude=lat,
                longitude=lon,
            )
        )

    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(
        eps_spatial_m=eps_spatial_m,
        eps_temporal_s=eps_temporal_s,
        min_samples=min_samples,
    )
    prov = H3NeighborhoodProvider(ds, cfg, resolution=8)
    report = verify_provider_against_oracle(ds, cfg, prov)
    _assert_oracle_parity(report)


# ---------------------------------------------------------------------------
# Fixture 15: Input permutation invariance
# ---------------------------------------------------------------------------
def test_15_input_permutation_invariance() -> None:
    """Fixture 15: Shuffling the raw input records produces identical H3 cluster results."""
    rng = random.Random(999)
    center_lat, center_lon = 33.74, -118.20
    base_records = [
        ObservationRecord(
            source_row=i + 1,
            mmsi=f"36600{i % 10:04d}",
            timestamp_utc=BASE_TIME + timedelta(seconds=rng.randint(0, 1800)),
            latitude=center_lat + rng.uniform(-0.005, 0.005),
            longitude=center_lon + rng.uniform(-0.005, 0.005),
        )
        for i in range(50)
    ]

    shuffled_records = base_records.copy()
    rng.shuffle(shuffled_records)

    ds1 = build_clustering_dataset(base_records)
    ds2 = build_clustering_dataset(shuffled_records)

    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=3)

    res1 = run_h3_st_dbscan(ds1, cfg, resolution=8)
    res2 = run_h3_st_dbscan(ds2, cfg, resolution=8)

    assert res1.num_clusters == res2.num_clusters
    assert res1.core_count == res2.core_count
    assert res1.border_count == res2.border_count
    assert res1.noise_count == res2.noise_count
    assert res1.roles == res2.roles
    np.testing.assert_array_equal(res1.labels, res2.labels)


# ---------------------------------------------------------------------------
# Fixture 16: Repeated-run determinism
# ---------------------------------------------------------------------------
def test_16_repeated_run_determinism() -> None:
    """Fixture 16: Executing H3 ST-DBSCAN repeatedly on the same dataset yields identical output."""
    center_lat, center_lon = 33.74, -118.20
    records = [
        ObservationRecord(
            i + 1,
            f"3660000{i % 5}",
            BASE_TIME + timedelta(seconds=i * 60),
            center_lat + i * 0.0001,
            center_lon + i * 0.0001,
        )
        for i in range(30)
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=3)

    res1 = run_h3_st_dbscan(ds, cfg, resolution=8)
    res2 = run_h3_st_dbscan(ds, cfg, resolution=8)

    np.testing.assert_array_equal(res1.labels, res2.labels)
    assert res1.roles == res2.roles
    assert res1.num_clusters == res2.num_clusters


# ---------------------------------------------------------------------------
# Fixture 17: Empty inputs (N = 0)
# ---------------------------------------------------------------------------
def test_17_empty_inputs() -> None:
    """Fixture 17: Empty input dataset returns an empty NeighborhoodGraph cleanly."""
    ds = build_clustering_dataset([])
    cfg = STDBSCANConfig()
    prov = H3NeighborhoodProvider(ds, cfg, resolution=8)

    assert prov.num_points == 0
    graph = prov.build_neighborhood_graph()
    assert graph.num_points == 0
    assert graph.total_edges == 0

    res = run_h3_st_dbscan(ds, cfg)
    assert res.num_clusters == 0
    assert res.core_count == 0
    assert res.border_count == 0
    assert res.noise_count == 0


# ---------------------------------------------------------------------------
# Fixture 18: Invalid configuration detection
# ---------------------------------------------------------------------------
def test_18_invalid_configuration() -> None:
    """Fixture 18: Invalid resolutions, negative radii, or malformed parameters raise ValueError."""
    ds = build_clustering_dataset([ObservationRecord(1, "111111111", BASE_TIME, 33.74, -118.27)])
    cfg = STDBSCANConfig()

    with pytest.raises(ValueError, match="H3 resolution must be between 0 and 15"):
        H3NeighborhoodProvider(ds, cfg, resolution=99)

    with pytest.raises(ValueError, match="k_ring must be >= 1"):
        H3NeighborhoodProvider(ds, cfg, resolution=8, k_ring=0)

    with pytest.raises(ValueError, match="provider must be one of"):
        STDBSCANConfig(provider="invalid_provider")

    with pytest.raises(ValueError, match="h3_resolution must be an integer"):
        STDBSCANConfig(h3_resolution=cast(Any, "invalid"))

    with pytest.raises(ValueError, match="h3_resolution must be between 0 and 15"):
        STDBSCANConfig(h3_resolution=99)


# ---------------------------------------------------------------------------
# Fixture 19: Data-quality filtering compatibility
# ---------------------------------------------------------------------------
def test_19_data_quality_filtering_compatibility() -> None:
    """Fixture 19: Data-quality filter policies exclude conflict rows identically under H3."""
    records = [
        ObservationRecord(1, "111111111", BASE_TIME, 33.74, -118.27),
        ObservationRecord(
            2,
            "111111111",
            BASE_TIME,
            33.75,
            -118.28,
            quality_flags=(FLAG_TIMESTAMP_POSITION_CONFLICT,),
        ),
        ObservationRecord(3, "111111111", BASE_TIME + timedelta(seconds=60), 33.7401, -118.2701),
        ObservationRecord(4, "111111111", BASE_TIME + timedelta(seconds=120), 33.7402, -118.2702),
    ]
    policy = QualityFilterPolicy(exclude_timestamp_conflicts=True)
    ds = build_clustering_dataset(records, quality_filter=policy)
    assert ds.excluded_count == 1
    assert ds.num_points == 3

    cfg = STDBSCANConfig(quality_filter=policy, min_samples=2)
    h3_prov = H3NeighborhoodProvider(ds, cfg, resolution=8)
    bt_prov = BallTreeNeighborhoodProvider(ds, cfg)
    _assert_h3_balltree_parity(ds, cfg, h3_prov, bt_prov)


# ---------------------------------------------------------------------------
# Fixture 20: Fallback correctness and logging
# ---------------------------------------------------------------------------
def test_20_fallback_correctness_and_metrics() -> None:
    """Fixture 20: Explicit fallback mechanism produces 100% correct results and logs metrics."""
    cfg = STDBSCANConfig(min_samples=2)

    # Force fallback on pentagons when near a pentagon
    pentagons = list(h3.get_pentagons(8))
    lat_p, lon_p = h3.cell_to_latlng(pentagons[0])
    p_records = [
        ObservationRecord(1, "111111111", BASE_TIME, lat_p, lon_p),
        ObservationRecord(
            2, "222222222", BASE_TIME + timedelta(seconds=30), lat_p + 0.0001, lon_p + 0.0001
        ),
    ]
    p_ds = build_clustering_dataset(p_records)

    prov = H3NeighborhoodProvider(p_ds, cfg, resolution=8, fallback_on_pentagons=True)
    metrics_before = prov.get_metrics()
    assert metrics_before["fallback_count"] == 0

    # Build graph triggers fallback for pentagon observations
    _ = prov.build_neighborhood_graph()
    metrics_after = prov.get_metrics()
    assert metrics_after["fallback_count"] == 2
    assert metrics_after["fallback_time_seconds"] >= 0.0

    # Fallback results must match BallTree 100%
    bt_prov = BallTreeNeighborhoodProvider(p_ds, cfg)
    _assert_h3_balltree_parity(p_ds, cfg, prov, bt_prov)


# ---------------------------------------------------------------------------
# Fixture 21: Undersized k-ring rejection
# ---------------------------------------------------------------------------
def test_21_undersized_k_ring_rejected() -> None:
    """Fixture 21: Configured k_ring smaller than safe completeness bound raises ValueError."""
    records = [
        ObservationRecord(1, "111111111", BASE_TIME, 33.74, -118.27),
        ObservationRecord(2, "222222222", BASE_TIME + timedelta(seconds=60), 33.7402, -118.2702),
    ]
    ds = build_clustering_dataset(records)

    # Resolution 9 with eps_spatial 300m requires safe_k >= 2
    cfg_safe = STDBSCANConfig(eps_spatial_m=300.0, h3_resolution=9)
    assert compute_safe_k_ring(9, 300.0) >= 2

    # Direct argument override with undersized k=1
    with pytest.raises(ValueError, match="smaller than required safe completeness bound"):
        H3NeighborhoodProvider(ds, cfg_safe, resolution=9, k_ring=1)

    # Configuration object specifying undersized k=1
    cfg_undersized = STDBSCANConfig(eps_spatial_m=300.0, h3_resolution=9, h3_k_ring=1)
    with pytest.raises(ValueError, match="smaller than required safe completeness bound"):
        H3NeighborhoodProvider(ds, cfg_undersized)


# ---------------------------------------------------------------------------
# Fixture 22: Forced grid_disk failure triggers fallback
# ---------------------------------------------------------------------------
def test_22_forced_grid_disk_failure_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture 22: Forced grid_disk failure marks cells for fallback, preserving 100% parity."""
    records = [
        ObservationRecord(1, "111111111", BASE_TIME, 33.74, -118.27),
        ObservationRecord(2, "222222222", BASE_TIME + timedelta(seconds=60), 33.7401, -118.2701),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, min_samples=2)

    target_cell = h3.latlng_to_cell(33.74, -118.27, 8)
    real_grid_disk = h3.grid_disk

    def faulty_grid_disk(origin: str, k: int) -> set[str]:
        if origin == target_cell:
            raise RuntimeError("Simulated H3 grid_disk failure")
        return set(real_grid_disk(origin, k))

    monkeypatch.setattr(h3, "grid_disk", faulty_grid_disk)

    # With fallback enabled (default), index builds cleanly and marks the cell for fallback
    prov = H3NeighborhoodProvider(ds, cfg, resolution=8, enable_fallback=True)
    assert target_cell in prov.cells_requiring_fallback

    # Neighborhood graph queries route through fallback provider
    _ = prov.build_neighborhood_graph()
    metrics = prov.get_metrics()
    assert metrics["fallback_count"] == 2
    assert any("grid_disk_failed" in reason for reason in metrics["fallback_reasons"])

    bt_prov = BallTreeNeighborhoodProvider(ds, cfg)
    _assert_h3_balltree_parity(ds, cfg, prov, bt_prov)


# ---------------------------------------------------------------------------
# Fixture 23: Forced grid_disk failure raises when fallback is disabled
# ---------------------------------------------------------------------------
def test_23_forced_grid_disk_failure_disabled_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fixture 23: Simulated grid_disk failure raises RuntimeError when fallback is disabled."""
    records = [
        ObservationRecord(1, "111111111", BASE_TIME, 33.74, -118.27),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, h3_enable_fallback=False)

    def failing_grid_disk(_origin: str, _k: int) -> set[str]:
        raise RuntimeError("Fatal grid_disk exception")

    monkeypatch.setattr(h3, "grid_disk", failing_grid_disk)

    with pytest.raises(RuntimeError, match="grid_disk expansion failed.*fallback is disabled"):
        H3NeighborhoodProvider(ds, cfg, resolution=8, enable_fallback=False)


# ---------------------------------------------------------------------------
# Fixture 24: Near-pentagon hexagon fallback
# ---------------------------------------------------------------------------
def test_24_near_pentagon_hex_fallback() -> None:
    """Fixture 24: Hexagons adjacent to pentagons trigger fallback when configured."""
    pentagons = list(h3.get_pentagons(8))
    pentagon_cell = pentagons[0]
    disk = list(h3.grid_disk(pentagon_cell, 1))
    # Pick a neighbor cell that is a regular hexagon (not a pentagon itself)
    hex_nbr = next(nbr for nbr in disk if not h3.is_pentagon(nbr))

    lat_hex, lon_hex = h3.cell_to_latlng(hex_nbr)
    records = [
        ObservationRecord(1, "111111111", BASE_TIME, lat_hex, lon_hex),
        ObservationRecord(
            2,
            "222222222",
            BASE_TIME + timedelta(seconds=30),
            lat_hex + 0.0001,
            lon_hex + 0.0001,
        ),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(min_samples=2)

    # 1. Fallback on pentagons enabled: near-pentagon hex must trigger fallback
    prov_fb = H3NeighborhoodProvider(
        ds, cfg, resolution=8, enable_fallback=True, fallback_on_pentagons=True
    )
    assert hex_nbr in prov_fb.cells_requiring_fallback
    _ = prov_fb.build_neighborhood_graph()
    assert prov_fb.fallback_count == 2
    assert prov_fb.fallback_reasons.get("pentagon_or_near_pentagon") == 2

    bt_prov = BallTreeNeighborhoodProvider(ds, cfg)
    _assert_h3_balltree_parity(ds, cfg, prov_fb, bt_prov)

    # 2. Fallback on pentagons enabled but fallback disabled: must fail closed on __init__
    with pytest.raises(RuntimeError, match="in or near an H3 pentagon and fallback is disabled"):
        H3NeighborhoodProvider(
            ds, cfg, resolution=8, enable_fallback=False, fallback_on_pentagons=True
        )


# ---------------------------------------------------------------------------
# Fixture 25: Cell vertex and boundary adversarial pairs
# ---------------------------------------------------------------------------
def test_25_cell_vertex_and_boundary_adversarial_pairs() -> None:
    """Fixture 25: Observations placed within sub-meter distances across cell vertices."""
    c = h3.latlng_to_cell(33.7400, -118.2700, 8)
    vertices = h3.cell_to_boundary(c)

    records: list[ObservationRecord] = []
    obs_id = 1
    # For each vertex, place a pair of points across the vertex boundary separated by ~0.5m
    for v_lat, v_lon in vertices:
        records.append(
            ObservationRecord(
                obs_id,
                f"3660000{obs_id:02d}",
                BASE_TIME,
                v_lat - 0.000004,
                v_lon - 0.000004,
            )
        )
        obs_id += 1
        records.append(
            ObservationRecord(
                obs_id,
                f"3660000{obs_id:02d}",
                BASE_TIME + timedelta(seconds=10),
                v_lat + 0.000004,
                v_lon + 0.000004,
            )
        )
        obs_id += 1

    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=50.0, eps_temporal_s=900.0, min_samples=2)

    h3_prov = H3NeighborhoodProvider(ds, cfg, resolution=8)
    bt_prov = BallTreeNeighborhoodProvider(ds, cfg)
    _assert_h3_balltree_parity(ds, cfg, h3_prov, bt_prov)

    oracle_report = verify_provider_against_oracle(ds, cfg, h3_prov)
    _assert_oracle_parity(oracle_report)


# ---------------------------------------------------------------------------
# Fixture 26: Multi-region oracle parity
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("region_name", "base_lat", "base_lon"),
    [
        ("equator_singapore", 1.3521, 103.8198),
        ("english_channel_dover", 51.1279, 1.3134),
        ("arctic_tromso", 69.6492, 18.9553),
    ],
)
def test_26_multi_region_oracle_parity(region_name: str, base_lat: float, base_lon: float) -> None:
    """Fixture 26: Candidate coverage and oracle parity across geographically diverse regions."""
    assert region_name is not None
    records = [
        ObservationRecord(1, "111111111", BASE_TIME, base_lat, base_lon),
        ObservationRecord(
            2,
            "222222222",
            BASE_TIME + timedelta(seconds=60),
            base_lat + 0.001,
            base_lon + 0.001,
        ),
        ObservationRecord(
            3,
            "333333333",
            BASE_TIME + timedelta(seconds=120),
            base_lat - 0.001,
            base_lon - 0.001,
        ),
        ObservationRecord(
            4,
            "444444444",
            BASE_TIME + timedelta(seconds=180),
            base_lat + 0.0005,
            base_lon - 0.0005,
        ),
        ObservationRecord(
            5,
            "555555555",
            BASE_TIME + timedelta(seconds=240),
            base_lat + 0.05,
            base_lon + 0.05,
        ),  # Distant noise
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=2)

    for res in (7, 8, 9):
        prov = H3NeighborhoodProvider(ds, cfg, resolution=res)
        oracle_report = verify_provider_against_oracle(ds, cfg, prov)
        _assert_oracle_parity(oracle_report)

        bt_prov = BallTreeNeighborhoodProvider(ds, cfg)
        _assert_h3_balltree_parity(ds, cfg, prov, bt_prov)


# ---------------------------------------------------------------------------
# Fixture 27: Spatial radii near clearance boundaries
# ---------------------------------------------------------------------------
def test_27_spatial_radii_near_clearance_boundaries() -> None:
    """Fixture 27: Verify ring transitions and candidate completeness near clearance boundaries."""
    records = [
        ObservationRecord(1, "111111111", BASE_TIME, 33.74, -118.27),
        ObservationRecord(2, "222222222", BASE_TIME + timedelta(seconds=60), 33.742, -118.272),
    ]
    ds = build_clustering_dataset(records)

    # Resolution 8 threshold between k=1 and k=2 is 395.0 m
    # eps = 394.0 m -> safe_k == 1
    cfg_394 = STDBSCANConfig(eps_spatial_m=394.0)
    prov_394 = H3NeighborhoodProvider(ds, cfg_394, resolution=8)
    assert prov_394.k_ring == 1
    bt_prov_394 = BallTreeNeighborhoodProvider(ds, cfg_394)
    _assert_h3_balltree_parity(ds, cfg_394, prov_394, bt_prov_394)

    # eps = 396.0 m -> safe_k == 2
    cfg_396 = STDBSCANConfig(eps_spatial_m=396.0)
    prov_396 = H3NeighborhoodProvider(ds, cfg_396, resolution=8)
    assert prov_396.k_ring == 2
    bt_prov_396 = BallTreeNeighborhoodProvider(ds, cfg_396)
    _assert_h3_balltree_parity(ds, cfg_396, prov_396, bt_prov_396)

    # Resolution 9 threshold between k=1 and k=2 is 141.0 m
    cfg_140 = STDBSCANConfig(eps_spatial_m=140.0)
    prov_140 = H3NeighborhoodProvider(ds, cfg_140, resolution=9)
    assert prov_140.k_ring == 1
    bt_prov_140 = BallTreeNeighborhoodProvider(ds, cfg_140)
    _assert_h3_balltree_parity(ds, cfg_140, prov_140, bt_prov_140)

    cfg_142 = STDBSCANConfig(eps_spatial_m=142.0)
    prov_142 = H3NeighborhoodProvider(ds, cfg_142, resolution=9)
    assert prov_142.k_ring == 2
    bt_prov_142 = BallTreeNeighborhoodProvider(ds, cfg_142)
    _assert_h3_balltree_parity(ds, cfg_142, prov_142, bt_prov_142)
