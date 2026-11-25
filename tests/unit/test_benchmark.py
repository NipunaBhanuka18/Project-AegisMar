"""Unit tests for the W3-02 benchmark harness and provider ``detailed_timing`` toggle."""

from __future__ import annotations

import importlib.util
import json
import math
import random
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pytest

import aegismar.clustering.benchmark as bench
from aegismar.clustering.balltree_neighbors import BallTreeNeighborhoodProvider
from aegismar.clustering.benchmark import (
    STATISTICAL_INTERPRETATION_NOTE,
    T_CRITICAL_95,
    Z_CRITICAL_95,
    W302BenchmarkConfig,
    compare_neighborhood_graphs,
    execution_order_label,
    run_w3_02_benchmark,
    summarize_paired_comparison,
    summarize_series,
    t_critical_95,
    trial_execution_order,
    undirected_edge_count,
    verify_nested_prefixes,
)
from aegismar.clustering.config import STDBSCANConfig
from aegismar.clustering.h3_neighbors import H3NeighborhoodProvider
from aegismar.clustering.st_dbscan import run_balltree_st_dbscan, run_h3_st_dbscan, run_st_dbscan
from aegismar.clustering.types import (
    ClusteringInputDataset,
    NeighborhoodGraph,
    ObservationRecord,
    build_clustering_dataset,
)
from aegismar.ingestion.pipeline import run_ingestion_pipeline
from aegismar.ingestion.provenance import compute_content_fingerprint, compute_file_sha256

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO_ROOT / "experiments" / "clustering" / "w3_02_benchmark.py"
BASE_TIME = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

STAGE_TIMERS = (
    "candidate_retrieval_time_s",
    "temporal_filtering_time_s",
    "distance_filtering_time_s",
)
H3_ONLY_TIMERS = ("cell_mapping_time_s", "candidate_precomputation_time_s")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _synthetic_dataset(seed: int = 7, n_per_anchor: int = 25) -> ClusteringInputDataset:
    """Dense anchorages, a transiting vessel, and isolated pings near San Pedro Bay."""
    rng = random.Random(seed)
    anchors = [(33.7200, -118.2600), (33.7215, -118.2580), (33.7450, -118.2100)]
    records: list[ObservationRecord] = []
    row = 1
    for a_idx, (lat0, lon0) in enumerate(anchors):
        for k in range(n_per_anchor):
            records.append(
                ObservationRecord(
                    source_row=row,
                    mmsi=f"36600000{a_idx}",
                    timestamp_utc=BASE_TIME + timedelta(seconds=60 * k + rng.randint(0, 30)),
                    latitude=lat0 + rng.uniform(-0.0012, 0.0012),
                    longitude=lon0 + rng.uniform(-0.0012, 0.0012),
                )
            )
            row += 1
    for k in range(15):  # transiting vessel ~1.5 km per minute
        records.append(
            ObservationRecord(
                row, "367000001", BASE_TIME + timedelta(seconds=60 * k), 33.70, -118.30 + 0.016 * k
            )
        )
        row += 1
    return build_clustering_dataset(records)


def _graph_equal(a: NeighborhoodGraph, b: NeighborhoodGraph) -> bool:
    return bool(np.array_equal(a.indptr, b.indptr) and np.array_equal(a.indices, b.indices))


def _write_synthetic_csv(path: Path) -> Path:
    """40 usable rows (4 vessels) plus one same-timestamp position conflict pair."""
    lines = ["mmsi,base_date_time,latitude,longitude,sog,cog,heading,status"]
    t0 = datetime(2025, 1, 1, 0, 0, 0)
    anchors = {
        "366000001": (33.7200, -118.2600),
        "366000002": (33.7210, -118.2590),
        "366000003": (33.7450, -118.2100),
    }
    for mmsi, (lat, lon) in anchors.items():
        for k in range(10):
            ts = (t0 + timedelta(seconds=60 * k)).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"{mmsi},{ts},{lat + 0.0001 * k:.5f},{lon + 0.0001 * k:.5f},0.1,0,0,1")
    for k in range(10):
        ts = (t0 + timedelta(seconds=60 * k)).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"367000001,{ts},33.70000,{-118.30 + 0.02 * k:.5f},20.0,90,90,0")
    conflict_ts = (t0 + timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"368000001,{conflict_ts},33.80000,-118.40000,1.0,0,0,0")
    lines.append(f"368000001,{conflict_ts},33.85000,-118.45000,1.0,0,0,0")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture()
def synthetic_parquet(tmp_path: Path) -> Path:
    csv_path = _write_synthetic_csv(tmp_path / "synthetic.csv")
    manifest = run_ingestion_pipeline(csv_path, tmp_path / "dataset")
    return Path(manifest.output_parquet_path)


def _load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("w3_02_benchmark_runner", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# detailed_timing toggle: invariance and metrics
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("min_samples", [2, 5])
def test_balltree_detailed_timing_behavioral_invariance(min_samples: int) -> None:
    ds = _synthetic_dataset()
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=min_samples)
    fast = BallTreeNeighborhoodProvider(ds, cfg, query_batch_size=16, detailed_timing=False)
    timed = BallTreeNeighborhoodProvider(ds, cfg, query_batch_size=16, detailed_timing=True)
    g_fast = fast.build_neighborhood_graph()
    g_timed = timed.build_neighborhood_graph()
    assert _graph_equal(g_fast, g_timed)
    assert g_fast.total_edges == g_timed.total_edges > ds.num_points

    for i in range(ds.num_points):
        np.testing.assert_array_equal(fast.query_neighbors(i), timed.query_neighbors(i))

    r_fast = run_balltree_st_dbscan(ds, cfg, detailed_timing=False)
    r_timed = run_balltree_st_dbscan(ds, cfg, detailed_timing=True)
    np.testing.assert_array_equal(r_fast.labels, r_timed.labels)
    assert r_fast.roles == r_timed.roles
    assert (r_fast.num_clusters, r_fast.core_count, r_fast.border_count, r_fast.noise_count) == (
        r_timed.num_clusters,
        r_timed.core_count,
        r_timed.border_count,
        r_timed.noise_count,
    )
    if min_samples == 2:
        assert r_fast.num_clusters >= 2


@pytest.mark.parametrize("resolution", [7, 8, 9])
def test_h3_detailed_timing_behavioral_invariance(resolution: int) -> None:
    ds = _synthetic_dataset()
    cfg = STDBSCANConfig(eps_spatial_m=300.0, eps_temporal_s=900.0, min_samples=3)
    fast = H3NeighborhoodProvider(ds, cfg, resolution=resolution, detailed_timing=False)
    timed = H3NeighborhoodProvider(ds, cfg, resolution=resolution, detailed_timing=True)
    g_fast = fast.build_neighborhood_graph()
    g_timed = timed.build_neighborhood_graph()
    assert _graph_equal(g_fast, g_timed)
    assert _graph_equal(g_fast, BallTreeNeighborhoodProvider(ds, cfg).build_neighborhood_graph())
    for i in range(ds.num_points):
        np.testing.assert_array_equal(fast.query_neighbors(i), timed.query_neighbors(i))

    r_fast = run_h3_st_dbscan(ds, cfg, resolution=resolution, detailed_timing=False)
    r_timed = run_h3_st_dbscan(ds, cfg, resolution=resolution, detailed_timing=True)
    np.testing.assert_array_equal(r_fast.labels, r_timed.labels)
    assert r_fast.roles == r_timed.roles
    assert r_fast.provider_metrics["fallback_count"] == 0
    assert r_timed.provider_metrics["fallback_count"] == 0


def test_h3_detailed_timing_fallback_invariance() -> None:
    """Fallback routing and counts are identical with and without stage timers."""
    ds = _synthetic_dataset(n_per_anchor=6)
    cfg = STDBSCANConfig(eps_spatial_m=3000.0, min_samples=2)  # beyond res-9 calibrated table
    fast = H3NeighborhoodProvider(ds, cfg, resolution=9, detailed_timing=False)
    timed = H3NeighborhoodProvider(ds, cfg, resolution=9, detailed_timing=True)
    assert _graph_equal(fast.build_neighborhood_graph(), timed.build_neighborhood_graph())
    m_fast, m_timed = fast.get_metrics(), timed.get_metrics()
    assert m_fast["fallback_count"] == m_timed["fallback_count"] == ds.num_points
    assert m_fast["fallback_reasons"] == m_timed["fallback_reasons"]
    assert m_fast["fallback_time_seconds"] is None
    assert m_timed["fallback_time_seconds"] is not None


def test_balltree_metrics_toggle() -> None:
    ds = _synthetic_dataset()
    cfg = STDBSCANConfig(min_samples=3)

    fast = BallTreeNeighborhoodProvider(ds, cfg)
    assert fast.detailed_timing is False
    fast.build_neighborhood_graph()
    m = fast.get_metrics()
    assert m["provider"] == "balltree"
    assert m["detailed_timing"] is False
    assert m["build_time_s"] >= 0.0
    assert all(m[k] is None for k in STAGE_TIMERS)
    assert m["candidates_evaluated"] is None

    timed = BallTreeNeighborhoodProvider(ds, cfg, detailed_timing=True)
    graph = timed.build_neighborhood_graph()
    mt = timed.get_metrics()
    assert mt["detailed_timing"] is True
    assert all(isinstance(mt[k], float) and mt[k] >= 0.0 for k in STAGE_TIMERS)
    assert sum(mt[k] for k in STAGE_TIMERS) > 0.0
    assert mt["candidates_evaluated"] >= graph.total_edges

    # Runner surfaces BallTree metrics in the clustering result
    res = run_balltree_st_dbscan(ds, cfg)
    assert res.provider_metrics["provider"] == "balltree"
    assert res.provider_metrics["detailed_timing"] is False

    with pytest.raises(ValueError, match="detailed_timing must be a boolean"):
        BallTreeNeighborhoodProvider(ds, cfg, detailed_timing=1)  # type: ignore[arg-type]


def test_h3_metrics_toggle() -> None:
    ds = _synthetic_dataset()
    cfg = STDBSCANConfig(min_samples=3)

    fast = H3NeighborhoodProvider(ds, cfg, resolution=8)
    assert fast.detailed_timing is False
    fast.build_neighborhood_graph()
    m = fast.get_metrics()
    assert m["provider"] == "h3"
    assert m["detailed_timing"] is False
    assert m["build_time_s"] > 0.0
    assert all(m[k] is None for k in (*STAGE_TIMERS, *H3_ONLY_TIMERS))
    assert m["candidates_evaluated"] is None
    assert m["total_candidates_evaluated"] is None
    assert m["fallback_count"] == 0
    assert m["unique_occupied_cells"] > 0

    timed = H3NeighborhoodProvider(ds, cfg, resolution=8, detailed_timing=True)
    graph = timed.build_neighborhood_graph()
    mt = timed.get_metrics()
    assert mt["detailed_timing"] is True
    assert all(isinstance(mt[k], float) and mt[k] >= 0.0 for k in (*STAGE_TIMERS, *H3_ONLY_TIMERS))
    assert mt["cell_mapping_time_s"] > 0.0
    assert mt["candidates_evaluated"] >= graph.total_edges
    assert mt["candidates_evaluated"] == mt["total_candidates_evaluated"]

    with pytest.raises(ValueError, match="detailed_timing must be a boolean"):
        H3NeighborhoodProvider(ds, cfg, detailed_timing="yes")  # type: ignore[arg-type]


def test_official_path_makes_no_perf_counter_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """detailed_timing=False graph construction performs zero perf_counter calls."""
    ds = _synthetic_dataset()
    cfg = STDBSCANConfig(min_samples=3)
    bt = BallTreeNeighborhoodProvider(ds, cfg)
    h3p = H3NeighborhoodProvider(ds, cfg, resolution=8)

    # Both providers call ``time.perf_counter`` through the stdlib module at call time.
    calls = {"n": 0}
    real = time.perf_counter

    def counting() -> float:
        calls["n"] += 1
        return real()

    monkeypatch.setattr(time, "perf_counter", counting)
    bt.build_neighborhood_graph()
    h3p.build_neighborhood_graph()
    assert calls["n"] == 0

    BallTreeNeighborhoodProvider(ds, cfg, detailed_timing=True).build_neighborhood_graph()
    assert calls["n"] > 0


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def test_t_critical_values() -> None:
    assert t_critical_95(1) == 12.706204736
    assert t_critical_95(9) == 2.262157163
    assert t_critical_95(30) == 2.042272456
    assert t_critical_95(31) == Z_CRITICAL_95 == 1.959964
    assert sorted(T_CRITICAL_95) == list(range(1, 31))
    assert all(T_CRITICAL_95[d] > T_CRITICAL_95[d + 1] for d in range(1, 30))
    with pytest.raises(ValueError):
        t_critical_95(0)


def test_summarize_series_known_values() -> None:
    s = summarize_series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert s["n"] == 5
    assert s["mean"] == 3.0
    assert s["median"] == 3.0
    assert s["std"] == pytest.approx(math.sqrt(2.5))
    assert (s["min"], s["max"]) == (1.0, 5.0)
    assert (s["iqr_p25"], s["iqr_p75"]) == (2.0, 4.0)
    half = 2.776445105 * math.sqrt(2.5) / math.sqrt(5)
    assert s["ci95_low"] == pytest.approx(3.0 - half)
    assert s["ci95_high"] == pytest.approx(3.0 + half)

    single = summarize_series([2.5])
    assert single["n"] == 1 and single["mean"] == 2.5
    assert single["std"] is None and single["ci95_low"] is None and single["ci95_high"] is None

    big = summarize_series([float(v) for v in range(40)])
    expected_half = Z_CRITICAL_95 * big["std"] / math.sqrt(40)
    assert big["ci95_high"] - big["mean"] == pytest.approx(expected_half)

    with pytest.raises(ValueError):
        summarize_series([])
    with pytest.raises(ValueError):
        summarize_series([1.0, float("nan")])


def test_summarize_paired_comparison_known_values() -> None:
    bt = [2.0, 4.0, 6.0, 8.0]
    h3 = [1.0, 2.0, 2.0, 4.0]
    p = summarize_paired_comparison(bt, h3)
    assert p["n_pairs"] == 4

    diff = p["difference_balltree_minus_h3_s"]  # [1, 2, 4, 4]
    assert diff["mean"] == 2.75
    assert diff["std"] == pytest.approx(math.sqrt(2.25))
    half = 3.182446305 * 1.5 / 2.0
    assert diff["ci95_low"] == pytest.approx(2.75 - half)
    assert diff["ci95_high"] == pytest.approx(2.75 + half)

    speed = p["per_trial_speedup_balltree_over_h3"]  # [2, 2, 3, 2]
    assert speed["mean"] == 2.25
    assert speed["median"] == 2.0
    assert speed["std"] == pytest.approx(0.5)
    assert speed["ci95_low"] == pytest.approx(2.25 - 3.182446305 * 0.5 / 2.0)

    assert p["ratio_of_means_speedup"] == pytest.approx(5.0 / 2.25)

    zero = summarize_paired_comparison([1.0, 1.0], [0.0, 1.0])
    assert zero["per_trial_speedup_balltree_over_h3"] is None
    assert zero["ratio_of_means_speedup"] == 2.0

    with pytest.raises(ValueError, match="equal length"):
        summarize_paired_comparison([1.0], [1.0, 2.0])
    with pytest.raises(ValueError):
        summarize_paired_comparison([], [])


def test_counterbalanced_execution_order() -> None:
    orders = [trial_execution_order(t) for t in range(6)]
    assert orders == [("balltree", "h3"), ("h3", "balltree")] * 3
    assert [execution_order_label(t) for t in range(4)] == [
        "balltree_first",
        "h3_first",
        "balltree_first",
        "h3_first",
    ]
    with pytest.raises(ValueError):
        trial_execution_order(-1)


def test_timed_trials_follow_counterbalanced_order(monkeypatch: pytest.MonkeyPatch) -> None:
    ds = _synthetic_dataset(n_per_anchor=4)
    config = W302BenchmarkConfig(
        dataset_path=Path("unused.parquet"), min_samples=2, warmup_runs=1, measured_trials=4
    )
    calls: list[str] = []
    real = bench.timed_provider_run

    def recording(kind: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(kind)
        return real(kind, *args, **kwargs)

    monkeypatch.setattr(bench, "timed_provider_run", recording)
    out = bench._paired_block_scale(ds, config, 8, None)
    assert calls == ["balltree", "h3"] + ["balltree", "h3", "h3", "balltree"] * 2
    assert [t["execution_order"] for t in out["trials"]] == [
        "balltree_first",
        "h3_first",
        "balltree_first",
        "h3_first",
    ]
    assert out["all_trials_detailed_timing_false"] is True
    assert out["results_consistent_with_phase_1"] is False  # no reference supplied


# ---------------------------------------------------------------------------
# Graph comparison helpers and config validation
# ---------------------------------------------------------------------------


def test_compare_neighborhood_graphs_detects_differences() -> None:
    ref = NeighborhoodGraph(
        indptr=np.array([0, 2, 4, 5], dtype=np.int64),
        indices=np.array([0, 1, 0, 1, 2], dtype=np.int64),
    )
    assert undirected_edge_count(ref) == 1
    same = compare_neighborhood_graphs(ref, ref)
    assert same["exact_graph_match"] and same["neighbor_recall"] == 1.0

    cand = NeighborhoodGraph(
        indptr=np.array([0, 1, 2, 4], dtype=np.int64),
        indices=np.array([0, 1, 1, 2], dtype=np.int64),
    )
    cmp = compare_neighborhood_graphs(ref, cand)
    assert cmp["exact_graph_match"] is False
    assert cmp["missing_neighbor_count"] == 2
    assert cmp["extra_neighbor_count"] == 1
    assert cmp["neighbor_recall"] == pytest.approx(3 / 5)
    assert cmp["neighbor_precision"] == pytest.approx(3 / 4)
    assert cmp["directed_edge_count_match"] is False


def test_benchmark_config_validation() -> None:
    p = Path("x.parquet")
    assert W302BenchmarkConfig(dataset_path=p).scales == (10_000, 50_000, 100_000, None)
    with pytest.raises(ValueError, match="official_detailed_timing must be False"):
        W302BenchmarkConfig(dataset_path=p, official_detailed_timing=True)
    with pytest.raises(ValueError, match="ascending"):
        W302BenchmarkConfig(dataset_path=p, scales=(None, 10))
    with pytest.raises(ValueError, match="ascending"):
        W302BenchmarkConfig(dataset_path=p, scales=(50, 10))
    with pytest.raises(ValueError, match="duplicates"):
        W302BenchmarkConfig(dataset_path=p, scales=(10, 10))
    with pytest.raises(ValueError, match="not calibrated"):
        W302BenchmarkConfig(dataset_path=p, sensitivity_h3_resolutions=(6,))
    with pytest.raises(ValueError, match="distinct"):
        W302BenchmarkConfig(dataset_path=p, sensitivity_h3_resolutions=(8,))
    with pytest.raises(ValueError, match="oracle_max_rows"):
        W302BenchmarkConfig(dataset_path=p, oracle_max_rows=10_000)
    with pytest.raises(ValueError, match="exceeds maximum empirically calibrated"):
        W302BenchmarkConfig(dataset_path=p, eps_spatial_m=5000.0)
    with pytest.raises(ValueError, match="measured_trials"):
        W302BenchmarkConfig(dataset_path=p, measured_trials=0)

    record = W302BenchmarkConfig(dataset_path=p).to_dict()
    assert record["official_trial_settings"]["detailed_timing"] is False
    assert record["official_trial_settings"]["measure_memory"] is False
    assert record["h3_k_rings"] == {"8": 1, "7": 1, "9": 2}
    assert record["memory_pass_settings"]["psutil_rss_measured"] is False


def test_verify_nested_prefixes() -> None:
    ds = _synthetic_dataset(n_per_anchor=5)
    cfg_rows = ds.num_points

    def prefix(n: int) -> ClusteringInputDataset:
        return ClusteringInputDataset(
            source_rows=ds.source_rows[:n],
            mmsis=ds.mmsis[:n],
            timestamps_us=ds.timestamps_us[:n],
            latitudes_deg=ds.latitudes_deg[:n],
            longitudes_deg=ds.longitudes_deg[:n],
            total_input_count=n,
            excluded_count=0,
            excluded_breakdown={},
        )

    assert verify_nested_prefixes([prefix(5), prefix(12), ds]) is True
    shifted = prefix(cfg_rows)
    shifted.latitudes_deg = shifted.latitudes_deg + 1e-9
    assert verify_nested_prefixes([prefix(5), shifted]) is False
    assert verify_nested_prefixes([ds, prefix(5)]) is False


# ---------------------------------------------------------------------------
# End-to-end mini benchmark and CLI runner
# ---------------------------------------------------------------------------


def _mini_config(parquet: Path) -> W302BenchmarkConfig:
    return W302BenchmarkConfig(
        dataset_path=parquet,
        min_samples=2,
        scales=(12, None),
        oracle_max_rows=12,
        warmup_runs=1,
        measured_trials=2,
        sensitivity_h3_resolutions=(7, 9),
    )


def test_end_to_end_mini_benchmark(synthetic_parquet: Path) -> None:
    messages: list[str] = []
    results = run_w3_02_benchmark(_mini_config(synthetic_parquet), log=messages.append)
    json.dumps(results, allow_nan=False)  # strictly JSON-serializable

    assert results["status"] == "completed"
    assert results["benchmark"] == "w3_02_balltree_vs_h3"
    assert results["statistical_interpretation_note"] == STATISTICAL_INTERPRETATION_NOTE
    assert any(m.startswith("[phase 2]") for m in messages)

    # Provenance
    prov = results["provenance"]
    ds_prov = prov["dataset"]
    assert ds_prov["file_sha256"] == compute_file_sha256(synthetic_parquet)
    fp = compute_content_fingerprint(synthetic_parquet)
    assert ds_prov["content_fingerprint_sha256"] == fp.content_fingerprint_sha256
    assert ds_prov["content_fingerprint_version"] == "aegismar-logical-v1"
    assert ds_prov["canonical_order_verified"] is True
    assert ds_prov["parquet_row_count"] == 42
    assert ds_prov["filtered_row_count"] == 40
    assert ds_prov["excluded_breakdown"] == {"TIMESTAMP_POSITION_CONFLICT": 2}
    manifest = prov["dataset_manifest_provenance"]
    assert manifest["output_parquet_sha256_matches_file"] is True
    assert manifest["content_fingerprint_matches_file"] is True
    assert len(manifest["source_sha256"]) == 64
    env = prov["environment"]
    assert set(env["library_versions"]) == {"numpy", "scikit-learn", "h3", "pyarrow"}
    assert all(env["library_versions"].values())
    assert env["platform"]["cpu_count"] >= 1
    assert env["runtime"]["python_version"].startswith("3.11")

    cfg = results["config"]
    assert cfg["official_trial_settings"]["detailed_timing"] is False
    assert cfg["official_trial_settings"]["measure_memory"] is False

    # Scale subsets
    assert [s["scale_label"] for s in results["scales"]] == ["12", "full"]
    assert [s["row_count"] for s in results["scales"]] == [12, 40]
    assert results["scales"][1]["unique_vessels"] == 4
    assert results["scales"][0]["max_timestamp_utc"] <= results["scales"][1]["max_timestamp_utc"]
    assert results["nested_prefix_verified"] is True

    # Phase 1: exact parity
    p1 = results["phase_1_correctness"]
    assert p1["all_parity_checks_passed"] is True
    oracle = p1["oracle_verification"]
    assert oracle["row_count"] == 12
    assert [c["candidate"] for c in oracle["comparisons"]] == [
        "balltree",
        "h3_r8",
        "h3_r7",
        "h3_r9",
    ]
    entries = oracle["comparisons"] + [c for s in p1["scale_parity"] for c in s["comparisons"]]
    for e in entries:
        assert e["neighbor_recall"] == 1.0
        assert e["neighbor_precision"] == 1.0
        assert e["adjusted_rand_index"] == 1.0
        assert e["directed_edge_count_match"] and e["undirected_edge_count_match"]
        assert e["passed"] is True
    assert all(c["h3_fallback_count"] == 0 for s in p1["scale_parity"] for c in s["comparisons"])
    assert p1["reference_counts_by_scale"]["full"]["num_clusters"] >= 2

    # Phase 2: three blocks, counterbalanced paired trials
    p2 = results["phase_2_timed_trials"]
    assert p2["all_trial_integrity_checks_passed"] is True
    assert [b["block"] for b in p2["blocks"]] == [
        "primary_h3_r8",
        "sensitivity_h3_r7",
        "sensitivity_h3_r9",
    ]
    for block in p2["blocks"]:
        assert [s["scale_label"] for s in block["scales"]] == ["12", "full"]
        for s in block["scales"]:
            assert [t["execution_order"] for t in s["trials"]] == ["balltree_first", "h3_first"]
            for t in s["trials"]:
                for p in ("balltree", "h3"):
                    rec = t[p]
                    assert rec["detailed_timing"] is False
                    assert rec["index_and_graph_time_s"] == pytest.approx(
                        rec["build_time_s"] + rec["query_and_prune_time_s"]
                    )
                    assert rec["total_time_s"] == pytest.approx(
                        rec["index_and_graph_time_s"] + rec["clustering_time_s"]
                    )
                assert t["h3"]["fallback_count"] == 0
            assert s["summary"]["balltree"]["total_time_s"]["n"] == 2
            paired = s["paired_comparison"]["total_time_s"]
            assert paired["n_pairs"] == 2
            assert paired["ratio_of_means_speedup"] > 0.0

    # Phase 3: separate memory pass; Phase 4: separate diagnostics pass
    p3 = results["phase_3_peak_memory"]
    assert p3["psutil_rss_measured"] is False
    for s in p3["scales"]:
        assert [r["provider"] for r in s["runs"]] == ["balltree", "h3_r7", "h3_r8", "h3_r9"]
        assert all(r["peak_tracemalloc_bytes"] > 0 for r in s["runs"])
    p4 = results["phase_4_stage_diagnostics"]
    for s in p4["scales"]:
        for r in s["runs"]:
            assert r["detailed_timing"] is True
            assert r["candidate_retrieval_time_s"] is not None
            assert r["candidates_evaluated"] is not None


def test_end_to_end_parity_failure_skips_timing(
    synthetic_parquet: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = bench.compare_neighborhood_graphs

    def broken(reference: NeighborhoodGraph, candidate: NeighborhoodGraph) -> dict[str, Any]:
        out = real(reference, candidate)
        out["exact_graph_match"] = False
        return out

    monkeypatch.setattr(bench, "compare_neighborhood_graphs", broken)
    results = run_w3_02_benchmark(_mini_config(synthetic_parquet))
    assert results["status"] == "parity_failed"
    assert results["phase_1_correctness"]["all_parity_checks_passed"] is False
    assert results["phase_2_timed_trials"] is None
    assert results["phase_3_peak_memory"] is None
    assert results["phase_4_stage_diagnostics"] is None


def test_cli_runner_writes_json_and_protects_overwrite(
    synthetic_parquet: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = _load_runner()
    out = tmp_path / "results" / "w3_02.json"
    args = [
        "-i",
        str(synthetic_parquet),
        "-o",
        str(out),
        "--scales",
        "12",
        "full",
        "--trials",
        "2",
        "--warmup",
        "1",
        "--oracle-rows",
        "12",
        "--sensitivity-resolutions",
        "7",
        "9",
    ]
    assert runner.main(args) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "completed"
    assert data["config"]["measured_trials"] == 2
    assert data["config"]["scales"] == ["12", "full"]
    captured = capsys.readouterr()
    assert "[phase 1]" in captured.out and "Results written to" in captured.out

    before = out.read_bytes()
    assert runner.main(args) == 1
    assert "Pass --overwrite" in capsys.readouterr().err
    assert out.read_bytes() == before

    assert runner.main([*args, "--overwrite", "--trials", "1"]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["config"]["measured_trials"] == 1

    assert runner.main(["-i", str(tmp_path / "missing.parquet"), "-o", str(out)]) == 1
    assert "input dataset not found" in capsys.readouterr().err

    bad = [*args, "--overwrite", "--sensitivity-resolutions", "6"]
    assert runner.main(bad) == 1
    assert "invalid benchmark configuration" in capsys.readouterr().err


def test_run_st_dbscan_metrics_flow_through_for_balltree() -> None:
    """run_st_dbscan picks up BallTree.get_metrics() (now present) without behavior change."""
    ds = _synthetic_dataset(n_per_anchor=5)
    cfg = STDBSCANConfig(min_samples=2)
    res = run_st_dbscan(ds, cfg, BallTreeNeighborhoodProvider(ds, cfg))
    assert res.provider_metrics["provider"] == "balltree"
    assert res.summary_dict()["provider_metrics"]["detailed_timing"] is False
