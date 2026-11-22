# ADR-003: Canonical PyArrow Schema with Explicit Quality Flags & Sentinel Nullification

**Status:** Accepted  
**Date:** 2026-11-14 (Hardened: 2026-11-18 in Milestone W2-01)  
**Deciders:** NipunaBhanuka18 (Project Lead)  
**Technical Scope:** Data Model, Ingestion Engine & Inter-Subsystem Contracts  

---

## 1. Context and Problem Statement

Raw AIS telemetry from international transponders contains widespread data quality flaws:
- Sentinel values defined by ITU-R M.1371 (e.g., Speed Over Ground `102.3` kt, True Heading `511`°, Course Over Ground `360.0`°, Navigational Status `15`).
- Dead-reckoning nulls `(0.0, 0.0)`, coordinate boundary violations, and malformed non-integer vessel identifiers.
- Duplicate transmissions, same-timestamp conflicting coordinates, and unannounced schema evolution between NOAA legacy formats (2018–2024 PascalCase) and NOAA modernized formats (2025+ snake_case).

If raw sentinels or coordinates are passed into spatial indexing or kinematic anomaly algorithms, distance trees and velocity models produce severe distortions (e.g. SOG of 102.3 kt triggering false teleportation alerts). We needed a strictly typed, immutable canonical data representation.

---

## 2. Considered Alternatives

### Alternative A: Ad-Hoc Pandas DataFrames with In-Place Mutation
- **Concept:** Load raw CSV into Pandas, apply ad-hoc vector filters (`df.drop()`), and pass mutable dataframes directly to clustering functions.
- **Evaluation at Decision Time (2026-11-14):** Evaluated and rejected. Mutable dataframes create implicit column-type coercions, lack microsecond timestamp guarantees, drop traceability back to original CSV row numbers, and silently propagate NaN/null inconsistencies.

### Alternative B: Silent Deletion of All Imperfect Pings
- **Concept:** Drop any row that contains missing heading, missing status, or same-timestamp conflicts.
- **Evaluation at Decision Time (2026-11-14; hardened 2026-11-18):** Evaluated and rejected. Dropping records with missing heading or status discards over 50% of commercial vessel broadcasts (e.g., 52.3% of San Pedro Bay pings omit heading or navigational status). Same-timestamp observations with differing metadata must be preserved for auditability rather than silently purged.

---

## 3. Decision

We define an official, immutable **19-column PyArrow Canonical Schema** (`get_canonical_arrow_schema()`) and clean records through a deterministic pipeline that:
1. Replaces ITU sentinels with explicit typed nulls (`None`) rather than dropping valid spatial pings.
2. Preserves MMSIs strictly as 9-character zero-padded strings (`"003671234"`), rejecting malformed decimal/float inputs.
3. Consolidates exact duplicate rows and preserves same-timestamp conflicts with analytical quality flags (`TIMESTAMP_POSITION_CONFLICT`, `TIMESTAMP_METADATA_CONFLICT`, `IMPLIED_SPEED_VIOLATION`, `ZERO_ELAPSED_TIME`).
4. Preserves 1-based original CSV row indices (`source_row`, `prev_source_row`) for permanent auditability.
5. Employs a strict schema adapter (`detect_and_build_column_mapping`) that rejects duplicate raw headers or mixed ambiguous legacy/modern mappings.

---

## 4. Rationale

1. **Traceability**: Every cleaned observation points directly back to its line in the original source CSV file.
2. **Separation of Policy from Representation**: Marking records with `quality_flags` allows downstream consumers (ST-DBSCAN vs. Trajectory Anomaly Detector) to choose their own exclusion policies (e.g., ST-DBSCAN excludes position conflicts, while an anomaly detector may specifically inspect them).
3. **Type Safety**: Strictly typed PyArrow scalars prevent cross-platform floating-point representation drift.
4. **Preservation of Low-Speed Pings**: Nullifying SOG/COG/Heading sentinels preserves valid coordinates for spatial dwell and anchorage analysis.

---

## 5. Consequences and Trade-offs

### Positive Consequences
- 100% schema consistency across legacy and 2025+ NOAA formats.
- Complete transparency: every dropped row or coerced sentinel is accounted for in `manifest.json`.
- Zero fictitious movement calculated on same-timestamp conflicting records (`distance_nm` and `implied_speed_knots` remain `None`).

### Negative Consequences / Trade-offs
- **Column Overhead**: Storing 19 columns and quality flag lists increases memory footprint compared to a bare `(lat, lon, time)` tuple.
  - *Mitigation:* Downstream clustering loads only the 6 columns required for ST-DBSCAN (`load_clustering_dataset_from_parquet`), leaving unused columns unread in columnar storage.

---

## 6. Implementation Status and Evidence Links

- **Status**: Implemented in W1-02B; hardened in W2-01.
- **Implementation**: [src/aegismar/ingestion/schema.py](../../../src/aegismar/ingestion/schema.py), [src/aegismar/ingestion/cleaner.py](../../../src/aegismar/ingestion/cleaner.py)
- **Unit Tests**: [tests/unit/test_ingestion.py](../../../tests/unit/test_ingestion.py) (20 unit tests, tests 1–20 covering all schema/sanitation rules).

---

## 7. Known Limitations

- Current ingestion materializes CSV rows in memory lists prior to Arrow table serialization (in-memory batch processing; not bounded-memory streaming). Operates comfortably on up to 500k rows on a 16 GB workstation.

---

## 8. Conditions for Revisiting

- Processing multi-million row datasets that exceed available host RAM, requiring chunked PyArrow RecordBatch streaming.
