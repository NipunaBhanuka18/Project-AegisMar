"""Typed, validated configuration models for ST-DBSCAN spatiotemporal clustering."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from aegismar.common.constants import (
    FLAG_IMPLIED_SPEED_VIOLATION,
    FLAG_TIMESTAMP_METADATA_CONFLICT,
    FLAG_TIMESTAMP_POSITION_CONFLICT,
)
from aegismar.spatial.haversine import EARTH_RADIUS_METERS

# Illustrative baseline defaults for exploratory experiments (not globally optimal settings)
DEFAULT_EPS_SPATIAL_M: float = 300.0
DEFAULT_EPS_TEMPORAL_S: float = 900.0
DEFAULT_MIN_SAMPLES: int = 5
ALGORITHM_VERSION: str = "stdbscan-core-first-v1.0"

# Neighborhood provider identifiers
PROVIDER_BALLTREE: str = "balltree_haversine"
PROVIDER_H3: str = "h3_haversine"
SUPPORTED_PROVIDERS: tuple[str, ...] = (PROVIDER_BALLTREE, PROVIDER_H3)

# H3 spatial indexing configuration defaults
DEFAULT_H3_RESOLUTION: int = 8
SUPPORTED_H3_RESOLUTIONS: tuple[int, ...] = (7, 8, 9)
SUPPORTED_CALIBRATED_H3_RESOLUTIONS: tuple[int, ...] = (7, 8, 9)

# Maximum valid great-circle distance on a sphere of radius EARTH_RADIUS_METERS
MAX_SPATIAL_RADIUS_M: float = math.pi * EARTH_RADIUS_METERS


@dataclass(frozen=True, slots=True)
class QualityFilterPolicy:
    """Deterministic analysis-input quality filtering policy applied before clustering.

    Attributes
    ----------
    exclude_timestamp_conflicts : bool
        If True (default), exclude observations tagged with
        ``TIMESTAMP_POSITION_CONFLICT`` or ``TIMESTAMP_METADATA_CONFLICT``.
        Conflicting records remain preserved in the canonical ingestion Parquet
        dataset for auditability and data-quality investigation.
    exclude_implied_speed_violations : bool
        If True, exclude observations tagged with ``IMPLIED_SPEED_VIOLATION``.
        Defaults to False so high-speed anomalies remain inspectable unless
        explicitly filtered.
    excluded_flags : tuple[str, ...]
        Additional custom quality flag names to exclude deterministically.
    """

    exclude_timestamp_conflicts: bool = True
    exclude_implied_speed_violations: bool = False
    excluded_flags: tuple[str, ...] = ()

    def effective_excluded_flags(self) -> frozenset[str]:
        """Return the complete immutable set of quality flags excluded by this policy."""
        flags: set[str] = set(self.excluded_flags)
        if self.exclude_timestamp_conflicts:
            flags.add(FLAG_TIMESTAMP_POSITION_CONFLICT)
            flags.add(FLAG_TIMESTAMP_METADATA_CONFLICT)
        if self.exclude_implied_speed_violations:
            flags.add(FLAG_IMPLIED_SPEED_VIOLATION)
        return frozenset(flags)

    def to_dict(self) -> dict[str, Any]:
        """Serialize policy configuration for experiment provenance."""
        return {
            "exclude_timestamp_conflicts": self.exclude_timestamp_conflicts,
            "exclude_implied_speed_violations": self.exclude_implied_speed_violations,
            "excluded_flags": sorted(self.effective_excluded_flags()),
        }


@dataclass(frozen=True, slots=True)
class STDBSCANConfig:
    """Validated parameter configuration for reference and accelerated ST-DBSCAN.

    Uses meters for spatial distance and seconds for temporal distance internally.
    Spatial radius is converted to radians via ``eps_spatial_m / EARTH_RADIUS_METERS``
    for ``scikit-learn`` Haversine ``BallTree`` queries.

    Attributes
    ----------
    eps_spatial_m : float
        Spatial neighborhood radius in meters (strictly positive, <= pi * R_earth).
    eps_temporal_s : float
        Temporal neighborhood threshold in seconds (strictly positive).
    min_samples : int
        Minimum number of eligible observations in a neighborhood (including the
        observation itself) required for core-point status (>= 1).
    quality_filter : QualityFilterPolicy
        Deterministic pre-clustering quality filtering policy.
    algorithm_version : str
        Semantic version tag for the clustering specification.
    """

    eps_spatial_m: float = DEFAULT_EPS_SPATIAL_M
    eps_temporal_s: float = DEFAULT_EPS_TEMPORAL_S
    min_samples: int = DEFAULT_MIN_SAMPLES
    provider: str = PROVIDER_BALLTREE
    h3_resolution: int = DEFAULT_H3_RESOLUTION
    h3_k_ring: int | None = None
    h3_enable_fallback: bool = True
    h3_fallback_on_pentagons: bool = False
    h3_allow_uncalibrated: bool = False
    quality_filter: QualityFilterPolicy = field(default_factory=QualityFilterPolicy)
    algorithm_version: str = ALGORITHM_VERSION

    def __post_init__(self) -> None:
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"provider must be one of {SUPPORTED_PROVIDERS}, got {self.provider!r}"
            )

        if isinstance(self.h3_resolution, bool) or not isinstance(self.h3_resolution, int):
            raise ValueError(f"h3_resolution must be an integer, got {self.h3_resolution!r}")
        if not (0 <= self.h3_resolution <= 15):
            raise ValueError(f"h3_resolution must be between 0 and 15, got {self.h3_resolution}")

        if not isinstance(self.h3_enable_fallback, bool):
            raise ValueError(
                f"h3_enable_fallback must be a boolean, got {self.h3_enable_fallback!r}"
            )
        if not isinstance(self.h3_fallback_on_pentagons, bool):
            raise ValueError(
                f"h3_fallback_on_pentagons must be a boolean, got {self.h3_fallback_on_pentagons!r}"
            )
        if not isinstance(self.h3_allow_uncalibrated, bool):
            raise ValueError(
                f"h3_allow_uncalibrated must be a boolean, got {self.h3_allow_uncalibrated!r}"
            )

        if self.h3_k_ring is not None and (
            isinstance(self.h3_k_ring, bool)
            or not isinstance(self.h3_k_ring, int)
            or self.h3_k_ring < 1
        ):
            raise ValueError(f"h3_k_ring must be None or an integer >= 1, got {self.h3_k_ring!r}")

        if isinstance(self.eps_spatial_m, bool) or not isinstance(self.eps_spatial_m, (int, float)):
            raise ValueError(
                f"eps_spatial_m must be a finite positive number, got {self.eps_spatial_m!r}"
            )
        if not math.isfinite(self.eps_spatial_m) or self.eps_spatial_m <= 0.0:
            raise ValueError(
                f"eps_spatial_m must be finite and strictly positive, got {self.eps_spatial_m!r}"
            )
        if self.eps_spatial_m > MAX_SPATIAL_RADIUS_M:
            raise ValueError(
                f"eps_spatial_m ({self.eps_spatial_m}) exceeds half Earth circumference "
                f"({MAX_SPATIAL_RADIUS_M:.2f} m)"
            )

        if isinstance(self.eps_temporal_s, bool) or not isinstance(
            self.eps_temporal_s, (int, float)
        ):
            raise ValueError(
                f"eps_temporal_s must be a finite positive number, got {self.eps_temporal_s!r}"
            )
        if not math.isfinite(self.eps_temporal_s) or self.eps_temporal_s <= 0.0:
            raise ValueError(
                f"eps_temporal_s must be finite and strictly positive, got {self.eps_temporal_s!r}"
            )

        if isinstance(self.min_samples, bool) or not isinstance(self.min_samples, int):
            raise ValueError(f"min_samples must be an integer >= 1, got {self.min_samples!r}")
        if self.min_samples < 1:
            raise ValueError(f"min_samples must be >= 1, got {self.min_samples}")

    @property
    def eps_spatial_rad(self) -> float:
        """Convert spatial radius in meters into radians on the mean spherical Earth."""
        return float(self.eps_spatial_m) / EARTH_RADIUS_METERS

    @property
    def eps_temporal_us(self) -> float:
        """Convert temporal threshold in seconds into microseconds."""
        return float(self.eps_temporal_s) * 1_000_000.0

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable configuration dictionary."""
        return {
            "provider": self.provider,
            "eps_spatial_m": float(self.eps_spatial_m),
            "eps_spatial_rad": self.eps_spatial_rad,
            "eps_temporal_s": float(self.eps_temporal_s),
            "min_samples": self.min_samples,
            "h3_resolution": self.h3_resolution,
            "h3_k_ring": self.h3_k_ring,
            "h3_enable_fallback": self.h3_enable_fallback,
            "h3_fallback_on_pentagons": self.h3_fallback_on_pentagons,
            "h3_allow_uncalibrated": self.h3_allow_uncalibrated,
            "quality_filter": self.quality_filter.to_dict(),
            "algorithm_version": self.algorithm_version,
        }
