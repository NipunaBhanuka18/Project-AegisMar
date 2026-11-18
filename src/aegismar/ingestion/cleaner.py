"""Validation, quality policy, and kinematic trajectory cleaning for AIS telemetry."""

from __future__ import annotations

import contextlib
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from aegismar.common.constants import (
    COG_MAX_VALID_DEGREES,
    COG_MIN_DEGREES,
    COG_SENTINEL_DEGREES,
    DEFAULT_IMPLIED_SPEED_THRESHOLD_KNOTS,
    FLAG_COG_SENTINEL_NULLIFIED,
    FLAG_EXACT_DUPLICATE,
    FLAG_HARD_INVALID_BAD_COORDINATES,
    FLAG_HARD_INVALID_BAD_MMSI,
    FLAG_HARD_INVALID_BAD_TIMESTAMP,
    FLAG_HARD_INVALID_MISSING_ID,
    FLAG_HARD_INVALID_NON_FINITE,
    FLAG_HEADING_SENTINEL_NULLIFIED,
    FLAG_IMPLIED_SPEED_VIOLATION,
    FLAG_MISSING_COG,
    FLAG_MISSING_HEADING,
    FLAG_MISSING_SOG,
    FLAG_SOG_SENTINEL_NULLIFIED,
    FLAG_STATUS_SENTINEL_NULLIFIED,
    FLAG_STATUS_UNDEFINED,
    FLAG_TIMESTAMP_METADATA_CONFLICT,
    FLAG_TIMESTAMP_POSITION_CONFLICT,
    FLAG_ZERO_ELAPSED_TIME,
    HEADING_MAX_VALID_DEGREES,
    HEADING_MIN_DEGREES,
    HEADING_SENTINEL_DEGREES,
    LATITUDE_MAX,
    LATITUDE_MIN,
    LONGITUDE_MAX,
    LONGITUDE_MIN,
    SECONDS_PER_HOUR,
    SOG_MAX_VALID_KNOTS,
    SOG_MIN_KNOTS,
    SOG_SENTINEL_KNOTS,
    STATUS_SENTINEL_UNDEFINED,
)
from aegismar.common.types import CanonicalPing
from aegismar.spatial.haversine import haversine_distance_nm


def parse_utc_timestamp(val: Any) -> datetime | None:
    """Parse various timestamp representations into a timezone-aware UTC datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=UTC)
        return val.astimezone(UTC)

    s = str(val).strip()
    if not s:
        return None

    # Handle standard ISO formats: 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DDTHH:MM:SS'
    s_iso = s.replace(" ", "T")
    try:
        dt = datetime.fromisoformat(s_iso)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        pass

    # Try common fallback patterns
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=UTC)
        except ValueError:
            continue

    return None


def sanitize_mmsi(val: Any) -> tuple[str | None, str | None]:
    """Validate and format an integer-format MMSI identifier into a 9-digit string.

    Only pure integer values (`int`, excluding `bool`) or pure ASCII digit strings
    matching the documented NOAA source schema are accepted. Decimal strings
    (e.g., ``'366745490.5'`` or ``'366745490.0'``), floats, signs, or non-digit
    characters are explicitly rejected rather than truncated.

    Returns
    -------
    tuple[str | None, str | None]
        A tuple of (clean_mmsi_str, error_flag). If error_flag is present, clean_mmsi is None.
    """
    if val is None:
        return None, FLAG_HARD_INVALID_MISSING_ID

    if isinstance(val, bool):
        return None, FLAG_HARD_INVALID_BAD_MMSI

    if isinstance(val, int):
        if val <= 0 or val > 999_999_999:
            return None, FLAG_HARD_INVALID_BAD_MMSI
        return f"{val:09d}", None

    if not isinstance(val, str):
        return None, FLAG_HARD_INVALID_BAD_MMSI

    s = val.strip()
    if not s:
        return None, FLAG_HARD_INVALID_MISSING_ID

    if not (s.isascii() and s.isdigit()):
        return None, FLAG_HARD_INVALID_BAD_MMSI

    # Check length and pad leading zeros if valid integer length (1..9 digits)
    if len(s) > 9:
        return None, FLAG_HARD_INVALID_BAD_MMSI

    padded = s.zfill(9)

    # All-zero MMSIs are unassigned / sentinel nulls
    if padded == "000000000":
        return None, FLAG_HARD_INVALID_BAD_MMSI

    return padded, None


class RecordValidator:
    """Validates and cleans individual raw AIS records into CanonicalPing objects."""

    def __init__(
        self, speed_threshold_knots: float = DEFAULT_IMPLIED_SPEED_THRESHOLD_KNOTS
    ) -> None:
        self.speed_threshold_knots = speed_threshold_knots

    def validate_raw_row(
        self,
        source_row: int,
        raw: dict[str, Any],
    ) -> tuple[CanonicalPing | None, str | None]:
        """Validate a single mapped row.

        Returns
        -------
        tuple[CanonicalPing | None, str | None]
            (ping, None) if usable; (None, hard_invalid_flag) if rejected.
        """
        # 1. MMSI Validation
        mmsi, mmsi_err = sanitize_mmsi(raw.get("mmsi"))
        if mmsi_err is not None or mmsi is None:
            return None, mmsi_err or FLAG_HARD_INVALID_MISSING_ID

        # 2. Timestamp Validation
        ts = parse_utc_timestamp(raw.get("timestamp_utc"))
        if ts is None:
            return None, FLAG_HARD_INVALID_BAD_TIMESTAMP

        # 3. Coordinate Validation
        lat_raw = raw.get("latitude")
        lon_raw = raw.get("longitude")
        if lat_raw is None or lon_raw is None or lat_raw == "" or lon_raw == "":
            return None, FLAG_HARD_INVALID_BAD_COORDINATES

        try:
            lat = float(lat_raw)
            lon = float(lon_raw)
        except (ValueError, TypeError):
            return None, FLAG_HARD_INVALID_BAD_COORDINATES

        if not (math.isfinite(lat) and math.isfinite(lon)):
            return None, FLAG_HARD_INVALID_NON_FINITE

        if not (LATITUDE_MIN <= lat <= LATITUDE_MAX and LONGITUDE_MIN <= lon <= LONGITUDE_MAX):
            return None, FLAG_HARD_INVALID_BAD_COORDINATES

        quality_flags: list[str] = []

        # 4. SOG Validation & Sentinel Nullification
        sog_val: float | None = None
        sog_raw = raw.get("sog")
        if sog_raw is None or sog_raw == "":
            quality_flags.append(FLAG_MISSING_SOG)
        else:
            try:
                sog_f = float(sog_raw)
                if not math.isfinite(sog_f):
                    quality_flags.append(FLAG_MISSING_SOG)
                elif (
                    sog_f == SOG_SENTINEL_KNOTS
                    or sog_f > SOG_MAX_VALID_KNOTS
                    or sog_f < SOG_MIN_KNOTS
                ):
                    quality_flags.append(FLAG_SOG_SENTINEL_NULLIFIED)
                else:
                    sog_val = sog_f
            except (ValueError, TypeError):
                quality_flags.append(FLAG_MISSING_SOG)

        # 5. COG Validation & Sentinel Nullification
        cog_val: float | None = None
        cog_raw = raw.get("cog")
        if cog_raw is None or cog_raw == "":
            quality_flags.append(FLAG_MISSING_COG)
        else:
            try:
                cog_f = float(cog_raw)
                if not math.isfinite(cog_f):
                    quality_flags.append(FLAG_MISSING_COG)
                elif (
                    cog_f == COG_SENTINEL_DEGREES
                    or cog_f > COG_MAX_VALID_DEGREES
                    or cog_f < COG_MIN_DEGREES
                ):
                    quality_flags.append(FLAG_COG_SENTINEL_NULLIFIED)
                else:
                    cog_val = cog_f
            except (ValueError, TypeError):
                quality_flags.append(FLAG_MISSING_COG)

        # 6. Heading Validation & Sentinel Nullification
        heading_val: float | None = None
        hdg_raw = raw.get("heading")
        if hdg_raw is None or hdg_raw == "":
            quality_flags.append(FLAG_MISSING_HEADING)
        else:
            try:
                hdg_f = float(hdg_raw)
                if not math.isfinite(hdg_f):
                    quality_flags.append(FLAG_MISSING_HEADING)
                elif (
                    hdg_f == HEADING_SENTINEL_DEGREES
                    or hdg_f > HEADING_MAX_VALID_DEGREES
                    or hdg_f < HEADING_MIN_DEGREES
                ):
                    quality_flags.append(FLAG_HEADING_SENTINEL_NULLIFIED)
                else:
                    heading_val = hdg_f
            except (ValueError, TypeError):
                quality_flags.append(FLAG_MISSING_HEADING)

        # 7. Navigational Status Validation
        status_val: int | None = None
        st_raw = raw.get("nav_status")
        if st_raw is None or st_raw == "":
            quality_flags.append(FLAG_STATUS_UNDEFINED)
        else:
            try:
                st_i = int(float(st_raw))
                if st_i == STATUS_SENTINEL_UNDEFINED or st_i < 0 or st_i > 15:
                    quality_flags.append(FLAG_STATUS_SENTINEL_NULLIFIED)
                else:
                    status_val = st_i
            except (ValueError, TypeError):
                quality_flags.append(FLAG_STATUS_UNDEFINED)

        # 8. Optional Vessel Metadata
        vessel_type_val: int | None = None
        vt_raw = raw.get("vessel_type")
        if vt_raw is not None and vt_raw != "":
            with contextlib.suppress(ValueError, TypeError):
                vessel_type_val = int(float(vt_raw))

        vessel_name = str(raw["vessel_name"]).strip() if raw.get("vessel_name") else None
        imo = str(raw["imo"]).strip() if raw.get("imo") else None
        call_sign = str(raw["call_sign"]).strip() if raw.get("call_sign") else None
        transceiver = (
            str(raw["transceiver_class"]).strip() if raw.get("transceiver_class") else None
        )

        ping = CanonicalPing(
            source_row=source_row,
            mmsi=mmsi,
            timestamp_utc=ts,
            latitude=lat,
            longitude=lon,
            sog=sog_val,
            cog=cog_val,
            heading=heading_val,
            nav_status=status_val,
            vessel_type=vessel_type_val,
            vessel_name=vessel_name,
            imo=imo,
            call_sign=call_sign,
            transceiver_class=transceiver,
            quality_flags=quality_flags,
        )
        return ping, None


def _full_record_dedup_key(ping: CanonicalPing) -> tuple[Any, ...]:
    """Return full-record equality key for exact duplicate detection.

    Deduplication requires full-record equality across spatial coordinates,
    kinematic fields, navigational status, and vessel metadata so that
    conflicting metadata at the same vessel-position-timestamp is never
    silently discarded.
    """
    return (
        ping.latitude,
        ping.longitude,
        ping.sog,
        ping.cog,
        ping.heading,
        ping.nav_status,
        ping.vessel_type,
        ping.vessel_name,
        ping.imo,
        ping.call_sign,
        ping.transceiver_class,
    )


def process_and_clean_observations(
    raw_rows: list[dict[str, Any]],
    speed_threshold_knots: float = DEFAULT_IMPLIED_SPEED_THRESHOLD_KNOTS,
) -> tuple[list[CanonicalPing], dict[str, Any]]:
    """Clean, deduplicate, sort, and validate implied speeds across AIS observations.

    Duplicate and conflict policy:
    - Exact duplicates are defined by full-record equality across coordinates,
      kinematics, status, and vessel metadata for the same ``(mmsi, timestamp_utc)``.
      Exact duplicates are consolidated into the lowest-``source_row`` observation
      tagged with ``EXACT_DUPLICATE``.
    - Same-``(mmsi, timestamp_utc)`` observations with differing coordinates are
      all retained for investigation and tagged with ``TIMESTAMP_POSITION_CONFLICT``.
    - Same-``(mmsi, timestamp_utc)`` observations with identical coordinates but
      differing kinematics or metadata are all retained and tagged with
      ``TIMESTAMP_METADATA_CONFLICT`` rather than silently discarding metadata.
    - Conflicting same-timestamp observations do not produce fictitious zero-time
      movement estimates (``prev_source_row``, ``elapsed_seconds``, ``distance_nm``,
      and ``implied_speed_knots`` remain ``None``).

    Parameters
    ----------
    raw_rows : list[dict[str, Any]]
        List of raw dictionaries with mapped canonical field names.
    speed_threshold_knots : float
        Implied speed threshold for flagging kinematic anomalies.

    Returns
    -------
    tuple[list[CanonicalPing], dict[str, Any]]
        (sorted_cleaned_pings, accounting_summary_dict)
    """
    validator = RecordValidator(speed_threshold_knots=speed_threshold_knots)
    valid_pings: list[CanonicalPing] = []
    hard_invalid_counts: Counter[str] = Counter()

    for idx, row in enumerate(raw_rows, start=1):
        ping, err = validator.validate_raw_row(source_row=idx, raw=row)
        if err is not None:
            hard_invalid_counts[err] += 1
        elif ping is not None:
            valid_pings.append(ping)

    # 1. Group observations by vessel (MMSI)
    vessels_dict: dict[str, list[CanonicalPing]] = defaultdict(list)
    for p in valid_pings:
        vessels_dict[p.mmsi].append(p)

    final_cleaned_pings: list[CanonicalPing] = []
    exact_duplicate_count = 0
    conflict_count = 0
    metadata_conflict_count = 0
    all_quality_flags: Counter[str] = Counter()

    # 2. Process each vessel trajectory independently
    for _mmsi, pings in vessels_dict.items():
        # Sort trajectory deterministically by (timestamp_utc, source_row)
        pings.sort(key=lambda p: (p.timestamp_utc, p.source_row))

        # Check for same-timestamp groups
        deduped_trajectory: list[CanonicalPing] = []
        i = 0
        while i < len(pings):
            curr = pings[i]
            same_ts_group = [curr]
            j = i + 1
            while j < len(pings) and pings[j].timestamp_utc == curr.timestamp_utc:
                same_ts_group.append(pings[j])
                j += 1

            if len(same_ts_group) == 1:
                deduped_trajectory.append(curr)
            else:
                # Step 2a: Collapse exact full-record duplicates deterministically
                unique_by_payload: dict[tuple[Any, ...], list[CanonicalPing]] = {}
                for p in same_ts_group:
                    unique_by_payload.setdefault(_full_record_dedup_key(p), []).append(p)

                unique_records: list[CanonicalPing] = []
                for payload_group in unique_by_payload.values():
                    rep = payload_group[0]
                    if len(payload_group) > 1:
                        rep.quality_flags.append(FLAG_EXACT_DUPLICATE)
                        exact_duplicate_count += len(payload_group) - 1
                    unique_records.append(rep)

                unique_records.sort(key=lambda p: p.source_row)

                # Step 2b: Classify remaining distinct records at the identical timestamp
                if len(unique_records) == 1:
                    deduped_trajectory.append(unique_records[0])
                else:
                    first_coord = (unique_records[0].latitude, unique_records[0].longitude)
                    all_same_coord = all(
                        (p.latitude, p.longitude) == first_coord for p in unique_records
                    )
                    if all_same_coord:
                        metadata_conflict_count += len(unique_records)
                        for p in unique_records:
                            p.quality_flags.append(FLAG_TIMESTAMP_METADATA_CONFLICT)
                            deduped_trajectory.append(p)
                    else:
                        conflict_count += len(unique_records)
                        for p in unique_records:
                            p.quality_flags.append(FLAG_TIMESTAMP_POSITION_CONFLICT)
                            deduped_trajectory.append(p)

            i = j

        # 3. Calculate implied speeds between consecutive unambiguous observations
        last_unambiguous_ping: CanonicalPing | None = None
        for k, current_ping in enumerate(deduped_trajectory):
            is_conflict = (
                FLAG_TIMESTAMP_POSITION_CONFLICT in current_ping.quality_flags
                or FLAG_TIMESTAMP_METADATA_CONFLICT in current_ping.quality_flags
            )

            if (
                k > 0
                and (
                    current_ping.timestamp_utc - deduped_trajectory[k - 1].timestamp_utc
                ).total_seconds()
                == 0.0
            ):
                current_ping.quality_flags.append(FLAG_ZERO_ELAPSED_TIME)

            if is_conflict:
                # Conflicting same-timestamp observations must not generate
                # fictitious zero-time movement estimates.
                current_ping.prev_source_row = None
                current_ping.elapsed_seconds = None
                current_ping.distance_nm = None
                current_ping.implied_speed_knots = None
            else:
                if last_unambiguous_ping is not None:
                    dt_sec = (
                        current_ping.timestamp_utc - last_unambiguous_ping.timestamp_utc
                    ).total_seconds()
                    current_ping.prev_source_row = last_unambiguous_ping.source_row
                    current_ping.elapsed_seconds = dt_sec

                    if dt_sec > 0.0:
                        dist_nm = haversine_distance_nm(
                            last_unambiguous_ping.latitude,
                            last_unambiguous_ping.longitude,
                            current_ping.latitude,
                            current_ping.longitude,
                        )
                        current_ping.distance_nm = dist_nm
                        hours = dt_sec / SECONDS_PER_HOUR
                        speed_kt = dist_nm / hours
                        current_ping.implied_speed_knots = speed_kt

                        if speed_kt > speed_threshold_knots:
                            current_ping.quality_flags.append(FLAG_IMPLIED_SPEED_VIOLATION)

                last_unambiguous_ping = current_ping

            # Record quality flags for accounting
            for flag in current_ping.quality_flags:
                all_quality_flags[flag] += 1

            final_cleaned_pings.append(current_ping)

    # 4. Final deterministic sort across the entire dataset: (mmsi, timestamp_utc, source_row)
    final_cleaned_pings.sort(key=lambda p: (p.mmsi, p.timestamp_utc, p.source_row))

    summary: dict[str, Any] = {
        "input_rows": len(raw_rows),
        "accepted_rows": len(final_cleaned_pings),
        "hard_invalid_total": sum(hard_invalid_counts.values()),
        "hard_invalid_breakdown": dict(hard_invalid_counts),
        "exact_duplicates_consolidated": exact_duplicate_count,
        "timestamp_conflicts_flagged": conflict_count,
        "metadata_conflicts_flagged": metadata_conflict_count,
        "quality_flag_totals": dict(all_quality_flags),
        "unique_mmsis": len(vessels_dict),
    }

    return final_cleaned_pings, summary
