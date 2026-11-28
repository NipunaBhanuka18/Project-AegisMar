# Project AegisMar — Live State Pointer

> **Dated Snapshot — Verify Before Acting**
> Last verified: `2026-11-28` | Verified `main` / `origin/main` SHA: `379ec16b763b005ce40808d7bbfc28940a140d89`
> Re-check `git status`, `origin/main`, open PRs, reviews, and checks at the start of every session. Update this file only on milestone completion or PR merges.

## Authoritative Documentation
- Overview & onboarding: `README.md`, `docs/START-HERE.md`
- Ownership & workflow: `CONTRIBUTING.md`, `docs/01-project/collaboration-plan.md`
- Roadmap & milestones: `docs/01-project/roadmap.md`, `docs/04-development/milestones.md`
- Architecture & ADRs: `docs/02-architecture/system-architecture.md`, `docs/02-architecture/decisions/README.md`
- Research & evidence: `docs/03-research/evaluation-protocol.md`, `docs/03-research/evidence-register.md`, `docs/03-research/datasets.md`
- W3-02 benchmark: `docs/03-research/w3-02-benchmark-protocol.md` (locked protocol), `docs/03-research/w3-02-benchmark-results.md` (executed results)
- Track B specs: `docs/03-research/vessel-behavior-ml.md`, `docs/03-research/ml-02-feature-spec.md`, `docs/03-research/ml-03-evaluation-protocol.md`
- Quality gates: `docs/04-development/testing-strategy.md`

## Current Baseline
- **Merged Track A:**
  - AIS ingestion (`W2-01` cleaner), BallTree reference ST-DBSCAN and brute-force oracle.
  - H3 Option B acceleration and parity contract (`W3-01` / `W3-01A` / `W3-01B`, PR #1 `fafa282`).
  - Dataset provenance and logical fingerprinting (`W3-02A`, PR #8 `7d2d114`).
  - GitHub Actions CI quality gates (PR #9 `2394855`).
  - W3-02 benchmark harness and locked protocol (PR #10 `c468fd1`).
- **Merged Track B:** `ML-01` profiling (PR #2 `87b9845`), `ML-02` feature spec (PR #3 `c4b9344`), `ML-03` evaluation protocol (PR #4 `b26b319`; amended to v1.2 in PR #13 `379ec16`), Track B doc sync (PR #5 `c088ee4`), `ML-04` trajectory features (PR #6 `95b7e50`).
- **Merged shared/docs:** agent continuity (PR #7 `dea008a`), canonical dataset v1.1 reconciliation and safe ingest commands (PR #11 `f7c475b`).
- **Merged PRs:** #1–#11 and #13.
- **Open PRs:** Check GitHub live. As of `2026-11-28`: PR #12 `feat/ml-05-perturbation-harness` (Track B ML-05), **draft**, not merged.
- **CI Status:** `.github/workflows/ci.yml` (PR #9) runs on pushes and PRs to `main`: ruff, ruff format, mypy, and pytest with coverage ≥ 85% (`--cov-fail-under=85`). GitGuardian also runs on PRs. Latest `main` push run (run 46139007832, `379ec16`): **success**. Local check at `379ec16`: 183 tests, 96% coverage.

## Dataset Provenance (LA/LB San Pedro Bay, NOAA 2025-01-01)
- **Raw extract (`data/raw/sample_lalb_20250101.csv`):** Verified SHA-256 `42e4f766feb98b20e98124685137bcc2be16a20c06dda46e33f415f0b281eac8` (143,156 rows).
- **Historical v1.0 Parquet (`data/processed/lalb_20250101/cleaned_ais.parquet`):** **IMMUTABLE — DO NOT OVERWRITE.**
  - File SHA-256 `4a7ca719dc2a3d9959cc4166edff773ca09156d8d914e54d0ab5f851ece5e88b`, logical fingerprint `570b0fb09182720fc476b4b712c0d599bed3ed34491aad4946719fab965a1473`.
  - 143,124 rows, sorted `(mmsi, timestamp_utc, source_row)`.
  - Generated Nov 14 22:34, before the W2-01 hardening `3ece859`.
  - The file SHA-256 was re-verified on disk on 2026-11-28.
- **Canonical v1.1 Parquet (`data/processed/lalb_20250101_v1_1/cleaned_ais.parquet`):** **CANONICAL for Track A (from W3-02) and Track B — DO NOT OVERWRITE.**
  - File SHA-256 `bdde2581302270a9e2c99a1a7aa1819a0bd1a24fbf6384458cfd8a81229eaf48`, logical fingerprint `d8a619f7d27314ae8418eff5da8e1c5c96004d038c2fce8f5ee868ed90fec2cf`.
  - Reproduced byte-for-byte on both workstations.
  - Re-verified on 2026-11-28 by the W3-02 harness (file hash, fingerprint, canonical order and sibling-manifest agreement).
  - The versions differ only in 12 rows of derived kinematic columns, and clustering inputs are bit-identical (`evidence-register.md` §2.1, `CLM-ING-07`/`CLM-ING-08`).

## Week 3 Completion Summary (Track A)
- **W3-02A (PR #8):** `manifest.json` provenance, canonical row-order verification, `aegismar-logical-v1` fingerprint, and the read-only `aegismar fingerprint` CLI (ADR-011).
- **W3-02 run:** 2026-11-28 at `379ec16`, `git_dirty=false`, on canonical v1.1, with `status = "completed"`.
- **W3-02 correctness:** H3 r7, r8 and r9 match BallTree exactly at 10k / 50k / 100k / full, and all four engines match the 2,000-row brute-force oracle. Recall = precision = ARI = 1.0, with 0 fallbacks.
- **W3-02 runtime:** H3 r8 (total time) is 0.773× at 10k, 0.908× at 50k, 1.004× at 100k (parity) and **1.150×** at full scale (12.4074 s vs 10.7867 s). r7 and r9 are slower than BallTree at all scales.
- **W3-02 memory:** full-scale `tracemalloc` peaks are 225.8 MiB (BallTree) and 233.8 MiB (H3 r8).
- **Write-up:** `w3-02-benchmark-results.md`, recorded as evidence claim `CLM-CLU-07`.
- The 2026-11-25 next-gate items (W3-02A, the v1.1 regeneration, and the reconciliation of `evaluation-protocol.md` §2.3 through the locked W3-02 protocol) are all done.

## Active Next Gate
1. **Track A — Week 4:** `W4-01` stay-point extraction ($\Delta D_{\max}$, $\Delta T_{\min}$) and berth polygon exclusion, then `W4-02` anchorage dwell and utilization analytics (anchorage intelligence by unique `MMSI`). Use canonical v1.1 as input.
2. **Track B:** `ML-05` in progress on draft PR #12. Merge requires Track B lead sign-off plus normal review.
