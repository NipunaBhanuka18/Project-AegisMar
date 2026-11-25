"""Command-line interface for Project AegisMar analytics platform."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from aegismar import __version__
from aegismar.clustering.config import (
    DEFAULT_EPS_SPATIAL_M,
    DEFAULT_EPS_TEMPORAL_S,
    DEFAULT_H3_RESOLUTION,
    DEFAULT_MIN_SAMPLES,
    PROVIDER_BALLTREE,
    PROVIDER_H3,
    QualityFilterPolicy,
    STDBSCANConfig,
)
from aegismar.clustering.export import export_clustering_artifacts
from aegismar.clustering.st_dbscan import run_balltree_st_dbscan, run_h3_st_dbscan
from aegismar.clustering.types import load_clustering_dataset_from_parquet
from aegismar.common.constants import DEFAULT_IMPLIED_SPEED_THRESHOLD_KNOTS
from aegismar.ingestion.pipeline import run_ingestion_pipeline
from aegismar.ingestion.provenance import compute_content_fingerprint, compute_file_sha256


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

    # Clustering subcommand (BallTree ST-DBSCAN reference engine)
    cluster_parser = subparsers.add_parser(
        "cluster",
        help="Run reference Haversine BallTree ST-DBSCAN clustering on cleaned AIS Parquet",
    )
    cluster_parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Path to canonical cleaned AIS Parquet file",
    )
    cluster_parser.add_argument(
        "--output",
        "-o",
        type=str,
        required=True,
        help="Target output directory for clustering Parquet, summary JSON, GeoJSON, and map",
    )
    cluster_parser.add_argument(
        "--eps-spatial-m",
        type=float,
        default=DEFAULT_EPS_SPATIAL_M,
        help=f"Spatial search radius in meters (default: {DEFAULT_EPS_SPATIAL_M})",
    )
    cluster_parser.add_argument(
        "--eps-temporal-s",
        type=float,
        default=DEFAULT_EPS_TEMPORAL_S,
        help=f"Temporal threshold in seconds (default: {DEFAULT_EPS_TEMPORAL_S})",
    )
    cluster_parser.add_argument(
        "--min-samples",
        type=int,
        default=DEFAULT_MIN_SAMPLES,
        help=f"Minimum neighborhood observations including self (default: {DEFAULT_MIN_SAMPLES})",
    )
    cluster_parser.add_argument(
        "--include-timestamp-conflicts",
        action="store_true",
        default=False,
        help="Retain same-timestamp conflict rows instead of excluding them",
    )
    cluster_parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional deterministic row limit applied after canonical sorting",
    )
    cluster_parser.add_argument(
        "--provider",
        type=str,
        default=PROVIDER_BALLTREE,
        choices=[PROVIDER_BALLTREE, PROVIDER_H3, "balltree", "h3"],
        help=(
            f"Neighborhood provider engine: '{PROVIDER_BALLTREE}' or "
            f"'{PROVIDER_H3}' (default: {PROVIDER_BALLTREE})"
        ),
    )
    cluster_parser.add_argument(
        "--h3-resolution",
        type=int,
        default=DEFAULT_H3_RESOLUTION,
        help=f"H3 discrete grid resolution (default: {DEFAULT_H3_RESOLUTION}; supported: 7, 8, 9)",
    )
    cluster_parser.add_argument(
        "--h3-k-ring",
        type=int,
        default=None,
        help="Optional explicit H3 k-ring radius (default: auto-computed safe completeness bound)",
    )
    cluster_parser.add_argument(
        "--allow-uncalibrated-h3",
        action="store_true",
        default=False,
        help="Permit experimental uncalibrated H3 resolutions or ring extrapolations",
    )
    cluster_parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Allow overwriting existing clustering output artifacts",
    )

    # Parity verification subcommand
    parity_parser = subparsers.add_parser(
        "verify-parity",
        help="Verify bit-for-bit neighborhood and clustering parity between BallTree and H3",
    )
    parity_parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Path to cleaned Parquet dataset file",
    )
    parity_parser.add_argument(
        "--eps-spatial-m",
        type=float,
        default=DEFAULT_EPS_SPATIAL_M,
        help=f"Spatial neighborhood radius in meters (default: {DEFAULT_EPS_SPATIAL_M})",
    )
    parity_parser.add_argument(
        "--eps-temporal-s",
        type=float,
        default=DEFAULT_EPS_TEMPORAL_S,
        help=f"Temporal neighborhood threshold in seconds (default: {DEFAULT_EPS_TEMPORAL_S})",
    )
    parity_parser.add_argument(
        "--min-samples",
        type=int,
        default=DEFAULT_MIN_SAMPLES,
        help=f"Minimum samples for core point status (default: {DEFAULT_MIN_SAMPLES})",
    )
    parity_parser.add_argument(
        "--h3-resolution",
        type=int,
        default=DEFAULT_H3_RESOLUTION,
        help=f"H3 discrete grid resolution (default: {DEFAULT_H3_RESOLUTION}; calibrated: 7, 8, 9)",
    )
    parity_parser.add_argument(
        "--h3-k-ring",
        type=int,
        default=None,
        help="Optional explicit H3 k-ring radius override",
    )
    parity_parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional deterministic row limit",
    )

    # Read-only dataset fingerprint subcommand (W3-02A, ADR-011)
    fingerprint_parser = subparsers.add_parser(
        "fingerprint",
        help="Read-only: report file SHA-256 and logical content fingerprint of a Parquet file",
    )
    fingerprint_parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Path to Parquet dataset file (never modified)",
    )
    fingerprint_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit the fingerprint report as JSON",
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


def handle_cluster(args: argparse.Namespace) -> int:
    """Execute the ST-DBSCAN clustering subcommand (BallTree reference or H3 accelerated)."""
    provider_name = args.provider
    if provider_name == "balltree":
        provider_name = PROVIDER_BALLTREE
    elif provider_name == "h3":
        provider_name = PROVIDER_H3

    print("=================================================================")
    print(f"Project AegisMar - ST-DBSCAN Clustering ({provider_name})")
    print("=================================================================")
    print(f"Input Parquet:    {args.input}")
    print(f"Output Dir:       {args.output}")
    print(f"Provider:         {provider_name}")
    print(f"eps_spatial_m:    {args.eps_spatial_m} m")
    print(f"eps_temporal_s:   {args.eps_temporal_s} s")
    print(f"min_samples:      {args.min_samples}")
    if provider_name == PROVIDER_H3:
        print(f"H3 Resolution:    {args.h3_resolution}")
        if args.h3_k_ring is not None:
            print(f"H3 k-ring:        {args.h3_k_ring}")
    print("-----------------------------------------------------------------")

    try:
        policy = QualityFilterPolicy(
            exclude_timestamp_conflicts=not args.include_timestamp_conflicts,
        )
        config = STDBSCANConfig(
            eps_spatial_m=args.eps_spatial_m,
            eps_temporal_s=args.eps_temporal_s,
            min_samples=args.min_samples,
            provider=provider_name,
            h3_resolution=args.h3_resolution,
            h3_k_ring=args.h3_k_ring,
            h3_allow_uncalibrated=args.allow_uncalibrated_h3,
            quality_filter=policy,
        )
        dataset = load_clustering_dataset_from_parquet(
            parquet_path=args.input,
            quality_filter=policy,
            max_rows=args.max_rows,
        )
        if provider_name == PROVIDER_H3:
            result = run_h3_st_dbscan(
                dataset=dataset,
                config=config,
                resolution=args.h3_resolution,
                k_ring=args.h3_k_ring,
                measure_memory=True,
            )
        else:
            result = run_balltree_st_dbscan(
                dataset=dataset,
                config=config,
                measure_memory=True,
            )
        artifacts = export_clustering_artifacts(
            result=result,
            output_dir=args.output,
            overwrite=args.overwrite,
            extra_metadata={"input_parquet_path": str(Path(args.input).resolve())},
        )
    except FileNotFoundError as e:
        print(f"Error: Input file not found: {e}", file=sys.stderr)
        return 1
    except FileExistsError as e:
        print(f"Error: Output artifact exists: {e}", file=sys.stderr)
        print("Hint: Pass --overwrite to permit replacement.", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: Invalid clustering configuration: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Fatal error during clustering: {e}", file=sys.stderr)
        return 1

    print("\nClustering Completed Successfully!")
    print("-----------------------------------------------------------------")
    print(f"Provider:             {result.provider_name}")
    if provider_name == PROVIDER_H3 and "h3_resolution" in result.provider_metrics:
        print(f"H3 Resolution:        {result.provider_metrics['h3_resolution']}")
        print(f"H3 k-ring:            {result.provider_metrics['h3_k_ring']}")
        print(
            f"Contract:             {result.provider_metrics.get('completeness_contract', 'N/A')}"
        )
        print(f"Fallback Count:       {result.provider_metrics['fallback_count']}")
    print(f"Total Input Rows:     {result.dataset.total_input_count:,}")
    print(f"Excluded Rows:        {result.dataset.excluded_count:,}")
    print(f"Analyzed Rows:        {result.dataset.num_points:,}")
    print(f"Clusters Found:       {result.num_clusters:,}")
    print(f"Core Observations:    {result.core_count:,}")
    print(f"Border Observations:  {result.border_count:,}")
    print(f"Noise Observations:   {result.noise_count:,}")
    print(f"Build Time:           {result.build_time_seconds:.3f} s")
    print(f"Query Time:           {result.query_time_seconds:.3f} s")
    print(f"Clustering Time:      {result.clustering_time_seconds:.3f} s")
    print(f"Total Wall Time:      {result.total_time_seconds:.3f} s")
    peak_mb = result.peak_tracemalloc_bytes / (1024 * 1024)
    print(f"Peak Python Heap:     {peak_mb:.2f} MB")
    print(f"Parquet Artifact:     {artifacts['parquet']}")
    print(f"Summary Artifact:     {artifacts['summary']}")
    print(f"GeoJSON Preview:      {artifacts['geojson']}")
    print(f"Static Map Artifact:  {artifacts['html_map']}")
    print("=================================================================")
    return 0


def handle_verify_parity(args: argparse.Namespace) -> int:
    """Handle the verify-parity CLI command."""
    import hashlib

    from aegismar.clustering.h3_neighbors import verify_dataset_h3_balltree_parity

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    sha256 = hashlib.sha256(input_path.read_bytes()).hexdigest()

    policy = QualityFilterPolicy(exclude_timestamp_conflicts=True)
    dataset = load_clustering_dataset_from_parquet(
        parquet_path=str(input_path),
        quality_filter=policy,
        max_rows=args.max_rows,
    )
    config = STDBSCANConfig(
        eps_spatial_m=args.eps_spatial_m,
        eps_temporal_s=args.eps_temporal_s,
        min_samples=args.min_samples,
        quality_filter=policy,
    )

    print("=================================================================")
    print("Project AegisMar - Dataset-Scoped H3 vs. BallTree Parity Verification")
    print("=================================================================")
    print(f"Input Parquet:         {input_path}")
    print(f"Dataset SHA-256:       {sha256}")
    print(f"Analyzed Observations: {dataset.num_points:,}")
    print(f"eps_spatial_m:         {args.eps_spatial_m} m")
    print(f"eps_temporal_s:        {args.eps_temporal_s} s")
    print(f"min_samples:           {args.min_samples}")
    print(f"H3 Resolution:         {args.h3_resolution}")
    print("-----------------------------------------------------------------")
    print("Executing parity verification across all observations...")

    res = verify_dataset_h3_balltree_parity(
        dataset=dataset,
        config=config,
        resolution=args.h3_resolution,
        k_ring=args.h3_k_ring,
        dataset_sha256=sha256,
    )

    print("\nParity Verification Results:")
    print("-----------------------------------------------------------------")
    print(f"CSR Graph Edge Count:  BT={res.total_edges_balltree:,} | H3={res.total_edges_h3:,}")
    indptr_str = "PASS (Identical degrees)" if res.csr_indptr_match else "FAIL"
    indices_str = "PASS (Identical neighbors)" if res.csr_indices_match else "FAIL"
    print(f"CSR indptr Match:      {indptr_str}")
    print(f"CSR indices Match:     {indices_str}")
    print(f"Cluster Count Match:   {'PASS' if res.clusters_match else 'FAIL'}")
    print(f"Core/Border/Noise:     {'PASS' if res.roles_match else 'FAIL'}")
    print(f"Cluster Labels Match:  {'PASS' if res.labels_match else 'FAIL'}")
    print(f"BallTree Query Time:   {res.balltree_query_time_s:.3f} s")
    print(f"H3 Query Time:         {res.h3_query_time_s:.3f} s")
    print(f"Graph Query Speedup:   {res.graph_query_speedup:.2f}x")
    print(f"H3 Fallback Count:     {res.h3_metrics['fallback_count']}")
    print(f"Completeness Contract: {res.h3_metrics['completeness_contract']}")
    print(f"Is Calibrated:         {res.h3_metrics['is_calibrated']}")
    print("=================================================================")

    if res.is_perfect_parity:
        print("VERIFICATION SUCCESS: 100% Bit-for-Bit Parity Confirmed on this dataset!")
        return 0

    print(
        "VERIFICATION FAILED: Neighborhood or clustering parity mismatch detected!",
        file=sys.stderr,
    )
    return 1


def handle_fingerprint(args: argparse.Namespace) -> int:
    """Execute the read-only fingerprint subcommand."""
    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        fingerprint = compute_content_fingerprint(input_path)
        file_sha256 = compute_file_sha256(input_path)
    except TypeError as e:
        print(f"Error: Unsupported dataset schema: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: Cannot read input as Parquet: {input_path}: {e}", file=sys.stderr)
        return 1

    report: dict[str, Any] = {
        "path": str(input_path.resolve()),
        "file_sha256": file_sha256,
        "content_fingerprint_sha256": fingerprint.content_fingerprint_sha256,
        "content_fingerprint_version": fingerprint.content_fingerprint_version,
        "row_count": fingerprint.row_count,
        "column_count": fingerprint.column_count,
        "canonical_row_order": fingerprint.canonical_row_order,
        "canonical_order_verified": fingerprint.canonical_order_verified,
        "schema": fingerprint.schema,
    }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print("=================================================================")
    print("Project AegisMar - Dataset Fingerprint (read-only)")
    print("=================================================================")
    print(f"Path:                      {report['path']}")
    print(f"File SHA-256:              {report['file_sha256']}")
    print(f"Content Fingerprint:       {report['content_fingerprint_sha256']}")
    print(f"Fingerprint Version:       {report['content_fingerprint_version']}")
    print(f"Row Count:                 {report['row_count']:,}")
    print(f"Column Count:              {report['column_count']}")
    print(f"Canonical Row Order:       {', '.join(report['canonical_row_order'])}")
    print(f"Canonical Order Verified:  {report['canonical_order_verified']}")
    print("Schema:")
    for field in fingerprint.schema:
        print(f"  - {field['name']}: {field['type']}")
    print("=================================================================")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ingest":
        return handle_ingest(args)
    if args.command == "cluster":
        return handle_cluster(args)
    if args.command == "verify-parity":
        return handle_verify_parity(args)
    if args.command == "fingerprint":
        return handle_fingerprint(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
