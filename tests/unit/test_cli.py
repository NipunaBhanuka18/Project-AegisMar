"""Unit tests for Project AegisMar CLI interface."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from aegismar import __version__
from aegismar.cli import build_parser, main
from aegismar.ingestion.provenance import compute_content_fingerprint, compute_file_sha256

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
SYNTHETIC_2025 = FIXTURE_DIR / "synthetic_2025_sample.csv"


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Test --help displays usage information and returns 0."""
    parser = build_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "aegismar" in captured.out
    assert "ingest" in captured.out


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    """Test --version displays current package version."""
    parser = build_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["--version"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert f"aegismar {__version__}" in captured.out


def test_cli_no_subcommand_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Running CLI with no arguments should display help and return 0."""
    ret = main([])
    assert ret == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out or "Available subcommands" in captured.out


def test_cli_ingest_valid_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Ingest command should succeed on valid input and write Parquet and manifest."""
    out_dir = tmp_path / "cli_output"
    ret = main(["ingest", "-i", str(SYNTHETIC_2025), "-o", str(out_dir)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Ingestion Completed Successfully!" in captured.out
    assert (out_dir / "cleaned_ais.parquet").is_file()
    assert (out_dir / "manifest.json").is_file()


def test_cli_ingest_missing_input(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Ingest command should fail cleanly with code 1 if input does not exist."""
    missing = tmp_path / "does_not_exist.csv"
    ret = main(["ingest", "-i", str(missing), "-o", str(tmp_path / "out")])
    assert ret == 1
    captured = capsys.readouterr()
    assert "Error: Input file not found" in captured.err


def test_cli_ingest_overwrite_behavior(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Ingest should reject overwriting without --overwrite, and succeed with it."""
    out_dir = tmp_path / "cli_overwrite"
    # First run: should succeed
    ret1 = main(["ingest", "-i", str(SYNTHETIC_2025), "-o", str(out_dir)])
    assert ret1 == 0

    # Second run without overwrite: should fail with code 1
    ret2 = main(["ingest", "-i", str(SYNTHETIC_2025), "-o", str(out_dir)])
    assert ret2 == 1
    captured2 = capsys.readouterr()
    assert "Error: Output destination exists" in captured2.err

    # Third run with --overwrite: should succeed
    ret3 = main(["ingest", "-i", str(SYNTHETIC_2025), "-o", str(out_dir), "--overwrite"])
    assert ret3 == 0
    captured3 = capsys.readouterr()
    assert "Ingestion Completed Successfully!" in captured3.out


def test_cli_ingest_custom_speed_threshold(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ingest with custom speed threshold should pass argument through."""
    out_dir = tmp_path / "cli_speed"
    ret = main(["ingest", "-i", str(SYNTHETIC_2025), "-o", str(out_dir), "-s", "30.0"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Speed threshold:  30.0 knots" in captured.out


def test_cli_cluster_end_to_end_and_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cluster subcommand should process Parquet inputs, export artifacts, and handle errors."""
    ingest_dir = tmp_path / "ingested"
    assert main(["ingest", "-i", str(SYNTHETIC_2025), "-o", str(ingest_dir)]) == 0
    parquet_file = ingest_dir / "cleaned_ais.parquet"
    cluster_dir = tmp_path / "clusters"

    # Valid run
    ret = main(
        [
            "cluster",
            "-i",
            str(parquet_file),
            "-o",
            str(cluster_dir),
            "--eps-spatial-m",
            "500",
            "--eps-temporal-s",
            "900",
            "--min-samples",
            "2",
        ]
    )
    assert ret == 0
    out = capsys.readouterr().out
    assert "Clustering Completed Successfully!" in out
    assert (cluster_dir / "cluster_assignments.parquet").is_file()
    assert (cluster_dir / "clustering_summary.json").is_file()
    assert (cluster_dir / "clusters_preview.geojson").is_file()
    assert (cluster_dir / "clusters_map.html").is_file()

    # Overwrite refusal
    ret_dup = main(["cluster", "-i", str(parquet_file), "-o", str(cluster_dir)])
    assert ret_dup == 1
    assert "Error: Output artifact exists" in capsys.readouterr().err

    # Invalid configuration
    ret_bad = main(
        [
            "cluster",
            "-i",
            str(parquet_file),
            "-o",
            str(tmp_path / "bad_cfg"),
            "--eps-spatial-m",
            "-10",
        ]
    )
    assert ret_bad == 1
    assert "Error: Invalid clustering configuration" in capsys.readouterr().err

    # Missing file
    ret_missing = main(
        ["cluster", "-i", str(tmp_path / "missing.parquet"), "-o", str(tmp_path / "m_out")]
    )
    assert ret_missing == 1
    assert "Error: Input file not found" in capsys.readouterr().err


def test_cli_verify_parity_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test verify-parity command executes and succeeds on valid Parquet dataset."""
    ingest_dir = tmp_path / "ingest_out"
    ret_ingest = main(["ingest", "-i", str(SYNTHETIC_2025), "-o", str(ingest_dir)])
    assert ret_ingest == 0
    parquet_file = ingest_dir / "cleaned_ais.parquet"

    ret_parity = main(
        [
            "verify-parity",
            "-i",
            str(parquet_file),
            "--eps-spatial-m",
            "500",
            "--eps-temporal-s",
            "900",
            "--min-samples",
            "2",
        ]
    )
    assert ret_parity == 0
    out = capsys.readouterr().out
    assert "Parity Verification Results:" in out
    assert "VERIFICATION SUCCESS" in out

    # Missing file returns 1
    ret_missing = main(["verify-parity", "-i", str(tmp_path / "missing.parquet")])
    assert ret_missing == 1
    assert "Error: Input file not found" in capsys.readouterr().err


def _ingested_parquet(tmp_path: Path) -> Path:
    ingest_dir = tmp_path / "fp_ingest"
    assert main(["ingest", "-i", str(SYNTHETIC_2025), "-o", str(ingest_dir)]) == 0
    return ingest_dir / "cleaned_ais.parquet"


def test_cli_fingerprint_json_is_read_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """fingerprint --json reports hashes and contracts without touching the file."""
    parquet_file = _ingested_parquet(tmp_path)
    capsys.readouterr()
    before_bytes = parquet_file.read_bytes()
    before_mtime = parquet_file.stat().st_mtime_ns

    ret = main(["fingerprint", "-i", str(parquet_file), "--json"])
    assert ret == 0
    report = json.loads(capsys.readouterr().out)

    expected = compute_content_fingerprint(parquet_file)
    assert report["path"] == str(parquet_file.resolve())
    assert report["file_sha256"] == compute_file_sha256(parquet_file)
    assert report["content_fingerprint_sha256"] == expected.content_fingerprint_sha256
    assert report["content_fingerprint_version"] == "aegismar-logical-v1"
    assert report["row_count"] == expected.row_count
    assert report["column_count"] == 19
    assert report["canonical_row_order"] == ["mmsi", "timestamp_utc", "source_row"]
    assert report["canonical_order_verified"] is True
    assert report["schema"][0] == {"name": "source_row", "type": "int64"}

    assert parquet_file.stat().st_mtime_ns == before_mtime
    assert parquet_file.read_bytes() == before_bytes


def test_cli_fingerprint_text_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Default text output lists the fingerprint fields and schema."""
    parquet_file = _ingested_parquet(tmp_path)
    before_mtime = parquet_file.stat().st_mtime_ns
    capsys.readouterr()

    ret = main(["fingerprint", "--input", str(parquet_file)])
    assert ret == 0
    out = capsys.readouterr().out
    assert "Dataset Fingerprint (read-only)" in out
    assert f"File SHA-256:              {compute_file_sha256(parquet_file)}" in out
    assert "Fingerprint Version:       aegismar-logical-v1" in out
    assert "Canonical Row Order:       mmsi, timestamp_utc, source_row" in out
    assert "Canonical Order Verified:  True" in out
    assert "  - timestamp_utc: timestamp[us, tz=UTC]" in out
    assert parquet_file.stat().st_mtime_ns == before_mtime


def test_cli_fingerprint_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Missing, non-Parquet, and unsupported-schema inputs return exit code 1."""
    missing = tmp_path / "missing.parquet"
    assert main(["fingerprint", "-i", str(missing)]) == 1
    assert "Error: Input file not found" in capsys.readouterr().err

    not_parquet = tmp_path / "bogus.parquet"
    not_parquet.write_bytes(b"this is not parquet")
    assert main(["fingerprint", "-i", str(not_parquet), "--json"]) == 1
    captured = capsys.readouterr()
    assert "Error: Cannot read input as Parquet" in captured.err
    assert captured.out == ""
    assert not_parquet.read_bytes() == b"this is not parquet"

    unsupported = tmp_path / "uint.parquet"
    pq.write_table(pa.table({"x": pa.array([1], type=pa.uint32())}), str(unsupported))
    assert main(["fingerprint", "-i", str(unsupported)]) == 1
    assert "Error: Unsupported dataset schema" in capsys.readouterr().err

    assert main(["fingerprint", "-i", str(tmp_path)]) == 1
    assert "Error: Input file not found" in capsys.readouterr().err
