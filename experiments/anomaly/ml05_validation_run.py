"""ML-05 stage 3: perturbed DEV-val evaluation, threshold freezing and validation metrics.

Implements ML-03 v1.2 sections 4-7 on the development set (DEV = D0 + D0B) only:

1. Test-day firewall on every input (metadata only), then the joint MMSI-grouped split (D16).
2. Clean features per day (F10 medians from DEV-train); R1, M1, M2 fitted on clean **DEV-train**
   windows; clean B0 noise labels for all nine grid points.
3. Perturbed copies of each development day (DEV-val vessels only): headline configurations x
   seeds 1000-1009, sweep configurations x seeds 1000-1002, plus one clean copy per day. Only
   DEV-val windows are scored; features of a vessel never depend on another vessel, so features
   are extracted on the DEV-val rows with the outage windows of the full perturbed day.
4. Thresholds: each method's threshold maximises F1 on DEV-val headline eligible-context windows
   (v1.2 D19) pooled over
   configurations, seeds and days; B0's grid point is the one with the best such F1. Written to
   ``thresholds.json`` and frozen for the test-day evaluation (stage 4).
5. Validation metrics (informational, not the hypothesis test).

Usage:
    uv run python experiments/anomaly/ml05_validation_run.py \
        --input data/processed/lalb_20250101_v1_1/cleaned_ais.parquet \
                data/processed/lalb_20250108/cleaned_ais.parquet \
        --expected-partition-sha256 <ML-04 DEV partition SHA-256, e.g. 7794e245...> \
        --output experiments/outputs/anomaly/ml05_validation --workers 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pickle
import platform
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import sklearn

from aegismar.anomaly.evaluation import (
    HEADLINE_CONFIGS,
    HEADLINE_SEEDS,
    LABEL_POSITIVE,
    SWEEP_CONFIGS,
    SWEEP_SEEDS,
    Injection,
    PerturbationConfig,
    TestDayFirewallError,
    alerts,
    attribution_accuracy,
    best_f1_threshold,
    check_test_day_firewall,
    cluster_bootstrap,
    confusion_at,
    eligible_context_windows,
    eligible_rows,
    event_recall,
    label_windows,
    merge_incidents,
    perturb_dataset,
    pr_auc,
    preexisting_flagged_rows,
    roc_auc,
    split_vessels,
    vessel_attributes,
)
from aegismar.anomaly.features import (
    FEATURE_SPEC_VERSION,
    detect_outage_windows,
    extract_features,
    fit_expected_intervals,
    prepare_observations,
)
from aegismar.anomaly.models import (
    B0_GRID,
    NoiseLabels,
    WindowModel,
    b0_window_scores,
    build_dataset,
    clustering_inputs_equal,
    grid_points,
    noise_labels_for_grid,
    remap_noise_labels,
    with_source_rows,
)
from aegismar.anomaly.rules import RuleScorer
from aegismar.ingestion import compute_content_fingerprint

EVALUATION_PROTOCOL = "ml-03-v1.2"
EXPERIMENT_ID = "EXP-ML05-DEV-VALIDATION"
CLEAN = "CLEAN"
B0_COLUMNS = [f"b0_{p}" for p in grid_points()]
MODEL_METHODS = ("R1", "R1_lin", "M1", "M2")
METHOD_COLUMN = {"R1": "r1", "R1_lin": "r1_lin", "M1": "m1", "M2": "m2"}


@dataclass(frozen=True)
class Task:
    config: PerturbationConfig | None  # None = clean copy
    seed: int
    day: int
    headline: bool
    sweep: bool

    @property
    def label(self) -> str:
        return CLEAN if self.config is None else self.config.label


# --------------------------------------------------------------------------- worker side
_CTX: dict[str, Any] = {}


def _init_worker(context_path: str) -> None:
    with open(context_path, "rb") as f:
        ctx = pickle.load(f)
    ctx["tables"] = [pq.read_table(p) for p in ctx["paths"]]
    ctx["clean_datasets"] = [build_dataset(t) for t in ctx["tables"]]
    _CTX.update(ctx)


def _score_copy(task: Task) -> tuple[pa.Table, dict[str, Any]]:
    t0 = time.perf_counter()
    table: pa.Table = _CTX["tables"][task.day]
    val: frozenset[str] = _CTX["val"]
    injections: tuple[Injection, ...] = ()
    manifest: dict[str, object] = {"n_injections": 0}
    new_to_orig: dict[int, int] | None = None
    perturbed = table
    if task.config is not None:
        d = perturb_dataset(table, task.config, val, task.seed)
        perturbed, new_to_orig, injections = d.table, d.new_to_original, d.injections
        manifest = d.manifest()
    mapping = new_to_orig if new_to_orig is not None else {}

    outages = detect_outage_windows(prepare_observations(perturbed).timestamp_s)
    val_rows = perturbed.filter(pc.is_in(perturbed.column("mmsi"), pa.array(sorted(val))))
    feats = extract_features(val_rows, _CTX["expected"], outages)
    windows = feats.windows
    labels, by_inj = label_windows(windows, mapping, injections, _CTX["masked"][task.day])
    eligible = eligible_context_windows(windows, mapping, _CTX["eligible"][task.day])

    r1 = _CTX["r1"].score(windows)
    m1 = _CTX["m1"].score(windows)
    m2 = _CTX["m2"].score(windows)

    dataset = build_dataset(perturbed)
    clean_labels: list[NoiseLabels] = _CTX["clean_b0"][task.day]
    if new_to_orig is None:
        b0_labels = clean_labels
        reused = True
    else:
        mapped = with_source_rows(dataset, new_to_orig)
        reused = clustering_inputs_equal(_CTX["clean_datasets"][task.day], mapped)
        if reused:
            orig_to_new = {o: n for n, o in new_to_orig.items()}
            b0_labels = [remap_noise_labels(lab, orig_to_new) for lab in clean_labels]
        else:
            b0_labels = noise_labels_for_grid(dataset, B0_GRID)

    inj_of_window: list[list[str]] = [[] for _ in range(windows.num_rows)]
    for inj_id, ws in by_inj.items():
        for w in ws:
            inj_of_window[w].append(inj_id)

    n = windows.num_rows
    cfg = task.config
    cols: dict[str, Any] = {
        "day": pa.array([_CTX["days"][task.day]] * n, pa.string()),
        "config": pa.array([task.label] * n, pa.string()),
        "kind": pa.array([cfg.kind if cfg else CLEAN] * n, pa.string()),
        "magnitude": pa.array([cfg.magnitude if cfg else 0.0] * n, pa.float64()),
        "seed": pa.array([task.seed] * n, pa.int64()),
        "headline": pa.array([task.headline] * n, pa.bool_()),
        "sweep": pa.array([task.sweep] * n, pa.bool_()),
        "mmsi": windows.column("mmsi"),
        "segment_id": windows.column("segment_id"),
        "window_start_utc": windows.column("window_start_utc"),
        "window_end_utc": windows.column("window_end_utc"),
        "motion_state": windows.column("motion_state"),
        "label": pa.array(labels.astype(np.int8), pa.int8()),
        "injection_ids": pa.array(inj_of_window, pa.list_(pa.string())),
        "r1": pa.array(r1.composite, pa.float64(), from_pandas=True),
        "r1_lin": pa.array(r1.linear, pa.float64(), from_pandas=True),
        "primary_factor": pa.array(list(r1.primary_factor), pa.string()),
        "m1": pa.array(m1, pa.float64(), from_pandas=True),
        "m2": pa.array(m2, pa.float64(), from_pandas=True),
        "eligible_context": pa.array(eligible, pa.bool_()),
    }
    for col, lab in zip(B0_COLUMNS, b0_labels, strict=True):
        cols[col] = pa.array(b0_window_scores(windows, lab), pa.float64(), from_pandas=True)
    info = {
        "config": task.label,
        "seed": task.seed,
        "day": _CTX["days"][task.day],
        "n_windows": n,
        "n_injections": len(injections),
        "b0_reused_clean": reused,
        "seconds": round(time.perf_counter() - t0, 1),
        "manifest": manifest,
    }
    return pa.table(cols), info


# --------------------------------------------------------------------------- main side
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

    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": run("status", "--porcelain") not in ("", "unavailable"),
    }


def build_tasks(n_days: int) -> list[Task]:
    keys: dict[tuple[str, int, int], Task] = {}
    for day in range(n_days):
        keys[(CLEAN, 0, day)] = Task(None, 0, day, False, False)
        for cfg in HEADLINE_CONFIGS:
            for seed in HEADLINE_SEEDS:
                keys[(cfg.label, seed, day)] = Task(cfg, seed, day, True, False)
        for cfg in SWEEP_CONFIGS:
            for seed in SWEEP_SEEDS:
                old = keys.get((cfg.label, seed, day))
                keys[(cfg.label, seed, day)] = Task(
                    cfg, seed, day, bool(old and old.headline), True
                )
    return sorted(keys.values(), key=lambda t: (t.day, t.label, t.seed))


def col(table: pa.Table, name: str) -> np.ndarray[Any, np.dtype[np.float64]]:
    return np.asarray(
        [math.nan if v is None else float(v) for v in table.column(name).to_pylist()],
        dtype=np.float64,
    )


def event_recall_from_rows(
    rows: pa.Table, alert: np.ndarray[Any, np.dtype[np.bool_]]
) -> tuple[int, int]:
    by_inj: dict[str, list[int]] = defaultdict(list)
    for w, ids in enumerate(rows.column("injection_ids").to_pylist()):
        for i in ids or []:
            by_inj[f"{rows.column('day')[w].as_py()}|{i}"].append(w)
    labels = np.asarray(rows.column("label").to_pylist(), dtype=np.int8)
    return event_recall(by_inj, labels, alert)


def main() -> int:  # noqa: C901 - linear pipeline, kept in one place for auditability
    ap = argparse.ArgumentParser(description="ML-05 stage 3 DEV-val evaluation")
    ap.add_argument("--input", type=Path, nargs="+", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--expected-partition-sha256", default=None)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument(
        "--smoke",
        action="store_true",
        help="debug only: first day, clean copy + seed 1000 of each headline config",
    )
    args = ap.parse_args()
    started = time.perf_counter()

    days: list[str] = []
    for path in args.input:
        try:
            days.append(",".join(d.isoformat() for d in check_test_day_firewall(path)))
        except TestDayFirewallError as exc:
            print(f"Refusing: {exc}", file=sys.stderr)
            return 2

    tables = [pq.read_table(p) for p in args.input]
    partition = split_vessels(tables)
    if (
        args.expected_partition_sha256
        and partition.partition_hash != args.expected_partition_sha256
    ):
        print(f"Refusing: partition hash {partition.partition_hash} differs", file=sys.stderr)
        return 3
    val = frozenset(partition.val)
    observations = [prepare_observations(t) for t in tables]
    expected = fit_expected_intervals(observations, partition.train)
    clean = [extract_features(t, expected_intervals=expected) for t in tables]

    train_windows = pa.concat_tables(
        [
            r.windows.filter(pc.is_in(r.windows.column("mmsi"), pa.array(sorted(partition.train))))
            for r in clean
        ]
    )
    r1 = RuleScorer().fit(train_windows)
    m1 = WindowModel("isolation_forest").fit(train_windows)
    m2 = WindowModel("lof").fit(train_windows)
    print(
        f"[{time.perf_counter() - started:.0f}s] models fitted on "
        f"{train_windows.num_rows} train windows"
    )

    clean_b0 = [noise_labels_for_grid(build_dataset(t), B0_GRID) for t in tables]
    print(f"[{time.perf_counter() - started:.0f}s] clean B0 grid computed")

    out = args.output
    (out / "models").mkdir(parents=True, exist_ok=True)
    for name, obj in (("r1.pkl", r1), ("m1_isolation_forest.pkl", m1), ("m2_lof.pkl", m2)):
        (out / "models" / name).write_bytes(pickle.dumps(obj))
    context = {
        "paths": [str(p) for p in args.input],
        "days": days,
        "val": val,
        "expected": expected,
        "r1": r1,
        "m1": m1,
        "m2": m2,
        "clean_b0": clean_b0,
        "masked": [preexisting_flagged_rows(t) for t in tables],
        "eligible": [eligible_rows(t) for t in tables],
    }
    context_path = out / "_worker_context.pkl"
    context_path.write_bytes(pickle.dumps(context))

    tasks = build_tasks(len(tables))
    if args.smoke:
        tasks = [
            t for t in tasks if t.day == 0 and (t.config is None or (t.headline and t.seed == 1000))
        ]
    results: list[pa.Table] = []
    infos: list[dict[str, Any]] = []
    with ProcessPoolExecutor(
        args.workers, initializer=_init_worker, initargs=(str(context_path),)
    ) as ex:
        futures = {ex.submit(_score_copy, t): t for t in tasks}
        for k, fut in enumerate(as_completed(futures), start=1):
            tab, info = fut.result()
            results.append(tab)
            infos.append(info)
            print(
                f"[{time.perf_counter() - started:.0f}s] {k}/{len(tasks)} {info['day']} "
                f"{info['config']} s{info['seed']} inj={info['n_injections']} "
                f"b0_reused={info['b0_reused_clean']} ({info['seconds']}s)",
                flush=True,
            )
    context_path.unlink()

    preds = pa.concat_tables(results)
    order = pc.sort_indices(
        preds,
        [
            ("day", "ascending"),
            ("config", "ascending"),
            ("seed", "ascending"),
            ("window_start_utc", "ascending"),
            ("mmsi", "ascending"),
        ],
    )
    preds = preds.take(order)
    pq.write_table(preds, out / "predictions.parquet", compression="zstd")
    with open(out / "perturbations.jsonl", "w", encoding="utf-8") as f:
        for info in sorted(infos, key=lambda i: (i["day"], i["config"], i["seed"])):
            f.write(json.dumps(info) + "\n")

    # ---- thresholds on DEV-val headline eligible-context windows (ML-03 v1.2 6.0 and 6.3)
    head_all = preds.filter(pc.field("headline"))
    head = head_all.filter(pc.field("eligible_context"))
    head_labels = np.asarray(head.column("label").to_pylist(), dtype=np.int8)
    b0_choice = {c: best_f1_threshold(head_labels, col(head, c)) for c in B0_COLUMNS}
    b0_best = max(B0_COLUMNS, key=lambda c: (b0_choice[c].f1, -B0_COLUMNS.index(c)))
    method_col = {**METHOD_COLUMN, "B0": b0_best}
    thresholds = {m: best_f1_threshold(head_labels, col(head, c)) for m, c in method_col.items()}

    frozen = {
        "evaluation_protocol": EVALUATION_PROTOCOL,
        "partition_sha256": partition.partition_hash,
        "b0_selected_grid_point": b0_best.removeprefix("b0_"),
        "b0_grid_dev_val_f1": {c.removeprefix("b0_"): b0_choice[c].f1 for c in B0_COLUMNS},
        "thresholds": {m: thresholds[m].threshold for m in method_col},
        "dev_val_headline_at_threshold": {m: thresholds[m].to_dict() for m in method_col},
    }
    (out / "thresholds.json").write_text(json.dumps(frozen, indent=2), encoding="utf-8")

    # ---- validation metrics (primary population: eligible-context; secondary: all, moving)
    metrics: dict[str, Any] = {
        "headline": {},
        "secondary_pr_auc": {},
        "negative_control": {},
        "sweep": {},
        "clean_false_alarms": {},
    }
    for cfg in HEADLINE_CONFIGS:
        rows = head.filter(pc.equal(head.column("config"), cfg.label))
        labels = np.asarray(rows.column("label").to_pylist(), dtype=np.int8)
        seeds = np.asarray(rows.column("seed").to_pylist())
        entry: dict[str, Any] = {
            "eligible_context_windows": int((labels >= 0).sum()),
            "positives": int((labels == LABEL_POSITIVE).sum()),
            "prevalence": float((labels == LABEL_POSITIVE).sum() / max(1, (labels >= 0).sum())),
        }
        for m, c in method_col.items():
            s = col(rows, c)
            per_seed = [pr_auc(labels[seeds == sd], s[seeds == sd]) for sd in HEADLINE_SEEDS]
            alert = alerts(s, thresholds[m].threshold)
            det, tot = event_recall_from_rows(rows, alert)
            e: dict[str, Any] = {
                "pr_auc_mean": float(np.nanmean(per_seed)),
                "pr_auc_sd": float(np.nanstd(per_seed, ddof=1)),
                "roc_auc": roc_auc(labels, s),
                "at_threshold": confusion_at(labels, s, thresholds[m].threshold).to_dict(),
                "event_recall": [det, tot],
            }
            if m != "B0":
                ok, tp = attribution_accuracy(
                    labels, alert, rows.column("primary_factor").to_pylist(), cfg.kind
                )
                e["attribution"] = [ok, tp]
            entry[m] = e
        metrics["headline"][cfg.label] = entry

        secondary: dict[str, Any] = {}
        all_rows = head_all.filter(pc.equal(head_all.column("config"), cfg.label))
        moving = np.asarray([s == "moving" for s in all_rows.column("motion_state").to_pylist()])
        all_labels = np.asarray(all_rows.column("label").to_pylist(), dtype=np.int8)
        for pop, mask in (("all_windows", np.ones_like(moving)), ("moving_only", moving)):
            lab = all_labels[mask]
            secondary[pop] = {
                "prevalence": float((lab == LABEL_POSITIVE).sum() / max(1, (lab >= 0).sum())),
                **{m: pr_auc(lab, col(all_rows, c)[mask]) for m, c in method_col.items()},
            }
        metrics["secondary_pr_auc"][cfg.label] = secondary

        if cfg.kind in ("A1", "B"):  # negative control: B0 cannot observe these faults (v1.2 §7)
            b0 = col(rows, method_col["B0"])
            known = labels >= 0
            vessels_of_rows = rows.column("mmsi").to_pylist()

            def ratio(
                idx: np.ndarray[Any, np.dtype[np.int64]], b0: Any = b0, labels: Any = labels
            ) -> float:
                lab = labels[idx]
                prev = (lab == LABEL_POSITIVE).sum() / max(1, (lab >= 0).sum())
                return pr_auc(lab, b0[idx]) / prev if prev else math.nan

            boot = cluster_bootstrap(vessels_of_rows, ratio)
            point = ratio(np.flatnonzero(known))
            lo, hi = np.nanpercentile(boot, [2.5, 97.5])
            metrics["negative_control"][cfg.label] = {
                "b0_pr_auc_over_prevalence": point,
                "bootstrap_95ci": [float(lo), float(hi)],
                "interval_excludes_1": bool(lo > 1.0 or hi < 1.0),
            }

    sweep = preds.filter(pc.field("sweep"))
    for cfg in SWEEP_CONFIGS:
        rows = sweep.filter(pc.equal(sweep.column("config"), cfg.label))
        metrics["sweep"][cfg.label] = {
            m: list(event_recall_from_rows(rows, alerts(col(rows, c), thresholds[m].threshold)))
            for m, c in method_col.items()
        }

    attrs = vessel_attributes(tables)
    clean_rows = preds.filter(pc.equal(preds.column("config"), CLEAN))
    vessel_hours = 0.0
    for r in clean:
        obs = r.observations
        for seg in np.unique(r.segments[r.segments >= 0]):
            idx = np.flatnonzero(r.segments == seg)
            if str(obs.mmsi[idx[0]]) in val:
                vessel_hours += (obs.timestamp_s[idx[-1]] - obs.timestamp_s[idx[0]]) / 3600.0
    starts = [v.timestamp() for v in clean_rows.column("window_start_utc").to_pylist()]
    ends = [v.timestamp() for v in clean_rows.column("window_end_utc").to_pylist()]
    mmsis = clean_rows.column("mmsi").to_pylist()
    cdays = clean_rows.column("day").to_pylist()
    states = clean_rows.column("motion_state").to_pylist()
    for m, c in method_col.items():
        alert = alerts(col(clean_rows, c), thresholds[m].threshold)
        groups: dict[tuple[str, str], list[int]] = defaultdict(list)
        for w in np.flatnonzero(alert):
            groups[(cdays[w], mmsis[w])].append(int(w))
        incidents = sum(
            merge_incidents([starts[w] for w in ws], [ends[w] for w in ws])
            for ws in groups.values()
        )
        by_group: dict[str, int] = defaultdict(int)
        by_state: dict[str, int] = defaultdict(int)
        for w in np.flatnonzero(alert):
            by_group[attrs[mmsis[w]][0]] += 1
            by_state[str(states[w])] += 1
        metrics["clean_false_alarms"][m] = {
            "incidents": incidents,
            "per_1000_vessel_hours": 1000.0 * incidents / vessel_hours
            if vessel_hours
            else math.nan,
            "flagged_windows_by_vessel_group": dict(by_group),
            "flagged_windows_by_motion_state": dict(by_state),
        }
    metrics["dev_val_vessel_hours"] = vessel_hours
    (out / "metrics.json").write_text(
        json.dumps(metrics, indent=2, default=float), encoding="utf-8"
    )

    meta = {
        "experiment_id": EXPERIMENT_ID,
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": git_state(),
        "evaluation_protocol": EVALUATION_PROTOCOL,
        "feature_spec": FEATURE_SPEC_VERSION,
        "inputs": [
            {
                "path": str(p),
                "day": d,
                "file_sha256": sha256_file(p),
                "content_fingerprint_sha256": compute_content_fingerprint(
                    p
                ).content_fingerprint_sha256,
            }
            for p, d in zip(args.input, days, strict=True)
        ],
        "partition_sha256": partition.partition_hash,
        "n_train_vessels": len(partition.train),
        "n_val_vessels": len(partition.val),
        "headline_seeds": list(HEADLINE_SEEDS),
        "sweep_seeds": list(SWEEP_SEEDS),
        "n_tasks": len(tasks),
        "workers": args.workers,
        "r1_calibration_sizes": r1.calibration_sizes(),
        "train_windows": train_windows.num_rows,
        "runtime_seconds": round(time.perf_counter() - started, 1),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pyarrow": pa.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }
    (out / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Done in {meta['runtime_seconds']}s -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
