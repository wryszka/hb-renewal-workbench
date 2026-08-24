# Demo Readiness — HB Renewal Workbench

Every demonstrable beat mapped to **Works / Works with caveat / Not working**, with the Phase 2 verification evidence, measured timings, fallbacks, and every known rough edge. The build spec §5 demo flow is **10 beats**; this maps them plus the added sub-panels as **18 items**. Detailed evidence (HTTP status, statement ids, row counts) is in `SMOKE_RESULTS_ADDENDUM.md`.

**Environment:** live app `https://hb-renewal-workbench-7474656169654171.aws.databricksapps.com`; clean post-seed state **53 docs / 49 scenarios / 5 findings**; app also verified locally against DEV (Phase 2).

## Measured timing (the two live drops), 3 runs each

| Path | Runs | Guidance |
|------|------|----------|
| Run-now (in-app **Upload & ingest**) | 11.1 / 9.9 / 11.1 s | Use for the live drop — deterministic ~10 s (FMAPI extraction dominates). |
| File-arrival **Job** trigger (drop → rows visible) | 57 / 51 / 62 s | Real but ~1-min poll; keep as the "it's a real Job" point, not the timed beat. |

## 18-point readiness

| # | Beat | State | Evidence (Phase 2 unless noted) |
|---|------|-------|--------------------------------|
| 1 | Problem, one line | Works | opening framing |
| 2 | Daily view — orient | Works | `GET /api/overview` HTTP 200, book_total 53 |
| 3 | Drop hero live → active | Works w/ caveat | run-now ~10 s; file-arrival Job ~57 s (timings above) |
| 4 | Ingestion drill-down — two-path reconciliation | Works | `reconciliation_detail` 17/17 on the hero |
| 5 | Trust beat — matches the sheet | Works w/ caveat | `baseline.quoted_change 0.269491` via `fn_renewal_buildup`; anchor on the blended action, not the monthly tab |
| 6 | Lineage — number → function → table version → file | Works | `GET /api/lineage` → `function.governed true`, `table_versions {2_renewal_inputs, 5_scenario}` |
| 7 | Download original from the Volume | Works | `GET /api/document/{id}/file` streams the archived `.xlsx`; writes `file_retrieved` audit |
| 8 | Drop broken → quarantine + field diff | Works | run-now ~11 s → `quarantined` 6/17 (DOC-Q900 twin also present) |
| 9 | Centre piece — levers + reviewer findings | Works w/ caveat | 5 findings shown; **live lever preview is client-side JS** (`computeBuildup`), authoritative value is UC on save |
| 10 | Move lever → recalc via governed function | Works | `POST /api/recompute` → UC path; direct `fn_renewal_action` statement_id recorded |
| 11 | Save scenario (name+reason) → row + audit + Delta | Works | `SCN-…` saved; `5_gov_audit_event` match; Delta v53→v54 |
| 12 | Empty reason rejected | Works | `POST /api/scenario` reason:"" → **HTTP 400** |
| 13 | Compare — carrier ask vs saved, value at stake | Works | `/api/document` scenarios list |
| 14 | Benchmarks — padder / fair / delta | Works | three stories read at a glance (Cascade ~8%, Evergreen ~5%, DELTA 1–4.5 pts) — table in `SMOKE_RESULTS_ADDENDUM.md` §3.1 |
| 15 | Exec summary (FMAPI) | Works w/ caveat | `/api/summary` generated; deterministic fallback if endpoint down |
| 16 | Reforecast — month13 → "fresh data" | Works w/ caveat | `reforecast_months 12→13`, banner fires; explicit old-vs-new recompute is a cue only (V2); **no pre-seeded twin** |
| 17 | In-app Genie — 4 questions + follow-up | Works | all 4 correct SQL+data; follow-up stateful (§2.2). Q2/Q4 phrase a clarifier but return the right rows |
| 18 | Native Genie + embedded dashboard | Works w/ caveat | iframes render only on an authenticated browser session — verify once on your session (localhost shows a login wall) |
| — | Finale / roadmap slides | Works | Vision beats (`ROADMAP.md`) |

Locked manual-rate input (not editable) verified: display-only with 🔒, absent from the editable `LEVERS` list.

## Pre-ingested twin fallbacks

| Live beat | Twin | State |
|-----------|------|-------|
| Hero active (3) | hero already seeded active through the pipeline | Ready |
| Quarantine (8) | `DOC-Q900` (Cascade / Fernbrook / 2026H2, 6/17) | Ready (seeded twin has `stored_path=NULL` — no download) |
| Differs | `DOC-D901` (Summit / Oakmont / 2026H1, 16/17) | Ready |
| Supersession | `DOC-S902` (Meridian / Harborview / 2025H2) | Ready |
| **Reforecast (16)** | none | **No fallback** — needs the live month13 drop |

## Known rough edges

**Resolved in this pass:**
- ~~`mv_` views created by no committed code~~ → **fixed**: now created by `data/build_schema.py` (D-16); a clean rebuild reproduces them.
- ~~Two Genie scripts, one broken~~ → **fixed**: single idempotent `data/deploy_genie_agent.py` (D-17); `create_genie_space.py` removed.
- ~~`renewal_engine.py` comment referenced gitignored `MODEL_SPEC.md`~~ → **fixed** to `docs/METHOD_SPEC.md`.
- ~~Personal email in a committed file~~ → **fixed** + history rewritten (D-14).

**Still present (by design or deferred):**
1. ~~`1_detailed_rates` is empty~~ → **fixed** (D24): the demo file now has a Detailed Rates sheet and `parse_detailed` populates `1_detailed_rates` (24 rows); all four source tables populated. Detailed rates are per-contract/illustrative, not fed into the build-up.
2. **Live lever preview is client-side JS** — the strip label "governed by fn_renewal_buildup" is accurate for the baseline and the saved record, not the live preview. Reconciles on save.
3. **`mv_` views are plain SQL views, not UC metric views** despite the name — promotion is on the roadmap.
4. **Regression skips on a clean clone** — needs the gitignored `reference_exhibit.json`; a public clone shows 2 skipped. Asserts the reference `0.3906`, distinct from the deployed hero's `26.9491%`.
5. **`selffunded.py` is unwired** dead code shipped in the app dir (V2).
6. **`/api/recompute` is defined but not called by the UI** (the UI uses the JS preview; the endpoint works — used in Phase 2 evidence).
7. **Genie Q2/Q4 phrasing** — correct SQL + rows, but the narrative poses a clarifying question rather than stating the top row.
8. **Embedded iframes** (dashboard + native Genie) verifiable only on an authenticated session.
9. **Reforecast has no pre-seeded twin** — the only beat without a fallback.
10. **Reviewer findings are precomputed** by default (live model only under `LIVE_REVIEWER=true`).
11. **Historical audit trail is sparse** — the seed emits one `scenario_approved` event per 7 historical scenarios.
