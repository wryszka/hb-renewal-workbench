# Smoke Results — WP11 checklist

Full run of `data/smoke_test.py` against `lr_dev_aws_us_catalog.hb_renewal` (warehouse `a3b61648ea4809e3`, profile `DEV`). **Latest run: 2026-08-22 — 9/9 pass.** The script reseeds at the start, exercises every pipeline branch (which mutates the schema), and reseeds to a clean demo state as its final step.

## Executed checks

| # | Check | Result | Output evidence |
|---|-------|--------|-----------------|
| 1 | Clean reseed | **PASS** | `53 docs (50 active + 3 governance) / 49 scenarios` |
| 2 | Hero ingested + provenance | **PASS** | `12 months, 2 audit events` (`ingested` + `archived`) |
| 3 | Method reproduces exhibit | **PASS** | `blended 26.9491% (exhibit 26.9491%)` — `fn_renewal_buildup` on the hero inputs, ≤0.01 tolerance |
| 4 | Broken → quarantine | **PASS** | `15/17 fields`; status `quarantined`; no source rows land |
| 5 | v2 → supersession | **PASS** | `hero now superseded, v2 active` |
| 6 | month13 → reforecast | **PASS** | `appended 1 month(s)` |
| 7 | Benchmark three stories | **PASS** | `Cascade 0.0809, Evergreen 0.054` (padder ≥0.078, fair ≤0.06) |
| 8 | Genie | **PASS** | `space 01f19d63fe03198a95c55b64a81ea535` present |
| 9 | Final clean state | **PASS** | `0 un-approved test scenarios remain (should be 0)` |

## Mapping to the WP11 spec checklist

The spec's WP11 lists a ~10-step scripted checklist; `smoke_test.py` implements it as the 9 checks above (steps for "open app loop" and "app-visible" beats are covered by the WP7 manual loop, not the headless smoke). Coverage:

- Ingestion active/quarantine/supersession/reforecast → checks 2, 4, 5, 6 (all four pipeline branches).
- Governed method fidelity → check 3.
- Decision layer + benchmark → check 7 (benchmark derives from `5_scenario`).
- Genie presence → check 8.
- Clean end state → checks 1, 9.

## Local regression (pytest)

`tests/test_regression.py` — **2 tests**, asserting the **reference** exhibit (gitignored `data/reference_exhibit.json`):
- `test_reproduces_reference_exhibit_to_4dp` → `0.3906`.
- `test_member_months_and_total_tie_out` → `3888`.

Both are `@pytest.mark.skipif(not REF.exists())`. On a machine with the reference present: **2 passed**. On a clean public clone (no reference): **2 skipped** (non-blocking, by design). Note this reference number (`0.3906`) is distinct from the deployed synthetic hero's `26.9491%` (check 3) — they are different exhibits.

## What failed initially and was fixed

- **Archive-to-Volume (`'bytes' object has no attribute 'seekable'`).** When the `stored_path` archiving was added (2026-08-22), `files.upload(dest, data)` was called with raw bytes; the installed SDK requires a file-like object. **Fixed** by wrapping in `io.BytesIO(data)` (`jobs/ingest_pipeline.py` `archive()`); re-ran seed and checks 2/4/5 (the archive branches) then passed. Verified the hero downloads 8,935 bytes from the Volume.
- **Stale doc-count assertion.** An earlier smoke revision expected 50 docs; the seed now leaves 53 (50 active + 3 governance rows). Assertion updated to 53 (check 1).

## Caveats on the run

- The smoke mutates DEV state (ingests broken/v2/month13) and then reseeds; do not interrupt it mid-run or the schema is left in the test-mutated state (re-run `seed_book.py` + `generate_reviewer.py` to recover).
- Check 8 verifies the Genie **space exists**, not that in-app answers return — that is a manual/authenticated-session beat (see `DEMO_READINESS.md`).
