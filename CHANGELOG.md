# Changelog

All notable changes to Project AegisMar will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> [!NOTE]
> Project AegisMar is currently in pre-alpha research and MVP development. Documentation versioning adheres to the v2.1 solo MVP baseline, while package implementation starts at `0.1.0.dev1`.

## [Unreleased]

### Added - Milestone W1-01 (2026-11-14)
- **Repository Setup**: Initialized Git repository structure with Python-first modular monolith layout (`src/aegismar`).
- **Toolchain & Packaging**: Configured `pyproject.toml` using `hatchling` build backend and pinned CPython `3.11.9` with `uv` package manager.
- **Quality Gates**: Configured Ruff (linting and formatting), Mypy (strict static type checking), and Pytest with initial smoke tests (`tests/test_smoke.py`).
- **Data Protection**: Established strict `.gitignore` rules preventing tracking of raw/processed AIS datasets, caches, virtual environments, and benchmark outputs, while preserving test fixtures.
- **Documentation Architecture**:
  - `docs/01-project/`: Vision, BRS (Draft v2.1), SRS (Draft v2.1), Scope breakdown, and 8-week Roadmap.
  - `docs/02-architecture/`: System Architecture and ADR-001 (Modular Monolith Decision).
  - `docs/03-research/`: Research Plan (H3 vs BallTree ST-DBSCAN), Evaluation Protocol, and Dataset Strategy.
  - `docs/04-development/`: Milestones, Development Log, and Testing Strategy.
  - `docs/05-guides/`: Developer Installation Guide.
  - Root `README.md` linking the entire documentation tree.

