"""ML-05 diagnostics: perturbation eligibility on the DEV validation vessels (ML-03 v1.1 section 7).

For every sweep configuration, counts how many injections the ML-03 v1.1 rules place on each
development day for the DEV-val vessels (from an ML-04 ``partition.json``), how many distinct
vessels they cover, and whether the pooled count reaches the protocol's 20-injection threshold for
non-descriptive reporting. Only injection *sites* are planned; no data is modified.

Usage:
    uv run python experiments/anomaly/ml05_eligibility_diagnostics.py \
        --input data/processed/lalb_20250101_v1_1/cleaned_ais.parquet \
                data/processed/lalb_20250108/cleaned_ais.parquet \
        --partition experiments/outputs/anomaly/ml04_dev_features/partition.json \
        --output experiments/outputs/anomaly/ml05_eligibility
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from aegismar.anomaly.evaluation import (
    HEADLINE_CONFIGS,
    SWEEP_CONFIGS,
    SWEEP_SEEDS,
    TestDayFirewallError,
    check_test_day_firewall,
    plan_injections,
)

MIN_INJECTIONS_FOR_FORMAL_RESULTS = 20  # ML-03 section 4.2 notes


def main() -> int:
    ap = argparse.ArgumentParser(description="ML-05 perturbation eligibility diagnostics")
    ap.add_argument("--input", type=Path, nargs="+", required=True)
    ap.add_argument("--partition", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    days: list[str] = []
    for path in args.input:
        try:
            days.append(",".join(d.isoformat() for d in check_test_day_firewall(path)))
        except TestDayFirewallError as exc:
            print(f"Refusing: {exc}", file=sys.stderr)
            return 2

    partition = json.loads(args.partition.read_text(encoding="utf-8"))
    val = set(partition["val"])
    tables = [pq.read_table(p) for p in args.input]

    rows: list[dict[str, Any]] = []
    for cfg in SWEEP_CONFIGS:
        for seed in SWEEP_SEEDS:
            per_day: dict[str, int] = {}
            vessels: set[str] = set()
            for day, table in zip(days, tables, strict=True):
                plans, _, obs = plan_injections(cfg, table, val, seed)
                per_day[day] = len(plans)
                vessels |= {str(obs.mmsi[p.label_row]) for p in plans}
            total = sum(per_day.values())
            rows.append(
                {
                    "config": cfg.label,
                    "headline": cfg in HEADLINE_CONFIGS,
                    "seed": seed,
                    "injections_per_day": per_day,
                    "injections_total": total,
                    "distinct_vessels": len(vessels),
                    "meets_formal_threshold": total >= MIN_INJECTIONS_FOR_FORMAL_RESULTS,
                }
            )

    args.output.mkdir(parents=True, exist_ok=True)
    result = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "evaluation_protocol": "ml-03-v1.1",
        "inputs": [str(p) for p in args.input],
        "days": days,
        "partition_sha256": partition["partition_sha256"],
        "n_val_vessels": len(val),
        "threshold": MIN_INJECTIONS_FOR_FORMAL_RESULTS,
        "rows": rows,
    }
    (args.output / "eligibility.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    for r in rows:
        if r["seed"] == SWEEP_SEEDS[0]:
            mark = "*" if r["headline"] else " "
            flag = "" if r["meets_formal_threshold"] else "  (descriptive only)"
            print(
                f"{mark}{r['config']:15s} total={r['injections_total']:3d} "
                f"vessels={r['distinct_vessels']:3d} per_day={r['injections_per_day']}{flag}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
