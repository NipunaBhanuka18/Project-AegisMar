"""Stream-decompress a NOAA AIS .csv.zst daily extract and slice a lat/lon bounding box.

Rows inside the inclusive box are copied byte-for-byte (header included) so the
output preserves the original NOAA formatting. Requires only pyarrow (zstd codec);
no new dependency. Prints row/vessel counts and the output SHA-256 for verification.

Usage (San Pedro Bay study region):
    uv run python scripts/slice_noaa_bbox.py data/raw/ais-2025-01-01.csv.zst \
        data/raw/sample_lalb_20250101.csv --lat 33.5 33.9 --lon -118.4 -118.0

Verified 2026-11-23: reproduces the documented 2025-01-01 sample exactly
(143,156 rows, 362 MMSIs, SHA-256 42e4f766feb98b20e98124685137bcc2be16a20c06dda46e33f415f0b281eac8).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
from pathlib import Path

import pyarrow as pa


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--lat", nargs=2, type=float, required=True, metavar=("MIN", "MAX"))
    ap.add_argument("--lon", nargs=2, type=float, required=True, metavar=("MIN", "MAX"))
    args = ap.parse_args()
    lat_min, lat_max = args.lat
    lon_min, lon_max = args.lon

    total = kept = bad = 0
    mmsis: set[str] = set()
    h = hashlib.sha256()

    with pa.CompressedInputStream(pa.OSFile(str(args.input), "rb"), "zstd") as raw:
        reader = io.BufferedReader(raw, buffer_size=1 << 22)
        header_bytes = reader.readline()
        header = next(csv.reader([header_bytes.decode("utf-8")]))
        cols = {name.strip(): i for i, name in enumerate(header)}
        lat_key = next(k for k in ("latitude", "LAT") if k in cols)
        lon_key = next(k for k in ("longitude", "LON") if k in cols)
        mmsi_key = next(k for k in ("mmsi", "MMSI") if k in cols)
        i_lat, i_lon, i_mmsi = cols[lat_key], cols[lon_key], cols[mmsi_key]
        print(f"header: {header}", file=sys.stderr)

        with open(args.output, "wb") as out:
            out.write(header_bytes)
            h.update(header_bytes)
            for line in reader:
                total += 1
                try:
                    row = next(csv.reader([line.decode("utf-8")]))
                    lat = float(row[i_lat])
                    lon = float(row[i_lon])
                except (ValueError, IndexError, StopIteration):
                    bad += 1
                    continue
                if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                    out.write(line)
                    h.update(line)
                    kept += 1
                    mmsis.add(row[i_mmsi].strip())

    print(f"input data rows : {total:,}")
    print(f"unparseable     : {bad:,}")
    print(f"rows kept       : {kept:,}")
    print(f"unique MMSI     : {len(mmsis):,}")
    print(f"output sha256   : {h.hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
