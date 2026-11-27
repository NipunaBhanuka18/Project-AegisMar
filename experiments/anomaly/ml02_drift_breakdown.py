"""ML-02 supporting analysis: COG-vs-heading disparity broken down by vessel group.

Quantifies how much of the large |COG - heading| disparity at speed comes from
near-reversal values (> 135 deg) versus lateral drift (45-135 deg), and which vessel
groups and individual vessels contribute. Read-only on the input Parquet.

Usage:
    uv run python experiments/anomaly/ml02_drift_breakdown.py \
        --input data/processed/lalb_20250101_v1_1/cleaned_ais.parquet \
        --output experiments/outputs/anomaly/ml02_drift_breakdown
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from numpy.typing import NDArray

SOG_GUARD_KT = 1.5
LATERAL_MIN_DEG = 45.0
REVERSAL_MIN_DEG = 135.0


def to_float(col: pa.ChunkedArray) -> NDArray[np.float64]:
    return np.asarray(
        pc.fill_null(pc.cast(col, pa.float64()), float("nan")).to_numpy(), dtype=np.float64
    )


def group_of(code: float) -> str:
    if not np.isfinite(code):
        return "unknown"
    v = int(code)
    if v in (31, 32, 52):
        return "tug_towing"
    if 70 <= v <= 79:
        return "cargo"
    if 80 <= v <= 89:
        return "tanker"
    if 60 <= v <= 69:
        return "passenger"
    if v == 37:
        return "pleasure"
    if v == 36:
        return "sailing"
    return "other"


def pct(x: NDArray[np.float64], q: float) -> float | None:
    return round(float(np.percentile(x, q)), 3) if x.size else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    t = pq.read_table(args.input)
    sog = to_float(t.column("sog"))
    cog = to_float(t.column("cog"))
    hdg = to_float(t.column("heading"))
    vt = to_float(t.column("vessel_type"))
    mmsi = np.asarray(t.column("mmsi").to_pylist(), dtype=object)
    grp = np.asarray([group_of(v) for v in vt], dtype=object)

    disparity = np.abs((cog - hdg + 180.0) % 360.0 - 180.0)
    ok = np.isfinite(disparity) & np.isfinite(sog) & (sog >= SOG_GUARD_KT)
    lateral = ok & (disparity > LATERAL_MIN_DEG) & (disparity <= REVERSAL_MIN_DEG)
    reversal = ok & (disparity > REVERSAL_MIN_DEG)

    by_group: dict[str, Any] = {}
    for g in sorted(set(grp[ok].tolist())):
        s = ok & (grp == g)
        x = disparity[s]
        by_group[g] = {
            "rows": int(s.sum()),
            "median_deg": pct(x, 50),
            "share_lateral_45_135": round(float((lateral & s).sum() / s.sum()), 4),
            "share_reversal_gt_135": round(float((reversal & s).sum() / s.sum()), 4),
            "vessels_with_reversal": len(set(mmsi[reversal & s].tolist())),
        }

    def summary(mask: NDArray[np.bool_]) -> dict[str, Any]:
        return {
            "rows": int(mask.sum()),
            "vessels": len(set(mmsi[mask].tolist())),
            "top_vessels": [[m, c] for m, c in Counter(mmsi[mask].tolist()).most_common(5)],
            "sog_p5_p50_p95": [pct(sog[mask], q) for q in (5, 50, 95)],
            "by_group_rows": dict(Counter(grp[mask].tolist()).most_common()),
        }

    h = hashlib.sha256(args.input.read_bytes()).hexdigest()
    result = {
        "metadata": {
            "experiment_id": "ML-02-DRIFT-BREAKDOWN",
            "input_path": str(args.input),
            "input_sha256": h,
            "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "parameters": {
                "sog_guard_kt": SOG_GUARD_KT,
                "lateral_min_deg": LATERAL_MIN_DEG,
                "reversal_min_deg": REVERSAL_MIN_DEG,
            },
        },
        "rows_with_cog_heading_and_sog_ge_guard": int(ok.sum()),
        "lateral_45_135": summary(lateral),
        "reversal_gt_135": summary(reversal),
        "by_group": by_group,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    out = args.output / "drift_breakdown.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "metadata"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
