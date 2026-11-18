"""Export utilities for ST-DBSCAN clustering results (Parquet, JSON, GeoJSON, static HTML map)."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from aegismar.clustering.types import (
    NOISE_CLUSTER_ID,
    STDBSCANResult,
    epoch_us_to_datetime,
)


def get_cluster_assignments_arrow_schema() -> pa.Schema:
    """Return the canonical PyArrow schema for exported ST-DBSCAN cluster assignments."""
    return pa.schema(
        [
            ("source_row", pa.int64()),
            ("mmsi", pa.string()),
            ("timestamp_utc", pa.timestamp("us", tz="UTC")),
            ("latitude", pa.float64()),
            ("longitude", pa.float64()),
            ("cluster_id", pa.int64()),
            ("point_role", pa.string()),
        ]
    )


def clustering_result_to_arrow_table(result: STDBSCANResult) -> pa.Table:
    """Convert an ``STDBSCANResult`` into a strictly typed PyArrow Table."""
    ds = result.dataset
    schema = get_cluster_assignments_arrow_schema()

    ts_array = pa.array(ds.timestamps_us.tolist(), type=pa.int64()).cast(
        pa.timestamp("us", tz="UTC")
    )
    arrays = [
        pa.array(ds.source_rows.tolist(), type=pa.int64()),
        pa.array(list(ds.mmsis), type=pa.string()),
        ts_array,
        pa.array(ds.latitudes_deg.tolist(), type=pa.float64()),
        pa.array(ds.longitudes_deg.tolist(), type=pa.float64()),
        pa.array(result.labels.tolist(), type=pa.int64()),
        pa.array(list(result.roles), type=pa.string()),
    ]
    return pa.Table.from_arrays(arrays, schema=schema)


def write_clustering_parquet(
    result: STDBSCANResult,
    output_path: Path | str,
    compression: str = "zstd",
) -> Path:
    """Write complete ST-DBSCAN observation assignments to a compressed Parquet file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = clustering_result_to_arrow_table(result)
    pq.write_table(table, where=str(path), compression=compression, use_dictionary=True)
    return path


def write_clustering_summary_json(
    result: STDBSCANResult,
    output_path: Path | str,
    extra_metadata: dict[str, Any] | None = None,
) -> Path:
    """Write structured JSON summary of clustering counts, configuration, and timings."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = result.summary_dict()
    if extra_metadata:
        payload["metadata"] = extra_metadata
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path


def _select_preview_indices(result: STDBSCANResult, max_features: int) -> list[int]:
    """Deterministically select a compact visual inspection subset across clusters and noise."""
    n = result.dataset.num_points
    if n <= max_features:
        return list(range(n))
    step = max(1, n // max_features)
    return list(range(0, n, step))[:max_features]


def write_clustering_geojson_preview(
    result: STDBSCANResult,
    output_path: Path | str,
    max_features: int = 2000,
) -> Path:
    """Export a compact deterministic GeoJSON FeatureCollection for visual inspection."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    ds = result.dataset
    selected = _select_preview_indices(result, max_features=max_features)

    features: list[dict[str, Any]] = []
    for idx in selected:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        round(float(ds.longitudes_deg[idx]), 6),
                        round(float(ds.latitudes_deg[idx]), 6),
                    ],
                },
                "properties": {
                    "source_row": int(ds.source_rows[idx]),
                    "mmsi": ds.mmsis[idx],
                    "timestamp_utc": epoch_us_to_datetime(int(ds.timestamps_us[idx])).isoformat(),
                    "cluster_id": int(result.labels[idx]),
                    "point_role": result.roles[idx],
                },
            }
        )

    fc = {
        "type": "FeatureCollection",
        "metadata": {
            "provider_name": result.provider_name,
            "total_analyzed": ds.num_points,
            "preview_feature_count": len(features),
            "num_clusters": result.num_clusters,
            "eps_spatial_m": result.config.eps_spatial_m,
            "eps_temporal_s": result.config.eps_temporal_s,
            "min_samples": result.config.min_samples,
        },
        "features": features,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fc, f, indent=2)
    return path


_PALETTE: tuple[str, ...] = (
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#17becf",
    "#bcbd22",
    "#393b79",
    "#637939",
    "#8c6d31",
)


def write_static_cluster_map_html(
    result: STDBSCANResult,
    output_path: Path | str,
    max_points: int = 5000,
    title: str = "AegisMar — BallTree ST-DBSCAN Spatial Preview",
) -> Path:
    """Generate a lightweight, offline, zero-dependency static HTML/SVG spatial plot."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    ds = result.dataset
    selected = _select_preview_indices(result, max_features=max_points)

    width = 900
    height = 640
    pad = 40

    svg_circles: list[str] = []
    if selected:
        lats = [float(ds.latitudes_deg[i]) for i in selected]
        lons = [float(ds.longitudes_deg[i]) for i in selected]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        lat_span = max(max_lat - min_lat, 1e-6)
        lon_span = max(max_lon - min_lon, 1e-6)

        for idx in selected:
            lon = float(ds.longitudes_deg[idx])
            lat = float(ds.latitudes_deg[idx])
            x = pad + ((lon - min_lon) / lon_span) * (width - 2 * pad)
            y = height - pad - ((lat - min_lat) / lat_span) * (height - 2 * pad)
            cid = int(result.labels[idx])
            role = result.roles[idx]
            if cid == NOISE_CLUSTER_ID:
                color = "#9aa0a6"
                radius = "1.8"
                opacity = "0.45"
            else:
                color = _PALETTE[cid % len(_PALETTE)]
                radius = "2.6" if role == "core" else "2.0"
                opacity = "0.80"
            svg_circles.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" '
                f'fill="{color}" fill-opacity="{opacity}"/>'
            )
        bbox_text = f"Lat [{min_lat:.4f}, {max_lat:.4f}] | Lon [{min_lon:.4f}, {max_lon:.4f}]"
    else:
        bbox_text = "Empty dataset"

    safe_title = html.escape(title)
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{safe_title}</title>
  <style>
    body {{
      font-family: system-ui, sans-serif; margin: 24px; background: #0f172a; color: #e2e8f0;
    }}
    .meta {{ margin-bottom: 12px; font-size: 14px; color: #cbd5e1; }}
    svg {{ background: #1e293b; border: 1px solid #334155; border-radius: 6px; }}
  </style>
</head>
<body>
  <h2>{safe_title}</h2>
  <div class="meta">
    Provider: <strong>{html.escape(result.provider_name)}</strong> |
    Analyzed: <strong>{ds.num_points:,}</strong> |
    Clusters: <strong>{result.num_clusters:,}</strong> |
    Core: <strong>{result.core_count:,}</strong> |
    Border: <strong>{result.border_count:,}</strong> |
    Noise: <strong>{result.noise_count:,}</strong> |
    Displayed: <strong>{len(selected):,}</strong><br/>
    Params: eps_spatial={result.config.eps_spatial_m}m,
    eps_temporal={result.config.eps_temporal_s}s,
    min_samples={result.config.min_samples} |
    Extent: {bbox_text}
  </div>
  <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">
    {"".join(svg_circles)}
  </svg>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path


def export_clustering_artifacts(
    result: STDBSCANResult,
    output_dir: Path | str,
    overwrite: bool = False,
    preview_geojson_limit: int = 2000,
    preview_map_limit: int = 5000,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Export Parquet, summary JSON, compact GeoJSON preview, and static HTML map."""
    out_dir = Path(output_dir)
    parquet_path = out_dir / "cluster_assignments.parquet"
    summary_path = out_dir / "clustering_summary.json"
    geojson_path = out_dir / "clusters_preview.geojson"
    html_map_path = out_dir / "clusters_map.html"

    if not overwrite:
        for target in (parquet_path, summary_path, geojson_path, html_map_path):
            if target.exists():
                raise FileExistsError(
                    f"Output artifact already exists: {target}. Pass overwrite=True to replace."
                )

    write_clustering_parquet(result, parquet_path)
    write_clustering_summary_json(result, summary_path, extra_metadata=extra_metadata)
    write_clustering_geojson_preview(result, geojson_path, max_features=preview_geojson_limit)
    write_static_cluster_map_html(result, html_map_path, max_points=preview_map_limit)

    return {
        "parquet": parquet_path,
        "summary": summary_path,
        "geojson": geojson_path,
        "html_map": html_map_path,
    }
