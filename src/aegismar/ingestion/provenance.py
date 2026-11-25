"""Dataset provenance: file hashing, logical content fingerprints, and runtime metadata.

Two distinct identities are computed for a canonical AIS dataset (ADR-011):

- **File-byte SHA-256** (:func:`compute_file_sha256`): identifies the exact bytes
  on disk. It changes with compression codec, dictionary encoding, row-group
  layout, writer version, or footer key-value metadata.
- **Logical content fingerprint** (:func:`compute_content_fingerprint`): an
  order-sensitive, versioned SHA-256 over the decoded schema and cell values
  (``aegismar-logical-v1``). It is invariant to Parquet encoding, compression,
  row-group/batch boundaries, and schema/field metadata, but changes whenever
  any value, null, row order, column order, column name, or column type changes.
"""

from __future__ import annotations

import hashlib
import itertools
import math
import platform
import struct
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeAlias

import pyarrow as pa
import pyarrow.parquet as pq

from aegismar.ingestion.schema import CANONICAL_ROW_ORDER

CONTENT_FINGERPRINT_VERSION = "aegismar-logical-v1"

_FILE_CHUNK_BYTES = 1024 * 1024
_BATCH_ROWS = 65_536

_NULL = b"\x00"
_PRESENT = b"\x01"

_U32 = struct.Struct("<I")
_U64 = struct.Struct("<Q")
_I8 = struct.Struct("<b")
_I16 = struct.Struct("<h")
_I32 = struct.Struct("<i")
_I64 = struct.Struct("<q")
_F32 = struct.Struct("<f")
_F64 = struct.Struct("<d")

_F32_CANONICAL_NAN = _U32.pack(0x7FC00000)
_F64_CANONICAL_NAN = _U64.pack(0x7FF8000000000000)
_F32_ZERO = _F32.pack(0.0)
_F64_ZERO = _F64.pack(0.0)

# A Parquet file path or an in-memory ``pa.Table`` (pyarrow ships no type stubs).
TableSource: TypeAlias = "Path | str | pa.Table"


def compute_file_sha256(file_path: Path | str) -> str:
    """Compute the SHA-256 of a file's raw bytes, streamed in 1 MB chunks."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(_FILE_CHUNK_BYTES):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Source adapters
# ---------------------------------------------------------------------------


def _is_table(source: object) -> bool:
    return isinstance(source, pa.Table)


def _source_schema_and_rows(source: TableSource) -> tuple[Any, int]:
    """Return the Arrow schema and total row count of a table or Parquet file."""
    if _is_table(source):
        table: Any = source
        return table.schema, int(table.num_rows)
    pf = pq.ParquetFile(str(source))
    return pf.schema_arrow, int(pf.metadata.num_rows)


def _iter_batches(source: TableSource, columns: list[str] | None = None) -> Iterator[Any]:
    """Stream record batches from a table or Parquet file."""
    if _is_table(source):
        table: Any = source
        if columns is not None:
            table = table.select(columns)
        yield from table.to_batches(max_chunksize=_BATCH_ROWS)
        return
    pf = pq.ParquetFile(str(source))
    yield from pf.iter_batches(batch_size=_BATCH_ROWS, columns=columns)


# ---------------------------------------------------------------------------
# Canonical row-order verification
# ---------------------------------------------------------------------------


def _order_key_values(array: Any) -> list[Any]:
    """Convert an order-key column to comparable Python values (timestamps as int64)."""
    if pa.types.is_timestamp(array.type):
        array = array.cast(pa.int64())
    values: list[Any] = array.to_pylist()
    return values


def verify_canonical_row_order(
    source: TableSource,
    order_columns: tuple[str, ...] = CANONICAL_ROW_ORDER,
) -> bool:
    """Return True if rows are in strictly ascending order of ``order_columns``.

    Returns False if any order column is missing, any key cell is null, or any
    consecutive pair of rows fails ``prev_key < curr_key``. Empty and single-row
    datasets with non-null keys are trivially ordered.
    """
    schema, _ = _source_schema_and_rows(source)
    if any(col not in schema.names for col in order_columns):
        return False

    prev_key: tuple[Any, ...] | None = None
    for batch in _iter_batches(source, columns=list(order_columns)):
        key_columns = [_order_key_values(batch.column(i)) for i in range(len(order_columns))]
        for key in zip(*key_columns, strict=True):
            if any(v is None for v in key):
                return False
            if prev_key is not None and not prev_key < key:
                return False
            prev_key = key
    return True


# ---------------------------------------------------------------------------
# Logical content fingerprint (aegismar-logical-v1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ContentFingerprintResult:
    """Result of computing an ``aegismar-logical-v1`` content fingerprint."""

    content_fingerprint_sha256: str
    content_fingerprint_version: str
    row_count: int
    column_count: int
    schema: list[dict[str, str]]
    canonical_row_order: list[str]
    canonical_order_verified: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert result to a JSON-serializable dictionary."""
        return asdict(self)


def _canonical_type_string(data_type: Any) -> str:
    """Return a writer-independent string for an Arrow type.

    List types are rendered without their child field name: PyArrow names the
    list child ``item`` in memory but ``element`` after a compliant Parquet
    round-trip, which would otherwise make the fingerprint writer-dependent.
    """
    if pa.types.is_large_list(data_type):
        return f"large_list<{_canonical_type_string(data_type.value_type)}>"
    if pa.types.is_list(data_type):
        return f"list<{_canonical_type_string(data_type.value_type)}>"
    return str(data_type)


def _length_prefixed(text: str) -> bytes:
    raw = text.encode("utf-8")
    return _U32.pack(len(raw)) + raw


def _encode_fixed(packer: struct.Struct) -> Callable[[list[Any]], list[bytes]]:
    pack = packer.pack

    def encode(values: list[Any]) -> list[bytes]:
        return [_NULL if v is None else _PRESENT + pack(v) for v in values]

    return encode


def _encode_bool(values: list[Any]) -> list[bytes]:
    return [_NULL if v is None else _PRESENT + (b"\x01" if v else b"\x00") for v in values]


def _encode_float32(values: list[Any]) -> list[bytes]:
    out: list[bytes] = []
    for v in values:
        if v is None:
            out.append(_NULL)
        elif math.isnan(v):
            out.append(_PRESENT + _F32_CANONICAL_NAN)
        elif v == 0.0:
            out.append(_PRESENT + _F32_ZERO)
        else:
            out.append(_PRESENT + _F32.pack(v))
    return out


def _encode_float64(values: list[Any]) -> list[bytes]:
    out: list[bytes] = []
    for v in values:
        if v is None:
            out.append(_NULL)
        elif math.isnan(v):
            out.append(_PRESENT + _F64_CANONICAL_NAN)
        elif v == 0.0:
            out.append(_PRESENT + _F64_ZERO)
        else:
            out.append(_PRESENT + _F64.pack(v))
    return out


def _encode_string(values: list[Any]) -> list[bytes]:
    return [_NULL if v is None else _PRESENT + _length_prefixed(v) for v in values]


def _encode_string_list(values: list[Any]) -> list[bytes]:
    out: list[bytes] = []
    for v in values:
        if v is None:
            out.append(_NULL)
            continue
        parts = [_PRESENT, _U32.pack(len(v))]
        for item in v:
            parts.append(_NULL if item is None else _PRESENT + _length_prefixed(item))
        out.append(b"".join(parts))
    return out


def _is_string_type(data_type: Any) -> bool:
    return bool(pa.types.is_string(data_type) or pa.types.is_large_string(data_type))


def _column_encoder(field: Any) -> Callable[[Any], list[bytes]]:
    """Select a canonical cell encoder for a field; raise TypeError if unsupported."""
    t = field.type
    value_encoder: Callable[[list[Any]], list[bytes]]
    cast_to_int64 = False

    if pa.types.is_int8(t):
        value_encoder = _encode_fixed(_I8)
    elif pa.types.is_int16(t):
        value_encoder = _encode_fixed(_I16)
    elif pa.types.is_int32(t):
        value_encoder = _encode_fixed(_I32)
    elif pa.types.is_int64(t):
        value_encoder = _encode_fixed(_I64)
    elif pa.types.is_boolean(t):
        value_encoder = _encode_bool
    elif pa.types.is_float32(t):
        value_encoder = _encode_float32
    elif pa.types.is_float64(t):
        value_encoder = _encode_float64
    elif pa.types.is_timestamp(t):
        value_encoder = _encode_fixed(_I64)
        cast_to_int64 = True
    elif _is_string_type(t):
        value_encoder = _encode_string
    elif (pa.types.is_list(t) or pa.types.is_large_list(t)) and _is_string_type(t.value_type):
        value_encoder = _encode_string_list
    else:
        raise TypeError(
            f"Unsupported Arrow type for {CONTENT_FINGERPRINT_VERSION} fingerprint: "
            f"column {field.name!r} has type {t}"
        )

    def encode(array: Any) -> list[bytes]:
        if cast_to_int64:
            array = array.cast(pa.int64())
        return value_encoder(array.to_pylist())

    return encode


def _fingerprint_header(schema: Any, row_count: int) -> bytes:
    parts = [CONTENT_FINGERPRINT_VERSION.encode("utf-8") + b"\n", _U32.pack(len(schema))]
    for field in schema:
        parts.append(_length_prefixed(field.name))
        parts.append(_length_prefixed(_canonical_type_string(field.type)))
    parts.append(_U64.pack(row_count))
    return b"".join(parts)


def compute_content_fingerprint(source: TableSource) -> ContentFingerprintResult:
    """Compute the order-sensitive ``aegismar-logical-v1`` content fingerprint.

    The digest covers a header (version tag, column count, length-prefixed column
    names and canonical type strings, total row count) followed by every cell in
    row-major order, each prefixed by a null/present marker and canonically
    encoded. The result is identical for an in-memory table and any Parquet file
    written from it, regardless of compression, dictionary encoding, row-group
    size, or footer metadata.

    Raises
    ------
    TypeError
        If any column has an Arrow type outside the supported set (fail closed).
    """
    schema, row_count = _source_schema_and_rows(source)
    encoders = [_column_encoder(field) for field in schema]

    h = hashlib.sha256()
    h.update(_fingerprint_header(schema, row_count))

    rows_seen = 0
    for batch in _iter_batches(source):
        encoded_columns = [encode(batch.column(i)) for i, encode in enumerate(encoders)]
        h.update(b"".join(itertools.chain.from_iterable(zip(*encoded_columns, strict=True))))
        rows_seen += int(batch.num_rows)

    if rows_seen != row_count:
        raise RuntimeError(
            f"Row count mismatch while fingerprinting: metadata={row_count}, streamed={rows_seen}"
        )

    return ContentFingerprintResult(
        content_fingerprint_sha256=h.hexdigest(),
        content_fingerprint_version=CONTENT_FINGERPRINT_VERSION,
        row_count=row_count,
        column_count=len(schema),
        schema=[{"name": f.name, "type": str(f.type)} for f in schema],
        canonical_row_order=list(CANONICAL_ROW_ORDER),
        canonical_order_verified=verify_canonical_row_order(source),
    )


# ---------------------------------------------------------------------------
# Runtime provenance
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeProvenance:
    """Code and runtime environment metadata captured at dataset generation time."""

    git_commit_sha: str | None
    git_dirty: bool | None
    python_version: str
    pyarrow_version: str
    generated_at_utc: str


def _run_git(args: list[str], cwd: Path) -> str | None:
    """Run a git command and return stdout, or None if git is unavailable or fails."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout


def collect_runtime_provenance(repo_dir: Path | None = None) -> RuntimeProvenance:
    """Collect git commit, dirty state, Python/PyArrow versions, and a UTC timestamp.

    Parameters
    ----------
    repo_dir : Path | None
        Directory used to query git. Defaults to the directory containing the
        ``aegismar`` package source, so the recorded commit identifies the code
        that produced the dataset regardless of the current working directory.
        Git fields are ``None`` if git is missing or ``repo_dir`` is not inside
        a git worktree.
    """
    cwd = repo_dir if repo_dir is not None else Path(__file__).resolve().parent

    commit_out = _run_git(["rev-parse", "HEAD"], cwd)
    git_commit_sha = commit_out.strip() if commit_out else None

    git_dirty: bool | None = None
    if git_commit_sha is not None:
        status_out = _run_git(["status", "--porcelain"], cwd)
        git_dirty = bool(status_out.strip()) if status_out is not None else None

    generated_at = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

    return RuntimeProvenance(
        git_commit_sha=git_commit_sha,
        git_dirty=git_dirty,
        python_version=platform.python_version(),
        pyarrow_version=str(pa.__version__),
        generated_at_utc=generated_at,
    )
