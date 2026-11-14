"""End-to-end AIS ingestion pipeline: CSV parsing, cleaning, Parquet, and manifest."""

from __future__ import annotations

import csv
import hashlib
import time
from pathlib import Path
from typing import Any

from aegismar import __version__
from aegismar.common.constants import DEFAULT_IMPLIED_SPEED_THRESHOLD_KNOTS
from aegismar.common.types import IngestionManifest
from aegismar.ingestion.cleaner import process_and_clean_observations
from aegismar.ingestion.schema import detect_and_build_column_mapping
from aegismar.ingestion.storage import (
    canonical_pings_to_arrow_table,
    write_manifest,
    write_parquet_dataset,
)


def compute_file_sha256(file_path: Path | str) -> str:
    """Compute the SHA-256 hash of a file efficiently in 1MB chunks."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def run_ingestion_pipeline(
    input_csv_path: Path | str,
    output_dir_or_file: Path | str,
    speed_threshold_knots: float = DEFAULT_IMPLIED_SPEED_THRESHOLD_KNOTS,
    overwrite: bool = False,
) -> IngestionManifest:
    """Execute the complete CSV-to-Parquet ingestion pipeline.

    Parameters
    ----------
    input_csv_path : Path | str
        Path to raw or regional CSV file.
    output_dir_or_file : Path | str
        Target output directory (will contain 'cleaned_ais.parquet' and 'manifest.json')
        or direct path to output '.parquet' file.
    speed_threshold_knots : float
        Threshold for implied-speed violation warnings (default 50.0 knots).
    overwrite : bool
        If False, refuses to overwrite existing output files.

    Returns
    -------
    IngestionManifest
        Detailed provenance and validation manifest.
    """
    t_start = time.time()
    input_path = Path(input_csv_path)

    if not input_path.is_file():
        raise FileNotFoundError(f"Source AIS file does not exist: {input_path}")

    # Determine destination paths
    out_target = Path(output_dir_or_file)
    if out_target.suffix.lower() == ".parquet":
        output_parquet = out_target
        output_manifest = out_target.with_name(f"{out_target.stem}_manifest.json")
    else:
        output_parquet = out_target / "cleaned_ais.parquet"
        output_manifest = out_target / "manifest.json"

    # Check overwrite protection
    if not overwrite:
        if output_parquet.exists():
            raise FileExistsError(
                f"Destination Parquet file already exists: {output_parquet}. "
                "Pass overwrite=True to allow replacement."
            )
        if output_manifest.exists():
            raise FileExistsError(
                f"Destination manifest file already exists: {output_manifest}. "
                "Pass overwrite=True to allow replacement."
            )

    # 1. Compute input SHA-256
    source_sha256 = compute_file_sha256(input_path)

    # 2. Read headers and detect schema
    with open(input_path, encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        header_row = next(reader, None)
        if header_row is None:
            raise ValueError(f"Input file is completely empty: {input_path}")

    schema_detected, column_mapping = detect_and_build_column_mapping(header_row)

    # 3. Stream/load raw rows with mapped column names
    mapped_rows: list[dict[str, Any]] = []
    with open(input_path, encoding="utf-8", errors="replace") as f:
        dict_reader = csv.DictReader(f)
        for row in dict_reader:
            # Map source column names to canonical target names
            mapped_row = {
                target_col: row[source_col]
                for source_col, target_col in column_mapping.items()
                if source_col in row
            }
            mapped_rows.append(mapped_row)

    input_count = len(mapped_rows)

    # 4. Clean, validate, deduplicate, and compute implied speeds
    cleaned_pings, summary = process_and_clean_observations(
        raw_rows=mapped_rows,
        speed_threshold_knots=speed_threshold_knots,
    )

    # 5. Convert to PyArrow Table and persist to Parquet
    arrow_table = canonical_pings_to_arrow_table(cleaned_pings)
    write_parquet_dataset(table=arrow_table, output_parquet_path=output_parquet)

    # 6. Extract summary metadata
    if cleaned_pings:
        min_ts = min(p.timestamp_utc for p in cleaned_pings).isoformat()
        max_ts = max(p.timestamp_utc for p in cleaned_pings).isoformat()
    else:
        min_ts = ""
        max_ts = ""

    t_elapsed = time.time() - t_start

    manifest = IngestionManifest(
        source_file_path=str(input_path.resolve()),
        source_sha256=source_sha256,
        code_version=__version__,
        schema_detected=schema_detected,
        field_mappings=column_mapping,
        timestamp_range={"min_utc": min_ts, "max_utc": max_ts},
        input_row_count=input_count,
        output_row_count=len(cleaned_pings),
        hard_invalid_row_count=summary["hard_invalid_total"],
        exact_duplicate_count=summary["exact_duplicates_consolidated"],
        conflict_count=summary["timestamp_conflicts_flagged"],
        quality_flag_counts=summary["quality_flag_totals"],
        unique_vessels_count=summary["unique_mmsis"],
        processing_time_seconds=t_elapsed,
        output_parquet_path=str(output_parquet.resolve()),
    )

    # 7. Write manifest JSON
    write_manifest(manifest=manifest, output_manifest_path=output_manifest)

    return manifest
