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
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from numpy.typing import NDArray

from aegismar.anomaly.features import (
    MOVING_SOG_KT,
    Observations,
    assign_segments,
    destination_point,
    detect_outage_windows,
    prepare_observations,
)
from aegismar.common.constants import (
    FLAG_IMPLIED_SPEED_VIOLATION,
    FLAG_TIMESTAMP_METADATA_CONFLICT,
    FLAG_TIMESTAMP_POSITION_CONFLICT,
    METERS_PER_NAUTICAL_MILE,
)
from aegismar.ingestion.cleaner import process_and_clean_observations
from aegismar.ingestion.storage import canonical_pings_to_arrow_table

FloatArr = NDArray[np.float64]
IntArr = NDArray[np.int64]
BoolArr = NDArray[np.bool_]
Int8Arr = NDArray[np.int8]

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


def _as_tables(tables: pa.Table | Sequence[pa.Table]) -> list[pa.Table]:
    return [tables] if isinstance(tables, pa.Table) else list(tables)


def vessel_attributes(tables: pa.Table | Sequence[pa.Table]) -> dict[str, tuple[str, bool]]:
    """Per-MMSI (raw vessel group, ever moving at SOG >= 1.5 kt) over one or more days.

    The group comes from the vessel's first non-null ``vessel_type`` in ``(timestamp_utc,
    source_row)`` order across all given days; a vessel is moving if it reaches 1.5 kt on any day.
    """
    first_type: dict[str, tuple[int, int, int | None]] = {}
    moving: dict[str, bool] = {}
    for table in _as_tables(tables):
        mmsi = table.column("mmsi").to_pylist()
        ts = pc.cast(table.column("timestamp_utc"), pa.int64()).to_pylist()
        src = table.column("source_row").to_pylist()
        vtype = table.column("vessel_type").to_pylist()
        sog = table.column("sog").to_pylist()
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
    tables: pa.Table | Sequence[pa.Table],
    seed: int = PARTITION_SEED,
    validation_fraction: float = VALIDATION_FRACTION,
    min_group_size: int = MIN_GROUP_SIZE,
) -> VesselPartition:
    """Stratified, deterministic, MMSI-grouped train/validation split (ML-03 v1.1 section 3.2).

    With several development days (D16), the split is computed jointly over all of them, so a
    vessel's data on every day falls into the same partition.
    """
    attrs = vessel_attributes(tables)
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


# =========================================================================== perturbation harness
# ML-03 section 4. Perturbations are applied to raw-equivalent copies of the canonical records and
# the movement columns are re-derived with the production cleaner, so perturbed data follows the
# same derivation as real data. Implementation choices where ML-03 v1.0 leaves a detail open:
#
# * The eligibility region of an injection is [span_start - 30 min, span_end + 30 min], where the
#   span is the target observation (A1/A2), the K drift observations (B), or the removed interval up
#   to the reappearance observation (C1/C2). Every observation of the vessel's segment in the
#   region must have SOG >= 2.0 kt and no pre-existing quality flag other than MISSING_*; the
#   region must not intersect a feed-wide outage window. The target needs a segment predecessor.
# * Placement: segments are visited in global segment order (MMSI, then time); candidates closer
#   than 60 min to an already chosen injection of the same vessel are dropped; one candidate is
#   drawn with ``rng.integers``; B and C2 then draw a side/sign with ``rng.choice([-1, 1])``.
# * C1/C2 remove observations with t in [t_target, t_target + G] (inclusive). The label row is the
#   first remaining observation after the gap (ML-03 section 4.4).
# * B headings are rounded to whole degrees modulo 360, because AIS headings are integers and the
#   cleaner nullifies values above 359.
# * Re-derivation drops only the EXACT_DUPLICATE provenance flag (duplicates were already merged in
#   the clean file; verified on the development day). Eligibility and masking use the clean flags.

PERTURBATION_KINDS: tuple[str, ...] = ("A1", "A2", "B", "C1", "C2")
ELIGIBILITY_MIN_SOG_KT: float = 2.0  # ML-03 section 4.1
ELIGIBILITY_MARGIN_S: float = 1800.0  # +/- 30 min
INJECTION_MIN_SPACING_S: float = 3600.0  # 2 x W
DRIFT_RUN_LENGTH: int = 5  # K for type B
HEADLINE_SEEDS: tuple[int, ...] = tuple(range(1000, 1010))
SWEEP_SEEDS: tuple[int, ...] = (1000, 1001, 1002)
ALLOWED_PRIOR_FLAG_PREFIX: str = "MISSING_"

EXPECTED_FACTORS: dict[str, frozenset[str]] = {
    "A1": frozenset({"SPEED_DISCONTINUITY", "SPEED_POSITION_INCONSISTENCY"}),
    "A2": frozenset({"SPEED_POSITION_INCONSISTENCY"}),
    "B": frozenset({"LATERAL_DRIFT"}),
    "C1": frozenset({"REPORTING_GAP"}),
    "C2": frozenset({"REPORTING_GAP", "SPEED_POSITION_INCONSISTENCY"}),
}

RAW_FIELDS: tuple[str, ...] = (
    "mmsi",
    "timestamp_utc",
    "latitude",
    "longitude",
    "sog",
    "cog",
    "heading",
    "nav_status",
    "vessel_type",
    "vessel_name",
    "imo",
    "call_sign",
    "transceiver_class",
)


@dataclass(frozen=True)
class PerturbationConfig:
    """One perturbation type at one magnitude (ML-03 section 4.2)."""

    kind: str
    magnitude: float  # A1/A2: delta-v kt; B: theta deg; C1/C2: gap minutes
    displacement_nm: float = 0.0  # C2 only

    def __post_init__(self) -> None:
        if self.kind not in PERTURBATION_KINDS:
            raise ValueError(f"unknown perturbation kind {self.kind!r}")
        if self.magnitude <= 0:
            raise ValueError("magnitude must be positive")
        if (self.kind == "C2") != (self.displacement_nm > 0):
            raise ValueError("displacement_nm must be > 0 for C2 and 0 otherwise")

    @property
    def label(self) -> str:
        unit = {"A1": "kt", "A2": "kt", "B": "deg", "C1": "min", "C2": "min"}[self.kind]
        base = f"{self.kind}_{self.magnitude:g}{unit}"
        return f"{base}_{self.displacement_nm:g}nm" if self.kind == "C2" else base


HEADLINE_CONFIGS: tuple[PerturbationConfig, ...] = (
    PerturbationConfig("A1", 20.0),
    PerturbationConfig("A2", 20.0),
    PerturbationConfig("B", 85.0),
    PerturbationConfig("C2", 60.0, 1.0),
)

SWEEP_CONFIGS: tuple[PerturbationConfig, ...] = (
    *(PerturbationConfig("A1", v) for v in (5.0, 10.0, 15.0, 20.0, 25.0)),
    *(PerturbationConfig("A2", v) for v in (5.0, 10.0, 15.0, 20.0, 25.0)),
    *(PerturbationConfig("B", v) for v in (30.0, 45.0, 60.0, 85.0)),
    *(PerturbationConfig("C1", g) for g in (30.0, 60.0, 120.0)),
    *(PerturbationConfig("C2", g, 1.0) for g in (30.0, 60.0, 120.0)),
    PerturbationConfig("C2", 60.0, 0.5),
    PerturbationConfig("C2", 60.0, 2.0),
)


@dataclass(frozen=True)
class Injection:
    """One injected perturbation, recorded in ``perturbations.json`` (ML-03 section 4.1 item 6)."""

    injection_id: str
    kind: str
    parameters: dict[str, float]
    mmsi: str
    label_source_rows: tuple[int, ...]  # original source rows defining the positive label
    modified_source_rows: tuple[int, ...]
    removed_source_rows: tuple[int, ...]
    before: dict[str, dict[str, object]]
    after: dict[str, dict[str, object]]
    span_start_utc: str
    span_end_utc: str
    seed: int

    def to_dict(self) -> dict[str, object]:
        return {
            "injection_id": self.injection_id,
            "kind": self.kind,
            "parameters": self.parameters,
            "mmsi": self.mmsi,
            "label_source_rows": list(self.label_source_rows),
            "modified_source_rows": list(self.modified_source_rows),
            "removed_source_rows": list(self.removed_source_rows),
            "before": self.before,
            "after": self.after,
            "span_start_utc": self.span_start_utc,
            "span_end_utc": self.span_end_utc,
            "seed": self.seed,
        }


@dataclass(frozen=True)
class PerturbedDataset:
    """A perturbed, re-derived canonical dataset with its injection manifest."""

    config: PerturbationConfig
    seed: int
    table: pa.Table
    new_to_original: dict[int, int]
    injections: tuple[Injection, ...]
    eligible_segments: int

    def manifest(self) -> dict[str, object]:
        return {
            "config": self.config.label,
            "kind": self.config.kind,
            "magnitude": self.config.magnitude,
            "displacement_nm": self.config.displacement_nm,
            "seed": self.seed,
            "eligible_segments": self.eligible_segments,
            "n_injections": len(self.injections),
            "injections": [i.to_dict() for i in self.injections],
        }


@dataclass(frozen=True)
class InjectionPlan:
    """A chosen injection site, in observation indices of the clean dataset."""

    rows: tuple[int, ...]  # target / drift run / removed observations
    label_row: int  # label observation (target, first of drift run, or reappearance)
    span: tuple[float, float]
    shift_rows: tuple[int, ...] = ()  # C2: observations displaced after the gap
    sign: int = 1


def _clean_flags_ok(table: pa.Table, obs_source_rows: IntArr) -> BoolArr:
    flags_by_src = dict(
        zip(
            table.column("source_row").to_pylist(),
            table.column("quality_flags").to_pylist(),
            strict=True,
        )
    )
    return np.asarray(
        [
            all(f.startswith(ALLOWED_PRIOR_FLAG_PREFIX) for f in (flags_by_src[int(s)] or []))
            for s in obs_source_rows
        ],
        dtype=bool,
    )


def _inside_outage(t: FloatArr, outages: list[tuple[float, float]]) -> BoolArr:
    out = np.zeros(t.shape, dtype=bool)
    for lo, hi in outages:
        out |= (t >= lo) & (t <= hi)
    return out


def _region_ok(
    t: FloatArr, good: BoolArr, lo: float, hi: float, outages: list[tuple[float, float]]
) -> bool:
    if any(o_lo <= hi and o_hi >= lo for o_lo, o_hi in outages):
        return False
    a = int(np.searchsorted(t, lo, side="left"))
    b = int(np.searchsorted(t, hi, side="right"))
    return bool(good[a:b].all())


def _candidate_plans(
    config: PerturbationConfig,
    obs: Observations,
    idx: IntArr,
    good: BoolArr,
    outages: list[tuple[float, float]],
) -> list[InjectionPlan]:
    t = obs.timestamp_s[idx]
    seg_good = good[idx]
    plans: list[InjectionPlan] = []
    n = idx.size
    for p in range(1, n):
        i = int(idx[p])
        if obs.prev_idx[i] < 0:
            continue
        if config.kind in ("A1", "A2"):
            if config.kind == "A2" and not (
                np.isfinite(obs.cog[i]) and np.isfinite(obs.elapsed_s[i]) and obs.elapsed_s[i] > 0
            ):
                continue
            plan = InjectionPlan((i,), i, (float(t[p]), float(t[p])))
        elif config.kind == "B":
            if p + DRIFT_RUN_LENGTH > n:
                break
            run = idx[p : p + DRIFT_RUN_LENGTH]
            if not (np.isfinite(obs.cog[run]).all() and np.isfinite(obs.heading[run]).all()):
                continue
            span = (float(t[p]), float(t[p + DRIFT_RUN_LENGTH - 1]))
            plan = InjectionPlan(tuple(int(r) for r in run), i, span)
        else:
            gap_end = float(t[p]) + 60.0 * config.magnitude
            q = int(np.searchsorted(t, gap_end, side="right"))
            if q >= n:
                break
            reappear = int(idx[q])
            if config.kind == "C2" and not np.isfinite(obs.cog[reappear]):
                continue
            plan = InjectionPlan(
                tuple(int(r) for r in idx[p:q]),
                reappear,
                (float(t[p]), float(t[q])),
                tuple(int(r) for r in idx[q:]) if config.kind == "C2" else (),
            )
        lo = plan.span[0] - ELIGIBILITY_MARGIN_S
        hi = plan.span[1] + ELIGIBILITY_MARGIN_S
        if _region_ok(t, seg_good, lo, hi, outages):
            plans.append(plan)
    return plans


def _far_enough(plan: InjectionPlan, taken: list[tuple[float, float]]) -> bool:
    return all(
        plan.span[0] - hi >= INJECTION_MIN_SPACING_S or lo - plan.span[1] >= INJECTION_MIN_SPACING_S
        for lo, hi in taken
    )


def plan_injections(
    config: PerturbationConfig, table: pa.Table, vessels: Iterable[str], seed: int
) -> tuple[list[InjectionPlan], int, Observations]:
    """Choose injection sites (ML-03 4.1); return plans, eligible segments, observations."""
    obs = prepare_observations(table)
    segments = assign_segments(obs)
    outages = detect_outage_windows(obs.timestamp_s)
    allowed = set(vessels)
    good = _clean_flags_ok(table, obs.source_row) & (obs.sog >= ELIGIBILITY_MIN_SOG_KT)
    good &= ~_inside_outage(obs.timestamp_s, outages)

    rng = np.random.default_rng(seed)
    chosen: list[InjectionPlan] = []
    spans_by_vessel: dict[str, list[tuple[float, float]]] = {}
    eligible_segments = 0
    for seg_id in np.unique(segments[segments >= 0]):
        idx = np.flatnonzero(segments == seg_id)
        mmsi = str(obs.mmsi[idx[0]])
        if mmsi not in allowed:
            continue
        candidates = _candidate_plans(config, obs, idx, good, outages)
        if candidates:
            eligible_segments += 1
        taken = spans_by_vessel.setdefault(mmsi, [])
        candidates = [c for c in candidates if _far_enough(c, taken)]
        if not candidates:
            continue
        plan = candidates[int(rng.integers(len(candidates)))]
        if config.kind in ("B", "C2"):
            plan = InjectionPlan(
                plan.rows, plan.label_row, plan.span, plan.shift_rows, int(rng.choice([-1, 1]))
            )
        chosen.append(plan)
        taken.append(plan.span)
    return chosen, eligible_segments, obs


def canonical_to_raw_rows(table: pa.Table) -> tuple[list[dict[str, object]], list[int]]:
    """Raw-equivalent records (canonical field names) in ``source_row`` order, plus that order."""
    rows = sorted(
        table.select(["source_row", *RAW_FIELDS]).to_pylist(), key=lambda r: int(r["source_row"])
    )
    order = [int(r.pop("source_row")) for r in rows]
    return rows, order


def rederive(
    raw_rows: list[dict[str, object]], original_rows: list[int]
) -> tuple[pa.Table, dict[int, int]]:
    """Run the production cleaner; return the canonical table and new -> original source rows."""
    pings, _ = process_and_clean_observations(raw_rows)
    return canonical_pings_to_arrow_table(pings), {k + 1: s for k, s in enumerate(original_rows)}


def _iso(t_s: float) -> str:
    return datetime.fromtimestamp(t_s, UTC).isoformat()


def _snapshot(row: Mapping[str, object]) -> dict[str, object]:
    keep = ("timestamp_utc", "latitude", "longitude", "sog", "cog", "heading")
    return {
        k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in row.items() if k in keep
    }


def _shift(row: dict[str, object], bearing_deg: float, distance_m: float) -> None:
    lat, lon = destination_point(
        np.array([float(row["latitude"])]),  # type: ignore[arg-type]
        np.array([float(row["longitude"])]),  # type: ignore[arg-type]
        np.array([bearing_deg]),
        np.array([distance_m]),
    )
    row["latitude"], row["longitude"] = float(lat[0]), float(lon[0])


def perturb_dataset(
    table: pa.Table, config: PerturbationConfig, vessels: Iterable[str], seed: int
) -> PerturbedDataset:
    """Inject one perturbation type and magnitude into eligible segments of ``vessels``."""
    plans, eligible, obs = plan_injections(config, table, vessels, seed)
    raw, order = canonical_to_raw_rows(table)
    pos = {s: k for k, s in enumerate(order)}
    removed: set[int] = set()
    injections: list[Injection] = []

    for n_inj, plan in enumerate(plans):
        src = [int(obs.source_row[r]) for r in plan.rows]
        before = {str(s): _snapshot(raw[pos[s]]) for s in src}
        params: dict[str, float] = {"magnitude": config.magnitude}
        modified = src
        if config.kind == "A1":
            row = raw[pos[src[0]]]
            row["sog"] = float(row["sog"]) + config.magnitude  # type: ignore[arg-type]
        elif config.kind == "A2":
            i = plan.rows[0]
            dist_m = config.magnitude * float(obs.elapsed_s[i]) / 3600.0 * METERS_PER_NAUTICAL_MILE
            _shift(raw[pos[src[0]]], float(obs.cog[i]), dist_m)
            params["shift_nm"] = dist_m / METERS_PER_NAUTICAL_MILE
        elif config.kind == "B":
            for r, s in zip(plan.rows, src, strict=True):
                new_heading = round(float(obs.cog[r]) + plan.sign * config.magnitude) % 360
                raw[pos[s]]["heading"] = float(new_heading)
            params["sign"] = float(plan.sign)
        else:
            removed.update(src)
            params["gap_min"] = config.magnitude
            modified = []
            if config.kind == "C2":
                bearing = (float(obs.cog[plan.label_row]) + plan.sign * 90.0) % 360.0
                modified = [int(obs.source_row[r]) for r in plan.shift_rows]
                for s in modified:
                    _shift(raw[pos[s]], bearing, config.displacement_nm * METERS_PER_NAUTICAL_MILE)
                params.update(
                    {
                        "displacement_nm": config.displacement_nm,
                        "sign": float(plan.sign),
                        "bearing_deg": bearing,
                    }
                )
        label_src = int(obs.source_row[plan.label_row])
        injections.append(
            Injection(
                injection_id=f"{config.label}-s{seed}-{n_inj:03d}",
                kind=config.kind,
                parameters=params,
                mmsi=str(obs.mmsi[plan.rows[0]]),
                label_source_rows=tuple(src) if config.kind == "B" else (label_src,),
                modified_source_rows=tuple(modified),
                removed_source_rows=tuple(src) if config.kind in ("C1", "C2") else (),
                before=before,
                after={str(s): _snapshot(raw[pos[s]]) for s in modified},
                span_start_utc=_iso(plan.span[0]),
                span_end_utc=_iso(plan.span[1]),
                seed=seed,
            )
        )

    kept = [k for k, s in enumerate(order) if s not in removed]
    perturbed, new_to_orig = rederive([raw[k] for k in kept], [order[k] for k in kept])
    return PerturbedDataset(config, seed, perturbed, new_to_orig, tuple(injections), eligible)


# =========================================================================== window labels
LABEL_POSITIVE: int = 1
LABEL_NEGATIVE: int = 0
LABEL_UNKNOWN: int = -1


def preexisting_flagged_rows(clean_table: pa.Table) -> frozenset[int]:
    """Original source rows with IMPLIED_SPEED_VIOLATION or a timestamp conflict (ML-03 D11)."""
    masked = {
        FLAG_IMPLIED_SPEED_VIOLATION,
        FLAG_TIMESTAMP_POSITION_CONFLICT,
        FLAG_TIMESTAMP_METADATA_CONFLICT,
    }
    return frozenset(
        int(s)
        for s, f in zip(
            clean_table.column("source_row").to_pylist(),
            clean_table.column("quality_flags").to_pylist(),
            strict=True,
        )
        if f and masked.intersection(f)
    )


def label_windows(
    windows: pa.Table,
    new_to_original: Mapping[int, int],
    injections: Iterable[Injection],
    masked_rows: frozenset[int],
) -> tuple[Int8Arr, dict[str, list[int]]]:
    """Window labels (1 / 0 / -1 unknown) and, per injection, the indices of its windows.

    Windows containing a pre-existing flagged observation or a conflict row are labelled unknown
    (ML-03 D11), which takes precedence over a positive label.
    """
    label_rows: dict[int, str] = {}
    for inj in injections:
        for s in inj.label_source_rows:
            label_rows[s] = inj.injection_id
    labels = np.zeros(windows.num_rows, dtype=np.int8)
    by_injection: dict[str, list[int]] = {inj_id: [] for inj_id in sorted(set(label_rows.values()))}
    conflicts = windows.column("n_conflict_rows").to_pylist()
    for w, rows in enumerate(windows.column("source_rows").to_pylist()):
        originals = {new_to_original.get(int(r), int(r)) for r in rows}
        hit = {label_rows[s] for s in originals if s in label_rows}
        for inj_id in hit:
            by_injection[inj_id].append(w)
        if conflicts[w] or originals & masked_rows:
            labels[w] = LABEL_UNKNOWN
        elif hit:
            labels[w] = LABEL_POSITIVE
    return labels, by_injection
