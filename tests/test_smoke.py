"""Smoke tests for Project AegisMar package initialization and environment sanity."""

from __future__ import annotations

import sys

import aegismar


def test_package_import() -> None:
    """Verify that aegismar package imports cleanly and exposes __version__."""
    assert hasattr(aegismar, "__version__")
    assert isinstance(aegismar.__version__, str)
    assert aegismar.__version__ == "0.1.0.dev1"


def test_python_runtime_version() -> None:
    """Verify that execution is running on Python 3.11 as specified in environment pinning."""
    major, minor = sys.version_info[:2]
    assert (major, minor) == (3, 11), f"Expected Python 3.11, running on {major}.{minor}"
