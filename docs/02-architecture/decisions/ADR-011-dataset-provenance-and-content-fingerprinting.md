# ADR-011: Dataset Provenance via Authoritative Manifest and Versioned Logical Content Fingerprints

**Status:** Accepted  
**Date:** 2026-11-25  
**Deciders:** NipunaBhanuka18 (Project Lead)  
**Technical Scope:** Data Layer, Provenance & Experiment Reproducibility (Track A, Milestone W3-02A)  
**Extends:** [ADR-004](ADR-004-parquet-columnar-storage.md) (Parquet storage with manifest verification)

---

## 1. Context and Problem Statement

ADR-004 made `manifest.json` the provenance record for each processed dataset, but it recorded only the **input** CSV's SHA-256. Nothing identified the **output** Parquet, and the identity that was used later (a file-byte SHA-256 of `cleaned_ais.parquet`) is not a reliable statement about dataset content:

- **Divergent hashes for the same path.** The historical v1.0 file at `data/processed/lalb_20250101/cleaned_ais.parquet` has file SHA-256 `4a7ca719dc2a3d9959cc4166edff773ca09156d8d914e54d0ab5f851ece5e88b` (143,124 rows, cited in ADR-009 and `milestones.md`). It was generated before the W2-01 cleaner hardening (`3ece859`). `docs/03-research/ml-02-feature-spec.md` §2 reports a different SHA-256, `bdde2581302270a9e2c99a1a7aa1819a0bd1a24fbf6384458cfd8a81229eaf48`, for a file at the same path with the same row count. A file hash cannot tell us whether those two files differ in **content** (cleaner behaviour changed values or flags) or only in **bytes** (writer version, encoding, layout).
- **Writer sensitivity.** Parquet bytes change with compression codec (`zstd`/`snappy`/none), dictionary encoding, row-group size, PyArrow version, and footer key-value metadata, even when every decoded value is identical.
- **Implicit row order.** The cleaner sorts by `(mmsi, timestamp_utc, source_row)`, but this was not a named contract and was never checked on the written file. Downstream consumers (ST-DBSCAN, Track B features) depend on it.

W3-02 benchmarking and the planned controlled regeneration need a provenance identity that answers "is this the same dataset?" independently of how it was serialized.

---

## 2. Considered Alternatives

### Alternative A: File-byte SHA-256 only (status quo)
- **Evaluation:** Rejected as the sole identity. It is exact for "same bytes", but it gives false "different" verdicts under benign writer changes and cannot locate the cause of a divergence. It is retained as one of two identities.

### Alternative B: Embed provenance in Parquet footer key-value metadata
- **Evaluation:** Rejected for W3-02A. Footer metadata changes the file bytes, so the file hash would depend on provenance content such as timestamps. It is invisible to non-Arrow tooling and splits the record of truth between two locations. `manifest.json` already exists and is human-readable.

### Alternative C: Hash a canonical re-serialization (e.g., Arrow IPC or a fixed Parquet writer)
- **Evaluation:** Rejected. It ties the identity to the byte format of a specific library version, which is the same fragility as Alternative A one layer down.

### Alternative D: Order-insensitive (set-based) content hash
- **Evaluation:** Rejected. Row order is part of the dataset contract. A reordered dataset must hash differently and fail order verification.

---

## 3. Decision

### 3.1 `manifest.json` is the authoritative provenance record
W3-02A adds **no** new Parquet footer key-value metadata. `write_parquet_dataset` is unchanged. After the Parquet file is written, `run_ingestion_pipeline` computes the following from **the file on disk** and records it in `manifest.json` alongside all pre-existing keys:

| Field | Meaning |
|---|---|
| `output_parquet_sha256` | SHA-256 of the written Parquet's raw bytes (1 MB streamed) |
| `content_fingerprint_sha256` | `aegismar-logical-v1` logical content fingerprint (§3.3) |
| `content_fingerprint_version` | `"aegismar-logical-v1"` |
| `row_order_contract` | `["mmsi", "timestamp_utc", "source_row"]` |
| `schema_contract_version` | `"1.0"` (`SCHEMA_CONTRACT_VERSION`) |
| `git_commit_sha`, `git_dirty` | Code revision and worktree dirtiness; `null` when git is unavailable |
| `python_version`, `pyarrow_version` | Runtime versions |
| `generated_at_utc` | ISO-8601 UTC timestamp ending in `Z` |

If the written file fails canonical row-order verification, the pipeline raises `RuntimeError` and does **not** write `manifest.json` (fail closed).

### 3.2 Canonical row-order contract
`CANONICAL_ROW_ORDER = ("mmsi", "timestamp_utc", "source_row")` (in `ingestion/schema.py`). A dataset satisfies the contract when every key cell is non-null and consecutive rows are **strictly** ascending (`prev_key < curr_key`). `source_row` breaks ties between rows with the same `(mmsi, timestamp_utc)`. Timestamps are compared as int64 microsecond ticks. `verify_canonical_row_order` streams batches and also accepts a custom key tuple.

### 3.3 `aegismar-logical-v1` fingerprint specification
SHA-256 over the following byte stream (all integers little-endian):

**Header**
1. `b"aegismar-logical-v1\n"`
2. Column count: `<I`
3. For each field in schema order: `<I` length + UTF-8 `field.name`, then `<I` length + UTF-8 canonical type string
4. Total row count: `<Q`

The **canonical type string** is `str(field.type)`, with one exception: list types are rendered without their child field name, as `list<string>` or `large_list<string>`. PyArrow names the list child `item` in memory but `element` after a standards-compliant Parquet round-trip (`list<item: string>` vs `list<element: string>`), so the raw `str()` form would make the fingerprint writer-dependent. Schema and field key-value metadata and nullability flags are excluded.

**Body:** every cell in strict **row-major** order (row by row, then column by column within a row) across all streamed batches. The digest is therefore independent of row-group and batch boundaries.

| Cell | Encoding |
|---|---|
| null | `0x00` |
| non-null | `0x01` + value encoding below |
| `int8` / `int16` / `int32` / `int64` | `<b` / `<h` / `<i` / `<q` |
| `bool` | `0x01` (true) / `0x00` (false) |
| `float32` | NaN → `<I 0x7FC00000`; `±0.0` → `<f 0.0`; else `<f v` |
| `float64` | NaN → `<Q 0x7FF8000000000000`; `±0.0` → `<d 0.0`; else `<d v` |
| `timestamp[*]` | int64 ticks in the column's unit, `<q` |
| `string` / `large_string` | `<I` byte length + UTF-8 bytes |
| `list<string>` / `large_list<string>` | `<I` element count, then per element: `0x00` if null, else `0x01` + `<I` length + UTF-8 |
| any other type (e.g. unsigned ints, dictionary, struct) | `TypeError` (fail closed) |

The same digest is produced for an in-memory `pa.Table` and any Parquet file written from it.

### 3.4 Read-only inspection
`aegismar fingerprint -i <parquet> [--json]` reports the file SHA-256, content fingerprint, version, row and column counts, row-order contract, its verification result, and the schema. It opens the file read-only. A missing or unreadable file, or an unsupported schema, exits with code `1`.

---

## 4. Rationale

1. **Two identities answer two questions.** The file hash answers "identical bytes?". The content fingerprint answers "identical logical dataset, in contract order?". Divergence in the first with agreement in the second isolates writer effects.
2. **Fail closed.** Unknown types raise rather than being hashed through an ambiguous fallback. A row-order violation blocks the manifest.
3. **Versioned.** Any future change to encoding rules must use a new version tag (e.g. `aegismar-logical-v2`). The two versions are never compared against each other.
4. **Normalizations are minimal and documented.** Only NaN payloads, the sign of zero, and the list child name are normalized. Each normalization is either value-equivalent under IEEE comparison or a pure serialization artifact.

---

## 5. Consequences and Trade-offs

### Positive Consequences
- Every new ingestion emits a self-describing manifest that can be checked against the file it describes.
- The historical v1.0 file and any regenerated file can be compared logically without mutating either.
- Row order becomes an enforced contract rather than an implicit cleaner behaviour.

### Negative Consequences / Trade-offs
- **Cost.** The fingerprint decodes every cell into Python objects. That is acceptable for regional daily extracts (~10⁵ rows) but is O(rows × columns) in interpreted code and is not designed for nationwide files.
- **Ingestion re-reads the output.** The pipeline reads the written Parquet back once more for hashing and verification.
- **`IngestionManifest` gained required fields.** All in-repo call sites were updated; external constructors (none known) would need to supply them.

---

## 6. Implementation Status and Evidence Links

- **Status:** Implemented in Milestone W3-02A (branch `feat/clu-w3-02a-dataset-provenance`).
- **Implementation:** [src/aegismar/ingestion/provenance.py](../../../src/aegismar/ingestion/provenance.py), [src/aegismar/ingestion/schema.py](../../../src/aegismar/ingestion/schema.py), [src/aegismar/ingestion/pipeline.py](../../../src/aegismar/ingestion/pipeline.py), [src/aegismar/common/types.py](../../../src/aegismar/common/types.py), [src/aegismar/cli.py](../../../src/aegismar/cli.py)
- **Test Evidence:** [tests/unit/test_provenance.py](../../../tests/unit/test_provenance.py), [tests/unit/test_ingestion.py](../../../tests/unit/test_ingestion.py) (`test_21`–`test_24`), [tests/unit/test_cli.py](../../../tests/unit/test_cli.py) (`test_cli_fingerprint_*`)

---

## 7. Known Limitations

- The fingerprint identifies logical content, not semantic equivalence. Two datasets with values that differ by floating-point rounding hash differently, by design.
- `git_dirty` reflects the whole worktree at generation time, not only files that affect ingestion.
- The historical v1.0 manifest predates this ADR and contains none of the new fields. Its fingerprint must be computed externally with `aegismar fingerprint`, never by rewriting it.

---

## 8. Conditions for Revisiting

- Support for new column types (e.g. `uint*`, `date32`, dictionary-encoded strings) requires a new fingerprint version.
- A bounded-memory or vectorized (Arrow compute) implementation becomes necessary for datasets beyond regional scale. It must reproduce `aegismar-logical-v1` digests exactly or carry a new version tag.
