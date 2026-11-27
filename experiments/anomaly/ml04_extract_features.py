"""ML-04: development-set feature extraction experiment (Track B, ML-03 v1.1).

Builds the joint, MMSI-grouped vessel partition over all given development days (ML-03 v1.1
section 3.2, D16), fits the F10 expected-interval medians on DEV-train only (pooled over days),
extracts ML-02 pair and window features **per day** (outages and segments never span days), and
writes reproducible artifacts:

    partition.json, expected_intervals.json, pair_features.parquet, window_features.parquet,
    metadata.json, summary.json, summary.md

Test-day firewall (ML-03 section 3.4): before any observation row is loaded, the shared guard
``aegismar.anomaly.check_test_day_firewall`` inspects only the Parquet file metadata of every input
and refuses (exit code 2) if any input covers a held-out test day, unless
``--override-test-day-firewall`` is passed (reserved for the single final evaluation).

Usage (development set DEV = D0 + D0B):
    uv run python experiments/anomaly/ml04_extract_features.py \
        --input data/processed/lalb_20250101_v1_1/cleaned_ais.parquet \
                data/processed/lalb_20250108/cleaned_ais.parquet \
        --output experiments/outputs/anomaly/ml04_dev_features
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
import sklearn

from aegismar import __version__
from aegismar.anomaly.evaluation import (
    TestDayFirewallError,
    check_test_day_firewall,
    split_vessels,
)
from aegismar.anomaly.features import (
    FEATURE_SPEC_VERSION,
    MAX_RATE_DT_S,
    MIN_DISPARITY_DT_S,
    MIN_NET_DISPLACEMENT_NM,
    MIN_WINDOW_PAIRS,
    MOVING_SOG_KT,
    OUTAGE_MERGE_TOLERANCE_S,
    OUTAGE_MIN_SILENCE_S,
    PAIR_FEATURE_COLUMNS,
    SEGMENT_GAP_S,
    WINDOW_FEATURE_COLUMNS,
    WINDOW_LENGTH_S,
    WINDOW_STEP_S,
    FeatureResult,
    extract_features,
    fit_expected_intervals,
    prepare_observations,
)
from aegismar.ingestion import compute_content_fingerprint

EXPERIMENT_ID = "EXP-ML04-DEV-FEATURES"
EVALUATION_PROTOCOL = "ml-03-v1.1"
FACTOR_COLUMNS = (  # ML-03 section 4.3
    "max_abs_delta_sog_kt",
    "max_abs_accel_ms2",
    "max_speed_disparity_kt",
    "max_dr_error_ratio",
    "max_abs_rot_deg_s",
    "p90_lateral_drift_deg",
    "reversal_share",
    "max_gap_ratio",
    "max_unexplained_gap_s",
    "tortuosity",
    "stationary_net_displacement_m",
)
QUANTILES = (0.5, 0.9, 0.99, 0.999, 1.0)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def git_state() -> dict[str, Any]:
    def run(*a: str) -> str:
        try:
            return subprocess.run(
                ["git", *a], capture_output=True, text=True, check=True
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return "unavailable"

    status = run("status", "--porcelain")
    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": status not in ("", "unavailable"),
    }


def quantiles(values: list[float | None]) -> dict[str, Any]:
    x = np.asarray([v for v in values if v is not None], dtype=np.float64)
    if x.size == 0:
        return {"n": 0}
    out: dict[str, Any] = {"n": int(x.size)}
    for q in QUANTILES:
        out[f"p{q * 100:g}"] = round(float(np.quantile(x, q)), 6)
    return out


def with_columns(table: pa.Table, day: str, split_of: dict[str, str]) -> pa.Table:
    mmsi = table.column("mmsi").to_pylist()
    table = table.append_column("dataset_day", pa.array([day] * table.num_rows, pa.string()))
    return table.append_column("partition", pa.array([split_of[m] for m in mmsi], pa.string()))


def day_summary(result: FeatureResult, windows: pa.Table, rows: int) -> dict[str, Any]:
    obs = result.observations
    w_part = windows.column("partition").to_pylist()
    w_state = windows.column("motion_state").to_pylist()
    return {
        "rows": rows,
        "vessels": len(set(obs.mmsi.tolist())),
        "outage_windows_utc": [
            [datetime.fromtimestamp(a, UTC).isoformat(), datetime.fromtimestamp(b, UTC).isoformat()]
            for a, b in result.outages
        ],
        "segments": int(result.segments.max()) + 1 if result.segments.size else 0,
        "conflict_rows": int(obs.is_conflict.sum()),
        "pairs": int((obs.prev_idx >= 0).sum()),
        "pair_feature_non_null": {
            c: int(np.isfinite(result.pair_features[c]).sum()) for c in PAIR_FEATURE_COLUMNS
        },
        "windows": {
            "total": windows.num_rows,
            "by_partition_and_state": {
                f"{p}|{s}": n
                for (p, s), n in sorted(Counter(zip(w_part, w_state, strict=True)).items())
            },
            "with_preexisting_implied_speed_violation": int(
                pc.sum(pc.greater(windows.column("n_implied_speed_violation"), 0)).as_py() or 0
            ),
            "with_conflict_rows": int(
                pc.sum(pc.greater(windows.column("n_conflict_rows"), 0)).as_py() or 0
            ),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="ML-04 development-set feature extraction")
    ap.add_argument("--input", type=Path, nargs="+", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--override-test-day-firewall", action="store_true")
    args = ap.parse_args()

    day_labels: list[str] = []
    for path in args.input:
        try:  # file metadata only, before any observation row is loaded
            days = check_test_day_firewall(path, override=args.override_test_day_firewall)
        except TestDayFirewallError as exc:
            print(f"Refusing: {exc}", file=sys.stderr)
            return 2
        day_labels.append(",".join(d.isoformat() for d in days))
    if len(set(day_labels)) != len(day_labels):
        print(f"Refusing: duplicate dataset days {day_labels}", file=sys.stderr)
        return 2

    tables = [pq.read_table(p) for p in args.input]
    partition = split_vessels(tables)
    observations = [prepare_observations(t) for t in tables]
    expected = fit_expected_intervals(observations, partition.train)
    results = [extract_features(t, expected_intervals=expected) for t in tables]

    split_of = dict.fromkeys(partition.train, "train") | dict.fromkeys(partition.val, "val")
    pair_tables = [
        with_columns(r.pair_table(), d, split_of) for r, d in zip(results, day_labels, strict=True)
    ]
    window_tables = [
        with_columns(r.windows, d, split_of) for r, d in zip(results, day_labels, strict=True)
    ]
    pairs = pa.concat_tables(pair_tables)
    windows = pa.concat_tables(window_tables)

    class_of: dict[str, str] = {}
    for obs in observations:
        for m, c in zip(obs.mmsi, obs.transceiver_class, strict=True):
            if c and not class_of.get(m):
                class_of[m] = str(c)

    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    pq.write_table(pairs, out / "pair_features.parquet", compression="zstd")
    pq.write_table(windows, out / "window_features.parquet", compression="zstd")
    (out / "partition.json").write_text(json.dumps(partition.to_dict(), indent=2), encoding="utf-8")
    (out / "expected_intervals.json").write_text(
        json.dumps({f"{c}|{s}": v for (c, s), v in expected.items()}, indent=2), encoding="utf-8"
    )

    # ---- diagnostics (ML-03 section 7, development set only)
    w_part = windows.column("partition").to_pylist()
    w_state = windows.column("motion_state").to_pylist()
    w_class = [class_of.get(m, "unknown") for m in windows.column("mmsi").to_pylist()]
    factor_vals = {c: windows.column(c).to_pylist() for c in FACTOR_COLUMNS}
    by_class: dict[str, dict[str, int]] = {}
    for i, cls in enumerate(w_class):
        d = by_class.setdefault(cls, {"windows": 0, "unscored": 0})
        d["windows"] += 1
        d["unscored"] += int(all(factor_vals[c][i] is None for c in FACTOR_COLUMNS))
    train_moving = [
        i for i in range(windows.num_rows) if w_part[i] == "train" and w_state[i] == "moving"
    ]
    vessels_per_day = [set(o.mmsi.tolist()) for o in observations]
    summary: dict[str, Any] = {
        "days": day_labels,
        "vessels_total": len(split_of),
        "vessels_on_all_days": len(set.intersection(*vessels_per_day)),
        "partition": {
            "n_train": len(partition.train),
            "n_val": len(partition.val),
            "partition_sha256": partition.partition_hash,
            "strata": partition.strata,
        },
        "per_day": {
            d: day_summary(r, w, t.num_rows)
            for d, r, w, t in zip(day_labels, results, window_tables, tables, strict=True)
        },
        "windows_by_partition_and_state": {
            f"{p}|{s}": n
            for (p, s), n in sorted(Counter(zip(w_part, w_state, strict=True)).items())
        },
        "unscored_all_factor_features_null_by_class": by_class,
        "expected_intervals_s": {f"{c}|{s}": v for (c, s), v in expected.items()},
        "train_moving_window_feature_quantiles": {
            c: quantiles([windows.column(c)[i].as_py() for i in train_moving])
            for c in WINDOW_FEATURE_COLUMNS
        },
    }

    inputs = []
    for path, day in zip(args.input, day_labels, strict=True):
        fp = compute_content_fingerprint(path)
        inputs.append(
            {
                "path": str(path),
                "dataset_day_utc": day,
                "file_sha256": sha256_file(path),
                "content_fingerprint_sha256": fp.content_fingerprint_sha256,
                "content_fingerprint_version": fp.content_fingerprint_version,
            }
        )
    meta: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": git_state(),
        "aegismar_version": __version__,
        "inputs": inputs,
        "feature_spec": FEATURE_SPEC_VERSION,
        "evaluation_protocol": EVALUATION_PROTOCOL,
        "partition_seed": partition.seed,
        "partition_sha256": partition.partition_hash,
        "parameters": {
            "moving_sog_kt": MOVING_SOG_KT,
            "min_disparity_dt_s": MIN_DISPARITY_DT_S,
            "segment_gap_s": SEGMENT_GAP_S,
            "max_rate_dt_s": MAX_RATE_DT_S,
            "outage_min_silence_s": OUTAGE_MIN_SILENCE_S,
            "outage_merge_tolerance_s": OUTAGE_MERGE_TOLERANCE_S,
            "min_net_displacement_nm": MIN_NET_DISPLACEMENT_NM,
            "window_length_s": WINDOW_LENGTH_S,
            "window_step_s": WINDOW_STEP_S,
            "min_window_pairs": MIN_WINDOW_PAIRS,
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pyarrow": pa.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }
    (out / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = [
        "# ML-04 Development-Set Feature Extraction",
        "",
        f"- Protocol: {EVALUATION_PROTOCOL}; feature spec: {FEATURE_SPEC_VERSION}",
        f"- Git: `{meta['git']['commit']}` on `{meta['git']['branch']}` "
        f"(dirty={meta['git']['dirty']})",
        *(
            f"- Input {i['dataset_day_utc']}: SHA-256 `{i['file_sha256']}`, "
            f"fingerprint `{i['content_fingerprint_sha256']}`"
            for i in inputs
        ),
        f"- Vessels: {summary['vessels_total']} total, "
        f"{summary['vessels_on_all_days']} on all days",
        f"- Partition: {len(partition.train)} train / {len(partition.val)} val vessels, "
        f"SHA-256 `{partition.partition_hash}`",
        "- Windows: "
        + ", ".join(f"{k}: {v:,}" for k, v in summary["windows_by_partition_and_state"].items()),
        f"- Expected intervals (train): {summary['expected_intervals_s']}",
        "",
        "Full numbers: `summary.json`.",
        "",
    ]
    (out / "summary.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote artifacts to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
