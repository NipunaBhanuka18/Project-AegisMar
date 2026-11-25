"""Track B evaluation utilities, implementing ML-03 v1.0.

ML-04 scope: the test-day firewall guard (ML-03 section 3.4) and the deterministic, stratified,
vessel-disjoint partition of the development day (ML-03 section 3.2). The perturbation harness and
metrics (ML-03 sections 4-8) are added in ML-05.

The firewall guard decides from Parquet column statistics (file metadata) whenever they are
present, so no observation rows of a held-out test day are loaded. Only if statistics are missing
does it read the ``timestamp_utc`` column alone; a timestamp range is an integrity check that
ML-03 section 3.4 explicitly allows.

Implementation choices where ML-03 v1.0 leaves a detail open:

* ``round(0.3 * n)`` is computed half-up (``floor(x + 0.5)``), not Python's banker's rounding.
* One ``numpy.random.default_rng(seed)`` generator is created once and consumed stratum by
  stratum in sorted stratum-key order, so the result does not depend on input row order.
* A vessel's type is its first non-null ``vessel_type`` in ``(timestamp_utc, source_row)`` order.
* The partition hash is the SHA-256 of the compact JSON ``{"train": [...], "val": [...]}`` with
  both MMSI lists sorted ascending.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from aegismar.anomaly.features import MOVING_SOG_KT

PARTITION_SEED: int = 42  # ML-03 D8
VALIDATION_FRACTION: float = 0.3  # ML-03 D8
MIN_GROUP_SIZE: int = 5  # ML-03 section 3.2
MERGED_GROUP: str = "other"

# ML-03 D7: held-out test days (UTC). Inspecting them is forbidden until the final evaluation.
TEST_DAYS: frozenset[date] = frozenset({date(2025, 1, 14), date(2025, 1, 22)})


class TestDayFirewallError(RuntimeError):
    """Raised when a held-out test day would be loaded without an explicit override."""

    __test__ = False  # not a pytest test class


def _timestamp_range_from_metadata(path: Path) -> tuple[datetime, datetime] | None:
    """Min/max ``timestamp_utc`` from Parquet row-group statistics; None if unavailable."""
    meta = pq.ParquetFile(path).metadata
    names = [meta.schema.column(i).name for i in range(meta.num_columns)]
    if "timestamp_utc" not in names:
        raise ValueError(f"{path} has no timestamp_utc column")
    col = names.index("timestamp_utc")
    lo: datetime | None = None
    hi: datetime | None = None
    for rg in range(meta.num_row_groups):
        stats = meta.row_group(rg).column(col).statistics
        if stats is None or not stats.has_min_max:
            return None
        rg_lo, rg_hi = _as_utc(stats.min), _as_utc(stats.max)
        lo = rg_lo if lo is None else min(lo, rg_lo)
        hi = rg_hi if hi is None else max(hi, rg_hi)
    if lo is None or hi is None:
        return None
    return lo, hi


def _as_utc(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, int):  # raw int64 microseconds when the logical type is not mapped
        return datetime.fromtimestamp(value / 1e6, UTC)
    raise TypeError(f"unexpected timestamp statistic type: {type(value).__name__}")


def dataset_days(path: Path | str) -> list[date]:
    """UTC calendar days spanned by a canonical Parquet file, without loading observation rows."""
    p = Path(path)
    span = _timestamp_range_from_metadata(p)
    if span is None:
        ts = pq.read_table(p, columns=["timestamp_utc"]).column("timestamp_utc")
        lo_v, hi_v = pc.min(ts).as_py(), pc.max(ts).as_py()
        if lo_v is None or hi_v is None:
            return []
        span = (_as_utc(lo_v), _as_utc(hi_v))
    first, last = span[0].date(), span[1].date()
    return [first + timedelta(days=k) for k in range((last - first).days + 1)]


def check_test_day_firewall(path: Path | str, override: bool = False) -> list[date]:
    """Refuse to proceed if the dataset covers a held-out test day (ML-03 section 3.4).

    Returns the dataset's UTC days. Raises :class:`TestDayFirewallError` when any day is a test
    day and ``override`` is False. ``override=True`` is reserved for the single final evaluation.
    """
    days = dataset_days(path)
    blocked = sorted(d for d in days if d in TEST_DAYS)
    if blocked and not override:
        names = ", ".join(d.isoformat() for d in blocked)
        raise TestDayFirewallError(
            f"{path} covers held-out test day(s) {names}; refusing (ML-03 section 3.4)."
        )
    return days


def vessel_group(code: int | None) -> str:
    """Coarse ITU-R M.1371 ship-type grouping (same mapping as the ML-01 profile)."""
    if code is None or code == 0:
        return "unknown"
    if code == 30:
        return "fishing"
    if code in (31, 32, 52):
        return "tug_towing"
    if code == 36:
        return "sailing"
    if code == 37:
        return "pleasure"
    if code == 35:
        return "military"
    if code in (50, 51, 53, 54, 55, 58):
        return "port_service_pilot_sar_le"
    if 60 <= code <= 69:
        return "passenger"
    if 70 <= code <= 79:
        return "cargo"
    if 80 <= code <= 89:
        return "tanker"
    if 20 <= code <= 29:
        return "wig"
    if 40 <= code <= 49:
        return "high_speed_craft"
    return "other"


@dataclass(frozen=True)
class VesselPartition:
    """Result of the ML-03 section 3.2 split."""

    train: tuple[str, ...]
    val: tuple[str, ...]
    seed: int
    validation_fraction: float
    strata: Mapping[str, Mapping[str, int]] = field(default_factory=dict)

    @property
    def partition_hash(self) -> str:
        payload = json.dumps(
            {"train": sorted(self.train), "val": sorted(self.val)}, separators=(",", ":")
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "seed": self.seed,
            "validation_fraction": self.validation_fraction,
            "partition_sha256": self.partition_hash,
            "n_train": len(self.train),
            "n_val": len(self.val),
            "strata": {k: dict(v) for k, v in self.strata.items()},
            "train": sorted(self.train),
            "val": sorted(self.val),
        }


def vessel_attributes(table: pa.Table) -> dict[str, tuple[str, bool]]:
    """Per-MMSI (raw vessel group, ever moving at SOG >= 1.5 kt)."""
    mmsi = table.column("mmsi").to_pylist()
    ts = pc.cast(table.column("timestamp_utc"), pa.int64()).to_pylist()
    src = table.column("source_row").to_pylist()
    vtype = table.column("vessel_type").to_pylist()
    sog = table.column("sog").to_pylist()

    first_type: dict[str, tuple[int, int, int | None]] = {}
    moving: dict[str, bool] = {}
    for m, t, s, v, g in zip(mmsi, ts, src, vtype, sog, strict=True):
        moving[m] = moving.get(m, False) or (g is not None and g >= MOVING_SOG_KT)
        if v is None:
            first_type.setdefault(m, (2**63 - 1, 2**63 - 1, None))
            continue
        current = first_type.get(m)
        if current is None or current[2] is None or (t, s) < (current[0], current[1]):
            first_type[m] = (t, s, int(v))
    return {m: (vessel_group(first_type[m][2]), moving[m]) for m in moving}


def split_vessels(
    table: pa.Table,
    seed: int = PARTITION_SEED,
    validation_fraction: float = VALIDATION_FRACTION,
    min_group_size: int = MIN_GROUP_SIZE,
) -> VesselPartition:
    """Stratified, deterministic, vessel-disjoint train/validation split (ML-03 section 3.2)."""
    attrs = vessel_attributes(table)
    group_sizes = Counter(g for g, _ in attrs.values())
    strata: dict[tuple[str, bool], list[str]] = {}
    for mmsi, (group, moving) in attrs.items():
        g = group if group_sizes[group] >= min_group_size else MERGED_GROUP
        strata.setdefault((g, moving), []).append(mmsi)

    rng = np.random.default_rng(seed)
    train: list[str] = []
    val: list[str] = []
    summary: dict[str, dict[str, int]] = {}
    for key in sorted(strata):
        members = sorted(strata[key])
        perm = rng.permutation(len(members))
        n_val = math.floor(validation_fraction * len(members) + 0.5)
        chosen = {members[i] for i in perm[:n_val]}
        val.extend(m for m in members if m in chosen)
        train.extend(m for m in members if m not in chosen)
        label = f"{key[0]}|{'moving' if key[1] else 'not_moving'}"
        summary[label] = {"vessels": len(members), "val": n_val, "train": len(members) - n_val}

    return VesselPartition(
        train=tuple(sorted(train)),
        val=tuple(sorted(val)),
        seed=seed,
        validation_fraction=validation_fraction,
        strata=summary,
    )
