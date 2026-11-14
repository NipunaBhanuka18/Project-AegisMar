"""Command-line interface for Project AegisMar analytics platform."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aegismar import __version__
from aegismar.common.constants import DEFAULT_IMPLIED_SPEED_THRESHOLD_KNOTS
from aegismar.ingestion.pipeline import run_ingestion_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="aegismar",
        description=(
            f"Project AegisMar CLI v{__version__}: Maritime Traffic Intelligence & Anomaly Platform"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"aegismar {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Ingestion subcommand
    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Ingest, validate, and convert raw/regional AIS CSV into canonical Parquet storage",
    )
    ingest_parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Path to source raw AIS CSV file",
    )
    ingest_parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=True,
        help="Target output directory (stores Parquet file and manifest.json) or Parquet filepath",
    )
    ingest_parser.add_argument(
        "--speed-threshold",
        "-s",
        type=float,
        default=DEFAULT_IMPLIED_SPEED_THRESHOLD_KNOTS,
        help=(
            "Implied speed threshold in knots for flagging anomalies "
            f"(default: {DEFAULT_IMPLIED_SPEED_THRESHOLD_KNOTS})"
        ),
    )
    ingest_parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Allow overwriting existing output Parquet and manifest files",
    )

    return parser


def handle_ingest(args: argparse.Namespace) -> int:
    """Execute the ingestion subcommand."""
    print("=================================================================")
    print("Project AegisMar - AIS Data Ingestion Pipeline")
    print("=================================================================")
    print(f"Source file:      {args.input}")
    print(f"Target output:    {args.output}")
    print(f"Speed threshold:  {args.speed_threshold} knots")
    print(f"Overwrite:        {args.overwrite}")
    print("-----------------------------------------------------------------")

    try:
        manifest = run_ingestion_pipeline(
            input_csv_path=args.input,
            output_dir_or_file=args.output,
            speed_threshold_knots=args.speed_threshold,
            overwrite=args.overwrite,
        )
    except FileNotFoundError as e:
        print(f"Error: Input file not found: {e}", file=sys.stderr)
        return 1
    except FileExistsError as e:
        print(f"Error: Output destination exists: {e}", file=sys.stderr)
        print("Hint: Pass --overwrite to permit replacement.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Fatal error during ingestion: {e}", file=sys.stderr)
        return 1

    parquet_size_mb = Path(manifest.output_parquet_path).stat().st_size / (1024 * 1024)

    print("\nIngestion Completed Successfully!")
    print("-----------------------------------------------------------------")
    print(f"Detected Schema:       {manifest.schema_detected}")
    print(f"Input Rows Scanned:    {manifest.input_row_count:,}")
    print(f"Accepted Output Rows:  {manifest.output_row_count:,}")
    print(f"Hard-Invalid Dropped:  {manifest.hard_invalid_row_count:,}")
    print(f"Duplicates Coerced:    {manifest.exact_duplicate_count:,}")
    print(f"Timestamp Conflicts:   {manifest.conflict_count:,}")
    print(f"Unique Vessels (MMSI): {manifest.unique_vessels_count:,}")
    t_min = manifest.timestamp_range["min_utc"]
    t_max = manifest.timestamp_range["max_utc"]
    print(f"Temporal Coverage:     {t_min} -> {t_max}")
    print(f"Output Parquet File:   {manifest.output_parquet_path} ({parquet_size_mb:.2f} MB)")
    print(f"Processing Time:       {manifest.processing_time_seconds:.2f} seconds")

    if manifest.quality_flag_counts:
        print("\nQuality Flag Summary:")
        for flag, count in sorted(manifest.quality_flag_counts.items(), key=lambda x: -x[1]):
            print(f"  - {flag}: {count:,}")
    print("=================================================================")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ingest":
        return handle_ingest(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
