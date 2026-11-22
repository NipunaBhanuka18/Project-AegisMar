# ADR-004: Apache Parquet Columnar Storage with Manifest Verification

**Status:** Accepted  
**Date:** 2026-11-14  
**Deciders:** NipunaBhanuka18 (Project Lead)  
**Technical Scope:** Data Layer, Persistence & Experiment Reproducibility  

---

## 1. Context and Problem Statement

Project AegisMar processes high-density spatial AIS telemetry. We evaluated persistent storage formats for cleaned canonical AIS telemetry, intermediate clustering partitions, and analytical results.

The storage format must support:
- Rapid column-selective reads (e.g., reading only coordinates and timestamps without loading ship names or call signs).
- High compression efficiency on disk.
- Strong static schema enforcement with native microsecond timestamp and nullable types.
- Cryptographic provenance and auditability.

---

## 2. Considered Alternatives

### Alternative A: Plain CSV Files
- **Concept:** Save cleaned records back into uncompressed or gzipped CSV files.
- **Evaluation at Decision Time (2026-11-14):** Evaluated and rejected. CSV lacks type metadata (requiring repetitive, fragile type parsing on every read), does not support columnar projection (every read parses all 19 columns), and produces 5–8× larger file sizes on disk.

### Alternative B: Embedded Relational SQLite Database
- **Concept:** Store cleaned records in a local SQLite file (`.db`).
- **Evaluation at Decision Time (2026-11-14):** Evaluated and rejected. Row-oriented SQLite exhibits poor analytical scan performance across 100k+ rows compared to columnar formats, lacks native microsecond timestamp types with timezones, and adds SQL schema migration overhead without performance benefit.

---

## 3. Decision

We will use **Apache Parquet with Zstandard (`zstd`) compression** as the standard analytical storage format for all cleaned datasets, cluster assignments, and trajectory partitions, managed via PyArrow.

Every processed dataset directory must include an immutable **`manifest.json`** recording:
- Input file path and SHA-256 hash.
- Codebase version.
- Schema detected and column mapping.
- Exact row counts (input, accepted, duplicate, conflicts).
- Quality flag frequency breakdown.
- Execution runtime.

---

## 4. Rationale

1. **Columnar Projection**: PyArrow reads only requested columns (e.g. `['timestamp_utc', 'latitude', 'longitude']`), skipping remaining data pages entirely and drastically cutting I/O latency.
2. **High Compression**: Zstandard compression achieves ~4:1 compression on real AIS telemetry (143k rows reduced to 4.15 MB), fitting easily into local SSDs and caches.
3. **DuckDB Interoperability**: Parquet is the native format for DuckDB, enabling direct zero-copy SQL queries over local files without loading data into memory tables.
4. **Cryptographic Traceability**: The accompanying `manifest.json` guarantees that every dataset is self-documenting and auditable.

---

## 5. Consequences and Trade-offs

### Positive Consequences
- Extremely fast analytical reads (Parquet reading in ST-DBSCAN takes <0.15 s on 143k rows).
- Compact storage: cleaned regional extracts occupy <5 MB on disk.
- Zero data corruption from text parsing ambiguities.

### Negative Consequences / Trade-offs
- **Binary Format**: Parquet files cannot be inspected directly with simple terminal commands like `cat` or `grep`.
  - *Mitigation:* Implemented CLI inspection utilities (`inspect_parquet_metadata`) and Python interactive inspection scripts.

---

## 6. Implementation Status and Evidence Links

- **Status**: Implemented and verified in Milestone W1-02B.
- **Implementation**: [src/aegismar/ingestion/storage.py](../../../src/aegismar/ingestion/storage.py), [src/aegismar/ingestion/pipeline.py](../../../src/aegismar/ingestion/pipeline.py)
- **Local Evidence**: `data/processed/lalb_20250101/cleaned_ais.parquet` (4.15 MB), `manifest.json`.
- **Test Evidence**: [tests/unit/test_ingestion.py](../../../tests/unit/test_ingestion.py) (`test_14_parquet_schema_roundtrip`).

---

## 7. Known Limitations

- Parquet files are immutable; appending new records requires writing a new partition or rewriting the file.

---

## 8. Conditions for Revisiting

- None identified within the 8-week MVP research scope.
