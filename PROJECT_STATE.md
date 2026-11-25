# Project AegisMar — Live State Pointer

> **Dated Snapshot — Verify Before Acting**
> Last verified: `2026-11-25` | Verified `origin/main` SHA: `c468fd14ea34b45d9c9c1b148bc3b486ae188953`
> Re-check `git status`, `origin/main`, open PRs, reviews, and checks at the start of every session. Update this file only on milestone completion or PR merges.

## Authoritative Documentation
- Overview & onboarding: `README.md`, `docs/START-HERE.md`
- Ownership & workflow: `CONTRIBUTING.md`, `docs/01-project/collaboration-plan.md`
- Roadmap & milestones: `docs/01-project/roadmap.md`, `docs/04-development/milestones.md`
- Architecture & ADRs: `docs/02-architecture/system-architecture.md`, `docs/02-architecture/decisions/README.md`
- Research & evidence: `docs/03-research/evaluation-protocol.md`, `docs/03-research/evidence-register.md`, `docs/03-research/datasets.md`
- Track B specs: `docs/03-research/vessel-behavior-ml.md`, `docs/03-research/ml-02-feature-spec.md`, `docs/03-research/ml-03-evaluation-protocol.md`
- Quality gates: `docs/04-development/testing-strategy.md`

## Current Baseline
- **Merged Track A:** AIS ingestion (`W2-01` cleaner), BallTree reference ST-DBSCAN + brute-force oracle, H3 Option B acceleration & parity contract (`W3-01` / `W3-01A` / `W3-01B`, PR #1 `fafa282`).
- **Merged Track B:** `ML-01` profiling (PR #2 `87b9845`), `ML-02` feature spec (PR #3 `c4b9344`), `ML-03` evaluation protocol (PR #4 `b26b319`), Track B doc sync (PR #5 `c088ee4`), `ML-04` trajectory features (PR #6 `95b7e50`).
- **Open PRs:** Check GitHub live (as of `2026-11-25` at `c468fd1`: none open).
- **CI Status:** `.github/workflows/ci.yml` (PR #9) runs ruff, ruff format, mypy and pytest with coverage ≥ 85% on pushes and PRs to `main`; GitGuardian also runs on PRs.

## Dataset Provenance (LA/LB San Pedro Bay, NOAA 2025-01-01)
- **Raw extract (`data/raw/sample_lalb_20250101.csv`):** Verified SHA-256 `42e4f766feb98b20e98124685137bcc2be16a20c06dda46e33f415f0b281eac8` (143,156 rows).
- **Historical v1.0 Parquet (`data/processed/lalb_20250101/cleaned_ais.parquet`):** **IMMUTABLE — DO NOT OVERWRITE.** Verified SHA-256 `4a7ca719dc2a3d9959cc4166edff773ca09156d8d914e54d0ab5f851ece5e88b` (143,124 rows; sorted `(mmsi, timestamp_utc, source_row)`; generated Nov 14 22:34 prior to W2-01 hardening `3ece859`).
- **Canonical v1.1 Parquet (`data/processed/lalb_20250101_v1_1/cleaned_ais.parquet`):** **CANONICAL for Track A (from W3-02) and Track B — DO NOT OVERWRITE.** File SHA-256 `bdde2581302270a9e2c99a1a7aa1819a0bd1a24fbf6384458cfd8a81229eaf48`, logical fingerprint `d8a619f7d27314ae8418eff5da8e1c5c96004d038c2fce8f5ee868ed90fec2cf`. Reproduced byte-for-byte on both workstations; v1.0 fingerprint `570b0fb09182720fc476b4b712c0d599bed3ed34491aad4946719fab965a1473`. The versions differ only in 12 rows of derived kinematic columns; clustering inputs are bit-identical (`evidence-register.md` §2.1, `CLM-ING-07`/`CLM-ING-08`).

## Active Next Gate
1. **Track A Next Milestone — `W3-02A` (Dataset Provenance & Deterministic Fingerprinting):** Authoritative provenance in `manifest.json` (no new Parquet footer metadata), separate file-byte SHA-256 vs. order-sensitive versioned logical content fingerprint, read-only CLI, tests, and scoped docs.
2. **Post-`W3-02A`:** *(Done 2026-11-25)* Corrected Parquet regenerated into `lalb_20250101_v1_1/`, hash and row-level diff verified against v1.0, `evidence-register.md` reconciled (v1.1 canonical).
3. **Before `W3-02` Benchmarking:** Resolve `evaluation-protocol.md` §2.3 contradictions (separate memory vs. timing runs, scale tiers `10k/50k/100k/full`, fair timing boundaries).
