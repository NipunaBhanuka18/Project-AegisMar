"""Unit and boundary tests for reference BallTree ST-DBSCAN clustering (all 16 fixtures)."""

from __future__ import annotations

import json
import math
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from aegismar.clustering.balltree_neighbors import BallTreeNeighborhoodProvider
from aegismar.clustering.config import QualityFilterPolicy, STDBSCANConfig
from aegismar.clustering.export import (
    export_clustering_artifacts,
    get_cluster_assignments_arrow_schema,
)
from aegismar.clustering.st_dbscan import run_balltree_st_dbscan, run_st_dbscan
from aegismar.clustering.types import (
    NOISE_CLUSTER_ID,
    POINT_ROLE_BORDER,
    POINT_ROLE_CORE,
    POINT_ROLE_NOISE,
    ObservationRecord,
    build_clustering_dataset,
    load_clustering_dataset_from_parquet,
)
from aegismar.common.constants import (
    FLAG_TIMESTAMP_METADATA_CONFLICT,
    FLAG_TIMESTAMP_POSITION_CONFLICT,
)
from aegismar.ingestion.pipeline import run_ingestion_pipeline
from aegismar.spatial.haversine import EARTH_RADIUS_METERS, haversine_distance_meters
from aegismar.spatial.oracle import (
    BruteForceNeighborhoodOracle,
    verify_provider_against_oracle,
)

BASE_TIME = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)


def _obs(
    source_row: int,
    lat: float,
    lon: float,
    offset_s: float = 0.0,
    mmsi: str = "366745490",
    quality_flags: tuple[str, ...] = (),
) -> ObservationRecord:
    """Create a deterministic ObservationRecord at BASE_TIME + offset_s."""
    return ObservationRecord(
        source_row=source_row,
        mmsi=mmsi,
        timestamp_utc=BASE_TIME + timedelta(seconds=offset_s),
        latitude=lat,
        longitude=lon,
        quality_flags=quality_flags,
    )


def _assert_accounting(
    core: int,
    border: int,
    noise: int,
    total: int,
    labels: np.ndarray,
    roles: tuple[str, ...],
) -> None:
    """Verify strict cluster accounting invariant: core + border + noise == analyzed."""
    assert core + border + noise == total
    assert len(labels) == total
    assert len(roles) == total
    for lbl, role in zip(labels.tolist(), roles, strict=True):
        if role == POINT_ROLE_NOISE:
            assert lbl == NOISE_CLUSTER_ID
        else:
            assert role in (POINT_ROLE_CORE, POINT_ROLE_BORDER)
            assert lbl >= 0


def test_01_single_isolated_observation() -> None:
    """Fixture 1: Single isolated observation is noise when min_samples > 1, core when == 1."""
    records = [_obs(1, 33.75, -118.20, 0.0)]
    ds = build_clustering_dataset(records)

    cfg_noise = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=3)
    res_noise = run_balltree_st_dbscan(ds, cfg_noise)
    _assert_accounting(
        res_noise.core_count,
        res_noise.border_count,
        res_noise.noise_count,
        1,
        res_noise.labels,
        res_noise.roles,
    )
    assert res_noise.num_clusters == 0
    assert res_noise.noise_count == 1
    assert res_noise.labels.tolist() == [-1]
    assert res_noise.roles == (POINT_ROLE_NOISE,)

    # With min_samples == 1, the point itself satisfies |N(i)| >= 1
    cfg_single = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=1)
    res_single = run_balltree_st_dbscan(ds, cfg_single)
    assert res_single.num_clusters == 1
    assert res_single.core_count == 1
    assert res_single.labels.tolist() == [0]
    assert res_single.roles == (POINT_ROLE_CORE,)


def test_02_two_separate_dense_clusters() -> None:
    """Fixture 2: Two spatially separated dense clusters receive distinct deterministic IDs."""
    records = [
        # Cluster A around (33.70, -118.20)
        _obs(1, 33.7000, -118.2000, 0.0, "366000001"),
        _obs(2, 33.7001, -118.2001, 60.0, "366000002"),
        _obs(3, 33.7002, -118.2000, 120.0, "366000003"),
        _obs(4, 33.7001, -118.1999, 180.0, "366000004"),
        # Cluster B ~5 km away around (33.75, -118.20)
        _obs(5, 33.7500, -118.2000, 30.0, "366000005"),
        _obs(6, 33.7501, -118.2001, 90.0, "366000006"),
        _obs(7, 33.7502, -118.2000, 150.0, "366000007"),
        _obs(8, 33.7501, -118.1999, 210.0, "366000008"),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=3)
    res = run_balltree_st_dbscan(ds, cfg)

    _assert_accounting(res.core_count, res.border_count, res.noise_count, 8, res.labels, res.roles)
    assert res.num_clusters == 2
    assert res.core_count == 8
    assert res.border_count == 0
    assert res.noise_count == 0
    assert res.cluster_member_counts == {0: 4, 1: 4}

    # Verify oracle match
    report = verify_provider_against_oracle(ds, cfg, BallTreeNeighborhoodProvider(ds, cfg))
    assert report.exact_neighborhood_match
    assert report.exact_role_match
    assert report.exact_label_match


def test_03_temporal_separation_at_identical_coordinates() -> None:
    """Fixture 3: Co-located observations separated beyond eps_temporal_s split into clusters."""
    records = [
        # Morning burst at exact same coordinate
        _obs(1, 33.7200, -118.2200, 0.0, "366000001"),
        _obs(2, 33.7200, -118.2200, 100.0, "366000002"),
        _obs(3, 33.7200, -118.2200, 200.0, "366000003"),
        # Afternoon burst 2 hours later at identical coordinate (> 900 s gap)
        _obs(4, 33.7200, -118.2200, 7200.0, "366000001"),
        _obs(5, 33.7200, -118.2200, 7300.0, "366000002"),
        _obs(6, 33.7200, -118.2200, 7400.0, "366000003"),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=100.0, eps_temporal_s=900.0, min_samples=3)
    res = run_balltree_st_dbscan(ds, cfg)

    assert res.num_clusters == 2
    assert res.core_count == 6
    assert res.cluster_member_counts == {0: 3, 1: 3}
    # First 3 chronological observations belong to cluster 0, last 3 to cluster 1
    assert res.labels[:3].tolist() == [0, 0, 0]
    assert res.labels[3:].tolist() == [1, 1, 1]


def test_04_points_exactly_on_spatial_threshold() -> None:
    """Fixture 4: Exact spatial threshold inclusion (<= eps) and exclusion (> eps)."""
    lat0, lon0 = 33.75, -118.20
    # Construct a point along the same meridian at a computed geodesic distance
    dlat_deg = math.degrees(300.0 / EARTH_RADIUS_METERS)
    lat_on = lat0 + dlat_deg
    exact_dist_m = haversine_distance_meters(lat0, lon0, lat_on, lon0)
    # Set eps_spatial_m to exact_dist_m so point 2 sits exactly on the threshold
    # and point 3 sits 1e-4 meters beyond the threshold.
    lat_outside = lat0 + math.degrees((exact_dist_m + 1e-3) / EARTH_RADIUS_METERS)
    outside_dist_m = haversine_distance_meters(lat0, lon0, lat_outside, lon0)
    assert outside_dist_m > exact_dist_m

    records = [
        _obs(1, lat0, lon0, 0.0, "366000001"),
        _obs(2, lat_on, lon0, 0.0, "366000002"),
        _obs(3, lat_outside, lon0, 0.0, "366000003"),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=exact_dist_m, eps_temporal_s=60.0, min_samples=2)

    bt = BallTreeNeighborhoodProvider(ds, cfg)
    oracle = BruteForceNeighborhoodOracle(ds, cfg)

    # Point 0 (origin) must include point 1 (exact boundary) and exclude point 2 (outside)
    bt_nbrs_0 = bt.query_neighbors(0).tolist()
    or_nbrs_0 = oracle.query_neighbors(0).tolist()
    assert bt_nbrs_0 == [0, 1]
    assert or_nbrs_0 == [0, 1]

    report = verify_provider_against_oracle(ds, cfg, bt)
    assert report.exact_neighborhood_match
    assert report.exact_label_match


def test_05_points_exactly_on_temporal_threshold() -> None:
    """Fixture 5: Exact temporal threshold inclusion (|dt| <= eps_t) and 1-us exclusion."""
    records = [
        _obs(1, 33.75, -118.20, 0.0, "366000001"),
        _obs(2, 33.75, -118.20, 900.0, "366000002"),  # Exactly 900.0 s
        ObservationRecord(
            source_row=3,
            mmsi="366000003",
            timestamp_utc=BASE_TIME + timedelta(seconds=900, microseconds=1),  # 900.000001 s
            latitude=33.75,
            longitude=-118.20,
        ),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=100.0, eps_temporal_s=900.0, min_samples=2)

    bt = BallTreeNeighborhoodProvider(ds, cfg)
    # Point 0 sees {0, 1} (not 2); point 1 sees {0, 1, 2}; point 2 sees {1, 2}
    assert bt.query_neighbors(0).tolist() == [0, 1]
    assert bt.query_neighbors(1).tolist() == [0, 1, 2]
    assert bt.query_neighbors(2).tolist() == [1, 2]

    report = verify_provider_against_oracle(ds, cfg, bt)
    assert report.exact_neighborhood_match
    assert report.exact_label_match


def test_06_duplicate_coordinates_different_timestamps() -> None:
    """Fixture 6: Moored/anchored vessel emitting pings at identical coordinates over time."""
    records = [_obs(i + 1, 33.7200, -118.2200, float(i * 300), "366000001") for i in range(6)]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=50.0, eps_temporal_s=350.0, min_samples=3)
    res = run_balltree_st_dbscan(ds, cfg)

    # Interior points (indices 1..4) have 3 neighbors {i-1, i, i+1} -> core;
    # Endpoints (indices 0 and 5) have 2 neighbors -> border attached to the single cluster.
    assert res.num_clusters == 1
    assert res.core_count == 4
    assert res.border_count == 2
    assert res.noise_count == 0
    assert res.roles == (
        POINT_ROLE_BORDER,
        POINT_ROLE_CORE,
        POINT_ROLE_CORE,
        POINT_ROLE_CORE,
        POINT_ROLE_CORE,
        POINT_ROLE_BORDER,
    )


def test_07_and_08_core_border_and_noise_classification() -> None:
    """Fixtures 7 & 8: Explicit verification of core, border, and noise roles."""
    # Dense core of 3 co-located points + 1 border point 200m away + 1 distant noise point
    dlat_200m = math.degrees(200.0 / EARTH_RADIUS_METERS)
    records = [
        _obs(1, 33.7500, -118.2000, 0.0, "366000001"),
        _obs(2, 33.7500, -118.2000, 10.0, "366000002"),
        _obs(3, 33.7500, -118.2000, 20.0, "366000003"),
        # Border: within 250m of core points (deg = 4 -> wait: make it only reach 1 core point!)
        # Actually with min_samples=4, let's place border 200m from core point 3 ONLY:
        # Place core cluster tightly within 50m (4 points -> all core with min_samples=4)
        _obs(4, 33.7500, -118.2000, 30.0, "366000004"),
        # Border point at 200m north (reaches the 4 core points? Wait: if it reaches 4 core points
        # plus itself, its degree is 5 >= 4 so it would be core!).
        # To be a TRUE border point with min_samples=4:
        # Chain: p0(0m), p1(0m), p2(0m), p3(180m) -> p0,p1,p2 see {p0,p1,p2,p3} (deg 4 -> core),
        # p4(360m) sees ONLY {p3, p4} (deg 2 < 4) -> wait p3 sees {p0,p1,p2,p3,p4} (deg 5 -> core),
        # so p4 has deg 2 < 4 and reaches core point p3 -> TRUE BORDER!
        _obs(5, 33.7500 + dlat_200m, -118.2000, 35.0, "366000005"),
        _obs(6, 33.7500 + 2.0 * dlat_200m, -118.2000, 40.0, "366000006"),
        # Noise point 10 km away
        _obs(7, 33.8500, -118.2000, 45.0, "366000007"),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=250.0, eps_temporal_s=600.0, min_samples=4)
    res = run_balltree_st_dbscan(ds, cfg)

    _assert_accounting(res.core_count, res.border_count, res.noise_count, 7, res.labels, res.roles)
    assert res.num_clusters == 1
    assert res.core_count == 5  # rows 1..5
    assert res.border_count == 1  # row 6 (only reaches row 5 + self -> deg 2 < 4)
    assert res.noise_count == 1  # row 7
    assert res.roles[5] == POINT_ROLE_BORDER
    assert res.labels[5] == 0
    assert res.roles[6] == POINT_ROLE_NOISE
    assert res.labels[6] == NOISE_CLUSTER_ID


def test_09_border_reachable_from_multiple_core_components() -> None:
    """Fixture 9: Border point reachable from two core components follows nearest-core tie-break."""
    # Exact dyadic midpoint lat_mid = 33.75 with symmetric offsets delta = 0.0018 deg (~200 m)
    # so bridge0 and bridge1 are bit-for-bit equidistant from lat_mid.
    lat_mid, lon0 = 33.75, -118.25
    delta = 0.0018  # ~200.15 m along meridian
    lat_b0 = lat_mid - delta
    lat_b1 = lat_mid + delta
    lat_base0 = lat_mid - 2.0 * delta
    lat_base1 = lat_mid + 2.0 * delta

    d0 = haversine_distance_meters(lat_mid, lon0, lat_b0, lon0)
    d1 = haversine_distance_meters(lat_mid, lon0, lat_b1, lon0)
    assert d0 == d1
    assert 190.0 < d0 < 210.0

    # Comp 0 base (4 points) + bridge core point at lat_b0 (deg >= 5 -> core)
    # Comp 1 base (4 points) + bridge core point at lat_b1 (deg >= 5 -> core)
    # Distance between bridge0 and bridge1 is ~400m > eps_spatial_m=250m (disjoint components).
    base_records = [
        _obs(1, lat_base0, lon0, 0.0, "366000001"),
        _obs(2, lat_base0, lon0, 1.0, "366000002"),
        _obs(3, lat_base0, lon0, 2.0, "366000003"),
        _obs(4, lat_base0, lon0, 3.0, "366000004"),
        _obs(5, lat_b0, lon0, 10.0, "366000005"),
        _obs(6, lat_base1, lon0, 0.0, "366000011"),
        _obs(7, lat_base1, lon0, 1.0, "366000012"),
        _obs(8, lat_base1, lon0, 2.0, "366000013"),
        _obs(9, lat_base1, lon0, 3.0, "366000014"),
        _obs(10, lat_b1, lon0, 10.0, "366000015"),
    ]
    cfg = STDBSCANConfig(eps_spatial_m=250.0, eps_temporal_s=600.0, min_samples=4)

    # Case 9A: Border closer to Comp 0 (lat_mid - 0.0001)
    ds_a = build_clustering_dataset(
        [*base_records, _obs(11, lat_mid - 0.0001, lon0, 10.0, "366000021")]
    )
    res_a = run_balltree_st_dbscan(ds_a, cfg)
    idx_a = int(np.flatnonzero(ds_a.source_rows == 11)[0])
    assert res_a.num_clusters == 2
    assert res_a.roles[idx_a] == POINT_ROLE_BORDER
    assert int(res_a.labels[idx_a]) == 0

    # Case 9B: Border closer to Comp 1 (lat_mid + 0.0001)
    ds_b = build_clustering_dataset(
        [*base_records, _obs(12, lat_mid + 0.0001, lon0, 10.0, "366000022")]
    )
    res_b = run_balltree_st_dbscan(ds_b, cfg)
    idx_b = int(np.flatnonzero(ds_b.source_rows == 12)[0])
    assert res_b.num_clusters == 2
    assert res_b.roles[idx_b] == POINT_ROLE_BORDER
    assert int(res_b.labels[idx_b]) == 1

    # Case 9C: Exact equidistant & equal-time border -> deterministic tie-break to Comp 0
    ds_c = build_clustering_dataset([*base_records, _obs(13, lat_mid, lon0, 10.0, "366000023")])
    res_c = run_balltree_st_dbscan(ds_c, cfg)
    idx_c = int(np.flatnonzero(ds_c.source_rows == 13)[0])
    assert res_c.num_clusters == 2
    assert res_c.roles[idx_c] == POINT_ROLE_BORDER
    assert int(res_c.labels[idx_c]) == 0

    # Oracle agrees 100% on ambiguous border tie-break
    report_c = verify_provider_against_oracle(ds_c, cfg, BallTreeNeighborhoodProvider(ds_c, cfg))
    assert report_c.exact_label_match
    assert report_c.exact_role_match


def test_10_dateline_crossing_spatial_neighbors() -> None:
    """Fixture 10: Neighbors straddling the +/-180 degree antimeridian cluster together."""
    records = [
        _obs(1, 0.0, 179.9995, 0.0, "366000001"),
        _obs(2, 0.0, 179.9998, 30.0, "366000002"),
        _obs(3, 0.0, -179.9998, 60.0, "366000003"),
        _obs(4, 0.0, -179.9995, 90.0, "366000004"),
    ]
    # Distance across dateline from +179.9995 to -179.9995 at equator is ~111 m
    dist_across = haversine_distance_meters(0.0, 179.9995, 0.0, -179.9995)
    assert 100.0 < dist_across < 120.0

    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=200.0, eps_temporal_s=300.0, min_samples=3)
    res = run_balltree_st_dbscan(ds, cfg)

    assert res.num_clusters == 1
    assert res.core_count == 4
    report = verify_provider_against_oracle(ds, cfg, BallTreeNeighborhoodProvider(ds, cfg))
    assert report.exact_neighborhood_match
    assert report.exact_label_match


def test_11_high_latitude_geographic_coordinates() -> None:
    """Fixture 11: High-latitude points (+80 deg) respect spherical cosine longitude convergence."""
    # At lat = 80.0 deg, 0.01 deg longitude is only ~193 m (vs ~1,112 m at equator)
    d_high = haversine_distance_meters(80.0, 10.0, 80.0, 10.01)
    assert 180.0 < d_high < 210.0

    records = [
        _obs(1, 80.0, 10.000, 0.0, "366000001"),
        _obs(2, 80.0, 10.005, 60.0, "366000002"),
        _obs(3, 80.0, 10.010, 120.0, "366000003"),
        # Southern high latitude (-80 deg), far away
        _obs(4, -80.0, 10.000, 0.0, "366000004"),
        _obs(5, -80.0, 10.005, 60.0, "366000005"),
        _obs(6, -80.0, 10.010, 120.0, "366000006"),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=250.0, eps_temporal_s=300.0, min_samples=3)
    res = run_balltree_st_dbscan(ds, cfg)

    assert res.num_clusters == 2
    assert res.core_count == 6
    report = verify_provider_against_oracle(ds, cfg, BallTreeNeighborhoodProvider(ds, cfg))
    assert report.exact_neighborhood_match
    assert report.exact_role_match
    assert report.exact_label_match


def test_13_input_row_permutation_invariance() -> None:
    """Fixture 13: Permuting input row order yields identical labels & roles per source_row."""
    rng = random.Random(20250101)
    records: list[ObservationRecord] = []
    for i in range(60):
        center_lat = 33.72 if i < 25 else (33.76 if i < 50 else 33.80)
        center_lon = -118.22 if i < 25 else (-118.18 if i < 50 else -118.10)
        records.append(
            _obs(
                source_row=i + 1,
                lat=center_lat + rng.uniform(-0.002, 0.002),
                lon=center_lon + rng.uniform(-0.002, 0.002),
                offset_s=rng.uniform(0.0, 1800.0),
                mmsi=f"366000{i % 10:03d}",
            )
        )

    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=4)
    res_orig = run_balltree_st_dbscan(build_clustering_dataset(records), cfg)
    map_orig = {
        int(sr): (int(lbl), role)
        for sr, lbl, role in zip(
            res_orig.dataset.source_rows.tolist(),
            res_orig.labels.tolist(),
            res_orig.roles,
            strict=True,
        )
    }

    for trial in range(3):
        shuffled = list(records)
        random.Random(100 + trial).shuffle(shuffled)
        res_perm = run_balltree_st_dbscan(build_clustering_dataset(shuffled), cfg)
        map_perm = {
            int(sr): (int(lbl), role)
            for sr, lbl, role in zip(
                res_perm.dataset.source_rows.tolist(),
                res_perm.labels.tolist(),
                res_perm.roles,
                strict=True,
            )
        }
        assert map_perm == map_orig
        assert np.array_equal(res_perm.labels, res_orig.labels)
        assert res_perm.roles == res_orig.roles


def test_14_deterministic_output_across_repeated_runs() -> None:
    """Fixture 14: Repeated runs produce identical labels, roles, counts, and memberships."""
    rng = random.Random(42)
    records = [
        _obs(
            source_row=i + 1,
            lat=33.74 + rng.uniform(-0.004, 0.004),
            lon=-118.21 + rng.uniform(-0.004, 0.004),
            offset_s=float(rng.randint(0, 2400)),
            mmsi=f"366100{i % 7:03d}",
        )
        for i in range(80)
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=4)

    res1 = run_balltree_st_dbscan(ds, cfg)
    res2 = run_balltree_st_dbscan(ds, cfg)

    assert np.array_equal(res1.labels, res2.labels)
    assert res1.roles == res2.roles
    assert res1.num_clusters == res2.num_clusters
    assert res1.core_count == res2.core_count
    assert res1.border_count == res2.border_count
    assert res1.noise_count == res2.noise_count
    assert res1.cluster_member_counts == res2.cluster_member_counts


def test_15_empty_input_and_invalid_configuration() -> None:
    """Fixture 15: Empty input returns clean empty result; invalid configs raise ValueError."""
    # Empty input
    empty_ds = build_clustering_dataset([])
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=5)
    res = run_balltree_st_dbscan(empty_ds, cfg, measure_memory=True)
    assert res.num_clusters == 0
    assert res.core_count == 0
    assert res.border_count == 0
    assert res.noise_count == 0
    assert res.labels.size == 0
    assert res.roles == ()

    # Invalid spatial radii
    for bad_spatial in (0.0, -10.0, float("nan"), float("inf"), 1e9, True):
        with pytest.raises(ValueError):
            STDBSCANConfig(eps_spatial_m=bad_spatial)

    # Invalid temporal radii
    for bad_temporal in (0.0, -5.0, float("nan"), float("inf"), False):
        with pytest.raises(ValueError):
            STDBSCANConfig(eps_temporal_s=bad_temporal)

    # Invalid min_samples
    for bad_min in (0, -1, True, 2.5):
        with pytest.raises(ValueError):
            STDBSCANConfig(min_samples=bad_min)  # type: ignore[arg-type]

    # Mismatched provider/dataset size rejected by run_st_dbscan
    ds_one = build_clustering_dataset([_obs(1, 33.7, -118.2)])
    bt_empty = BallTreeNeighborhoodProvider(empty_ds, cfg)
    with pytest.raises(ValueError, match="does not match"):
        run_st_dbscan(ds_one, cfg, bt_empty)


def test_16_quality_filtering_of_same_timestamp_conflicts(tmp_path: Path) -> None:
    """Fixture 16: Flagged same-timestamp conflicts excluded deterministically by default policy."""
    # Programmatic verification
    records = [
        _obs(1, 33.7500, -118.2000, 0.0, "366000001"),
        _obs(2, 33.7500, -118.2000, 30.0, "366000002"),
        _obs(3, 33.7500, -118.2000, 60.0, "366000003"),
        _obs(
            4,
            33.7500,
            -118.2000,
            60.0,
            "366000004",
            quality_flags=(FLAG_TIMESTAMP_POSITION_CONFLICT,),
        ),
        _obs(
            5,
            33.7500,
            -118.2000,
            60.0,
            "366000005",
            quality_flags=(FLAG_TIMESTAMP_METADATA_CONFLICT,),
        ),
    ]
    ds_filtered = build_clustering_dataset(
        records, QualityFilterPolicy(exclude_timestamp_conflicts=True)
    )
    assert ds_filtered.total_input_count == 5
    assert ds_filtered.excluded_count == 2
    assert ds_filtered.num_points == 3
    assert ds_filtered.excluded_breakdown[FLAG_TIMESTAMP_POSITION_CONFLICT] == 1
    assert ds_filtered.excluded_breakdown[FLAG_TIMESTAMP_METADATA_CONFLICT] == 1

    ds_unfiltered = build_clustering_dataset(
        records, QualityFilterPolicy(exclude_timestamp_conflicts=False)
    )
    assert ds_unfiltered.excluded_count == 0
    assert ds_unfiltered.num_points == 5

    # End-to-end Parquet roundtrip with real ingestion pipeline creating conflict flags
    csv_path = tmp_path / "conflict_input.csv"
    csv_path.write_text(
        "mmsi,base_date_time,longitude,latitude,sog\n"
        "366000001,2025-01-01 00:00:00,-118.2000,33.7500,0.0\n"
        "366000002,2025-01-01 00:00:30,-118.2000,33.7500,0.0\n"
        "366000003,2025-01-01 00:01:00,-118.2000,33.7500,0.0\n"
        "366000004,2025-01-01 00:01:00,-118.2000,33.7500,0.0\n"
        "366000004,2025-01-01 00:01:00,-118.2500,33.7900,0.0\n",
        encoding="utf-8",
    )
    ingest_dir = tmp_path / "ingested"
    manifest = run_ingestion_pipeline(csv_path, ingest_dir)
    assert manifest.output_row_count == 5  # Conflicts preserved in canonical Parquet
    assert manifest.conflict_count == 2

    parquet_ds = load_clustering_dataset_from_parquet(
        manifest.output_parquet_path,
        quality_filter=QualityFilterPolicy(exclude_timestamp_conflicts=True),
    )
    assert parquet_ds.total_input_count == 5
    assert parquet_ds.excluded_count == 2
    assert parquet_ds.num_points == 3
    assert parquet_ds.excluded_breakdown == {FLAG_TIMESTAMP_POSITION_CONFLICT: 2}


def test_export_clustering_artifacts_roundtrip(tmp_path: Path) -> None:
    """Verify Parquet, JSON summary, GeoJSON preview, and static HTML map export & overwrite."""
    records = [
        _obs(1, 33.7000, -118.2000, 0.0, "366000001"),
        _obs(2, 33.7001, -118.2001, 60.0, "366000002"),
        _obs(3, 33.7002, -118.2000, 120.0, "366000003"),
        _obs(4, 33.8000, -118.1000, 180.0, "366000004"),
    ]
    ds = build_clustering_dataset(records)
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=3)
    res = run_balltree_st_dbscan(ds, cfg, measure_memory=True)

    out_dir = tmp_path / "artifacts"
    paths = export_clustering_artifacts(res, out_dir, overwrite=False)

    assert paths["parquet"].is_file()
    assert paths["summary"].is_file()
    assert paths["geojson"].is_file()
    assert paths["html_map"].is_file()

    # Parquet schema & row check
    table = pq.read_table(str(paths["parquet"]))
    assert table.schema.names == get_cluster_assignments_arrow_schema().names
    assert table.num_rows == 4

    # Summary JSON check
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert summary["clustering_summary"]["num_clusters"] == 1
    assert summary["clustering_summary"]["accounting_check_passed"] is True

    # GeoJSON FeatureCollection check
    geojson = json.loads(paths["geojson"].read_text(encoding="utf-8"))
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 4

    # HTML map check
    html_text = paths["html_map"].read_text(encoding="utf-8")
    assert "<svg" in html_text
    assert "<circle" in html_text

    # Overwrite protection
    with pytest.raises(FileExistsError):
        export_clustering_artifacts(res, out_dir, overwrite=False)
