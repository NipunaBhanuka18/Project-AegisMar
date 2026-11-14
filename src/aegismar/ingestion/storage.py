"""Parquet columnar storage and ingestion manifest writer for AegisMar."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from aegismar.common.types import CanonicalPing, IngestionManifest
from aegismar.ingestion.schema import get_canonical_arrow_schema


def canonical_pings_to_arrow_table(pings: list[CanonicalPing]) -> pa.Table:
    """Convert a sequence of CanonicalPing records into a strictly-typed PyArrow Table.

    Parameters
    ----------
    pings : list[CanonicalPing]
        List of cleaned, sorted CanonicalPing dataclass objects.

    Returns
    -------
    pa.Table
        PyArrow Table adhering strictly to the canonical schema.
    """
    schema = get_canonical_arrow_schema()

    source_row_data = [p.source_row for p in pings]
    mmsi_data = [p.mmsi for p in pings]
    timestamp_data = [p.timestamp_utc for p in pings]
    latitude_data = [p.latitude for p in pings]
    longitude_data = [p.longitude for p in pings]
    sog_data = [p.sog for p in pings]
    cog_data = [p.cog for p in pings]
    heading_data = [p.heading for p in pings]
    status_data = [p.nav_status for p in pings]
    vessel_type_data = [p.vessel_type for p in pings]
    vessel_name_data = [p.vessel_name for p in pings]
    imo_data = [p.imo for p in pings]
    call_sign_data = [p.call_sign for p in pings]
    transceiver_data = [p.transceiver_class for p in pings]
    prev_source_row_data = [p.prev_source_row for p in pings]
    elapsed_seconds_data = [p.elapsed_seconds for p in pings]
    distance_nm_data = [p.distance_nm for p in pings]
    implied_speed_data = [p.implied_speed_knots for p in pings]
    quality_flags_data = [p.quality_flags for p in pings]

    arrays = [
        pa.array(source_row_data, type=pa.int64()),
        pa.array(mmsi_data, type=pa.string()),
        pa.array(timestamp_data, type=pa.timestamp("us", tz="UTC")),
        pa.array(latitude_data, type=pa.float64()),
        pa.array(longitude_data, type=pa.float64()),
        pa.array(sog_data, type=pa.float32()),
        pa.array(cog_data, type=pa.float32()),
        pa.array(heading_data, type=pa.float32()),
        pa.array(status_data, type=pa.int8()),
        pa.array(vessel_type_data, type=pa.int16()),
        pa.array(vessel_name_data, type=pa.string()),
        pa.array(imo_data, type=pa.string()),
        pa.array(call_sign_data, type=pa.string()),
        pa.array(transceiver_data, type=pa.string()),
        pa.array(prev_source_row_data, type=pa.int64()),
        pa.array(elapsed_seconds_data, type=pa.float64()),
        pa.array(distance_nm_data, type=pa.float64()),
        pa.array(implied_speed_data, type=pa.float64()),
        pa.array(quality_flags_data, type=pa.list_(pa.string())),
    ]

    return pa.Table.from_arrays(arrays, schema=schema)


def write_parquet_dataset(
    table: pa.Table,
    output_parquet_path: Path | str,
    compression: str = "zstd",
) -> Path:
    """Write PyArrow table to a compressed Parquet file.

    Parameters
    ----------
    table : pa.Table
        The PyArrow table to persist.
    output_parquet_path : Path | str
        Destination path for the Parquet file.
    compression : str
        Compression codec (default 'zstd').

    Returns
    -------
    Path
        Path of the written Parquet file.
    """
    path = Path(output_parquet_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    pq.write_table(
        table,
        where=str(path),
        compression=compression,
        use_dictionary=True,
    )
    return path


def write_manifest(manifest: IngestionManifest, output_manifest_path: Path | str) -> Path:
    """Write ingestion manifest to a structured JSON file."""
    path = Path(output_manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2)

    return path


def read_parquet_dataset(parquet_path: Path | str) -> pa.Table:
    """Read a canonical AIS Parquet file into memory as a PyArrow Table."""
    path = Path(parquet_path)
    if not path.is_file():
        raise FileNotFoundError(f"Parquet file does not exist: {path}")

    return pq.read_table(str(path))


def inspect_parquet_metadata(parquet_path: Path | str) -> dict[str, Any]:
    """Inspect schema, row counts, and metadata of a written Parquet file."""
    path = Path(parquet_path)
    parquet_file = pq.ParquetFile(str(path))
    meta = parquet_file.metadata
    schema = parquet_file.schema_arrow

    return {
        "file_path": str(path),
        "num_rows": meta.num_rows,
        "num_columns": meta.num_columns,
        "num_row_groups": meta.num_row_groups,
        "serialized_size_bytes": path.stat().st_size,
        "schema_names": schema.names,
    }
