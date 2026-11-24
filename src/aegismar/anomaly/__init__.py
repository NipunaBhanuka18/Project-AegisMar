"""Track B: vessel behavior feature engineering and anomaly detection.

Implements ``docs/03-research/ml-02-feature-spec.md`` (features) and the partition part of
``docs/03-research/ml-03-evaluation-protocol.md`` (evaluation). Scoring models arrive in ML-05.
"""

from aegismar.anomaly.evaluation import (
    TEST_DAYS,
    TestDayFirewallError,
    VesselPartition,
    check_test_day_firewall,
    dataset_days,
    split_vessels,
    vessel_group,
)
from aegismar.anomaly.features import (
    FEATURE_SPEC_VERSION,
    PAIR_FEATURE_COLUMNS,
    WINDOW_FEATURE_COLUMNS,
    FeatureResult,
    Observations,
    angdiff,
    assign_segments,
    build_windows,
    compute_pair_features,
    destination_point,
    detect_outage_windows,
    extract_features,
    fit_expected_intervals,
    haversine_m,
    outage_overlap_s,
    prepare_observations,
    sangdiff,
)

__all__ = [
    "FEATURE_SPEC_VERSION",
    "PAIR_FEATURE_COLUMNS",
    "TEST_DAYS",
    "WINDOW_FEATURE_COLUMNS",
    "FeatureResult",
    "Observations",
    "TestDayFirewallError",
    "VesselPartition",
    "angdiff",
    "assign_segments",
    "build_windows",
    "check_test_day_firewall",
    "compute_pair_features",
    "dataset_days",
    "destination_point",
    "detect_outage_windows",
    "extract_features",
    "fit_expected_intervals",
    "haversine_m",
    "outage_overlap_s",
    "prepare_observations",
    "sangdiff",
    "split_vessels",
    "vessel_group",
]
