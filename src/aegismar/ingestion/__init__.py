"""AIS data ingestion, validation, and columnar storage subsystem."""

from __future__ import annotations

from aegismar.ingestion.cleaner import (
    RecordValidator,
    parse_utc_timestamp,
    process_and_clean_observations,
    sanitize_mmsi,
)
from aegismar.ingestion.pipeline import run_ingestion_pipeline
from aegismar.ingestion.provenance import (
    CONTENT_FINGERPRINT_VERSION,
    ContentFingerprintResult,
    RuntimeProvenance,
    collect_runtime_provenance,
    compute_content_fingerprint,
    compute_file_sha256,
    verify_canonical_row_order,
)
from aegismar.ingestion.schema import (
    CANONICAL_ROW_ORDER,
    NOAA_2025_MAPPINGS,
    NOAA_LEGACY_MAPPINGS,
    SCHEMA_CONTRACT_VERSION,
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
    "CANONICAL_ROW_ORDER",
    "CONTENT_FINGERPRINT_VERSION",
    "NOAA_2025_MAPPINGS",
    "NOAA_LEGACY_MAPPINGS",
    "SCHEMA_CONTRACT_VERSION",
    "ContentFingerprintResult",
    "RecordValidator",
    "RuntimeProvenance",
    "SchemaAdapterError",
    "canonical_pings_to_arrow_table",
    "collect_runtime_provenance",
    "compute_content_fingerprint",
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
    "verify_canonical_row_order",
    "write_manifest",
    "write_parquet_dataset",
]
