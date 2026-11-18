"""Unit tests for AIS ingestion, schema mapping, quality policy, and Parquet storage."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegismar.common.constants import (
    FLAG_COG_SENTINEL_NULLIFIED,
    FLAG_EXACT_DUPLICATE,
    FLAG_HARD_INVALID_BAD_COORDINATES,
    FLAG_HARD_INVALID_BAD_MMSI,
    FLAG_HARD_INVALID_BAD_TIMESTAMP,
    FLAG_HEADING_SENTINEL_NULLIFIED,
    FLAG_IMPLIED_SPEED_VIOLATION,
    FLAG_SOG_SENTINEL_NULLIFIED,
    FLAG_STATUS_SENTINEL_NULLIFIED,
    FLAG_TIMESTAMP_METADATA_CONFLICT,
    FLAG_TIMESTAMP_POSITION_CONFLICT,
    FLAG_ZERO_ELAPSED_TIME,
)
from aegismar.ingestion.cleaner import (
    RecordValidator,
    process_and_clean_observations,
    sanitize_mmsi,
)
from aegismar.ingestion.pipeline import run_ingestion_pipeline
from aegismar.ingestion.schema import (
    SchemaAdapterError,
    detect_and_build_column_mapping,
    get_canonical_arrow_schema,
)
from aegismar.ingestion.storage import (
    inspect_parquet_metadata,
    read_parquet_dataset,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_01_2025_schema_mapping() -> None:
    """Verify detection and mapping of modern 2025 NOAA snake_case headers."""
    headers = [
        "mmsi",
        "base_date_time",
        "longitude",
        "latitude",
        "sog",
        "cog",
        "heading",
        "status",
        "vessel_type",
    ]
    detected, mapping = detect_and_build_column_mapping(headers)
    assert detected == "noaa_2025"
    assert mapping["mmsi"] == "mmsi"
    assert mapping["base_date_time"] == "timestamp_utc"
    assert mapping["longitude"] == "longitude"
    assert mapping["latitude"] == "latitude"
    assert mapping["status"] == "nav_status"


def test_02_legacy_header_mapping() -> None:
    """Verify detection and mapping of legacy 2018-2024 NOAA PascalCase headers."""
    headers = [
        "MMSI",
        "BaseDateTime",
        "LAT",
        "LON",
        "SOG",
        "COG",
        "Heading",
        "Status",
        "VesselType",
    ]
    detected, mapping = detect_and_build_column_mapping(headers)
    assert detected == "noaa_legacy"
    assert mapping["MMSI"] == "mmsi"
    assert mapping["BaseDateTime"] == "timestamp_utc"
    assert mapping["LAT"] == "latitude"
    assert mapping["LON"] == "longitude"
    assert mapping["Status"] == "nav_status"


def test_03_missing_required_columns() -> None:
    """Verify informative failure when required coordinates or timestamps are absent."""
    incomplete_headers = ["mmsi", "sog", "cog"]
    with pytest.raises(SchemaAdapterError, match="missing required canonical fields"):
        detect_and_build_column_mapping(incomplete_headers)


def test_04_leading_zero_mmsi_preservation() -> None:
    """Verify that leading-zero MMSIs and small integers are zero-padded to 9 digits."""
    clean, err = sanitize_mmsi("003667454")
    assert err is None
    assert clean == "003667454"
    assert len(clean) == 9

    clean_num, err2 = sanitize_mmsi(3667454)
    assert err2 is None
    assert clean_num == "003667454"


def test_05_invalid_mmsi() -> None:
    """Verify rejection of invalid, non-numeric, or all-zero MMSIs."""
    clean1, err1 = sanitize_mmsi("000000000")
    assert clean1 is None
    assert err1 == FLAG_HARD_INVALID_BAD_MMSI

    clean2, err2 = sanitize_mmsi("NOT_A_NUMBER")
    assert clean2 is None
    assert err2 == FLAG_HARD_INVALID_BAD_MMSI

    clean3, err3 = sanitize_mmsi(None)
    assert clean3 is None


def test_06_unavailable_and_sentinel_kinematics() -> None:
    """Verify that kinematics sentinels (102.3, 360, 511, 15) are nullified with flags."""
    validator = RecordValidator()

    # Raw row with legacy sentinels
    raw = {
        "mmsi": "366745490",
        "timestamp_utc": "2025-01-01 00:00:00",
        "latitude": "33.7",
        "longitude": "-118.2",
        "sog": "102.3",
        "cog": "360.0",
        "heading": "511.0",
        "nav_status": "15",
    }
    ping, err = validator.validate_raw_row(source_row=1, raw=raw)
    assert err is None
    assert ping is not None
    assert ping.sog is None
    assert ping.cog is None
    assert ping.heading is None
    assert ping.nav_status is None
    assert FLAG_SOG_SENTINEL_NULLIFIED in ping.quality_flags
    assert FLAG_COG_SENTINEL_NULLIFIED in ping.quality_flags
    assert FLAG_HEADING_SENTINEL_NULLIFIED in ping.quality_flags
    assert FLAG_STATUS_SENTINEL_NULLIFIED in ping.quality_flags


def test_07_coordinate_limits_including_zero() -> None:
    """Verify coordinate domain enforcement and preservation of legitimate (0, 0) coordinates."""
    validator = RecordValidator()

    # Legitimate (0, 0) coordinates
    raw_zero = {
        "mmsi": "366745490",
        "timestamp_utc": "2025-01-01 00:00:00",
        "latitude": "0.0",
        "longitude": "0.0",
    }
    ping_zero, err_zero = validator.validate_raw_row(1, raw_zero)
    assert err_zero is None
    assert ping_zero is not None
    assert ping_zero.latitude == 0.0
    assert ping_zero.longitude == 0.0

    # Out-of-bounds latitude
    raw_bad_lat = {
        "mmsi": "366745490",
        "timestamp_utc": "2025-01-01 00:00:00",
        "latitude": "95.0",
        "longitude": "-118.2",
    }
    _, err_bad_lat = validator.validate_raw_row(2, raw_bad_lat)
    assert err_bad_lat == FLAG_HARD_INVALID_BAD_COORDINATES

    # Out-of-bounds longitude
    raw_bad_lon = {
        "mmsi": "366745490",
        "timestamp_utc": "2025-01-01 00:00:00",
        "latitude": "33.0",
        "longitude": "-195.0",
    }
    _, err_bad_lon = validator.validate_raw_row(3, raw_bad_lon)
    assert err_bad_lon == FLAG_HARD_INVALID_BAD_COORDINATES


def test_08_missing_or_invalid_timestamps() -> None:
    """Verify that unparseable or absent timestamps cause hard-invalid rejections."""
    validator = RecordValidator()

    raw_bad_ts = {
        "mmsi": "366745490",
        "timestamp_utc": "NOT_A_TIMESTAMP",
        "latitude": "33.0",
        "longitude": "-118.0",
    }
    _, err = validator.validate_raw_row(1, raw_bad_ts)
    assert err == FLAG_HARD_INVALID_BAD_TIMESTAMP

    raw_none_ts = {
        "mmsi": "366745490",
        "timestamp_utc": None,
        "latitude": "33.0",
        "longitude": "-118.0",
    }
    _, err2 = validator.validate_raw_row(2, raw_none_ts)
    assert err2 == FLAG_HARD_INVALID_BAD_TIMESTAMP


def test_09_exact_duplicate_observations() -> None:
    """Verify that exact duplicate observations are consolidated."""
    raw_rows = [
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:00:00",
            "latitude": "33.7",
            "longitude": "-118.2",
            "sog": "5.0",
        },
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:00:00",
            "latitude": "33.7",
            "longitude": "-118.2",
            "sog": "5.0",
        },
    ]
    cleaned, summary = process_and_clean_observations(raw_rows)
    assert len(cleaned) == 1
    assert summary["exact_duplicates_consolidated"] == 1
    assert FLAG_EXACT_DUPLICATE in cleaned[0].quality_flags


def test_10_conflicting_same_timestamp_records() -> None:
    """Verify observations with same MMSI/timestamp but different coords are retained."""
    raw_rows = [
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:00:00",
            "latitude": "33.70000",
            "longitude": "-118.20000",
        },
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:00:00",
            "latitude": "33.75000",
            "longitude": "-118.25000",
        },
    ]
    cleaned, summary = process_and_clean_observations(raw_rows)
    assert len(cleaned) == 2
    assert summary["timestamp_conflicts_flagged"] == 2
    for p in cleaned:
        assert FLAG_TIMESTAMP_POSITION_CONFLICT in p.quality_flags


def test_11_deterministic_chronological_ordering() -> None:
    """Verify that out-of-order pings are deterministically sorted chronologically."""
    raw_rows = [
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:10:00",
            "latitude": "33.72",
            "longitude": "-118.22",
        },
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:00:00",
            "latitude": "33.70",
            "longitude": "-118.20",
        },
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:05:00",
            "latitude": "33.71",
            "longitude": "-118.21",
        },
    ]
    cleaned, _ = process_and_clean_observations(raw_rows)
    assert len(cleaned) == 3
    assert [p.timestamp_utc.minute for p in cleaned] == [0, 5, 10]


def test_12_implied_speed_flagging() -> None:
    """Verify kinematic displacements exceeding speed threshold get warning flag."""
    raw_rows = [
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:00:00",
            "latitude": "33.70000",
            "longitude": "-118.20000",
        },
        # Move ~1 degree longitude (~50 nautical miles) in 60 seconds -> >3000 knots
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:01:00",
            "latitude": "33.70000",
            "longitude": "-117.20000",
        },
    ]
    cleaned, summary = process_and_clean_observations(raw_rows, speed_threshold_knots=50.0)
    assert len(cleaned) == 2
    second_ping = cleaned[1]
    assert FLAG_IMPLIED_SPEED_VIOLATION in second_ping.quality_flags
    assert second_ping.implied_speed_knots is not None
    assert second_ping.implied_speed_knots > 50.0
    assert summary["quality_flag_totals"][FLAG_IMPLIED_SPEED_VIOLATION] == 1


def test_13_zero_elapsed_time_behavior() -> None:
    """Verify zero elapsed time between consecutive pings records ZERO_ELAPSED_TIME flag."""
    raw_rows = [
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:00:00",
            "latitude": "33.70",
            "longitude": "-118.20",
        },
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:00:00",
            "latitude": "33.75",
            "longitude": "-118.25",
        },
    ]
    cleaned, _ = process_and_clean_observations(raw_rows)
    assert len(cleaned) == 2
    assert FLAG_ZERO_ELAPSED_TIME in cleaned[1].quality_flags
    assert cleaned[1].distance_nm is None
    assert cleaned[1].implied_speed_knots is None


def test_14_parquet_schema_roundtrip(tmp_path: Path) -> None:
    """Verify full PyArrow Table conversion, Parquet writing, and readback schema fidelity."""
    fixture_path = FIXTURES_DIR / "synthetic_2025_sample.csv"
    output_dir = tmp_path / "parquet_roundtrip"

    manifest = run_ingestion_pipeline(
        input_csv_path=fixture_path,
        output_dir_or_file=output_dir,
    )

    parquet_file = Path(manifest.output_parquet_path)
    assert parquet_file.is_file()

    table = read_parquet_dataset(parquet_file)
    schema = get_canonical_arrow_schema()

    assert table.schema.names == schema.names
    assert len(table) == manifest.output_row_count

    meta = inspect_parquet_metadata(parquet_file)
    assert meta["num_rows"] == manifest.output_row_count
    assert meta["serialized_size_bytes"] > 0


def test_15_invalid_input_and_overwrite_protection(tmp_path: Path) -> None:
    """Verify error handling on missing files and protection against overwrites."""
    # Non-existent input
    with pytest.raises(FileNotFoundError, match="does not exist"):
        run_ingestion_pipeline(
            input_csv_path="non_existent_file.csv",
            output_dir_or_file=tmp_path / "out",
        )

    # Overwrite protection
    fixture_path = FIXTURES_DIR / "synthetic_2025_sample.csv"
    output_dir = tmp_path / "overwrite_test"

    run_ingestion_pipeline(
        input_csv_path=fixture_path,
        output_dir_or_file=output_dir,
        overwrite=False,
    )

    # Attempting to rerun without overwrite=True must raise FileExistsError
    with pytest.raises(FileExistsError, match="already exists"):
        run_ingestion_pipeline(
            input_csv_path=fixture_path,
            output_dir_or_file=output_dir,
            overwrite=False,
        )


def test_16_repeated_run_behavior_and_determinism(tmp_path: Path) -> None:
    """Verify that repeated runs with overwrite=True produce identical, deterministic outputs."""
    fixture_path = FIXTURES_DIR / "synthetic_2025_sample.csv"
    output_dir = tmp_path / "deterministic_test"

    manifest1 = run_ingestion_pipeline(
        input_csv_path=fixture_path,
        output_dir_or_file=output_dir,
        overwrite=False,
    )

    manifest2 = run_ingestion_pipeline(
        input_csv_path=fixture_path,
        output_dir_or_file=output_dir,
        overwrite=True,
    )

    assert manifest1.output_row_count == manifest2.output_row_count
    assert manifest1.unique_vessels_count == manifest2.unique_vessels_count
    assert manifest1.hard_invalid_row_count == manifest2.hard_invalid_row_count
    assert manifest1.source_sha256 == manifest2.source_sha256


def test_17_malformed_decimal_mmsi_rejected() -> None:
    """Reject decimal/float/signed/boolean MMSIs rather than silently truncating."""
    invalid_values: list[object] = [
        "366745490.5",
        "366745490.0",
        "366745490.123",
        "123.45.67",
        366745490.5,
        366745490.0,
        "-366745490",
        "+366745490",
        "3.6674549e8",
        True,
        False,
        -123456789,
        0,
        1_000_000_000,
    ]
    for bad in invalid_values:
        clean, err = sanitize_mmsi(bad)
        assert clean is None, f"Expected None for malformed MMSI {bad!r}, got {clean!r}"
        assert err == FLAG_HARD_INVALID_BAD_MMSI

    # Valid integer-format MMSIs with and without leading zeros remain accepted
    assert sanitize_mmsi("003667454") == ("003667454", None)
    assert sanitize_mmsi("366745490") == ("366745490", None)
    assert sanitize_mmsi(3667454) == ("003667454", None)


def test_18_conflicting_same_timestamp_no_fictitious_movement() -> None:
    """Conflicting same-timestamp pings stay auditable without zero-time movement estimates."""
    raw_rows = [
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:00:00",
            "latitude": "33.70000",
            "longitude": "-118.20000",
        },
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:01:00",
            "latitude": "33.70100",
            "longitude": "-118.20100",
        },
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:01:00",
            "latitude": "33.75000",
            "longitude": "-118.25000",
        },
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:02:00",
            "latitude": "33.70200",
            "longitude": "-118.20200",
        },
    ]
    cleaned, summary = process_and_clean_observations(raw_rows)
    assert len(cleaned) == 4
    assert summary["timestamp_conflicts_flagged"] == 2

    # Conflicting records (rows 2 and 3) must not have fabricated movement estimates
    for conflict_ping in (cleaned[1], cleaned[2]):
        assert FLAG_TIMESTAMP_POSITION_CONFLICT in conflict_ping.quality_flags
        assert conflict_ping.prev_source_row is None
        assert conflict_ping.elapsed_seconds is None
        assert conflict_ping.distance_nm is None
        assert conflict_ping.implied_speed_knots is None

    assert FLAG_ZERO_ELAPSED_TIME in cleaned[2].quality_flags

    # Next unambiguous record (row 4) links back to the last unambiguous record (row 1)
    assert cleaned[3].prev_source_row == 1
    assert cleaned[3].elapsed_seconds == 120.0
    assert cleaned[3].distance_nm is not None and cleaned[3].distance_nm > 0.0


def test_19_same_position_different_metadata_not_silently_discarded() -> None:
    """Differing metadata at identical vessel/position/time is retained and flagged."""
    raw_rows = [
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:00:00",
            "latitude": "33.70000",
            "longitude": "-118.20000",
            "sog": "5.0",
            "vessel_name": "ALPHA",
        },
        # Exact full-record duplicate of row 1 -> should be consolidated
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:00:00",
            "latitude": "33.70000",
            "longitude": "-118.20000",
            "sog": "5.0",
            "vessel_name": "ALPHA",
        },
        # Same position and timestamp, but different SOG and vessel_name -> must be retained
        {
            "mmsi": "366745490",
            "timestamp_utc": "2025-01-01 00:00:00",
            "latitude": "33.70000",
            "longitude": "-118.20000",
            "sog": "12.5",
            "vessel_name": "BETA",
        },
    ]
    cleaned, summary = process_and_clean_observations(raw_rows)
    assert len(cleaned) == 2
    assert summary["exact_duplicates_consolidated"] == 1
    assert summary["metadata_conflicts_flagged"] == 2
    assert FLAG_EXACT_DUPLICATE in cleaned[0].quality_flags
    for p in cleaned:
        assert FLAG_TIMESTAMP_METADATA_CONFLICT in p.quality_flags
        assert p.distance_nm is None
        assert p.implied_speed_knots is None


def test_20_mixed_and_ambiguous_legacy_modern_headers() -> None:
    """Reject duplicate/ambiguous canonical header mappings; allow unambiguous mixed headers."""
    # Both legacy LAT and modern latitude present -> must reject
    with pytest.raises(SchemaAdapterError, match="Ambiguous header mapping"):
        detect_and_build_column_mapping(["mmsi", "base_date_time", "latitude", "LAT", "longitude"])

    # Both modern mmsi and legacy MMSI present -> must reject
    with pytest.raises(SchemaAdapterError, match="Ambiguous header mapping"):
        detect_and_build_column_mapping(["mmsi", "MMSI", "base_date_time", "latitude", "longitude"])

    # Duplicate exact header -> must reject
    with pytest.raises(SchemaAdapterError, match="Ambiguous header mapping"):
        detect_and_build_column_mapping(["mmsi", "mmsi", "base_date_time", "latitude", "longitude"])

    # Duplicate canonical target on optional column (status + Status) -> must reject
    with pytest.raises(SchemaAdapterError, match="Ambiguous header mapping"):
        detect_and_build_column_mapping(
            ["mmsi", "base_date_time", "latitude", "longitude", "status", "Status"]
        )

    # Unambiguous 1-to-1 mixed legacy/modern headers -> accepted cleanly
    schema_name, mapping = detect_and_build_column_mapping(
        ["MMSI", "base_date_time", "LAT", "longitude", "SOG"]
    )
    assert schema_name == "noaa_mixed"
    assert mapping == {
        "MMSI": "mmsi",
        "base_date_time": "timestamp_utc",
        "LAT": "latitude",
        "longitude": "longitude",
        "SOG": "sog",
    }
