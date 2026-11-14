"""Exact geodesic distance calculations using the Haversine formula."""

from __future__ import annotations

import math
from collections.abc import Sequence

from aegismar.common.constants import METERS_PER_NAUTICAL_MILE

EARTH_RADIUS_METERS: float = 6371008.8


def haversine_distance_meters(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Calculate the great-circle distance between two geographic coordinates in meters.

    Parameters
    ----------
    lat1 : float
        Latitude of first point in decimal degrees.
    lon1 : float
        Longitude of first point in decimal degrees.
    lat2 : float
        Latitude of second point in decimal degrees.
    lon2 : float
        Longitude of second point in decimal degrees.

    Returns
    -------
    float
        Geodesic distance across spherical Earth in meters.
    """
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    sin_half_dphi = math.sin(delta_phi / 2.0)
    sin_half_dlambda = math.sin(delta_lambda / 2.0)

    a = (sin_half_dphi * sin_half_dphi) + (
        math.cos(phi1) * math.cos(phi2) * (sin_half_dlambda * sin_half_dlambda)
    )
    # Clamp to [0.0, 1.0] against precision roundoff
    clamped_a = max(0.0, min(1.0, a))
    c = 2.0 * math.atan2(math.sqrt(clamped_a), math.sqrt(1.0 - clamped_a))

    return EARTH_RADIUS_METERS * c


def haversine_distance_nm(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Calculate the great-circle distance between two geographic coordinates in nautical miles."""
    meters = haversine_distance_meters(lat1, lon1, lat2, lon2)
    return meters / METERS_PER_NAUTICAL_MILE


def haversine_vector_meters(
    lats1: Sequence[float],
    lons1: Sequence[float],
    lats2: Sequence[float],
    lons2: Sequence[float],
) -> list[float]:
    """Calculate pairwise haversine distances for coordinate sequences."""
    return [
        haversine_distance_meters(lat1, lon1, lat2, lon2)
        for lat1, lon1, lat2, lon2 in zip(lats1, lons1, lats2, lons2, strict=True)
    ]
