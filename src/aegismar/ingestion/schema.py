"""Schema adaptation, header mapping, and canonical PyArrow schema definitions."""

from __future__ import annotations

from collections.abc import Mapping

import pyarrow as pa

# NOAA 2025+ snake_case canonical mappings
NOAA_2025_MAPPINGS: dict[str, str] = {
    "mmsi": "mmsi",
    "base_date_time": "timestamp_utc",
    "latitude": "latitude",
    "longitude": "longitude",
    "sog": "sog",
    "cog": "cog",
    "heading": "heading",
    "status": "nav_status",
    "vessel_type": "vessel_type",
    "vessel_name": "vessel_name",
    "imo": "imo",
    "call_sign": "call_sign",
    "transceiver": "transceiver_class",
}

# NOAA 2018-2024 legacy PascalCase mappings
NOAA_LEGACY_MAPPINGS: dict[str, str] = {
    "MMSI": "mmsi",
    "BaseDateTime": "timestamp_utc",
    "LAT": "latitude",
    "LON": "longitude",
    "SOG": "sog",
    "COG": "cog",
    "Heading": "heading",
    "Status": "nav_status",
    "VesselType": "vessel_type",
    "VesselName": "vessel_name",
    "IMO": "imo",
    "CallSign": "call_sign",
    "TransceiverClass": "transceiver_class",
}

# Required canonical fields without which processing cannot occur
REQUIRED_CANONICAL_FIELDS: tuple[str, ...] = (
    "mmsi",
    "timestamp_utc",
    "latitude",
    "longitude",
)

# Canonical row-order contract for cleaned AIS datasets (ADR-011). Rows are sorted
# strictly ascending by this key; ``source_row`` breaks same-vessel, same-timestamp ties.
CANONICAL_ROW_ORDER: tuple[str, ...] = ("mmsi", "timestamp_utc", "source_row")

# Version of the canonical schema + row-order contract recorded in manifest.json.
SCHEMA_CONTRACT_VERSION: str = "1.0"


def get_canonical_arrow_schema() -> pa.Schema:
    """Return the official PyArrow schema for cleaned canonical AIS records."""
    return pa.schema(
        [
            ("source_row", pa.int64()),
            ("mmsi", pa.string()),
            ("timestamp_utc", pa.timestamp("us", tz="UTC")),
            ("latitude", pa.float64()),
            ("longitude", pa.float64()),
            ("sog", pa.float32()),
            ("cog", pa.float32()),
            ("heading", pa.float32()),
            ("nav_status", pa.int8()),
            ("vessel_type", pa.int16()),
            ("vessel_name", pa.string()),
            ("imo", pa.string()),
            ("call_sign", pa.string()),
            ("transceiver_class", pa.string()),
            ("prev_source_row", pa.int64()),
            ("elapsed_seconds", pa.float64()),
            ("distance_nm", pa.float64()),
            ("implied_speed_knots", pa.float64()),
            ("quality_flags", pa.list_(pa.string())),
        ]
    )


class SchemaAdapterError(ValueError):
    """Raised when an input schema cannot be recognized or contains conflicting mappings."""


# Unified case-insensitive alias lookup across NOAA 2025 and legacy schemas
_UNIFIED_LOWERCASE_ALIASES: dict[str, str] = {
    **{src.lower(): tgt for src, tgt in NOAA_LEGACY_MAPPINGS.items()},
    **{src.lower(): tgt for src, tgt in NOAA_2025_MAPPINGS.items()},
}


def detect_and_build_column_mapping(
    headers: list[str],
) -> tuple[str, dict[str, str]]:
    """Detect source schema format and construct an unambiguous column mapping.

    Inspects every source column across both modern NOAA 2025 (`snake_case`)
    and legacy NOAA 2018-2024 (`PascalCase`) header vocabularies. Any duplicate
    raw header or mixed legacy/modern header pair that resolves to the same
    canonical target is explicitly rejected via ``SchemaAdapterError`` rather
    than silently choosing one column.

    Parameters
    ----------
    headers : list[str]
        List of raw header names present in the source CSV.

    Returns
    -------
    tuple[str, dict[str, str]]
        A tuple of (schema_detected_name, mapping_dict_from_source_to_canonical).

    Raises
    ------
    SchemaAdapterError
        If required canonical columns are missing, or duplicate/ambiguous mappings exist.
    """
    clean_headers = [h.strip() for h in headers]

    mapping: dict[str, str] = {}
    target_to_sources: dict[str, list[str]] = {}
    families_used: set[str] = set()

    # 1. Resolve every header against both 2025 and legacy vocabularies
    for h in clean_headers:
        if h in NOAA_2025_MAPPINGS:
            target = NOAA_2025_MAPPINGS[h]
            families_used.add("2025")
        elif h in NOAA_LEGACY_MAPPINGS:
            target = NOAA_LEGACY_MAPPINGS[h]
            families_used.add("legacy")
        elif h.lower() in _UNIFIED_LOWERCASE_ALIASES:
            target = _UNIFIED_LOWERCASE_ALIASES[h.lower()]
            families_used.add("case_insensitive")
        else:
            continue

        target_to_sources.setdefault(target, []).append(h)
        mapping[h] = target

    # 2. Reject any duplicate or ambiguous canonical mappings before schema selection
    ambiguous = {tgt: srcs for tgt, srcs in target_to_sources.items() if len(srcs) > 1}
    if ambiguous:
        raise SchemaAdapterError(
            f"Ambiguous header mapping: multiple source columns map to same target: {ambiguous}"
        )

    # 3. Assign descriptive schema family name
    if families_used == {"2025"}:
        schema_name = "noaa_2025"
    elif families_used == {"legacy"}:
        schema_name = "noaa_legacy"
    elif families_used == {"2025", "legacy"}:
        schema_name = "noaa_mixed"
    elif families_used:
        schema_name = "generic_case_insensitive"
    else:
        schema_name = "unknown"

    # 4. Verify all required canonical fields are present
    mapped_targets = set(mapping.values())
    missing_required = [req for req in REQUIRED_CANONICAL_FIELDS if req not in mapped_targets]
    if missing_required:
        raise SchemaAdapterError(
            f"Input schema is missing required canonical fields: {missing_required}. "
            f"Headers present: {headers}"
        )

    return schema_name, mapping


def get_field_semantics() -> Mapping[str, str]:
    """Return dictionary explaining semantic definitions for canonical fields."""
    return {
        "source_row": "1-based line number in raw source CSV file for audit and traceability.",
        "mmsi": "9-character zero-padded Maritime Mobile Service Identity string.",
        "timestamp_utc": "UTC ISO 8601 timestamp with microsecond resolution.",
        "latitude": "WGS 84 geographic latitude in decimal degrees [-90.0, 90.0].",
        "longitude": "WGS 84 geographic longitude in decimal degrees [-180.0, 180.0].",
        "sog": "Speed Over Ground in knots; legacy 102.3 sentinel coerced to null.",
        "cog": "Course Over Ground in degrees [0.0, 359.9]; legacy 360.0 coerced to null.",
        "heading": "True Heading in degrees [0, 359]; legacy 511 coerced to null.",
        "nav_status": "ITU navigational status code (0-14); status 15 coerced to null.",
        "vessel_type": "ITU numeric vessel classification category code.",
        "vessel_name": "Vessel station license name string.",
        "imo": "International Maritime Organization vessel registration number.",
        "call_sign": "Radio call sign assigned by licensing authority.",
        "transceiver_class": "Transceiver equipment class ('A' commercial, 'B' small craft).",
        "prev_source_row": "Source row index of preceding valid observation for this vessel.",
        "elapsed_seconds": "Time delta in seconds from preceding observation.",
        "distance_nm": "Haversine geodesic displacement in nautical miles from preceding ping.",
        "implied_speed_knots": "Displacement divided by elapsed time in knots.",
        "quality_flags": "Array of analytical warning flags (e.g. IMPLIED_SPEED_VIOLATION).",
    }
