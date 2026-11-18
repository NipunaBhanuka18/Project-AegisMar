"""Provider-agnostic deterministic core-first ST-DBSCAN clustering engine.

Deterministic Labeling Policy (``stdbscan-core-first-v1.0``)
------------------------------------------------------------
Unlike classic sequential queue-based DBSCAN implementations (whose border-point
assignments can depend on input row order or neighbor iteration order), AegisMar
enforces a strict six-step core-first policy so that ``BallTree``, ``H3``, and the
independent brute-force oracle yield bit-for-bit identical clusterings:

1. **Canonical Input Ordering**: Observations are sorted by the total order
   ``(timestamp_us, mmsi, latitude_deg, longitude_deg, source_row)`` prior to indexing.
2. **Core Classification**: An observation ``i`` is a ``core`` point iff its full
   eligible spatiotemporal neighborhood (including ``i`` itself) satisfies
   ``|N(i)| >= min_samples``.
3. **Core Connected Components**: Connected components are formed strictly over
   the subgraph of core points (edges ``(i, j)`` where ``i`` and ``j`` are both
   core points and ``j in N(i)``) via deterministic breadth-first search seeded
   in ascending canonical core-index order.
4. **Canonical Component Numbering**: Core connected components are ordered by
   the minimum canonical index of any core point in the component, receiving
   contiguous cluster IDs ``0, 1, ..., K - 1``.
5. **Deterministic Border Attachment**: Every non-core observation ``i`` with at
   least one core neighbor ``c in N(i)`` is classified as ``border`` and attached
   to the component of the core neighbor ``c*`` minimizing:
   ``(haversine_distance_m(i, c), |t_i_us - t_c_us|, cluster_id[c], c)``.
6. **Noise Classification**: Any non-core observation with zero core neighbors is
   classified as ``noise`` and assigned label ``-1``.

Note: Because border points are attached via nearest-core tie-breaking rather than
first-visited queue order, border assignments for points equidistant to multiple
clusters may differ from standard ``sklearn.cluster.DBSCAN``. This semantic choice
is intentional and documented to guarantee order independence and exact cross-index
comparability between BallTree and H3.
"""

from __future__ import annotations

import time
import tracemalloc
from collections import Counter, deque

import numpy as np
from numpy.typing import NDArray

from aegismar.clustering.balltree_neighbors import BallTreeNeighborhoodProvider
from aegismar.clustering.config import STDBSCANConfig
from aegismar.clustering.types import (
    NOISE_CLUSTER_ID,
    POINT_ROLE_BORDER,
    POINT_ROLE_CORE,
    POINT_ROLE_NOISE,
    ClusteringInputDataset,
    NeighborhoodProvider,
    STDBSCANResult,
)
from aegismar.spatial.haversine import haversine_distance_meters


def run_st_dbscan(
    dataset: ClusteringInputDataset,
    config: STDBSCANConfig,
    provider: NeighborhoodProvider,
    measure_memory: bool = False,
) -> STDBSCANResult:
    """Execute deterministic core-first ST-DBSCAN using an injectable neighborhood provider.

    Parameters
    ----------
    dataset : ClusteringInputDataset
        Canonically sorted observations to cluster.
    config : STDBSCANConfig
        Validated spatiotemporal clustering configuration.
    provider : NeighborhoodProvider
        Injectable spatial-temporal neighborhood engine (e.g., BallTree, H3, Oracle).
    measure_memory : bool
        If True, wraps query and clustering phases in ``tracemalloc`` to capture
        peak Python heap allocation in bytes.

    Returns
    -------
    STDBSCANResult
        Complete cluster labels, roles, membership counts, and timing metrics.
    """
    if provider.num_points != dataset.num_points:
        raise ValueError(
            f"NeighborhoodProvider point count ({provider.num_points}) does not match "
            f"dataset point count ({dataset.num_points})"
        )

    n = dataset.num_points
    started_tracemalloc = False
    if measure_memory and not tracemalloc.is_tracing():
        tracemalloc.start()
        started_tracemalloc = True
    elif measure_memory:
        tracemalloc.reset_peak()

    t_query_start = time.perf_counter()
    graph = provider.build_neighborhood_graph()
    query_time_s = time.perf_counter() - t_query_start

    t_cluster_start = time.perf_counter()
    labels: NDArray[np.int64] = np.full(n, NOISE_CLUSTER_ID, dtype=np.int64)
    roles_list: list[str] = [POINT_ROLE_NOISE] * n

    if n == 0:
        clustering_time_s = time.perf_counter() - t_cluster_start
        peak_bytes = 0
        if measure_memory:
            _, peak_bytes = tracemalloc.get_traced_memory()
            if started_tracemalloc:
                tracemalloc.stop()
        return STDBSCANResult(
            dataset=dataset,
            config=config,
            provider_name=provider.provider_name,
            labels=labels,
            roles=(),
            num_clusters=0,
            core_count=0,
            border_count=0,
            noise_count=0,
            cluster_member_counts={},
            build_time_seconds=provider.build_time_seconds,
            query_time_seconds=query_time_s,
            clustering_time_seconds=clustering_time_s,
            total_time_seconds=provider.build_time_seconds + query_time_s + clustering_time_s,
            peak_tracemalloc_bytes=peak_bytes,
        )

    # Step 2: Determine core status from full eligible neighborhood (including self)
    min_samples = config.min_samples
    degrees = np.diff(graph.indptr)
    is_core: NDArray[np.bool_] = degrees >= min_samples

    # Step 3 & 4: Connected components among core points in ascending canonical order.
    # Iterating core_indices in strictly ascending order guarantees that each new
    # unvisited seed is the minimum canonical core index of its component, yielding
    # contiguous cluster IDs 0..K-1 deterministically.
    indptr = graph.indptr
    indices = graph.indices
    core_indices = np.flatnonzero(is_core)
    unvisited_core: NDArray[np.bool_] = is_core.copy()
    num_clusters = 0

    for seed in core_indices.tolist():
        if not bool(unvisited_core[seed]):
            continue
        cid = num_clusters
        num_clusters += 1
        unvisited_core[seed] = False
        labels[seed] = cid
        roles_list[seed] = POINT_ROLE_CORE
        queue: deque[int] = deque((seed,))

        while queue:
            curr = queue.popleft()
            nbrs = indices[int(indptr[curr]) : int(indptr[curr + 1])]
            new_cores = nbrs[unvisited_core[nbrs]]
            if new_cores.size > 0:
                unvisited_core[new_cores] = False
                labels[new_cores] = cid
                for nc in new_cores.tolist():
                    roles_list[nc] = POINT_ROLE_CORE
                    queue.append(nc)

    # Step 5 & 6: Attach border points deterministically; remaining points stay noise (-1)
    lats = dataset.latitudes_deg
    lons = dataset.longitudes_deg
    ts_us = dataset.timestamps_us
    non_core_indices = np.flatnonzero(~is_core)

    for i in non_core_indices.tolist():
        nbrs = indices[int(indptr[i]) : int(indptr[i + 1])]
        core_nbrs = nbrs[is_core[nbrs]]
        if core_nbrs.size == 0:
            continue

        best_key: tuple[float, int, int, int] | None = None
        best_cluster_id: int = NOISE_CLUSTER_ID

        lat_i = float(lats[i])
        lon_i = float(lons[i])
        t_i = int(ts_us[i])

        for c in core_nbrs.tolist():
            dist_m = haversine_distance_meters(lat_i, lon_i, float(lats[c]), float(lons[c]))
            dt_us = abs(t_i - int(ts_us[c]))
            cid = int(labels[c])
            key = (dist_m, dt_us, cid, c)
            if best_key is None or key < best_key:
                best_key = key
                best_cluster_id = cid

        if best_key is not None:
            labels[i] = best_cluster_id
            roles_list[i] = POINT_ROLE_BORDER

    clustering_time_s = time.perf_counter() - t_cluster_start
    peak_bytes = 0
    if measure_memory:
        _, peak_bytes = tracemalloc.get_traced_memory()
        if started_tracemalloc:
            tracemalloc.stop()

    # Exact accounting verification
    core_count = int(core_indices.shape[0])
    border_count = sum(1 for r in roles_list if r == POINT_ROLE_BORDER)
    noise_count = sum(1 for r in roles_list if r == POINT_ROLE_NOISE)
    if core_count + border_count + noise_count != n:
        raise RuntimeError(
            f"Internal accounting violation: core({core_count}) + border({border_count}) "
            f"+ noise({noise_count}) != total({n})"
        )

    member_counter: Counter[int] = Counter(
        int(lbl) for lbl in labels if int(lbl) != NOISE_CLUSTER_ID
    )
    cluster_member_counts = {cid: member_counter[cid] for cid in sorted(member_counter)}

    return STDBSCANResult(
        dataset=dataset,
        config=config,
        provider_name=provider.provider_name,
        labels=labels,
        roles=tuple(roles_list),
        num_clusters=num_clusters,
        core_count=core_count,
        border_count=border_count,
        noise_count=noise_count,
        cluster_member_counts=cluster_member_counts,
        build_time_seconds=provider.build_time_seconds,
        query_time_seconds=query_time_s,
        clustering_time_seconds=clustering_time_s,
        total_time_seconds=provider.build_time_seconds + query_time_s + clustering_time_s,
        peak_tracemalloc_bytes=peak_bytes,
    )


def run_balltree_st_dbscan(
    dataset: ClusteringInputDataset,
    config: STDBSCANConfig,
    leaf_size: int = 40,
    query_batch_size: int = 2048,
    measure_memory: bool = False,
) -> STDBSCANResult:
    """Convenience runner executing reference BallTree-backed ST-DBSCAN on a dataset."""
    started_tracemalloc = False
    if measure_memory and not tracemalloc.is_tracing():
        tracemalloc.start()
        started_tracemalloc = True
    elif measure_memory:
        tracemalloc.reset_peak()

    provider = BallTreeNeighborhoodProvider(
        dataset=dataset,
        config=config,
        leaf_size=leaf_size,
        query_batch_size=query_batch_size,
    )
    result = run_st_dbscan(
        dataset=dataset,
        config=config,
        provider=provider,
        measure_memory=measure_memory,
    )
    if started_tracemalloc and tracemalloc.is_tracing():
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        result.peak_tracemalloc_bytes = max(result.peak_tracemalloc_bytes, peak_bytes)
    return result
