"""ML-04: development-day feature extraction experiment (Track B).

Builds the D0 vessel partition (ML-03 section 3.2), fits the F10 expected-interval medians on
D0-train only, extracts ML-02 pair and window features, and writes reproducible artifacts:

    partition.json, expected_intervals.json, pair_features.parquet, window_features.parquet,
    metadata.json, summary.json, summary.md

Test-day firewall (ML-03 section 3.4): before any observation row is loaded, the shared guard
``aegismar.anomaly.check_test_day_firewall`` inspects only the Parquet file metadata and refuses
(exit code 2) if the dataset covers a held-out test day, unless ``--override-test-day-firewall``
is passed (reserved for the single final evaluation).

Usage:
    uv run python experiments/anomaly/ml04_extract_features.py \
        --input data/processed/lalb_20250101/cleaned_ais.parquet \
        --output experiments/outputs/anomaly/ml04_d0_features
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
    extract_features,
    fit_expected_intervals,
    prepare_observations,
)

EXPERIMENT_ID = "EXP-ML04-D0-FEATURES"
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


def main() -> int:
    ap = argparse.ArgumentParser(description="ML-04 development-day feature extraction")
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--override-test-day-firewall", action="store_true")
    args = ap.parse_args()

    try:  # runs on file metadata only, before any observation row is loaded
        days = check_test_day_firewall(args.input, override=args.override_test_day_firewall)
    except TestDayFirewallError as exc:
        print(f"Refusing: {exc}", file=sys.stderr)
        return 2
    day = ",".join(d.isoformat() for d in days)

    table = pq.read_table(args.input)

    partition = split_vessels(table)
    obs = prepare_observations(table)
    expected = fit_expected_intervals(obs, partition.train)
    result = extract_features(table, expected_intervals=expected)

    split_of = dict.fromkeys(partition.train, "train") | dict.fromkeys(partition.val, "val")
    pairs = result.pair_table()
    pairs = pairs.append_column(
        "partition", pa.array([split_of[m] for m in pairs.column("mmsi").to_pylist()], pa.string())
    )
    windows = result.windows
    win_mmsi = windows.column("mmsi").to_pylist()
    windows = windows.append_column(
        "partition", pa.array([split_of[m] for m in win_mmsi], pa.string())
    )

    class_of: dict[str, str] = {}
    for m, c in zip(obs.mmsi, obs.transceiver_class, strict=True):
        if c and not class_of.get(m):
            class_of[m] = str(c)
    win_class = [class_of.get(m, "unknown") for m in win_mmsi]

    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    pq.write_table(pairs, out / "pair_features.parquet", compression="zstd")
    pq.write_table(windows, out / "window_features.parquet", compression="zstd")
    (out / "partition.json").write_text(json.dumps(partition.to_dict(), indent=2), encoding="utf-8")
    (out / "expected_intervals.json").write_text(
        json.dumps({f"{c}|{s}": v for (c, s), v in expected.items()}, indent=2), encoding="utf-8"
    )

    # ---- diagnostics (ML-03 section 7, development day only)
    w_part = windows.column("partition").to_pylist()
    w_state = windows.column("motion_state").to_pylist()
    factor_vals = {c: windows.column(c).to_pylist() for c in FACTOR_COLUMNS}
    unscored = [
        all(factor_vals[c][i] is None for c in FACTOR_COLUMNS) for i in range(windows.num_rows)
    ]
    by_class: dict[str, dict[str, int]] = {}
    for cls, u in zip(win_class, unscored, strict=True):
        d = by_class.setdefault(cls, {"windows": 0, "unscored": 0})
        d["windows"] += 1
        d["unscored"] += int(u)

    train_moving = [
        i for i in range(windows.num_rows) if w_part[i] == "train" and w_state[i] == "moving"
    ]
    summary: dict[str, Any] = {
        "rows": table.num_rows,
        "vessels": len(split_of),
        "partition": {
            "n_train": len(partition.train),
            "n_val": len(partition.val),
            "partition_sha256": partition.partition_hash,
            "strata": partition.strata,
        },
        "outage_windows_utc": [
            [datetime.fromtimestamp(a, UTC).isoformat(), datetime.fromtimestamp(b, UTC).isoformat()]
            for a, b in result.outages
        ],
        "segments": int(result.segments.max()) + 1,
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
            "unscored_all_factor_features_null_by_class": by_class,
            "with_preexisting_implied_speed_violation": int(
                pc.sum(pc.greater(windows.column("n_implied_speed_violation"), 0)).as_py() or 0
            ),
            "with_conflict_rows": int(
                pc.sum(pc.greater(windows.column("n_conflict_rows"), 0)).as_py() or 0
            ),
        },
        "expected_intervals_s": {f"{c}|{s}": v for (c, s), v in expected.items()},
        "train_moving_window_feature_quantiles": {
            c: quantiles([windows.column(c)[i].as_py() for i in train_moving])
            for c in WINDOW_FEATURE_COLUMNS
        },
    }

    meta: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": git_state(),
        "aegismar_version": __version__,
        "input_path": str(args.input),
        "input_sha256": sha256_file(args.input),
        "dataset_day_utc": day,
        "feature_spec": FEATURE_SPEC_VERSION,
        "evaluation_protocol": "ml-03-v1.0",
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

    wb = summary["windows"]
    md = [
        "# ML-04 Development-Day Feature Extraction",
        "",
        f"- Input SHA-256: `{meta['input_sha256']}` ({day})",
        f"- Git: `{meta['git']['commit']}` on `{meta['git']['branch']}` "
        f"(dirty={meta['git']['dirty']})",
        f"- Partition: {len(partition.train)} train / {len(partition.val)} val vessels, "
        f"SHA-256 `{partition.partition_hash}`",
        f"- Segments: {summary['segments']}; pairs: {summary['pairs']:,}; "
        f"conflict rows: {summary['conflict_rows']}",
        f"- Windows: {wb['total']:,} — "
        + ", ".join(f"{k}: {v:,}" for k, v in wb["by_partition_and_state"].items()),
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
