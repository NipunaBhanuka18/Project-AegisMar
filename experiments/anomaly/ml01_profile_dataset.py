"""ML-01: Descriptive profiling of a cleaned canonical AIS Parquet dataset (Track B).

Reads ``cleaned_ais.parquet`` (read-only) and writes a reproducible JSON profile plus a
Markdown summary. Every number in the outputs is computed from the input file; nothing
is hard-coded. The profile informs the ML-02 feature specification (reporting intervals,
low-speed guards, heading availability, segmentation thresholds, kinematic ranges).

Consecutive-observation pairs are formed with the ingestion pointer ``prev_source_row``
(previous unambiguous observation of the same vessel), so same-timestamp conflicts are
never paired.

Usage:
    uv run python experiments/anomaly/ml01_profile_dataset.py \
        --input data/processed/lalb_20250101/cleaned_ais.parquet \
        --output experiments/outputs/anomaly/ml01_profile
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from numpy.typing import NDArray

LOW_SPEED_GUARDS_KT: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)
GAP_THRESHOLDS_S: tuple[int, ...] = (60, 120, 300, 600, 900, 1800, 3600, 7200)
SEGMENT_THRESHOLDS_S: tuple[int, ...] = (600, 1800, 3600, 7200)
OUTAGE_MIN_SILENCE_S: int = 60
QUANTILES: tuple[float, ...] = (0.0, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.999, 1.0)

FloatArr = NDArray[np.float64]


# --------------------------------------------------------------------------- helpers
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def git_state() -> dict[str, Any]:
    def run(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], capture_output=True, text=True, check=True
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return "unavailable"

    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": run("status", "--porcelain") not in ("", "unavailable"),
    }


def to_float(col: pa.ChunkedArray) -> FloatArr:
    """Convert a numeric Arrow column to float64 with nulls as NaN."""
    return np.asarray(
        pc.fill_null(pc.cast(col, pa.float64()), float("nan")).to_numpy(), dtype=np.float64
    )


def quantiles(x: FloatArr) -> dict[str, Any]:
    x = x[np.isfinite(x)]
    if x.size == 0:
        return {"n": 0}
    out: dict[str, Any] = {"n": int(x.size), "mean": round(float(x.mean()), 6)}
    for q in QUANTILES:
        out[f"p{q * 100:g}"] = round(float(np.quantile(x, q)), 6)
    return out


def angle_diff_deg(a: FloatArr, b: FloatArr) -> FloatArr:
    """Smallest absolute angular difference in degrees, wrapped to [0, 180]."""
    return np.abs((a - b + 180.0) % 360.0 - 180.0)


def vessel_group(code: int | None) -> str:
    """Coarse ITU-R M.1371 ship-type grouping."""
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
    if 90 <= code <= 99:
        return "other"
    if 20 <= code <= 29:
        return "wig"
    if 40 <= code <= 49:
        return "high_speed_craft"
    return "other"


def share(mask: NDArray[np.bool_], denom: int) -> float:
    return round(float(mask.sum()) / denom, 6) if denom else 0.0


# --------------------------------------------------------------------------- profile
def profile(table: pa.Table) -> dict[str, Any]:
    n = table.num_rows
    mmsi = np.asarray(table.column("mmsi").to_pylist(), dtype=object)
    ts_us = np.asarray(
        pc.cast(table.column("timestamp_utc"), pa.int64()).to_numpy(), dtype=np.int64
    )
    sog = to_float(table.column("sog"))
    cog = to_float(table.column("cog"))
    hdg = to_float(table.column("heading"))
    status = to_float(table.column("nav_status"))
    vtype = to_float(table.column("vessel_type"))
    elapsed = to_float(table.column("elapsed_seconds"))
    implied = to_float(table.column("implied_speed_knots"))
    tclass = np.asarray(
        [c if c is not None else "null" for c in table.column("transceiver_class").to_pylist()],
        dtype=object,
    )
    src = np.asarray(table.column("source_row").to_numpy(), dtype=np.int64)
    prev_src = to_float(table.column("prev_source_row"))

    # ---- previous-observation index via prev_source_row
    idx_of = np.full(int(src.max()) + 1, -1, dtype=np.int64)
    idx_of[src] = np.arange(n)
    has_prev = np.isfinite(prev_src)
    prev_idx = np.full(n, -1, dtype=np.int64)
    prev_idx[has_prev] = idx_of[prev_src[has_prev].astype(np.int64)]
    pair = prev_idx >= 0
    pi = prev_idx[pair]
    dt = elapsed[pair]

    # ---- vessel-level metadata (first non-null vessel_type / class per MMSI)
    vessel_type_of: dict[str, int | None] = {}
    vessel_class_of: dict[str, str] = {}
    for m, vt, tc in zip(mmsi, vtype, tclass, strict=True):
        if m not in vessel_type_of or (vessel_type_of[m] is None and np.isfinite(vt)):
            vessel_type_of[m] = int(vt) if np.isfinite(vt) else None
        if vessel_class_of.get(m, "null") == "null":
            vessel_class_of[m] = str(tc)
    group_of = {m: vessel_group(v) for m, v in vessel_type_of.items()}
    row_group = np.asarray([group_of[m] for m in mmsi], dtype=object)

    uniq, counts = np.unique(mmsi, return_counts=True)
    n_vessels = int(uniq.size)

    # ---- per-vessel time span
    first_ts: dict[str, int] = {}
    last_ts: dict[str, int] = {}
    for m, t in zip(mmsi, ts_us, strict=True):
        if m not in first_ts or t < first_ts[m]:
            first_ts[m] = int(t)
        if m not in last_ts or t > last_ts[m]:
            last_ts[m] = int(t)
    span_h = np.asarray([(last_ts[m] - first_ts[m]) / 3.6e9 for m in uniq], dtype=np.float64)

    out: dict[str, Any] = {}

    out["overview"] = {
        "rows": n,
        "vessels": n_vessels,
        "timestamp_min_utc": datetime.fromtimestamp(ts_us.min() / 1e6, UTC).isoformat(),
        "timestamp_max_utc": datetime.fromtimestamp(ts_us.max() / 1e6, UTC).isoformat(),
        "rows_with_previous_observation": int(pair.sum()),
        "vessels_with_single_observation": int((counts == 1).sum()),
        "pings_per_vessel": quantiles(counts.astype(np.float64)),
        "observed_span_hours_per_vessel": quantiles(span_h),
    }

    # ---- vessel composition
    groups = sorted(set(group_of.values()))
    comp: dict[str, Any] = {}
    for g in groups:
        vs = [m for m in uniq if group_of[m] == g]
        rows_g = row_group == g
        comp[g] = {
            "vessels": len(vs),
            "vessel_share": round(len(vs) / n_vessels, 4),
            "rows": int(rows_g.sum()),
            "row_share": share(rows_g, n),
        }
    out["vessel_groups"] = dict(sorted(comp.items(), key=lambda kv: -kv[1]["vessels"]))
    out["vessel_type_codes"] = {
        str(k): v
        for k, v in sorted(
            Counter("null" if v is None else str(v) for v in vessel_type_of.values()).items(),
            key=lambda kv: -kv[1],
        )
    }
    out["transceiver_class"] = {
        "vessels": dict(Counter(vessel_class_of.values())),
        "rows": {k: int(v) for k, v in Counter(tclass.tolist()).items()},
    }

    # ---- field availability
    def avail(mask_rows: NDArray[np.bool_]) -> dict[str, Any]:
        d = int(mask_rows.sum())
        return {
            "rows": d,
            "sog_present": share(np.isfinite(sog) & mask_rows, d),
            "cog_present": share(np.isfinite(cog) & mask_rows, d),
            "heading_present": share(np.isfinite(hdg) & mask_rows, d),
            "nav_status_present": share(np.isfinite(status) & mask_rows, d),
            "cog_and_heading_present": share(np.isfinite(cog) & np.isfinite(hdg) & mask_rows, d),
        }

    all_rows = np.ones(n, dtype=bool)
    out["field_availability"] = {
        "all": avail(all_rows),
        "by_class": {c: avail(tclass == c) for c in sorted(set(tclass.tolist()))},
        "by_group": {g: avail(row_group == g) for g in groups},
    }

    # ---- nav status
    out["nav_status_rows"] = {
        ("null" if not np.isfinite(k) else str(int(k))): int(v)
        for k, v in sorted(
            Counter(status.tolist()).items(),
            key=lambda kv: -kv[1],
        )
    }

    # ---- speed
    sog_ok = np.isfinite(sog)
    sog_n = int(sog_ok.sum())
    out["sog_knots"] = {
        "distribution": quantiles(sog),
        "share_below_guard": {
            f"{g:g}kt": share(sog_ok & (sog < g), sog_n) for g in LOW_SPEED_GUARDS_KT
        },
        "share_exactly_zero": share(sog_ok & (sog == 0.0), sog_n),
        "by_group_median": {
            g: round(float(np.nanmedian(sog[row_group == g])), 3)
            if np.isfinite(sog[row_group == g]).any()
            else None
            for g in groups
        },
    }

    # ---- reporting interval / gaps
    gap_rows = int(np.isfinite(dt).sum())
    moving_prev = np.isfinite(sog[pi]) & (sog[pi] >= 1.5)
    out["reporting_interval_s"] = {
        "all_pairs": quantiles(dt),
        "previous_ping_moving_sog_ge_1.5": quantiles(dt[moving_prev]),
        "previous_ping_stationary_sog_lt_0.5": quantiles(
            dt[np.isfinite(sog[pi]) & (sog[pi] < 0.5)]
        ),
        "by_class": {c: quantiles(dt[tclass[pair] == c]) for c in sorted(set(tclass.tolist()))},
        "share_of_pairs_exceeding": {
            f"{t}s": share(np.isfinite(dt) & (dt > t), gap_rows) for t in GAP_THRESHOLDS_S
        },
        "count_of_pairs_exceeding": {
            f"{t}s": int((np.isfinite(dt) & (dt > t)).sum()) for t in GAP_THRESHOLDS_S
        },
        "interval_modulo_check": {
            "share_integer_seconds": share(np.isfinite(dt) & (dt == np.round(dt)), gap_rows),
            "most_common_intervals_s": [
                [float(k), int(v)] for k, v in Counter(dt[np.isfinite(dt)].tolist()).most_common(15)
            ],
        },
    }

    # ---- segmentation
    seg: dict[str, Any] = {}
    for t in SEGMENT_THRESHOLDS_S:
        breaks = np.isfinite(elapsed) & (elapsed > t)
        per_vessel = Counter(mmsi[breaks].tolist())
        segs = np.asarray([1 + per_vessel.get(m, 0) for m in uniq], dtype=np.float64)
        seg[f"gap_gt_{t}s"] = {
            "total_segments": int(segs.sum()),
            "vessels_with_more_than_one_segment": int((segs > 1).sum()),
            "segments_per_vessel": quantiles(segs),
        }
    out["segmentation"] = seg

    # ---- kinematics on consecutive pairs
    sog_c, sog_p = sog[pair], sog[pi]
    cog_c, cog_p = cog[pair], cog[pi]
    valid_dt = np.isfinite(dt) & (dt > 0)

    accel_ok = valid_dt & np.isfinite(sog_c) & np.isfinite(sog_p)
    accel_kt_s = (sog_c - sog_p)[accel_ok] / dt[accel_ok]
    accel_ms2 = accel_kt_s * (1852.0 / 3600.0)
    dsog = np.abs(sog_c - sog_p)[accel_ok]

    rot_ok = (
        valid_dt
        & np.isfinite(cog_c)
        & np.isfinite(cog_p)
        & np.isfinite(sog_c)
        & np.isfinite(sog_p)
        & (sog_c >= 1.5)
        & (sog_p >= 1.5)
    )
    dcog = angle_diff_deg(cog_c, cog_p)[rot_ok]
    rot_deg_s = dcog / dt[rot_ok]
    short_dt = rot_ok & (dt <= 60)

    out["kinematics_pairs"] = {
        "abs_delta_sog_kt": quantiles(dsog),
        "acceleration_m_s2_abs": quantiles(np.abs(accel_ms2)),
        "acceleration_m_s2_abs_dt_le_60s": quantiles(
            np.abs((sog_c - sog_p) / np.where(dt > 0, dt, np.nan))[accel_ok & (dt <= 60)]
            * (1852.0 / 3600.0)
        ),
        "share_abs_accel_gt_0.5_m_s2": share(np.abs(accel_ms2) > 0.5, int(accel_ok.sum())),
        "abs_delta_cog_deg_both_sog_ge_1.5": quantiles(dcog),
        "rate_of_course_change_deg_s_both_sog_ge_1.5": quantiles(rot_deg_s),
        "rate_of_course_change_deg_s_dt_le_60s": quantiles(
            angle_diff_deg(cog_c, cog_p)[short_dt] / dt[short_dt]
        ),
    }

    # ---- drift (COG vs heading) conditioned on speed
    drift_all = np.isfinite(cog) & np.isfinite(hdg)
    drift: dict[str, Any] = {"rows_with_cog_and_heading": int(drift_all.sum())}
    for guard in (0.5, 1.5, 5.0):
        m = drift_all & np.isfinite(sog) & (sog >= guard)
        d = angle_diff_deg(cog[m], hdg[m])
        drift[f"sog_ge_{guard:g}kt"] = {
            "distribution_deg": quantiles(d),
            "share_gt_20deg": share(d > 20, d.size),
            "share_gt_45deg": share(d > 45, d.size),
            "share_gt_60deg": share(d > 60, d.size),
        }
    m_low = drift_all & np.isfinite(sog) & (sog < 0.5)
    d_low = angle_diff_deg(cog[m_low], hdg[m_low])
    drift["sog_lt_0.5kt"] = {
        "distribution_deg": quantiles(d_low),
        "share_gt_45deg": share(d_low > 45, d_low.size),
    }
    out["drift_cog_minus_heading"] = drift

    # ---- implied vs reported speed
    disp_ok = np.isfinite(implied) & np.isfinite(sog) & np.isfinite(elapsed) & (elapsed > 0)
    disp = np.abs(implied - sog)[disp_ok]
    out["implied_vs_reported_speed_kt"] = {
        "abs_disparity_all": quantiles(disp),
        "abs_disparity_elapsed_ge_30s": quantiles(np.abs(implied - sog)[disp_ok & (elapsed >= 30)]),
        "implied_speed": quantiles(implied),
    }

    # ---- diurnal activity
    hour = ((ts_us // 3_600_000_000) % 24).astype(np.int64)
    out["hourly_utc"] = {
        "rows": {int(h): int((hour == h).sum()) for h in range(24)},
        "active_vessels": {int(h): len(set(mmsi[hour == h].tolist())) for h in range(24)},
        "moving_vessels_sog_ge_1.5": {
            int(h): len(set(mmsi[(hour == h) & sog_ok & (sog >= 1.5)].tolist())) for h in range(24)
        },
    }

    # ---- dataset-wide reception silences (no observation from ANY vessel)
    uniq_s = np.unique(ts_us // 1_000_000)
    silence = np.diff(uniq_s)
    sil_idx = np.flatnonzero(silence > OUTAGE_MIN_SILENCE_S)
    end_s = ts_us // 1_000_000
    long_gap = np.isfinite(elapsed) & (elapsed > 600)
    gap_end = end_s[long_gap]
    gap_start = gap_end - elapsed[long_gap].astype(np.int64)
    explained = np.zeros(gap_end.size, dtype=bool)
    windows = []
    for i in sil_idx:
        lo, hi = int(uniq_s[i]), int(uniq_s[i + 1])
        overlaps = (gap_start <= lo) & (gap_end >= hi)
        explained |= overlaps
        windows.append(
            {
                "from_utc": datetime.fromtimestamp(lo, UTC).isoformat(),
                "to_utc": datetime.fromtimestamp(hi, UTC).isoformat(),
                "silence_s": hi - lo,
                "vessel_gaps_gt_600s_spanning_it": int(overlaps.sum()),
            }
        )
    out["feed_wide_silences"] = {
        "min_silence_s": OUTAGE_MIN_SILENCE_S,
        "windows": windows,
        "vessel_gaps_gt_600s_total": int(long_gap.sum()),
        "vessel_gaps_gt_600s_spanning_any_silence": int(explained.sum()),
    }

    # ---- moving vessels and split feasibility
    moving_vessels = set(mmsi[sog_ok & (sog >= 1.5)].tolist())
    out["split_feasibility"] = {
        "vessels_ever_moving_sog_ge_1.5": len(moving_vessels),
        "moving_vessels_by_group": dict(
            sorted(Counter(group_of[m] for m in moving_vessels).items(), key=lambda kv: -kv[1])
        ),
        "expected_test_vessels_at_30pct": round(0.3 * n_vessels, 1),
    }

    # ---- quality flags
    flat = pc.list_flatten(table.column("quality_flags"))
    vc = pc.value_counts(flat).to_pylist()
    out["quality_flags"] = {d["values"]: int(d["counts"]) for d in vc}

    return out


# --------------------------------------------------------------------------- report
def write_markdown(p: dict[str, Any], meta: dict[str, Any], path: Path) -> None:
    o = p["overview"]
    ri = p["reporting_interval_s"]
    lines = [
        "# ML-01 Dataset Profile",
        "",
        f"- Input: `{meta['input_path']}`",
        f"- Input SHA-256: `{meta['input_sha256']}`",
        f"- Git: `{meta['git']['commit']}` on `{meta['git']['branch']}`"
        f" (dirty={meta['git']['dirty']})",
        f"- Generated (UTC): {meta['generated_utc']}",
        "",
        "## Overview",
        f"- Rows: {o['rows']:,}; vessels: {o['vessels']}; "
        f"span {o['timestamp_min_utc']} -> {o['timestamp_max_utc']}",
        f"- Pings per vessel: median {o['pings_per_vessel']['p50']:g}, "
        f"p5 {o['pings_per_vessel']['p5']:g}, p95 {o['pings_per_vessel']['p95']:g}, "
        f"max {o['pings_per_vessel']['p100']:g}",
        f"- Vessels with a single observation: {o['vessels_with_single_observation']}",
        "",
        "## Vessel groups",
        "| group | vessels | rows | row share |",
        "|---|---:|---:|---:|",
    ]
    for g, v in p["vessel_groups"].items():
        lines.append(f"| {g} | {v['vessels']} | {v['rows']:,} | {v['row_share']:.3f} |")
    lines += [
        "",
        "## Field availability by transceiver class",
        "| class | rows | sog | cog | heading | cog&heading |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for c, v in p["field_availability"]["by_class"].items():
        lines.append(
            f"| {c} | {v['rows']:,} | {v['sog_present']:.3f} | {v['cog_present']:.3f} | "
            f"{v['heading_present']:.3f} | {v['cog_and_heading_present']:.3f} |"
        )
    lines += [
        "",
        "## Reporting interval (s) between consecutive observations",
        f"- All pairs: median {ri['all_pairs']['p50']:g}, p95 {ri['all_pairs']['p95']:g}, "
        f"p99 {ri['all_pairs']['p99']:g}, max {ri['all_pairs']['p100']:g}",
        "- Share of pairs exceeding: "
        + ", ".join(f"{k}: {v:.4f}" for k, v in ri["share_of_pairs_exceeding"].items()),
        "",
        "## Low-speed shares (SOG below guard)",
        ", ".join(f"{k}: {v:.3f}" for k, v in p["sog_knots"]["share_below_guard"].items()),
        "",
        "## Segmentation (segments created by gap threshold)",
    ]
    for k, v in p["segmentation"].items():
        lines.append(
            f"- {k}: {v['total_segments']} segments; "
            f"{v['vessels_with_more_than_one_segment']} vessels split"
        )
    dr = p["drift_cog_minus_heading"]
    lines += ["", "## Drift |COG - heading| by speed condition"]
    for k in ("sog_ge_0.5kt", "sog_ge_1.5kt", "sog_ge_5kt"):
        d = dr[k]
        lines.append(
            f"- {k}: n={d['distribution_deg'].get('n', 0):,}, "
            f"median {d['distribution_deg'].get('p50', float('nan')):g} deg, "
            f">45 deg share {d['share_gt_45deg']:.4f}"
        )
    fw = p["feed_wide_silences"]
    lines += [
        "",
        f"## Feed-wide silences (> {fw['min_silence_s']} s with no observation from any vessel)",
    ]
    for w in fw["windows"]:
        lines.append(
            f"- {w['from_utc']} -> {w['to_utc']} ({w['silence_s']} s); "
            f"vessel gaps > 600 s spanning it: {w['vessel_gaps_gt_600s_spanning_it']}"
        )
    lines.append(
        f"- Vessel gaps > 600 s spanning any silence: "
        f"{fw['vessel_gaps_gt_600s_spanning_any_silence']} of {fw['vessel_gaps_gt_600s_total']}"
    )
    lines += ["", "Full numbers: `profile.json`.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    table = pq.read_table(args.input)
    result = profile(table)
    meta = {
        "experiment_id": "ML-01-PROFILE",
        "input_path": str(args.input),
        "input_sha256": sha256_file(args.input),
        "git": git_state(),
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pyarrow": pa.__version__,
        "parameters": {
            "low_speed_guards_kt": LOW_SPEED_GUARDS_KT,
            "gap_thresholds_s": GAP_THRESHOLDS_S,
            "segment_thresholds_s": SEGMENT_THRESHOLDS_S,
            "moving_threshold_kt": 1.5,
            "outage_min_silence_s": OUTAGE_MIN_SILENCE_S,
        },
    }

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "profile.json").write_text(
        json.dumps({"metadata": meta, "profile": result}, indent=2), encoding="utf-8"
    )
    write_markdown(result, meta, args.output / "profile.md")
    print(f"Wrote {args.output / 'profile.json'} and {args.output / 'profile.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
