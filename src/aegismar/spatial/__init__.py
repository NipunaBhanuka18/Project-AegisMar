"""Spatial calculation and indexing package for AegisMar."""

from __future__ import annotations

from aegismar.spatial.haversine import (
    EARTH_RADIUS_METERS,
    haversine_distance_meters,
    haversine_distance_nm,
    haversine_vector_meters,
)

__all__ = [
    "EARTH_RADIUS_METERS",
    "haversine_distance_meters",
    "haversine_distance_nm",
    "haversine_vector_meters",
]
