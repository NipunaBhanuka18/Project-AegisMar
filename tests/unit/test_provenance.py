"""Unit tests for W3-02A dataset provenance and aegismar-logical-v1 fingerprinting."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from aegismar.ingestion.provenance import (
    CONTENT_FINGERPRINT_VERSION,
    collect_runtime_provenance,
    compute_content_fingerprint,
    compute_file_sha256,
    verify_canonical_row_order,
)
from aegismar.ingestion.schema import (
    CANONICAL_ROW_ORDER,
    get_canonical_arrow_schema,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
T0 = datetime(2025, 1, 1, tzinfo=UTC)


def _rows() -> list[dict[str, Any]]:
    """Return canonical rows sorted by (mmsi, timestamp_utc, source_row)."""
    base: dict[str, Any] = {
        "latitude": 33.7,
        "longitude": -118.2,
        "sog": 5.5,
        "cog": 90.0,
        "heading": 91.0,
        "nav_status": 0,
        "vessel_type": 70,
        "vessel_name": "ALPHA",
        "imo": "IMO1234567",
        "call_sign": "WXYZ",
        "transceiver_class": "A",
        "prev_source_row": None,
        "elapsed_seconds": None,
        "distance_nm": None,
        "implied_speed_knots": None,
        "quality_flags": [],
    }
    return [
        {**base, "source_row": 3, "mmsi": "111111111", "timestamp_utc": T0},
        {
            **base,
            "source_row": 1,
            "mmsi": "111111111",
            "timestamp_utc": T0 + timedelta(seconds=60),
            "prev_source_row": 3,
            "elapsed_seconds": 60.0,
            "distance_nm": 0.25,
            "implied_speed_knots": 15.0,
            "quality_flags": ["IMPLIED_SPEED_VIOLATION"],
        },
        {
            **base,
            "source_row": 4,
            "mmsi": "111111111",
            "timestamp_utc": T0 + timedelta(seconds=60),
            "quality_flags": None,
            "vessel_name": None,
        },
        {
            **base,
            "source_row": 2,
            "mmsi": "222222222",
            "timestamp_utc": T0,
            "sog": None,
            "vessel_name": "",
        },
    ]


def _table(rows: list[dict[str, Any]] | None = None, schema: Any = None) -> Any:
    return pa.Table.from_pylist(
        rows if rows is not None else _rows(),
        schema=schema if schema is not None else get_canonical_arrow_schema(),
    )


def _fp(source: Any) -> str:
    return compute_content_fingerprint(source).content_fingerprint_sha256


def _write(table: Any, path: Path, **kwargs: Any) -> Path:
    pq.write_table(table, str(path), **kwargs)
    return path


def test_fingerprint_result_fields() -> None:
    result = compute_content_fingerprint(_table())
    assert result.content_fingerprint_version == CONTENT_FINGERPRINT_VERSION
    assert result.row_count == 4
    assert result.column_count == 19
    assert result.canonical_row_order == list(CANONICAL_ROW_ORDER)
    assert result.canonical_order_verified is True
    assert result.schema[0] == {"name": "source_row", "type": "int64"}
    assert result.schema[2] == {"name": "timestamp_utc", "type": "timestamp[us, tz=UTC]"}
    assert len(result.content_fingerprint_sha256) == 64
    assert result.to_dict()["row_count"] == 4


def test_writer_encoding_and_metadata_invariance(tmp_path: Path) -> None:
    """Different Parquet bytes, identical logical content fingerprint."""
    table = _table()
    variants: dict[str, dict[str, Any]] = {
        "zstd": {"compression": "zstd"},
        "snappy": {"compression": "snappy"},
        "none": {"compression": "none"},
        "no_dict": {"compression": "zstd", "use_dictionary": False},
        "rg1": {"compression": "zstd", "row_group_size": 1},
        "rg2": {"compression": "zstd", "row_group_size": 2},
        "rg_full": {"compression": "zstd", "row_group_size": table.num_rows},
    }
    paths = {
        name: _write(table, tmp_path / f"{name}.parquet", **kw) for name, kw in variants.items()
    }
    meta_table = table.replace_schema_metadata({"writer": "extra-footer-kv", "run": "42"})
    paths["footer_kv"] = _write(meta_table, tmp_path / "footer_kv.parquet", compression="zstd")

    file_hashes = {name: compute_file_sha256(p) for name, p in paths.items()}
    # A single full-table row group is the writer default for 4 rows, so "rg_full"
    # may be byte-identical to "zstd"; every other variant must differ on disk.
    distinct_variants = {k: v for k, v in file_hashes.items() if k != "rg_full"}
    assert len(set(distinct_variants.values())) == len(distinct_variants), file_hashes

    expected = _fp(table)
    for name, p in paths.items():
        assert _fp(p) == expected, name
        assert _fp(str(p)) == expected, name
    assert _fp(meta_table) == expected


def test_table_batch_boundaries_invariance() -> None:
    table = _table()
    rechunked = pa.concat_tables([table.slice(0, 1), table.slice(1, 2), table.slice(3)])
    assert rechunked.column(0).num_chunks == 3
    assert _fp(rechunked) == _fp(table)


def test_order_sensitivity() -> None:
    rows = _rows()
    swapped = [rows[1], rows[0], rows[2], rows[3]]
    original = compute_content_fingerprint(_table(rows))
    reordered = compute_content_fingerprint(_table(swapped))
    assert original.canonical_order_verified is True
    assert reordered.canonical_order_verified is False
    assert reordered.content_fingerprint_sha256 != original.content_fingerprint_sha256


@pytest.mark.parametrize(
    ("row_index", "column", "value"),
    [
        (1, "prev_source_row", 2),
        (1, "elapsed_seconds", 61.0),
        (1, "distance_nm", 0.26),
        (1, "implied_speed_knots", 15.5),
        (0, "quality_flags", None),
        (0, "quality_flags", ["FLAG"]),
        (2, "quality_flags", []),
        (3, "vessel_name", None),
        (2, "vessel_name", ""),
        (0, "sog", None),
        (0, "nav_status", 1),
        (0, "mmsi", "111111110"),
        (0, "timestamp_utc", T0 - timedelta(microseconds=1)),
    ],
)
def test_value_null_and_derived_column_sensitivity(row_index: int, column: str, value: Any) -> None:
    rows = _rows()
    baseline = _fp(_table(rows))
    rows[row_index] = {**rows[row_index], column: value}
    assert _fp(_table(rows)) != baseline


def test_quality_flags_empty_vs_null_vs_value_all_distinct() -> None:
    fingerprints = set()
    for flags in ([], None, ["FLAG"], [None], [""]):
        rows = _rows()
        rows[0] = {**rows[0], "quality_flags": flags}
        fingerprints.add(_fp(_table(rows)))
    assert len(fingerprints) == 5


def test_schema_type_name_and_order_sensitivity() -> None:
    table = _table()
    baseline = _fp(table)

    schema = get_canonical_arrow_schema()
    idx = schema.get_field_index("vessel_type")
    retyped = table.cast(schema.set(idx, pa.field("vessel_type", pa.int32())))
    assert _fp(retyped) != baseline

    renamed = table.rename_columns([*table.column_names[:-1], "flags"])
    assert _fp(renamed) != baseline

    reordered_cols = table.select(
        [table.column_names[1], table.column_names[0], *table.column_names[2:]]
    )
    assert _fp(reordered_cols) != baseline


def test_nullability_and_field_metadata_ignored() -> None:
    table = _table()
    schema = get_canonical_arrow_schema()
    idx = schema.get_field_index("mmsi")
    strict = schema.set(idx, pa.field("mmsi", pa.string(), nullable=False, metadata={"note": "x"}))
    assert _fp(table.cast(strict)) == _fp(table)


def test_float_zero_normalization_and_nan_determinism() -> None:
    def with_values(f64: float, f32: float) -> Any:
        rows = _rows()
        rows[0] = {**rows[0], "distance_nm": f64, "sog": f32}
        return _table(rows)

    assert _fp(with_values(-0.0, -0.0)) == _fp(with_values(0.0, 0.0))

    nan_a = _fp(with_values(float("nan"), float("nan")))
    nan_b = _fp(with_values(float("nan"), float("nan")))
    assert nan_a == nan_b
    assert nan_a != _fp(with_values(0.0, 0.0))

    # A NaN with a different payload/sign still hashes as the canonical quiet NaN
    neg_nan = -float("nan")
    assert _fp(with_values(neg_nan, neg_nan)) == nan_a


def test_bool_and_large_types_supported() -> None:
    table = pa.table(
        {
            "flag": pa.array([True, False, None], type=pa.bool_()),
            "name": pa.array(["a", None, ""], type=pa.large_string()),
            "tags": pa.array([["x"], None, []], type=pa.large_list(pa.string())),
            "n32": pa.array([1, None, -1], type=pa.int32()),
        }
    )
    result = compute_content_fingerprint(table)
    assert result.row_count == 3
    assert result.canonical_order_verified is False  # order columns absent

    flipped = table.set_column(0, "flag", pa.array([False, False, None], type=pa.bool_()))
    assert _fp(flipped) != result.content_fingerprint_sha256


def test_unsupported_arrow_type_raises() -> None:
    table = pa.table({"x": pa.array([1, 2], type=pa.uint32())})
    with pytest.raises(TypeError, match="Unsupported Arrow type"):
        compute_content_fingerprint(table)

    dict_table = pa.table({"s": pa.array(["a", "b"]).dictionary_encode()})
    with pytest.raises(TypeError, match="Unsupported Arrow type"):
        compute_content_fingerprint(dict_table)


def test_empty_table_fingerprint_and_order() -> None:
    empty = _table([])
    result = compute_content_fingerprint(empty)
    assert result.row_count == 0
    assert result.canonical_order_verified is True
    assert result.content_fingerprint_sha256 != _fp(_table())


def test_verify_canonical_row_order_cases(tmp_path: Path) -> None:
    rows = _rows()
    assert verify_canonical_row_order(_table(rows)) is True
    assert verify_canonical_row_order(_table(rows[:1])) is True

    # Parquet source with multiple row groups/batches
    path = _write(_table(rows), tmp_path / "ordered.parquet", row_group_size=1)
    assert verify_canonical_row_order(path) is True

    # Duplicate key (not strictly ascending)
    dup = [rows[0], {**rows[0]}]
    assert verify_canonical_row_order(_table(dup)) is False

    # source_row tie-break descending within same (mmsi, timestamp)
    tie = [rows[0], rows[2], rows[1], rows[3]]
    assert verify_canonical_row_order(_table(tie)) is False

    # Missing order column
    assert verify_canonical_row_order(_table(rows).drop_columns(["source_row"])) is False

    # Null key value
    null_ts = pa.table(
        {
            "mmsi": ["111111111", "111111111"],
            "timestamp_utc": pa.array([T0, None], type=pa.timestamp("us", tz="UTC")),
            "source_row": [1, 2],
        }
    )
    assert verify_canonical_row_order(null_ts) is False

    # Custom order columns
    assert verify_canonical_row_order(_table(rows), order_columns=("source_row",)) is False


def test_compute_file_sha256_matches_hashlib(tmp_path: Path) -> None:
    import hashlib

    payload = b"x" * (1024 * 1024 + 17)
    p = tmp_path / "blob.bin"
    p.write_bytes(payload)
    assert compute_file_sha256(p) == hashlib.sha256(payload).hexdigest()


def test_collect_runtime_provenance_in_repo() -> None:
    prov = collect_runtime_provenance(REPO_ROOT)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert prov.git_commit_sha == head
    assert isinstance(prov.git_dirty, bool)
    assert prov.python_version.startswith("3.11")
    assert prov.pyarrow_version == pa.__version__
    assert prov.generated_at_utc.endswith("Z")
    datetime.fromisoformat(prov.generated_at_utc.replace("Z", "+00:00"))

    default = collect_runtime_provenance()
    assert default.git_commit_sha == head


def test_collect_runtime_provenance_outside_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    prov = collect_runtime_provenance(tmp_path)
    assert prov.git_commit_sha is None
    assert prov.git_dirty is None
    assert prov.pyarrow_version == pa.__version__


def test_collect_runtime_provenance_without_git_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _missing_git(*_args: Any, **_kwargs: Any) -> Any:
        raise FileNotFoundError("git not installed")

    monkeypatch.setattr(subprocess, "run", _missing_git)
    prov = collect_runtime_provenance(tmp_path)
    assert prov.git_commit_sha is None
    assert prov.git_dirty is None
