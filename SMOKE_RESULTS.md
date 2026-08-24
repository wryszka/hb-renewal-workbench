# Smoke results — HB Renewal Workbench

Run 2026-08-24T13:31:59 against DEV `lr_dev_aws_us_catalog.hb_renewal`.

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | 1 reseed | ✅ PASS | 53 docs (50 active + 3 governance) / 49 scenarios |
| 2 | 2 hero ingested + provenance | ✅ PASS | 12 months, 2 audit events |
| 3 | 3 method reproduces exhibit | ✅ PASS | blended 26.9491% (exhibit 26.9491%) |
| 4 | 4 broken -> quarantine | ✅ PASS | 15/17 fields |
| 5 | 5 v2 -> supersession | ✅ PASS | hero now superseded, v2 active |
| 6 | 6 month13 -> reforecast | ✅ PASS | appended 1 month(s) |
| 7 | 7 benchmark three stories | ✅ PASS | Cascade 0.0809, Evergreen 0.054 |
| 8 | 8 genie | ✅ PASS | space 01f19d63fe03198a95c55b64a81ea535 |
| 9 | final clean state | ✅ PASS | 0 un-approved test scenarios remain (should be 0) |

**9/9 passed.** Regression (local pytest) and name-scan recorded separately.