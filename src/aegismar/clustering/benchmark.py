"""W3-02 comparative benchmark harness: BallTree reference vs. H3 candidate acceleration.

The harness runs four strictly separated phases (see
``docs/03-research/w3-02-benchmark-protocol.md``):

1. **Correctness**: brute-force oracle verification on a small chronological
   prefix, then H3-vs-BallTree parity at every benchmark scale. Exact graph,
   label, and role agreement plus zero fallbacks are required.
2. **Official timed trials**: ``detailed_timing=False`` and
   ``measure_memory=False``, one warm-up per provider and counterbalanced
   paired trials (even trial index: BallTree first; odd: H3 first), with
   ``gc.collect()`` immediately before every provider run.
3. **Peak memory**: one isolated ``tracemalloc`` pass per provider and scale.
4. **Stage diagnostics**: one ``detailed_timing=True`` pass per provider and
   scale, explaining stage-level costs without biasing Phase 2.

Statistics are descriptive. Confidence intervals use exact two-sided 95%
Student-t critical values and describe run-to-run dispersion on one host.
"""

from __future__ import annotations

import gc
import json
import math
import os
import platform
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import adjusted_rand_score

from aegismar import __version__ as aegismar_version
from aegismar.clustering.balltree_neighbors import BallTreeNeighborhoodProvider
from aegismar.clustering.config import (
    SUPPORTED_CALIBRATED_H3_RESOLUTIONS,
    QualityFilterPolicy,
    STDBSCANConfig,
)
from aegismar.clustering.h3_neighbors import H3NeighborhoodProvider, compute_safe_k_ring
from aegismar.clustering.st_dbscan import run_balltree_st_dbscan, run_h3_st_dbscan, run_st_dbscan
from aegismar.clustering.types import (
    ClusteringInputDataset,
    NeighborhoodGraph,
    NeighborhoodProvider,
    STDBSCANResult,
    epoch_us_to_datetime,
    load_clustering_dataset_from_parquet,
)
from aegismar.ingestion.provenance import (
    collect_runtime_provenance,
    compute_content_fingerprint,
    compute_file_sha256,
)
from aegismar.spatial.oracle import DEFAULT_MAX_ORACLE_POINTS, BruteForceNeighborhoodOracle

BENCHMARK_NAME = "w3_02_balltree_vs_h3"
BENCHMARK_SCHEMA_VERSION = "1.0"

BALLTREE = "balltree"
H3 = "h3"

# Scale tiers: chronological prefixes of the filtered dataset; None = full filtered dataset.
DEFAULT_SCALES: tuple[int | None, ...] = (10_000, 50_000, 100_000, None)

TIMING_METRICS: tuple[str, ...] = (
    "build_time_s",
    "query_and_prune_time_s",
    "clustering_time_s",
    "index_and_graph_time_s",
    "total_time_s",
)

# Exact two-sided 95% Student-t critical values t_{0.975, df} for df = 1..30
# (verified against scipy.stats.t.ppf(0.975, df) to 9 decimal places).
T_CRITICAL_95: dict[int, float] = {
    1: 12.706204736,
    2: 4.302652730,
    3: 3.182446305,
    4: 2.776445105,
    5: 2.570581836,
    6: 2.446911851,
    7: 2.364624252,
    8: 2.306004135,
    9: 2.262157163,
    10: 2.228138852,
    11: 2.200985160,
    12: 2.178812830,
    13: 2.160368656,
    14: 2.144786688,
    15: 2.131449546,
    16: 2.119905299,
    17: 2.109815578,
    18: 2.100922040,
    19: 2.093024054,
    20: 2.085963447,
    21: 2.079613845,
    22: 2.073873068,
    23: 2.068657610,
    24: 2.063898562,
    25: 2.059538553,
    26: 2.055529439,
    27: 2.051830516,
    28: 2.048407142,
    29: 2.045229642,
    30: 2.042272456,
}
Z_CRITICAL_95: float = 1.959964

STATISTICAL_INTERPRETATION_NOTE = (
    "Descriptive statistics only. Confidence intervals are two-sided 95% Student-t intervals "
    "over repeated runs on a single host and a single dataset; they describe run-to-run "
    "execution-time dispersion under these conditions and do not claim statistical "
    "significance across hardware, operating systems, datasets, or parameter settings."
)

LogFn = Callable[[str], None]


def _no_log(_message: str) -> None:
    return None


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def t_critical_95(df: int) -> float:
    """Return the two-sided 95% Student-t critical value (normal approximation for df > 30)."""
    if isinstance(df, bool) or not isinstance(df, int) or df < 1:
        raise ValueError(f"degrees of freedom must be an integer >= 1, got {df!r}")
    return T_CRITICAL_95.get(df, Z_CRITICAL_95)


def summarize_series(values: Sequence[float]) -> dict[str, Any]:
    """Descriptive statistics with a two-sided 95% Student-t CI for the mean.

    ``std`` uses ``ddof=1``. ``std`` and CI bounds are ``None`` when ``n == 1``.
    """
    arr = np.asarray(values, dtype=np.float64)
    n = int(arr.size)
    if n == 0:
        raise ValueError("summarize_series requires at least one value")
    if not bool(np.all(np.isfinite(arr))):
        raise ValueError("summarize_series requires finite values")

    mean = float(arr.mean())
    p25, p75 = (float(v) for v in np.percentile(arr, [25.0, 75.0]))
    std: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    if n > 1:
        std = float(arr.std(ddof=1))
        half_width = t_critical_95(n - 1) * std / math.sqrt(n)
        ci_low = mean - half_width
        ci_high = mean + half_width

    return {
        "n": n,
        "mean": mean,
        "median": float(np.median(arr)),
        "std": std,
        "min": float(arr.min()),
        "max": float(arr.max()),
        "iqr_p25": p25,
        "iqr_p75": p75,
        "ci95_low": ci_low,
        "ci95_high": ci_high,
    }


def summarize_paired_comparison(
    balltree_values: Sequence[float],
    h3_values: Sequence[float],
) -> dict[str, Any]:
    """Paired BallTree-vs-H3 comparison on matched trial indices.

    Reports the paired difference ``balltree - h3`` (seconds; positive means H3
    is faster), the per-trial speedup ``balltree / h3`` (> 1 means H3 is faster),
    and the ratio-of-means speedup ``mean(balltree) / mean(h3)``.
    """
    bt = np.asarray(balltree_values, dtype=np.float64)
    h3 = np.asarray(h3_values, dtype=np.float64)
    if bt.shape != h3.shape:
        raise ValueError(f"paired series must have equal length, got {bt.size} and {h3.size}")
    if bt.size == 0:
        raise ValueError("paired comparison requires at least one pair")

    speedup: dict[str, Any] | None = None
    if bool(np.all(h3 > 0.0)):
        speedup = summarize_series((bt / h3).tolist())

    h3_mean = float(h3.mean())
    return {
        "n_pairs": int(bt.size),
        "difference_balltree_minus_h3_s": summarize_series((bt - h3).tolist()),
        "per_trial_speedup_balltree_over_h3": speedup,
        "ratio_of_means_speedup": float(bt.mean()) / h3_mean if h3_mean > 0.0 else None,
    }


def trial_execution_order(trial_index: int) -> tuple[str, str]:
    """Counterbalanced provider order: even trials BallTree first, odd trials H3 first."""
    if isinstance(trial_index, bool) or not isinstance(trial_index, int) or trial_index < 0:
        raise ValueError(f"trial_index must be a non-negative integer, got {trial_index!r}")
    return (BALLTREE, H3) if trial_index % 2 == 0 else (H3, BALLTREE)


def execution_order_label(trial_index: int) -> str:
    """Return ``"balltree_first"`` or ``"h3_first"`` for a trial index."""
    return f"{trial_execution_order(trial_index)[0]}_first"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def scale_label(scale: int | None) -> str:
    """Human-readable scale identifier (``"full"`` for the whole filtered dataset)."""
    return "full" if scale is None else str(scale)


@dataclass(frozen=True, slots=True)
class W302BenchmarkConfig:
    """Locked W3-02 benchmark configuration."""

    dataset_path: Path
    eps_spatial_m: float = 300.0
    eps_temporal_s: float = 900.0
    min_samples: int = 5
    scales: tuple[int | None, ...] = DEFAULT_SCALES
    primary_h3_resolution: int = 8
    sensitivity_h3_resolutions: tuple[int, ...] = (7, 9)
    oracle_max_rows: int = 2_000
    warmup_runs: int = 1
    measured_trials: int = 10
    official_detailed_timing: bool = False
    quality_filter: QualityFilterPolicy = field(default_factory=QualityFilterPolicy)

    def __post_init__(self) -> None:
        if self.official_detailed_timing is not False:
            raise ValueError(
                "official_detailed_timing must be False: official timed trials never run "
                "with per-stage instrumentation (use the separate diagnostics phase)."
            )
        if not self.scales:
            raise ValueError("scales must contain at least one entry")
        numeric = [s for s in self.scales if s is not None]
        for s in numeric:
            if isinstance(s, bool) or not isinstance(s, int) or s < 1:
                raise ValueError(f"scales must be positive integers or None, got {s!r}")
        if len(set(self.scales)) != len(self.scales):
            raise ValueError(f"scales must not contain duplicates, got {self.scales!r}")
        if numeric != sorted(numeric) or (None in self.scales and self.scales[-1] is not None):
            raise ValueError(
                f"scales must be ascending with None (full dataset) last, got {self.scales!r}"
            )

        resolutions = (self.primary_h3_resolution, *self.sensitivity_h3_resolutions)
        for r in resolutions:
            if r not in SUPPORTED_CALIBRATED_H3_RESOLUTIONS:
                raise ValueError(
                    f"H3 resolution {r} is not calibrated "
                    f"(calibrated: {SUPPORTED_CALIBRATED_H3_RESOLUTIONS})"
                )
        if len(set(resolutions)) != len(resolutions):
            raise ValueError(f"H3 resolutions must be distinct, got {resolutions!r}")

        if not (1 <= self.oracle_max_rows <= DEFAULT_MAX_ORACLE_POINTS):
            raise ValueError(
                f"oracle_max_rows must be in [1, {DEFAULT_MAX_ORACLE_POINTS}], "
                f"got {self.oracle_max_rows}"
            )
        if self.warmup_runs < 0:
            raise ValueError(f"warmup_runs must be >= 0, got {self.warmup_runs}")
        if self.measured_trials < 1:
            raise ValueError(f"measured_trials must be >= 1, got {self.measured_trials}")

        # Validates eps/min_samples and confirms every resolution is inside the calibrated table
        self.clustering_config()
        for r in resolutions:
            compute_safe_k_ring(r, float(self.eps_spatial_m))

    @property
    def all_h3_resolutions(self) -> tuple[int, ...]:
        """Primary resolution followed by sensitivity resolutions."""
        return (self.primary_h3_resolution, *self.sensitivity_h3_resolutions)

    def clustering_config(self) -> STDBSCANConfig:
        """ST-DBSCAN configuration shared by every provider."""
        return STDBSCANConfig(
            eps_spatial_m=float(self.eps_spatial_m),
            eps_temporal_s=float(self.eps_temporal_s),
            min_samples=self.min_samples,
            quality_filter=self.quality_filter,
        )

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable configuration, including fixed official-trial settings."""
        return {
            "dataset_path": str(self.dataset_path),
            "eps_spatial_m": float(self.eps_spatial_m),
            "eps_temporal_s": float(self.eps_temporal_s),
            "min_samples": self.min_samples,
            "scales": [scale_label(s) for s in self.scales],
            "primary_h3_resolution": self.primary_h3_resolution,
            "sensitivity_h3_resolutions": list(self.sensitivity_h3_resolutions),
            "h3_k_rings": {
                str(r): compute_safe_k_ring(r, float(self.eps_spatial_m))
                for r in self.all_h3_resolutions
            },
            "oracle_max_rows": self.oracle_max_rows,
            "warmup_runs": self.warmup_runs,
            "measured_trials": self.measured_trials,
            "quality_filter": self.quality_filter.to_dict(),
            "clustering_config": self.clustering_config().to_dict(),
            "official_trial_settings": {
                "detailed_timing": False,
                "measure_memory": False,
                "timer": "time.perf_counter",
                "gc_collect_before_each_provider_run": True,
                "gc_enabled_during_timing": True,
                "counterbalancing": "even trial index: balltree_first; odd: h3_first",
                "warmup_order": "balltree then h3, excluded from statistics",
            },
            "memory_pass_settings": {
                "measure_memory": True,
                "detailed_timing": False,
                "method": "tracemalloc peak (Python-tracked allocations only)",
                "psutil_rss_measured": False,
            },
            "diagnostics_pass_settings": {"detailed_timing": True, "measure_memory": False},
        }


# ---------------------------------------------------------------------------
# Datasets, providers, and graph/cluster comparison
# ---------------------------------------------------------------------------


def load_benchmark_dataset(
    config: W302BenchmarkConfig, max_rows: int | None
) -> ClusteringInputDataset:
    """Load the quality-filtered, canonically sorted chronological prefix."""
    return load_clustering_dataset_from_parquet(
        config.dataset_path,
        quality_filter=config.quality_filter,
        max_rows=max_rows,
    )


def subset_provenance(dataset: ClusteringInputDataset, requested: int | None) -> dict[str, Any]:
    """Row count, time span, and vessel count of a benchmark subset."""
    n = dataset.num_points
    min_ts = max_ts = None
    if n > 0:
        min_ts = epoch_us_to_datetime(int(dataset.timestamps_us.min())).isoformat()
        max_ts = epoch_us_to_datetime(int(dataset.timestamps_us.max())).isoformat()
    return {
        "scale_label": scale_label(requested),
        "requested_rows": requested,
        "row_count": n,
        "capped_by_dataset_size": requested is not None and n < requested,
        "min_timestamp_utc": min_ts,
        "max_timestamp_utc": max_ts,
        "unique_vessels": len(set(dataset.mmsis)),
    }


def verify_nested_prefixes(datasets: Sequence[ClusteringInputDataset]) -> bool:
    """True if each dataset equals the leading rows of the next (larger) dataset."""
    for small, large in zip(datasets, datasets[1:], strict=False):
        n = small.num_points
        if n > large.num_points:
            return False
        if not (
            np.array_equal(small.source_rows, large.source_rows[:n])
            and np.array_equal(small.timestamps_us, large.timestamps_us[:n])
            and np.array_equal(small.latitudes_deg, large.latitudes_deg[:n])
            and np.array_equal(small.longitudes_deg, large.longitudes_deg[:n])
            and small.mmsis == large.mmsis[:n]
        ):
            return False
    return True


def make_provider(
    kind: str,
    dataset: ClusteringInputDataset,
    config: STDBSCANConfig,
    resolution: int | None = None,
    detailed_timing: bool = False,
) -> BallTreeNeighborhoodProvider | H3NeighborhoodProvider:
    """Construct a BallTree or H3 provider (index build happens in the constructor)."""
    if kind == BALLTREE:
        return BallTreeNeighborhoodProvider(dataset, config, detailed_timing=detailed_timing)
    if kind == H3:
        if resolution is None:
            raise ValueError("H3 provider requires a resolution")
        return H3NeighborhoodProvider(
            dataset, config, resolution=resolution, detailed_timing=detailed_timing
        )
    raise ValueError(f"unknown provider kind {kind!r}")


class _PrecomputedGraphProvider:
    """Adapter returning an already-built graph so correctness checks cluster it once."""

    def __init__(self, name: str, graph: NeighborhoodGraph, build_time_s: float) -> None:
        self._name = name
        self._graph = graph
        self._build_time_s = build_time_s

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def num_points(self) -> int:
        return self._graph.num_points

    @property
    def build_time_seconds(self) -> float:
        return self._build_time_s

    def query_neighbors(self, index: int) -> NDArray[np.int64]:
        return self._graph.neighbors_of(index)

    def build_neighborhood_graph(self) -> NeighborhoodGraph:
        return self._graph


def undirected_edge_count(graph: NeighborhoodGraph) -> int:
    """Count neighbor pairs ``(i, j)`` with ``i < j`` (excludes self-entries)."""
    rows = np.repeat(np.arange(graph.num_points, dtype=np.int64), np.diff(graph.indptr))
    return int(np.count_nonzero(graph.indices > rows))


def compare_neighborhood_graphs(
    reference: NeighborhoodGraph, candidate: NeighborhoodGraph
) -> dict[str, Any]:
    """Exact neighbor recall/precision and edge-count agreement against a reference graph."""
    if reference.num_points != candidate.num_points:
        raise ValueError(
            f"graph sizes differ: reference={reference.num_points}, "
            f"candidate={candidate.num_points}"
        )
    exact = bool(
        np.array_equal(reference.indptr, candidate.indptr)
        and np.array_equal(reference.indices, candidate.indices)
    )
    total_ref = reference.total_edges
    total_cand = candidate.total_edges
    if exact:
        matched, missing, extra = total_ref, 0, 0
    else:
        matched = missing = extra = 0
        for i in range(reference.num_points):
            ref_set = set(reference.neighbors_of(i).tolist())
            cand_set = set(candidate.neighbors_of(i).tolist())
            matched += len(ref_set & cand_set)
            missing += len(ref_set - cand_set)
            extra += len(cand_set - ref_set)

    ref_undirected = undirected_edge_count(reference)
    cand_undirected = undirected_edge_count(candidate)
    return {
        "exact_graph_match": exact,
        "neighbor_recall": 1.0 if total_ref == 0 else matched / total_ref,
        "neighbor_precision": 1.0 if total_cand == 0 else matched / total_cand,
        "missing_neighbor_count": missing,
        "extra_neighbor_count": extra,
        "reference_directed_edges": total_ref,
        "candidate_directed_edges": total_cand,
        "directed_edge_count_match": total_ref == total_cand,
        "reference_undirected_edges": ref_undirected,
        "candidate_undirected_edges": cand_undirected,
        "undirected_edge_count_match": ref_undirected == cand_undirected,
    }


def clustering_counts(result: STDBSCANResult) -> dict[str, int]:
    """Cluster, core, border, and noise counts of a clustering result."""
    return {
        "num_clusters": result.num_clusters,
        "core_count": result.core_count,
        "border_count": result.border_count,
        "noise_count": result.noise_count,
    }


def compare_clusterings(reference: STDBSCANResult, candidate: STDBSCANResult) -> dict[str, Any]:
    """Adjusted Rand Index plus exact label/role/count agreement."""
    ref_labels = reference.labels
    cand_labels = candidate.labels
    if ref_labels.size == 0 and cand_labels.size == 0:
        ari = 1.0
    else:
        ari = float(adjusted_rand_score(ref_labels, cand_labels))
    ref_counts = clustering_counts(reference)
    cand_counts = clustering_counts(candidate)
    return {
        "adjusted_rand_index": ari,
        "labels_identical": bool(np.array_equal(ref_labels, cand_labels)),
        "roles_identical": reference.roles == candidate.roles,
        "reference_counts": ref_counts,
        "candidate_counts": cand_counts,
        "counts_match": ref_counts == cand_counts,
    }


def _build_and_cluster(
    provider: NeighborhoodProvider,
    dataset: ClusteringInputDataset,
    config: STDBSCANConfig,
) -> tuple[NeighborhoodGraph, STDBSCANResult]:
    graph = provider.build_neighborhood_graph()
    adapter = _PrecomputedGraphProvider(provider.provider_name, graph, provider.build_time_seconds)
    return graph, run_st_dbscan(dataset, config, adapter)


def _parity_entry(
    candidate_label: str,
    graph_cmp: dict[str, Any],
    cluster_cmp: dict[str, Any],
    fallback_count: int | None,
) -> dict[str, Any]:
    passed = bool(
        graph_cmp["exact_graph_match"]
        and graph_cmp["neighbor_recall"] == 1.0
        and graph_cmp["neighbor_precision"] == 1.0
        and graph_cmp["directed_edge_count_match"]
        and graph_cmp["undirected_edge_count_match"]
        and cluster_cmp["adjusted_rand_index"] == 1.0
        and cluster_cmp["labels_identical"]
        and cluster_cmp["roles_identical"]
        and cluster_cmp["counts_match"]
        and (fallback_count is None or fallback_count == 0)
    )
    return {
        "candidate": candidate_label,
        **graph_cmp,
        **cluster_cmp,
        "h3_fallback_count": fallback_count,
        "passed": passed,
    }


def _h3_label(resolution: int) -> str:
    return f"h3_r{resolution}"


# ---------------------------------------------------------------------------
# Phase 1: correctness
# ---------------------------------------------------------------------------


def run_correctness_phase(
    config: W302BenchmarkConfig,
    datasets: Sequence[tuple[int | None, ClusteringInputDataset]],
    log: LogFn = _no_log,
) -> dict[str, Any]:
    """Oracle verification on a small prefix and H3-vs-BallTree parity at every scale."""
    cfg = config.clustering_config()

    # 1a. Brute-force oracle on the deterministic chronological prefix
    oracle_ds = load_benchmark_dataset(config, config.oracle_max_rows)
    log(f"[phase 1] oracle verification on {oracle_ds.num_points} rows")
    oracle = BruteForceNeighborhoodOracle(oracle_ds, cfg, max_points=DEFAULT_MAX_ORACLE_POINTS)
    oracle_graph, oracle_result = _build_and_cluster(oracle, oracle_ds, cfg)

    oracle_entries: list[dict[str, Any]] = []
    candidates: list[tuple[str, str, int | None]] = [(BALLTREE, BALLTREE, None)]
    candidates += [(_h3_label(r), H3, r) for r in config.all_h3_resolutions]
    for label, kind, resolution in candidates:
        provider = make_provider(kind, oracle_ds, cfg, resolution)
        graph, result = _build_and_cluster(provider, oracle_ds, cfg)
        fallback = (
            provider.get_metrics()["fallback_count"]
            if isinstance(provider, H3NeighborhoodProvider)
            else None
        )
        oracle_entries.append(
            _parity_entry(
                label,
                compare_neighborhood_graphs(oracle_graph, graph),
                compare_clusterings(oracle_result, result),
                fallback,
            )
        )

    # 1b. H3 vs BallTree parity at every benchmark scale
    scale_entries: list[dict[str, Any]] = []
    reference_counts: dict[str, dict[str, int]] = {}
    for requested, ds in datasets:
        label_s = scale_label(requested)
        log(f"[phase 1] scale parity {label_s} ({ds.num_points} rows)")
        bt_graph, bt_result = _build_and_cluster(make_provider(BALLTREE, ds, cfg), ds, cfg)
        reference_counts[label_s] = clustering_counts(bt_result)
        comparisons: list[dict[str, Any]] = []
        for r in config.all_h3_resolutions:
            h3_provider = make_provider(H3, ds, cfg, r)
            h3_graph, h3_result = _build_and_cluster(h3_provider, ds, cfg)
            comparisons.append(
                _parity_entry(
                    _h3_label(r),
                    compare_neighborhood_graphs(bt_graph, h3_graph),
                    compare_clusterings(bt_result, h3_result),
                    int(h3_provider.get_metrics()["fallback_count"]),
                )
            )
        scale_entries.append(
            {
                "scale_label": label_s,
                "row_count": ds.num_points,
                "reference": BALLTREE,
                "reference_counts": reference_counts[label_s],
                "comparisons": comparisons,
            }
        )

    all_passed = all(e["passed"] for e in oracle_entries) and all(
        c["passed"] for s in scale_entries for c in s["comparisons"]
    )
    return {
        "oracle_verification": {
            "row_count": oracle_ds.num_points,
            "reference": "brute_force_oracle",
            "oracle_counts": clustering_counts(oracle_result),
            "comparisons": oracle_entries,
        },
        "scale_parity": scale_entries,
        "reference_counts_by_scale": reference_counts,
        "all_parity_checks_passed": all_passed,
    }


# ---------------------------------------------------------------------------
# Phase 2: official timed trials
# ---------------------------------------------------------------------------


def timed_provider_run(
    kind: str,
    dataset: ClusteringInputDataset,
    config: STDBSCANConfig,
    resolution: int | None = None,
) -> dict[str, Any]:
    """One official timed run (``detailed_timing=False``, ``measure_memory=False``)."""
    gc.collect()
    provider = make_provider(kind, dataset, config, resolution, detailed_timing=False)
    result = run_st_dbscan(dataset, config, provider, measure_memory=False)
    metrics = provider.get_metrics()
    build = float(result.build_time_seconds)
    query = float(result.query_time_seconds)
    clustering = float(result.clustering_time_seconds)
    record: dict[str, Any] = {
        "provider": kind if resolution is None else _h3_label(resolution),
        "build_time_s": build,
        "query_and_prune_time_s": query,
        "clustering_time_s": clustering,
        "index_and_graph_time_s": build + query,
        "total_time_s": build + query + clustering,
        "detailed_timing": bool(metrics["detailed_timing"]),
        "fallback_count": int(metrics["fallback_count"]) if kind == H3 else None,
        **clustering_counts(result),
    }
    return record


def _paired_block_scale(
    dataset: ClusteringInputDataset,
    config: W302BenchmarkConfig,
    resolution: int,
    reference_counts: dict[str, int] | None,
    log: LogFn = _no_log,
    log_prefix: str = "[phase 2]",
) -> dict[str, Any]:
    cfg = config.clustering_config()

    def run(kind: str) -> dict[str, Any]:
        return timed_provider_run(kind, dataset, cfg, resolution if kind == H3 else None)

    for _ in range(config.warmup_runs):
        run(BALLTREE)
        run(H3)
    log(f"{log_prefix} warm-up complete")

    trials: list[dict[str, Any]] = []
    n_trials = config.measured_trials
    for t in range(n_trials):
        records = {kind: run(kind) for kind in trial_execution_order(t)}
        trials.append(
            {
                "trial_index": t,
                "execution_order": execution_order_label(t),
                BALLTREE: records[BALLTREE],
                H3: records[H3],
            }
        )
        # Progress only: emitted after both timed provider runs of this trial have
        # returned and before the next trial's gc.collect(), so it is outside every
        # timed region and does not affect any recorded timing.
        log(
            f"{log_prefix} trial {t + 1}/{n_trials} complete "
            f"({execution_order_label(t)}; total balltree "
            f"{records[BALLTREE]['total_time_s']:.3f} s, h3 {records[H3]['total_time_s']:.3f} s)"
        )

    instrumentation_ok = all(not tr[k]["detailed_timing"] for tr in trials for k in (BALLTREE, H3))
    fallback_free = all(tr[H3]["fallback_count"] == 0 for tr in trials)
    count_keys = ("num_clusters", "core_count", "border_count", "noise_count")
    consistent = reference_counts is not None and all(
        {k: tr[p][k] for k in count_keys} == reference_counts
        for tr in trials
        for p in (BALLTREE, H3)
    )

    summary = {
        p: {m: summarize_series([tr[p][m] for tr in trials]) for m in TIMING_METRICS}
        for p in (BALLTREE, H3)
    }
    paired = {
        m: summarize_paired_comparison(
            [tr[BALLTREE][m] for tr in trials], [tr[H3][m] for tr in trials]
        )
        for m in TIMING_METRICS
    }
    return {
        "row_count": dataset.num_points,
        "warmup_runs_per_provider": config.warmup_runs,
        "measured_trials": config.measured_trials,
        "all_trials_detailed_timing_false": instrumentation_ok,
        "all_trials_fallback_free": fallback_free,
        "results_consistent_with_phase_1": consistent,
        "trials": trials,
        "summary": summary,
        "paired_comparison": paired,
    }


def run_timed_phase(
    config: W302BenchmarkConfig,
    datasets: Sequence[tuple[int | None, ClusteringInputDataset]],
    reference_counts: dict[str, dict[str, int]],
    log: LogFn = _no_log,
) -> dict[str, Any]:
    """Primary (BallTree vs. H3 primary) and sensitivity blocks across all scales."""
    blocks: list[dict[str, Any]] = []
    for role, resolution in [("primary", config.primary_h3_resolution)] + [
        ("sensitivity", r) for r in config.sensitivity_h3_resolutions
    ]:
        scales_out: list[dict[str, Any]] = []
        for requested, ds in datasets:
            label_s = scale_label(requested)
            log(
                f"[phase 2] {role} block balltree vs {_h3_label(resolution)} @ {label_s} "
                f"({ds.num_points} rows, {config.warmup_runs} warm-up + "
                f"{config.measured_trials} trials)"
            )
            entry = _paired_block_scale(
                ds,
                config,
                resolution,
                reference_counts.get(label_s),
                log=log,
                log_prefix=f"[phase 2] {role} {_h3_label(resolution)} @ {label_s}",
            )
            scales_out.append({"scale_label": label_s, **entry})
        blocks.append(
            {
                "block": f"{role}_{_h3_label(resolution)}",
                "role": role,
                "h3_resolution": resolution,
                "h3_k_ring": compute_safe_k_ring(resolution, float(config.eps_spatial_m)),
                "scales": scales_out,
            }
        )

    all_ok = all(
        s["all_trials_detailed_timing_false"]
        and s["all_trials_fallback_free"]
        and s["results_consistent_with_phase_1"]
        for b in blocks
        for s in b["scales"]
    )
    return {
        "metrics": list(TIMING_METRICS),
        "metric_definitions": {
            "build_time_s": "provider constructor index build (provider.build_time_seconds)",
            "query_and_prune_time_s": "wall time of build_neighborhood_graph() "
            "(candidate retrieval + temporal + exact distance filtering)",
            "clustering_time_s": "core-first ST-DBSCAN labeling on the built graph",
            "index_and_graph_time_s": "build_time_s + query_and_prune_time_s",
            "total_time_s": "build_time_s + query_and_prune_time_s + clustering_time_s",
        },
        "blocks": blocks,
        "all_trial_integrity_checks_passed": all_ok,
        "statistical_interpretation_note": STATISTICAL_INTERPRETATION_NOTE,
    }


# ---------------------------------------------------------------------------
# Phase 3: peak memory, Phase 4: stage diagnostics
# ---------------------------------------------------------------------------


def run_memory_phase(
    config: W302BenchmarkConfig,
    datasets: Sequence[tuple[int | None, ClusteringInputDataset]],
    log: LogFn = _no_log,
) -> dict[str, Any]:
    """One isolated tracemalloc pass per provider and scale (``detailed_timing=False``)."""
    cfg = config.clustering_config()
    scales_out: list[dict[str, Any]] = []
    for requested, ds in datasets:
        log(f"[phase 3] peak memory @ {scale_label(requested)}")
        runs: list[dict[str, Any]] = []
        targets: list[tuple[str, int | None]] = [(BALLTREE, None)]
        targets += [(H3, r) for r in sorted(config.all_h3_resolutions)]
        for kind, resolution in targets:
            gc.collect()
            if kind == BALLTREE:
                result = run_balltree_st_dbscan(ds, cfg, measure_memory=True)
            else:
                result = run_h3_st_dbscan(ds, cfg, resolution=resolution, measure_memory=True)
            peak = int(result.peak_tracemalloc_bytes)
            runs.append(
                {
                    "provider": kind if resolution is None else _h3_label(resolution),
                    "peak_tracemalloc_bytes": peak,
                    "peak_tracemalloc_mib": peak / (1024 * 1024),
                    "detailed_timing": False,
                }
            )
        scales_out.append(
            {"scale_label": scale_label(requested), "row_count": ds.num_points, "runs": runs}
        )
    return {
        "method": "tracemalloc peak over index build + graph + clustering, one pass per provider",
        "note": (
            "tracemalloc measures Python-tracked allocations (including NumPy buffers); "
            "allocations made inside native libraries that bypass the Python allocator are "
            "not captured. psutil RSS is not measured because psutil is not a project "
            "dependency. Memory passes are never mixed with timed trials."
        ),
        "psutil_rss_measured": False,
        "scales": scales_out,
    }


_DIAGNOSTIC_KEYS: tuple[str, ...] = (
    "build_time_s",
    "cell_mapping_time_s",
    "candidate_precomputation_time_s",
    "candidate_retrieval_time_s",
    "temporal_filtering_time_s",
    "distance_filtering_time_s",
    "candidates_evaluated",
    "fallback_count",
    "unique_occupied_cells",
    "h3_k_ring",
)


def run_diagnostics_phase(
    config: W302BenchmarkConfig,
    datasets: Sequence[tuple[int | None, ClusteringInputDataset]],
    log: LogFn = _no_log,
) -> dict[str, Any]:
    """One ``detailed_timing=True`` pass per provider and scale (stage breakdown)."""
    cfg = config.clustering_config()
    scales_out: list[dict[str, Any]] = []
    for requested, ds in datasets:
        log(f"[phase 4] stage diagnostics @ {scale_label(requested)}")
        runs: list[dict[str, Any]] = []
        targets: list[tuple[str, int | None]] = [(BALLTREE, None)]
        targets += [(H3, r) for r in sorted(config.all_h3_resolutions)]
        for kind, resolution in targets:
            gc.collect()
            provider = make_provider(kind, ds, cfg, resolution, detailed_timing=True)
            result = run_st_dbscan(ds, cfg, provider, measure_memory=False)
            metrics = provider.get_metrics()
            runs.append(
                {
                    "provider": kind if resolution is None else _h3_label(resolution),
                    "detailed_timing": bool(metrics["detailed_timing"]),
                    "instrumented_query_and_prune_time_s": float(result.query_time_seconds),
                    "clustering_time_s": float(result.clustering_time_seconds),
                    **{k: metrics[k] for k in _DIAGNOSTIC_KEYS if k in metrics},
                }
            )
        scales_out.append(
            {"scale_label": scale_label(requested), "row_count": ds.num_points, "runs": runs}
        )
    return {
        "note": (
            "Instrumented runs explain stage-level costs. Per-stage timers add overhead, so "
            "these timings are not comparable with Phase 2 official timings."
        ),
        "scales": scales_out,
    }


# ---------------------------------------------------------------------------
# Provenance and orchestration
# ---------------------------------------------------------------------------


def _pkg_version(name: str) -> str | None:
    try:
        return package_version(name)
    except PackageNotFoundError:
        return None


def collect_dataset_provenance(
    config: W302BenchmarkConfig, full_dataset: ClusteringInputDataset
) -> dict[str, Any]:
    """File hash, logical fingerprint, filtering accounting, and sibling manifest record."""
    path = Path(config.dataset_path)
    file_sha = compute_file_sha256(path)
    fingerprint = compute_content_fingerprint(path)

    manifest_record: dict[str, Any] | None = None
    manifest_path = path.parent / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_record = {
            "manifest_path": str(manifest_path.resolve()),
            "source_sha256": manifest.get("source_sha256"),
            "git_commit_sha": manifest.get("git_commit_sha"),
            "git_dirty": manifest.get("git_dirty"),
            "output_parquet_sha256": manifest.get("output_parquet_sha256"),
            "content_fingerprint_sha256": manifest.get("content_fingerprint_sha256"),
            "output_parquet_sha256_matches_file": manifest.get("output_parquet_sha256") == file_sha,
            "content_fingerprint_matches_file": manifest.get("content_fingerprint_sha256")
            == fingerprint.content_fingerprint_sha256,
        }

    return {
        "dataset": {
            "path": str(path.resolve()),
            "file_sha256": file_sha,
            "content_fingerprint_sha256": fingerprint.content_fingerprint_sha256,
            "content_fingerprint_version": fingerprint.content_fingerprint_version,
            "canonical_order_verified": fingerprint.canonical_order_verified,
            "parquet_row_count": fingerprint.row_count,
            "filtered_row_count": full_dataset.num_points,
            "excluded_row_count": full_dataset.excluded_count,
            "excluded_breakdown": dict(full_dataset.excluded_breakdown),
        },
        "dataset_manifest_provenance": manifest_record,
    }


def collect_environment_provenance() -> dict[str, Any]:
    """Runtime, library versions, and host description."""
    return {
        "runtime": asdict(collect_runtime_provenance()),
        "aegismar_version": aegismar_version,
        "library_versions": {
            "numpy": np.__version__,
            "scikit-learn": _pkg_version("scikit-learn"),
            "h3": _pkg_version("h3"),
            "pyarrow": _pkg_version("pyarrow"),
        },
        "platform": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "python_implementation": platform.python_implementation(),
        },
    }


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def run_w3_02_benchmark(config: W302BenchmarkConfig, log: LogFn = _no_log) -> dict[str, Any]:
    """Run all four W3-02 phases and return a JSON-serializable result record.

    If any Phase 1 parity check fails, Phases 2-4 are skipped and ``status`` is
    ``"parity_failed"``.
    """
    started_at = _utc_now()
    t_start = time.perf_counter()

    log(f"[setup] loading {config.dataset_path}")
    full = load_benchmark_dataset(config, None)
    datasets: list[tuple[int | None, ClusteringInputDataset]] = [
        (s, full if s is None else load_benchmark_dataset(config, s)) for s in config.scales
    ]
    nested_ok = verify_nested_prefixes([ds for _, ds in datasets])

    log("[setup] computing dataset provenance")
    provenance = collect_dataset_provenance(config, full)
    provenance["environment"] = collect_environment_provenance()

    correctness = run_correctness_phase(config, datasets, log)
    results: dict[str, Any] = {
        "benchmark": BENCHMARK_NAME,
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "status": "completed",
        "started_at_utc": started_at,
        "statistical_interpretation_note": STATISTICAL_INTERPRETATION_NOTE,
        "config": config.to_dict(),
        "provenance": provenance,
        "scales": [subset_provenance(ds, s) for s, ds in datasets],
        "nested_prefix_verified": nested_ok,
        "phase_1_correctness": correctness,
        "phase_2_timed_trials": None,
        "phase_3_peak_memory": None,
        "phase_4_stage_diagnostics": None,
    }

    if not correctness["all_parity_checks_passed"] or not nested_ok:
        results["status"] = "parity_failed"
        log("[abort] correctness/prefix checks failed; timing phases skipped")
    else:
        results["phase_2_timed_trials"] = run_timed_phase(
            config, datasets, correctness["reference_counts_by_scale"], log
        )
        results["phase_3_peak_memory"] = run_memory_phase(config, datasets, log)
        results["phase_4_stage_diagnostics"] = run_diagnostics_phase(config, datasets, log)
        if not results["phase_2_timed_trials"]["all_trial_integrity_checks_passed"]:
            results["status"] = "trial_integrity_failed"

    results["finished_at_utc"] = _utc_now()
    results["total_wall_time_s"] = time.perf_counter() - t_start
    log(f"[done] status={results['status']} in {results['total_wall_time_s']:.1f} s")
    return results
