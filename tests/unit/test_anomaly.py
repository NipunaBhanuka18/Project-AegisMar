"""Unit tests for Track B features (ML-02 v1.0) and the D0 vessel partition (ML-03 v1.0).

Synthetic trajectories are passed through the production ingestion cleaner
(``process_and_clean_observations``) so that pair pointers, elapsed time, distance and implied
speed are derived exactly as for real data. Test names reference the ML-02 section 11 cases.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pytest

from aegismar.anomaly.evaluation import (
    MERGED_GROUP,
    TEST_DAYS,
    TestDayFirewallError,
    _as_utc,
    check_test_day_firewall,
    dataset_days,
    split_vessels,
    vessel_attributes,
    vessel_group,
)
from aegismar.anomaly.features import (
    MAX_RATE_DT_S,
    MIN_NET_DISPLACEMENT_NM,
    MOTION_MOVING,
    MOTION_STATIONARY,
    MOTION_UNKNOWN,
    WINDOW_LENGTH_S,
    FeatureResult,
    angdiff,
    destination_point,
    detect_outage_windows,
    extract_features,
    fit_expected_intervals,
    haversine_m,
    outage_overlap_s,
    prepare_observations,
    sangdiff,
    window_starts,
)
from aegismar.ingestion.cleaner import process_and_clean_observations
from aegismar.ingestion.schema import get_canonical_arrow_schema
from aegismar.ingestion.storage import canonical_pings_to_arrow_table
from aegismar.spatial.haversine import haversine_distance_meters

T0 = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
NM = 1852.0
D0_PARQUET = Path("data/processed/lalb_20250101/cleaned_ais.parquet")


# --------------------------------------------------------------------------- helpers
def _track(
    mmsi: str,
    n: int,
    dt_s: float,
    sog: float,
    cog: float,
    *,
    start_s: float = 0.0,
    lat0: float = 33.6,
    lon0: float = -118.2,
    heading: float | None = None,
    cls: str = "A",
    vessel_type: int = 70,
) -> list[dict[str, Any]]:
    """Great-circle constant-speed track; positions follow ``destination_point`` exactly."""
    rows: list[dict[str, Any]] = []
    lat, lon = lat0, lon0
    for k in range(n):
        if k:
            lat_a, lon_a = destination_point(
                np.array([lat]),
                np.array([lon]),
                np.array([cog]),
                np.array([sog * dt_s / 3600 * NM]),
            )
            lat, lon = float(lat_a[0]), float(lon_a[0])
        rows.append(
            _row(
                mmsi,
                start_s + k * dt_s,
                lat,
                lon,
                sog=sog,
                cog=cog,
                heading=heading,
                cls=cls,
                vessel_type=vessel_type,
            )
        )
    return rows


def _row(
    mmsi: str,
    t_s: float,
    lat: float,
    lon: float,
    *,
    sog: float | None,
    cog: float | None,
    heading: float | None = None,
    cls: str | None = "A",
    vessel_type: int | None = 70,
) -> dict[str, Any]:
    return {
        "mmsi": mmsi,
        "timestamp_utc": T0 + timedelta(seconds=t_s),
        "latitude": lat,
        "longitude": lon,
        "sog": sog,
        "cog": cog,
        "heading": heading,
        "nav_status": 0,
        "vessel_type": vessel_type,
        "transceiver_class": cls,
    }


def _ingest(rows: list[dict[str, Any]]) -> pa.Table:
    pings, _ = process_and_clean_observations(rows)
    return canonical_pings_to_arrow_table(pings)


def _manual_table(records: list[dict[str, Any]]) -> pa.Table:
    """Canonical table with explicit pointers (bypasses the cleaner for guard edge cases)."""
    schema = get_canonical_arrow_schema()
    defaults: dict[str, Any] = dict.fromkeys(schema.names)
    defaults["quality_flags"] = []
    full = [{**defaults, **r} for r in records]
    return pa.Table.from_pylist(full, schema=schema)


def _col(result: FeatureResult, name: str) -> np.ndarray[Any, np.dtype[np.float64]]:
    return result.pair_features[name]


# --------------------------------------------------------------------------- geometry (11.1, 11.3)
def test_angdiff_and_sangdiff_wrap_correctly() -> None:
    assert float(angdiff(359.0, 1.0)) == pytest.approx(2.0)
    assert float(angdiff(0.0, 180.0)) == pytest.approx(180.0)
    assert float(angdiff(10.0, 10.0)) == 0.0
    assert float(sangdiff(10.0, 350.0)) == pytest.approx(20.0)
    assert float(sangdiff(350.0, 10.0)) == pytest.approx(-20.0)
    assert np.isnan(angdiff(np.array([np.nan]), 5.0)[0])


def test_haversine_matches_spatial_reference_implementation() -> None:
    rng = random.Random(7)
    pts = [
        (rng.uniform(-80, 80), rng.uniform(-180, 180), rng.uniform(-80, 80), rng.uniform(-180, 180))
        for _ in range(200)
    ]
    arr = np.array(pts)
    vec = haversine_m(arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3])
    ref = np.array([haversine_distance_meters(*p) for p in pts])
    np.testing.assert_allclose(vec, ref, rtol=1e-12, atol=1e-6)


def test_destination_point_due_north_matches_spec_case() -> None:
    lat, lon = destination_point(
        np.array([0.0]), np.array([0.0]), np.array([0.0]), np.array([60 * NM])
    )
    expected_deg = math.degrees(60 * NM / 6371008.8)
    assert lat[0] == pytest.approx(expected_deg, abs=1e-12)
    assert expected_deg == pytest.approx(0.9993247881707066, abs=1e-12)
    assert lon[0] == pytest.approx(0.0, abs=1e-12)


def test_destination_point_normalises_across_dateline() -> None:
    lat, lon = destination_point(
        np.array([0.0]), np.array([179.9]), np.array([90.0]), np.array([50_000.0])
    )
    assert -180.0 <= lon[0] < -179.0
    dist = haversine_m(np.array([0.0]), np.array([179.9]), lat, lon)
    assert dist[0] == pytest.approx(50_000.0, rel=1e-9)


# --------------------------------------------------------------------------- straight track (11.2)
def test_straight_constant_speed_track_has_zero_kinematic_signal() -> None:
    table = _ingest(_track("366000001", 20, 60.0, 12.0, 0.0, heading=0.0))
    r = extract_features(table, outages=[])
    has_pair = r.observations.prev_idx >= 0
    assert int(has_pair.sum()) == 19
    for name in ("delta_sog_kt", "accel_ms2", "rot_deg_s", "abs_delta_cog_deg"):
        np.testing.assert_allclose(_col(r, name)[has_pair], 0.0, atol=1e-12)
    np.testing.assert_allclose(_col(r, "speed_disparity_kt")[has_pair], 0.0, atol=1e-6)
    np.testing.assert_allclose(_col(r, "dr_error_nm")[has_pair], 0.0, atol=1e-6)
    np.testing.assert_allclose(_col(r, "lateral_drift_deg"), 0.0, atol=1e-12)
    np.testing.assert_allclose(_col(r, "course_heading_reversal"), 0.0)
    np.testing.assert_allclose(_col(r, "unexplained_gap_s")[has_pair], 60.0)
    assert np.isnan(_col(r, "dt_s")[0])

    w = r.windows
    assert w.num_rows == 1
    assert w.column("motion_state")[0].as_py() == MOTION_MOVING
    assert w.column("tortuosity")[0].as_py() == pytest.approx(1.0, abs=1e-9)
    assert w.column("n_obs")[0].as_py() == 20
    assert w.column("n_pairs")[0].as_py() == 19
    assert w.column("stationary_net_displacement_m")[0].as_py() is None


# ----------------------------------------------------------------- pairing & guards (11.4)
def test_conflict_rows_are_skipped_and_rate_guards_apply() -> None:
    m = "366000002"
    rows = _track(m, 3, 60.0, 10.0, 0.0)  # t = 0, 60, 120
    conflict = dict(rows[-1])
    conflict["latitude"] += 0.01  # same timestamp, different position -> conflict pair
    rows.append(conflict)
    last = rows[1]
    rows.append(_row(m, 180.0, last["latitude"] + 0.005, last["longitude"], sog=11.0, cog=0.0))
    rows.append(_row(m, 1000.0, last["latitude"] + 0.03, last["longitude"], sog=13.0, cog=5.0))
    r = extract_features(_ingest(rows), outages=[])
    obs = r.observations
    t = obs.timestamp_s - T0.timestamp()

    conflict_rows = np.flatnonzero(obs.is_conflict)
    assert conflict_rows.size == 2
    for name in ("dt_s", "delta_sog_kt", "speed_disparity_kt", "dr_error_nm", "gap_s"):
        assert np.isnan(_col(r, name)[conflict_rows]).all()
    assert (r.segments[conflict_rows] == -1).all()

    i180 = int(np.flatnonzero(t == 180.0)[0])
    assert t[obs.prev_idx[i180]] == 60.0  # skips both conflict rows
    assert _col(r, "dt_s")[i180] == 120.0
    assert np.isfinite(_col(r, "accel_ms2")[i180])

    i1000 = int(np.flatnonzero(t == 1000.0)[0])
    assert _col(r, "dt_s")[i1000] == 820.0 > MAX_RATE_DT_S
    assert np.isnan(_col(r, "accel_ms2")[i1000])
    assert np.isnan(_col(r, "rot_deg_s")[i1000])
    assert _col(r, "gap_s")[i1000] == 820.0
    assert _col(r, "delta_sog_kt")[i1000] == pytest.approx(2.0)  # not a rate: kept


def test_zero_elapsed_time_nulls_rates_and_implied_speed() -> None:
    base = {"mmsi": "366000003", "latitude": 33.6, "longitude": -118.2, "transceiver_class": "A"}
    table = _manual_table(
        [
            {**base, "source_row": 1, "timestamp_utc": T0, "sog": 10.0, "cog": 0.0},
            {
                **base,
                "source_row": 2,
                "timestamp_utc": T0,
                "sog": 12.0,
                "cog": 10.0,
                "prev_source_row": 1,
                "elapsed_seconds": 0.0,
                "distance_nm": 0.0,
            },
        ]
    )
    r = extract_features(table, outages=[])
    i = int(np.flatnonzero(r.observations.source_row == 2)[0])
    for name in ("accel_ms2", "rot_deg_s", "implied_speed_kt", "speed_disparity_kt"):
        assert np.isnan(_col(r, name)[i]), name
    assert _col(r, "delta_sog_kt")[i] == pytest.approx(2.0)


def test_speed_disparity_requires_minimum_interval() -> None:
    m = "366000004"
    rows = [
        _row(m, 0.0, 33.6, -118.2, sog=10.0, cog=0.0),
        _row(m, 20.0, 33.601, -118.2, sog=10.0, cog=0.0),
        _row(m, 80.0, 33.603, -118.2, sog=10.0, cog=0.0),
    ]
    r = extract_features(_ingest(rows), outages=[])
    assert np.isnan(_col(r, "speed_disparity_kt")[1])  # dt = 20 s < G3
    assert np.isfinite(_col(r, "speed_disparity_kt")[2])
    expected = abs(r.observations.implied_speed_kt[2] - 10.0)
    assert _col(r, "speed_disparity_kt")[2] == pytest.approx(expected)


# --------------------------------------------------------------------------- outages (11.5)
def test_outage_detection_merges_close_silences() -> None:
    times = (
        list(range(0, 1001, 10))
        + list(range(1100, 1201, 10))
        + list(range(1300, 5001, 10))
        + list(range(5100, 5201, 10))
    )
    assert detect_outage_windows(times) == [(1000.0, 1300.0), (5000.0, 5100.0)]
    assert detect_outage_windows([5.0]) == []


def test_outage_overlap_full_and_partial() -> None:
    windows = [(1000.0, 1300.0)]
    overlap = outage_overlap_s(
        np.array([1010.0, 900.0, 0.0]), np.array([1090.0, 1050.0, 100.0]), windows
    )
    np.testing.assert_allclose(overlap, [80.0, 50.0, 0.0])


def test_unexplained_gap_subtracts_outage_overlap() -> None:
    m = "366000005"
    rows = _track(m, 3, 60.0, 10.0, 0.0)
    last = rows[-1]
    rows.append(_row(m, 1320.0, last["latitude"] + 0.03, last["longitude"], sog=10.0, cog=0.0))
    r = extract_features(_ingest(rows), outages=[(T0.timestamp() + 200.0, T0.timestamp() + 1500.0)])
    i = r.observations.size - 1
    assert _col(r, "gap_s")[i] == 1200.0
    assert _col(r, "outage_overlap_s")[i] == pytest.approx(1120.0)
    assert _col(r, "unexplained_gap_s")[i] == pytest.approx(80.0)

    inside = extract_features(_ingest(rows), outages=[(T0.timestamp(), T0.timestamp() + 2000.0)])
    assert _col(inside, "unexplained_gap_s")[i] == 0.0


# --------------------------------------------------------------------------- low-speed guard (11.6)
def test_low_speed_guard_and_reversal_split() -> None:
    m = "366000006"
    rows = [
        _row(m, 0.0, 33.6, -118.2, sog=1.4, cog=0.0, heading=60.0),
        _row(m, 60.0, 33.6005, -118.2, sog=2.0, cog=0.0, heading=150.0),
        _row(m, 120.0, 33.601, -118.2, sog=2.0, cog=10.0, heading=340.0),
        _row(m, 180.0, 33.6015, -118.2, sog=2.0, cog=10.0, heading=None),
    ]
    r = extract_features(_ingest(rows), outages=[])
    lateral, reversal = _col(r, "lateral_drift_deg"), _col(r, "course_heading_reversal")
    assert np.isnan(lateral[0]) and np.isnan(reversal[0])  # SOG 1.4 < G1
    assert np.isnan(lateral[1]) and reversal[1] == 1.0  # 150 deg > 135
    assert lateral[2] == pytest.approx(30.0) and reversal[2] == 0.0
    assert np.isnan(lateral[3]) and np.isnan(reversal[3])  # heading missing


def test_rate_of_turn_requires_both_speeds_above_guard() -> None:
    m = "366000007"
    rows = [
        _row(m, 0.0, 33.6, -118.2, sog=1.0, cog=350.0),
        _row(m, 60.0, 33.6003, -118.2, sog=5.0, cog=20.0),
        _row(m, 120.0, 33.6009, -118.2, sog=5.0, cog=50.0),
    ]
    r = extract_features(_ingest(rows), outages=[])
    assert np.isnan(_col(r, "rot_deg_s")[1])
    assert _col(r, "rot_deg_s")[2] == pytest.approx(30.0 / 60.0)
    assert _col(r, "abs_delta_cog_deg")[2] == pytest.approx(30.0)


# --------------------------------------------------------------------------- windows (11.7)
def test_window_starts_cover_last_observation() -> None:
    assert window_starts(0.0, 1000.0).tolist() == [0.0]
    assert window_starts(0.0, WINDOW_LENGTH_S).tolist() == [0.0, 600.0]
    starts = window_starts(0.0, 2340.0)
    assert starts.tolist() == [0.0, 600.0]
    assert starts[-1] + WINDOW_LENGTH_S > 2340.0


def test_windows_never_cross_segments_and_need_three_pairs() -> None:
    m = "366000008"
    rows = _track(m, 40, 60.0, 10.0, 0.0)  # span 2340 s
    last = rows[-1]
    rows.append(
        _row(m, 2340.0 + 2000.0, last["latitude"] + 0.1, last["longitude"], sog=10.0, cog=0.0)
    )
    rows.append(
        _row(m, 2340.0 + 2060.0, last["latitude"] + 0.103, last["longitude"], sog=10.0, cog=0.0)
    )
    r = extract_features(_ingest(rows), outages=[])
    assert sorted(set(r.segments.tolist())) == [0, 1]
    w = r.windows
    assert w.num_rows == 2
    assert set(w.column("segment_id").to_pylist()) == {0}
    seg_of = dict(zip(r.observations.source_row.tolist(), r.segments.tolist(), strict=True))
    for srcs in w.column("source_rows").to_pylist():
        assert {seg_of[s] for s in srcs} == {0}
    # the pair spanning the break keeps gap features
    first_of_seg1 = int(np.flatnonzero(r.segments == 1)[0])
    assert _col(r, "gap_s")[first_of_seg1] == 2000.0
    assert np.isfinite(_col(r, "dr_error_nm")[first_of_seg1])


def test_stationary_window_masks_kinematic_aggregates() -> None:
    m = "366000009"
    rows = [
        _row(m, k * 180.0, 33.6 + 1e-5 * (k % 2), -118.2, sog=0.1, cog=None, heading=None)
        for k in range(8)
    ]
    r = extract_features(_ingest(rows), outages=[])
    w = r.windows
    assert w.num_rows == 1
    assert w.column("motion_state")[0].as_py() == MOTION_STATIONARY
    for name in ("max_abs_delta_sog_kt", "max_speed_disparity_kt", "p90_lateral_drift_deg"):
        assert w.column(name)[0].as_py() is None
    assert w.column("tortuosity")[0].as_py() is None  # net displacement < G8
    assert w.column("stationary_net_displacement_m")[0].as_py() == pytest.approx(
        haversine_distance_meters(33.6, -118.2, 33.60001, -118.2)
    )
    assert w.column("max_unexplained_gap_s")[0].as_py() == 180.0
    assert w.column("heading_availability")[0].as_py() == 0.0


def test_window_with_all_sog_missing_is_unknown_state() -> None:
    m = "366000010"
    rows = [_row(m, k * 60.0, 33.6 + 0.001 * k, -118.2, sog=None, cog=None) for k in range(5)]
    w = extract_features(_ingest(rows), outages=[]).windows
    assert w.column("motion_state")[0].as_py() == MOTION_UNKNOWN
    assert w.column("median_sog_kt")[0].as_py() is None


def test_window_quality_context_counts() -> None:
    m = "366000011"
    rows = _track(m, 6, 60.0, 10.0, 0.0)
    jump = dict(rows[3])
    jump["latitude"] += 0.5  # ~30 NM jump in 60 s -> IMPLIED_SPEED_VIOLATION
    rows[3] = jump
    conflict = dict(rows[4])
    conflict["longitude"] += 0.01
    rows.append(conflict)
    r = extract_features(_ingest(rows), outages=[])
    w = r.windows
    assert w.num_rows == 1
    assert w.column("n_implied_speed_violation")[0].as_py() >= 1
    assert w.column("n_conflict_rows")[0].as_py() == 2
    assert w.column("n_obs")[0].as_py() == 5  # conflict rows are not window members


# --------------------------------------------------------------------------- dead reckoning
def test_dead_reckoning_detects_displaced_reappearance() -> None:
    m = "366000012"
    rows = _track(m, 5, 60.0, 10.0, 0.0)
    last = rows[-1]
    dr_lat, dr_lon = destination_point(
        np.array([last["latitude"]]),
        np.array([last["longitude"]]),
        np.array([0.0]),
        np.array([10.0 * NM]),
    )
    disp_lat, disp_lon = destination_point(dr_lat, dr_lon, np.array([90.0]), np.array([1.0 * NM]))
    rows.append(_row(m, 240.0 + 3600.0, float(disp_lat[0]), float(disp_lon[0]), sog=10.0, cog=0.0))
    r = extract_features(_ingest(rows), outages=[])
    i = r.observations.size - 1
    assert _col(r, "dr_error_nm")[i] == pytest.approx(1.0, rel=1e-3)
    assert _col(r, "dr_error_ratio")[i] == pytest.approx(0.1, rel=1e-3)


def test_dr_error_ratio_floor_for_stationary_vessel() -> None:
    m = "366000013"
    rows = [
        _row(m, 0.0, 33.6, -118.2, sog=0.0, cog=0.0),
        _row(m, 180.0, 33.6, -118.199, sog=0.0, cog=0.0),
    ]
    r = extract_features(_ingest(rows), outages=[])
    err = _col(r, "dr_error_nm")[1]
    assert _col(r, "dr_error_ratio")[1] == pytest.approx(err / MIN_NET_DISPLACEMENT_NM)


# ----------------------------------------------------------------- invariance (11.8, 11.9)
def _two_vessel_rows() -> list[dict[str, Any]]:
    return _track("366000020", 30, 60.0, 9.0, 45.0, heading=50.0) + _track(
        "366000021", 30, 70.0, 14.0, 200.0, lat0=33.7, lon0=-118.1, heading=190.0, cls="B"
    )


def test_permutation_invariance() -> None:
    table = _ingest(_two_vessel_rows())
    perm = np.random.default_rng(3).permutation(table.num_rows)
    a = extract_features(table, outages=[])
    b = extract_features(table.take(pa.array(perm)), outages=[])
    assert a.pair_table().equals(b.pair_table())
    assert a.windows.equals(b.windows)


def test_no_cross_vessel_leakage() -> None:
    table = _ingest(_two_vessel_rows())
    only_a = table.filter(pc.equal(table.column("mmsi"), "366000020"))
    full = extract_features(table, outages=[])
    single = extract_features(only_a, outages=[])
    full_a = full.pair_table().filter(pc.equal(full.pair_table().column("mmsi"), "366000020"))
    assert full_a.drop_columns(["segment_id"]).equals(
        single.pair_table().drop_columns(["segment_id"])
    )
    wa = full.windows.filter(pc.equal(full.windows.column("mmsi"), "366000020"))
    assert wa.drop_columns(["segment_id"]).equals(single.windows.drop_columns(["segment_id"]))


# --------------------------------------------------------------------------- F10 expected intervals
def test_gap_ratio_uses_training_medians_only() -> None:
    table = _ingest(_two_vessel_rows())
    obs = prepare_observations(table)
    medians = fit_expected_intervals(obs, ["366000020"])
    assert medians == {("A", "moving"): 60.0}
    r = extract_features(table, expected_intervals=medians, outages=[])
    is_a = r.observations.mmsi == "366000020"
    has_pair = r.observations.prev_idx >= 0
    np.testing.assert_allclose(_col(r, "gap_ratio")[is_a & has_pair], 1.0)
    assert np.isnan(_col(r, "gap_ratio")[~is_a]).all()  # class B not in fitted medians
    assert np.isnan(extract_features(table, outages=[]).pair_features["gap_ratio"]).all()


# --------------------------------------------------------------------------- input validation
def test_prepare_observations_rejects_bad_pointers() -> None:
    base = {"latitude": 33.6, "longitude": -118.2, "timestamp_utc": T0}
    with pytest.raises(ValueError, match="unique"):
        prepare_observations(
            _manual_table(
                [{**base, "mmsi": "1", "source_row": 1}, {**base, "mmsi": "1", "source_row": 1}]
            )
        )
    with pytest.raises(ValueError, match="not found"):
        prepare_observations(
            _manual_table([{**base, "mmsi": "1", "source_row": 1, "prev_source_row": 9}])
        )
    with pytest.raises(ValueError, match="different vessel"):
        prepare_observations(
            _manual_table(
                [
                    {**base, "mmsi": "1", "source_row": 1},
                    {**base, "mmsi": "2", "source_row": 2, "prev_source_row": 1},
                ]
            )
        )


# --------------------------------------------------------------------------- partition (ML-03 3.2)
def _partition_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    specs = (
        [(70, 12.0)] * 10 + [(70, 0.0)] * 10 + [(37, 6.0)] * 7 + [(52, 0.0)] * 3 + [(30, 4.0)] * 2
    )
    for k, (vtype, sog) in enumerate(specs):
        mmsi = f"3660001{k:02d}"
        rows += _track(mmsi, 3, 60.0, sog, 0.0, lat0=33.5 + 0.01 * k, vessel_type=vtype)
    return rows


def test_vessel_group_mapping() -> None:
    assert vessel_group(None) == "unknown"
    assert vessel_group(0) == "unknown"
    assert vessel_group(52) == "tug_towing"
    assert vessel_group(74) == "cargo"
    assert vessel_group(84) == "tanker"
    assert vessel_group(37) == "pleasure"
    assert vessel_group(99) == "other"
    assert vessel_group(45) == "high_speed_craft"
    assert vessel_group(1) == "other"


def test_vessel_attributes_first_non_null_type_and_moving() -> None:
    m = "366000030"
    rows = [
        _row(m, 0.0, 33.6, -118.2, sog=0.0, cog=0.0, vessel_type=None),
        _row(m, 60.0, 33.601, -118.2, sog=2.0, cog=0.0, vessel_type=52),
        _row(m, 120.0, 33.602, -118.2, sog=0.0, cog=0.0, vessel_type=70),
    ]
    assert vessel_attributes(_ingest(rows)) == {m: ("tug_towing", True)}


def test_split_is_deterministic_disjoint_and_stratified() -> None:
    table = _ingest(_partition_rows())
    p1 = split_vessels(table)
    p2 = split_vessels(table.take(pa.array(np.random.default_rng(1).permutation(table.num_rows))))
    assert p1.partition_hash == p2.partition_hash
    assert set(p1.train).isdisjoint(p1.val)
    assert len(p1.train) + len(p1.val) == 32
    # strata: cargo moving 10 -> 3 val; cargo not moving 10 -> 3; pleasure moving 7 -> 2;
    # tug (3) and fishing (2) are merged into "other": other|moving 2 -> 1, other|not_moving 3 -> 1
    assert p1.strata == {
        "cargo|moving": {"vessels": 10, "val": 3, "train": 7},
        "cargo|not_moving": {"vessels": 10, "val": 3, "train": 7},
        f"{MERGED_GROUP}|moving": {"vessels": 2, "val": 1, "train": 1},
        f"{MERGED_GROUP}|not_moving": {"vessels": 3, "val": 1, "train": 2},
        "pleasure|moving": {"vessels": 7, "val": 2, "train": 5},
    }
    assert len(p1.val) == 10
    assert split_vessels(table, seed=7).partition_hash != p1.partition_hash
    d = p1.to_dict()
    assert d["partition_sha256"] == p1.partition_hash and d["n_val"] == 10


# --------------------------------------------------------------------------- real development day
@pytest.mark.skipif(not D0_PARQUET.exists(), reason="development dataset not available locally")
def test_development_day_outages_and_segments_match_ml01() -> None:
    table = pq.read_table(D0_PARQUET)
    obs = prepare_observations(table)
    windows = detect_outage_windows(obs.timestamp_s)
    as_utc = [
        (
            datetime.fromtimestamp(a, UTC).strftime("%H:%M:%S"),
            datetime.fromtimestamp(b, UTC).strftime("%H:%M:%S"),
        )
        for a, b in windows
    ]
    assert as_utc == [("03:07:37", "03:20:25"), ("12:06:09", "12:18:20")]
    from aegismar.anomaly.features import assign_segments

    assert int(assign_segments(obs).max()) + 1 == 468  # ML-01 profile, gap > 1800 s


# --------------------------------------------------------------------------- test-day firewall
DAY_S = 86_400.0


def _day_parquet(tmp_path: Path, start_s: float, span_s: float, **write_kwargs: Any) -> Path:
    rows = _track("366000040", 4, span_s / 3, 10.0, 0.0, start_s=start_s)
    path = tmp_path / f"d_{int(start_s)}.parquet"
    pq.write_table(_ingest(rows), path, **write_kwargs)
    return path


def test_firewall_refuses_test_day_and_allows_development_day(tmp_path: Path) -> None:
    assert {d.isoformat() for d in TEST_DAYS} == {"2025-01-14", "2025-01-22"}
    dev = _day_parquet(tmp_path, 3600.0, 600.0)
    assert [d.isoformat() for d in check_test_day_firewall(dev)] == ["2025-01-01"]

    test_day = _day_parquet(tmp_path, 13 * DAY_S + 3600.0, 600.0)
    with pytest.raises(TestDayFirewallError, match="2025-01-14"):
        check_test_day_firewall(test_day)
    assert [d.isoformat() for d in check_test_day_firewall(test_day, override=True)] == [
        "2025-01-14"
    ]


def test_firewall_refuses_dataset_spanning_into_test_day(tmp_path: Path) -> None:
    spanning = _day_parquet(tmp_path, 13 * DAY_S - 3600.0, 7200.0)  # 2025-01-13 23:00 -> 01:00
    assert [d.isoformat() for d in dataset_days(spanning)] == ["2025-01-13", "2025-01-14"]
    with pytest.raises(TestDayFirewallError):
        check_test_day_firewall(spanning)


def test_firewall_uses_metadata_without_loading_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_day = _day_parquet(tmp_path, 21 * DAY_S + 60.0, 600.0)  # 2025-01-22

    def forbidden(*_args: Any, **_kwargs: Any) -> pa.Table:
        raise AssertionError("observation rows must not be read")

    monkeypatch.setattr("aegismar.anomaly.evaluation.pq.read_table", forbidden)
    with pytest.raises(TestDayFirewallError, match="2025-01-22"):
        check_test_day_firewall(test_day)


def test_firewall_falls_back_to_timestamp_column_without_statistics(tmp_path: Path) -> None:
    no_stats = _day_parquet(tmp_path, 13 * DAY_S + 60.0, 600.0, write_statistics=False)
    with pytest.raises(TestDayFirewallError):
        check_test_day_firewall(no_stats)
    empty = tmp_path / "empty.parquet"
    pq.write_table(_ingest([]), empty)
    assert dataset_days(empty) == []


def test_firewall_rejects_files_without_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "no_ts.parquet"
    pq.write_table(pa.table({"mmsi": ["1"]}), path)
    with pytest.raises(ValueError, match="timestamp_utc"):
        check_test_day_firewall(path)


def test_timestamp_statistic_conversion() -> None:
    assert _as_utc(1_736_812_800_000_000) == datetime(2025, 1, 14, tzinfo=UTC)
    assert _as_utc(datetime(2025, 1, 14, 5)) == datetime(2025, 1, 14, 5, tzinfo=UTC)
    with pytest.raises(TypeError):
        _as_utc("2025-01-14")
