"""Entry point for python -m aegismar execution."""

from __future__ import annotations

import sys

from aegismar.cli import main

if __name__ == "__main__":
    sys.exit(main())
