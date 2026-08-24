# Smoke Results — Addendum (post-review verification)

Appends Phase 2 (app-layer) and Phase 3 (fixes) verification to the original 9/9 in `SMOKE_RESULTS.md` (left untouched as the historical data-layer record). Run 26 Aug 2026 against `lr_dev_aws_us_catalog.hb_renewal` (warehouse `a3b61648ea4809e3`, profile `DEV`), with the FastAPI app run locally against DEV to exercise the real HTTP endpoints. All verification artifacts were removed afterward by a full reseed (`seed_book.py` + `generate_reviewer.py`).

## Phase 2.1 — App loop (evidence, not code citations)

Endpoints exercised on the running app; DB writes confirmed by direct warehouse reads.

| Step | Result | Evidence |
|------|--------|----------|
| Open hero renewal | PASS | `GET /api/document/{hero}` → HTTP 200; `baseline.quoted_change = 0.269491` computed by `fn_renewal_buildup` |
| Recalc goes through the governed function | PASS | Direct warehouse call `SELECT fn_renewal_action(...)` → **statement_id `01f19fa7-2f52-1139-bf4b-54be9d48dad2`**, result `0.26949054280587653` (matches the exhibit to 4dp) |
| Move a lever (trend 12.2%→7.2%) | PASS | `POST /api/recompute` → HTTP 200, `scenario.quoted_change = 0.231197`, `value_at_stake_annual = 176,507` (UC path) |
| Save scenario (name + reason) | PASS | `POST /api/scenario` → HTTP 200 `SCN-bb626951`; `5_scenario` row `[saved, 'recorded evidence run', 0.2312, 176507]`; audit row `[scenario_saved, SCN-bb626951, workbench-user]`; Delta history `5_scenario` **v53 → v54** |
| Empty reason rejected | PASS | `POST /api/scenario` with `reason:""` → **HTTP 400** `{"detail":"scenario_name and reason are required"}` |
| Compare panel | PASS | `GET /api/document` → `scenarios` length reflects the saved decision (carrier ask vs saved scenario with value-at-stake) |
| Lineage resolves | PASS | `GET /api/lineage/{hero}` → `function.governed = true`, `table_versions = {2_renewal_inputs: 52, 5_scenario: 54}` |
| Exec summary from saved scenario | PASS | `POST /api/summary` → HTTP 200, text begins "## Harborview Logistics \| Meridian Assurance Renewal Summary … Carrier Action: +26.9% \| Negotiated Position: +23.1%" (FMAPI) |
| Locked manual-rate not editable | PASS | `manual_rating_pool_increase` appears in the display `LINES` with a 🔒 (`index.html:401,:444`) but is **not** in the editable `LEVERS` list (`index.html:391`) |
| Quarantined doc with field diff | PASS | `GET /api/document/DOC-Q900` → status `quarantined`, 6/17 fields, diff fields `[annual_trend, member_months, target_loss_ratio]` |
| Reforecast banner after month13 | PASS | `POST /api/ingest/upload` month13 → `reforecast`, appended 1 month; `GET /api/document` → `reforecast_months 12 → 13` → banner condition `>12` true |

**Recorded caveat:** the live lever *preview* number ("Your position"/"Value at stake") is computed client-side in JS (`computeBuildup`); the authoritative value is the UC-function recompute on save (verified above). See `APP_MAP.md`. The reforecast beat shows the banner cue; an explicit old-vs-new recomputed action is not auto-rendered (V2).

## Phase 2.2 — In-app Genie (four seeded questions + follow-up)

Through `POST /api/genie/ask` (Conversation API). Every question returned correct SQL and a correct result set.

| # | Question | SQL target | Result | Correct? |
|---|----------|-----------|--------|----------|
| 1 | Average carrier action, groups >500 lives | `6_book_trend_benchmark` WHERE band IN 500-1999,2000+ | `avg_carrier_action = 0.2862` (28.6%) | YES |
| 2 | Which carrier runs richest vs book trend | `6_book_trend_benchmark`, `avg(avg_carrier_action - book_trend_median)` | 5 rows; top = **Cascade Care** (gap 0.2296) | YES (data correct; narrative posed a clarifying question — phrasing nuance) |
| 3 | Which months drove claims for Harborview Logistics | `mv_claims_experience` | 13 rows; top Jan-2026 $397,758, Dec-2025 $368,450 | YES |
| 4 | Biggest gap carrier ask vs negotiated | `6_book_trend_benchmark` ORDER BY `avg_negotiation_delta` | 10 rows; top = Cascade Care 2000+ (Δ 0.0453, $3.85M) | YES (data correct; narrative posed a clarifying question) |
| follow-up | "And for groups under 100 lives?" | `6_book_trend_benchmark` WHERE band `<100` | 19.0%; **same `conversation_id`** → statefulness proven | YES |

Q2/Q4 return the correct result set but phrase the narrative as a clarifying question; the Genie instructions were tightened (`deploy_genie_agent.py`) to answer "richest/biggest gap" with the top row. No answer was wrong, so no further agent fix was forced.

## Phase 2.3 — Live-drop timing (3 runs each)

| Path | Run 1 | Run 2 | Run 3 | Notes |
|------|------:|------:|------:|-------|
| Run-now (in-app Upload & ingest) | 11.1 s | 9.9 s | 11.1 s | pure pipeline incl. FMAPI extraction; no trigger latency |
| File-arrival trigger (drop → rows visible) | 57 s | 51 s | 62 s | includes the ~1-min file-arrival poll then the same processing |

**Takeaway:** demo the live drop via the run-now button (~10 s); the file-arrival Job is real but adds ~1 min.

## Phase 3.1 — Benchmark three stories (clean post-seed view output)

`SELECT … FROM 6_book_trend_benchmark ORDER BY carrier, group_band` — the padder, the fair carrier, and the negotiation delta all read at a glance:

```
carrier             band     n   book  carrier  negot  DELTA      value
Cascade Care        100-499  4   8.1%  21.2%   19.2%   2.0pt  $  232,087   <- padder (high book trend)
Cascade Care        2000+    3   8.2%  52.8%   48.3%   4.5pt  $3,851,104
Evergreen Health    100-499  4   5.4%  21.3%   20.3%   1.0pt  $  103,538   <- fair carrier (low book trend)
Evergreen Health    2000+    2   5.0%  31.4%   30.0%   1.4pt  $  575,290
Meridian Assurance  500-1999 3   6.9%  30.2%   26.5%   3.7pt  $1,202,430
Ridgeline Mutual    2000+    4   6.5%  35.9%   32.9%   3.0pt  $3,428,680
Summit Health       2000+    2   6.5%  29.3%   26.2%   3.1pt  $1,518,234
```
`book` = firm's own median trend; `carrier`/`negot` = avg carrier vs negotiated action; **DELTA** = avg_negotiation_delta (what challenging was worth). All three stories are visible in the view **and** in the app benchmark panel (Δ column + padder/fair flags). No retune required.

## Phase 3.2 — Genie deploy idempotency

`data/deploy_genie_agent.py DEV` run **twice** in a row:
- Run 1: "space 'HB Renewal Book' exists (01f19d63…) → updating in place"; grant CAN_RUN ok.
- Run 2: same — updates in place; grant ok.
- Post-check: `GET /api/2.0/genie/spaces` → **exactly one** "HB Renewal Book" (`01f19d63fe03198a95c55b64a81ea535`). No duplicate created.
- Auto-wire: writes `data/genie_space_id.txt` and rewrites `HB_GENIE_SPACE_ID` in `app/app.yaml` (regex verified).

## Phase 3.3 — Local regression (reference exhibit)

`pytest tests/test_regression.py -v` → **2 passed**: `test_reproduces_reference_exhibit_to_4dp` and `test_member_months_and_total_tie_out`. The governed method reproduces the reference exhibit's blended action to 4 decimal places. (Numbers only; reference-exhibit language, no confidential identifiers.)

## Learn panel (how-it-works layer) — acceptance

`GET /api/learn` returns **9 cards**; every link validated against DEV (26 Aug 2026).

- **Readability rule:** card layers 1–2 (activity, how) contain **no** Databricks object names across all nine cards (automated check) — object names appear only in the "See it live" links. PASS.
- **External link targets all exist:** `0_carrier_template`, `1_source_document`, `4_reviewer_finding`, `5_scenario`, `5_gov_audit_event` (tables); `6_book_trend_benchmark`, `v_1_incurred_claims_latest`, `mv_renewal_actions` (views); `fn_renewal_action` (function); `landing` (volume); ingestion Job (id 167601632366629 resolved by name); Genie space `01f19d63…`. PASS.
- **In-app anchors** (`book`, `workspace`, `agents`, `benchmarks`, `ask`) all present in the frontend `RENDER` map. PASS.
- **No hardcoded hosts:** links built server-side by `_workspace_links()` from `Config().host` + catalog/schema; frontend contains no workspace host. PASS.
- **Anchor param:** the "❓ how does this work?" glyphs on Book/Workspace/Benchmarks/Ask set `LEARN_ANCHOR` → Learn opens pre-expanded at nodes 2/3/8/9. PASS.

## Phase 5 — Extended smoke — 13/13 GREEN

| # | Step | Result |
|---|------|--------|
| 1–9 | Original data-layer smoke (`data/smoke_test.py`) re-run | **9/9 PASS** (reseed 53/49; hero 26.9491%; quarantine 15/17; supersession; reforecast; benchmark Cascade 0.0809 / Evergreen 0.054; Genie space present; clean end) — see `SMOKE_RESULTS.md` |
| 10 | App loop (Phase 2.1) | **PASS** — full loop with recorded HTTP/statement-id/Delta-version evidence |
| 11 | In-app Genie 4 questions + follow-up (Phase 2.2) | **PASS** — all 4 correct SQL+data; stateful follow-up |
| 12 | Name scan against a fresh public clone (Phase 1) | **PASS** — 0 real-party hits, no confidential files, no secrets, no personal email, single commit `6f8fe31…` (`NAME_SCAN.md`) |
| 13 | Local regression (Phase 3.3) | **PASS** — 2/2 to 4dp |

**Definition of done met:** 13/13 green on record; `docs/REVIEW/` complete (7 files); public clone scans clean; run-sheet carries the measured live-drop timings.
