"""Spatiotemporal clustering subsystem for Project AegisMar."""

from __future__ import annotations

from aegismar.clustering.balltree_neighbors import BallTreeNeighborhoodProvider
from aegismar.clustering.config import (
    ALGORITHM_VERSION,
    DEFAULT_EPS_SPATIAL_M,
    DEFAULT_EPS_TEMPORAL_S,
    DEFAULT_H3_RESOLUTION,
    DEFAULT_MIN_SAMPLES,
    PROVIDER_BALLTREE,
    PROVIDER_H3,
    SUPPORTED_H3_RESOLUTIONS,
    SUPPORTED_PROVIDERS,
    QualityFilterPolicy,
    STDBSCANConfig,
)
from aegismar.clustering.export import (
    clustering_result_to_arrow_table,
    export_clustering_artifacts,
    get_cluster_assignments_arrow_schema,
    write_clustering_geojson_preview,
    write_clustering_parquet,
    write_clustering_summary_json,
    write_static_cluster_map_html,
)
from aegismar.clustering.h3_neighbors import H3NeighborhoodProvider, compute_safe_k_ring
from aegismar.clustering.st_dbscan import run_balltree_st_dbscan, run_h3_st_dbscan, run_st_dbscan
from aegismar.clustering.types import (
    NOISE_CLUSTER_ID,
    POINT_ROLE_BORDER,
    POINT_ROLE_CORE,
    POINT_ROLE_NOISE,
    ClusteringInputDataset,
    NeighborhoodGraph,
    NeighborhoodProvider,
    ObservationRecord,
    STDBSCANResult,
    build_clustering_dataset,
    load_clustering_dataset_from_parquet,
)

__all__ = [
    "ALGORITHM_VERSION",
    "DEFAULT_EPS_SPATIAL_M",
    "DEFAULT_EPS_TEMPORAL_S",
    "DEFAULT_H3_RESOLUTION",
    "DEFAULT_MIN_SAMPLES",
    "NOISE_CLUSTER_ID",
    "POINT_ROLE_BORDER",
    "POINT_ROLE_CORE",
    "POINT_ROLE_NOISE",
    "PROVIDER_BALLTREE",
    "PROVIDER_H3",
    "SUPPORTED_H3_RESOLUTIONS",
    "SUPPORTED_PROVIDERS",
    "BallTreeNeighborhoodProvider",
    "ClusteringInputDataset",
    "H3NeighborhoodProvider",
    "NeighborhoodGraph",
    "NeighborhoodProvider",
    "ObservationRecord",
    "QualityFilterPolicy",
    "STDBSCANConfig",
    "STDBSCANResult",
    "build_clustering_dataset",
    "clustering_result_to_arrow_table",
    "compute_safe_k_ring",
    "export_clustering_artifacts",
    "get_cluster_assignments_arrow_schema",
    "load_clustering_dataset_from_parquet",
    "run_balltree_st_dbscan",
    "run_h3_st_dbscan",
    "run_st_dbscan",
    "write_clustering_geojson_preview",
    "write_clustering_parquet",
    "write_clustering_summary_json",
    "write_static_cluster_map_html",
]
