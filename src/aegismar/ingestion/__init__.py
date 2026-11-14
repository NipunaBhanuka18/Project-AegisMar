"""AIS data ingestion, validation, and columnar storage subsystem."""

from __future__ import annotations

from aegismar.ingestion.cleaner import (
    RecordValidator,
    parse_utc_timestamp,
    process_and_clean_observations,
    sanitize_mmsi,
)
from aegismar.ingestion.pipeline import compute_file_sha256, run_ingestion_pipeline
from aegismar.ingestion.schema import (
    NOAA_2025_MAPPINGS,
    NOAA_LEGACY_MAPPINGS,
    SchemaAdapterError,
    detect_and_build_column_mapping,
    get_canonical_arrow_schema,
    get_field_semantics,
)
from aegismar.ingestion.storage import (
    canonical_pings_to_arrow_table,
    inspect_parquet_metadata,
    read_parquet_dataset,
    write_manifest,
    write_parquet_dataset,
)

__all__ = [
    "NOAA_2025_MAPPINGS",
    "NOAA_LEGACY_MAPPINGS",
    "RecordValidator",
    "SchemaAdapterError",
    "canonical_pings_to_arrow_table",
    "compute_file_sha256",
    "detect_and_build_column_mapping",
    "get_canonical_arrow_schema",
    "get_field_semantics",
    "inspect_parquet_metadata",
    "parse_utc_timestamp",
    "process_and_clean_observations",
    "read_parquet_dataset",
    "run_ingestion_pipeline",
    "sanitize_mmsi",
    "write_manifest",
    "write_parquet_dataset",
]
