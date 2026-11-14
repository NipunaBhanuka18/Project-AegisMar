"""Common type definitions and canonical record schemas for Project AegisMar."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class CanonicalPing:
    """Canonical representation of an AIS observation after schema normalization."""

    source_row: int
    mmsi: str
    timestamp_utc: datetime
    latitude: float
    longitude: float
    sog: float | None = None
    cog: float | None = None
    heading: float | None = None
    nav_status: int | None = None
    vessel_type: int | None = None
    vessel_name: str | None = None
    imo: str | None = None
    call_sign: str | None = None
    transceiver_class: str | None = None
    prev_source_row: int | None = None
    elapsed_seconds: float | None = None
    distance_nm: float | None = None
    implied_speed_knots: float | None = None
    quality_flags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class IngestionManifest:
    """Provenance and analytical accounting metadata emitted by the ingestion pipeline."""

    source_file_path: str
    source_sha256: str
    code_version: str
    schema_detected: str
    field_mappings: dict[str, str]
    timestamp_range: dict[str, str]
    input_row_count: int
    output_row_count: int
    hard_invalid_row_count: int
    exact_duplicate_count: int
    conflict_count: int
    quality_flag_counts: dict[str, int]
    unique_vessels_count: int
    processing_time_seconds: float
    output_parquet_path: str

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to serializable dictionary."""
        return {
            "source_file_path": self.source_file_path,
            "source_sha256": self.source_sha256,
            "code_version": self.code_version,
            "schema_detected": self.schema_detected,
            "field_mappings": self.field_mappings,
            "timestamp_range": self.timestamp_range,
            "input_row_count": self.input_row_count,
            "output_row_count": self.output_row_count,
            "hard_invalid_row_count": self.hard_invalid_row_count,
            "exact_duplicate_count": self.exact_duplicate_count,
            "conflict_count": self.conflict_count,
            "quality_flag_counts": self.quality_flag_counts,
            "unique_vessels_count": self.unique_vessels_count,
            "processing_time_seconds": round(self.processing_time_seconds, 3),
            "output_parquet_path": self.output_parquet_path,
        }
