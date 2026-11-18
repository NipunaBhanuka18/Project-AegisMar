"""Unit tests for Project AegisMar CLI interface."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegismar import __version__
from aegismar.cli import build_parser, main

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
