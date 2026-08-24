# Implementation Report — HB Renewal Workbench

**Audience:** an external reviewer who has the build spec (`HB_DEMO_BUILD_SPEC.md`, provided separately — it is **not** committed to this repo) and wants to verify what was built against what was specified.

**Environment (all facts below verified against this):**
- Workspace `fevm-lr-dev-aws-us` (CLI profile `DEV`)
- Catalog `lr_dev_aws_us_catalog`, schema `hb_renewal`
- Serverless SQL warehouse `a3b61648ea4809e3`
- App `hb-renewal-workbench`, service principal `b417c702-dd1f-4ba7-a81c-2459b48fb325`, URL `https://hb-renewal-workbench-7474656169654171.aws.databricksapps.com`
- Genie space `01f19d63fe03198a95c55b64a81ea535` ("HB Renewal Book")
- Lakeview dashboard `01f19d737ef41c468039d889d47d91a9`
- FMAPI endpoint `databricks-claude-sonnet-4-5`

**Verification date:** 2026-08-22. Object counts are the clean post-seed state (`data/seed_book.py` + `data/generate_reviewer.py`).

All data is synthetic. Carriers present in the deployed schema: Summit Health, Ridgeline Mutual, Cascade Care, Evergreen Health, Meridian Assurance (verified — see `NAME_SCAN.md`).

---

## Deviations from the spec (read first)

These are the places where the delivered build differs from the spec, was reinterpreted, or is thinner than the spec implies. Each is expanded in the WP sections below.

**Resolved in the post-review pass (26 Aug 2026):** D-1 (mv_ views now created by `build_schema.py`, `DECISIONS.md` D16), D-3 (demo file now has a Detailed Rates sheet + `parse_detailed`; `1_detailed_rates` = 24 rows, D24), D-6 (single idempotent `deploy_genie_agent.py`, D17), D-10 (comment fixed). The public-push, seed-count, smoke-divergence, `fn_renewal_buildup`, and deploy-shape items (D-12…D-17 below) are **accepted deviations**, logged not "fixed". Still-open thin spots: D-4, D-5, D-7.

| # | Deviation | Spec reference | Where | Impact |
|---|-----------|----------------|-------|--------|
| **D-1** | The two consumption views `mv_renewal_actions` and `mv_claims_experience` **exist in the deployed schema but are created by no committed code** — not in `data/build_schema.py`, not in any `create_*`/`deploy_*` script. They were created ad-hoc during the build. | WP8 ("create the metric views"), WP10 ("bundle deploy from clean checkout succeeds end-to-end") | live schema vs `data/build_schema.py` | A clean rebuild (`build_schema.py` + `bundle deploy`) does **not** recreate them. `create_genie_space.py` and the dashboard reference them, so a from-scratch Genie/dashboard deploy would fail until they are created manually. **AC gap.** |
| **D-2** | Those two views are **plain SQL views** (`CREATE VIEW … WITH SCHEMA COMPENSATION`), not Unity Catalog **metric views** (no `MEASURE`/`DIMENSION` YAML). The `mv_` prefix and the word "metric views" in `DECISIONS.md` D12 / `docs/README.md` / `docs/ARCHITECTURE.md` are misleading. | WP8 ("metric views") | live DDL (see `OBJECT_INVENTORY.md`) | Naming/description only; the objects function for Genie and the dashboard. ROADMAP already lists "promote consumption views to formal UC metric views" as V2, so this is acknowledged. |
| **D-3** | ~~`1_detailed_rates` holds 0 rows — no `parse_detailed`, hero file has no rate sheet.~~ **RESOLVED (D24):** the demo file now has a Detailed Rates sheet and `parse_detailed` populates `1_detailed_rates` (24 rows). All four source tables are now populated. Current premium is still read from the `Current Premium & Fees` PMPM field (detailed rates are per-contract/illustrative, not fed into the build-up). | WP1 AC: "rows in **all four** source tables" | `jobs/ingest_pipeline.py:parse_detailed`; live row count = 24 | WP1 AC now met for all four. |
| **D-4** | The renewal method exists in **three** implementations, not one: the governed UC function `fn_renewal_buildup`, a Python mirror `app/renewal_engine.py`, and a **JavaScript mirror `computeBuildup`** in the app frontend used for instant lever preview. | "One compute path" / WP7 ("no math in the app container") | `app/frontend/index.html:143`; `app/renewal_engine.py`; `fn_renewal_buildup` | The container runs no math (true). But the **number shown while dragging a lever is computed client-side in JS**; only the **saved / initially-loaded** number comes from the UC function. Three implementations must be kept in agreement by hand. Detailed in `APP_MAP.md`. |
| **D-5** | The local regression test asserts the **reference exhibit** action `0.3906` and `3888` member-months (`tests/test_regression.py:19,51`). The **deployed synthetic hero** reproduces a **different** number, `26.9491%` (`data/reference_exhibit.json` is a distinct, gitignored fixture). The test `skipif`s when that fixture is absent, so on a clean public clone it reports **2 skipped**, not 2 passed. | WP3 AC ("local regression green") | `tests/test_regression.py:41,48` | Honest and non-blocking, but "regression green" only holds on a machine that has the gitignored reference. Two distinct fidelity numbers exist; do not conflate them. |
| **D-6** | Two Genie deployment scripts are committed. `data/deploy_genie_agent.py` (SDK `w.genie.create_space`) **does not work** (fails on `serialized_space` encoding). The working, reproducible path is `data/create_genie_space.py` (genie-rooms `GenieSpaceBuilder` + `databricks api post`). | WP8 AC ("deploy script creates the agent from scratch on a clean deploy") | `data/deploy_genie_agent.py` vs `data/create_genie_space.py` | WP8 AC met **only** via `create_genie_space.py`, and **only** if the `mv_` views (D-1) already exist. The non-working script remains in the repo. |
| **D-7** | `app/selffunded.py` is committed but **unwired dead code** — not imported by `app/main.py` or the frontend. | Out of scope / V2 | `app/selffunded.py`; grep shows no import | ROADMAP.md lists "fully-insured → self-funded … currently unwired" as V2, so acknowledged, but the file ships in the deployable app directory. |
| **D-8** | WP2 is titled "Data model verification & **migration**" but the delivered mechanism is **drop-and-recreate** (`CREATE OR REPLACE`), not a migration. | WP2 | `data/build_schema.py` header | Fine for a demo (no production data), but there is no migration path; a rebuild discards all rows and is re-seeded. |
| **D-9** | The spec's demo flow (Section 5) is **10 beats**, not the "18-point show list" referenced in the documentation request. `docs/DEMO_RUNSHEET.md` expands these to 12 beats (adds the ingestion drill-down, native-Genie toggle, embedded dashboard, and the audit→original-file beat). `DEMO_READINESS.md` maps every beat that actually exists. | Section 5 | — | No functional impact; the readiness map covers all delivered beats. |
| **D-10** | `app/renewal_engine.py:5` comment points to `MODEL_SPEC.md`, which is gitignored (the confidential original). The committed replacement is `docs/METHOD_SPEC.md`. | WP9 hygiene | `app/renewal_engine.py:5` | Stale doc reference in a committed comment; no name leak. |
| **D-11** | `HB_DEMO_BUILD_SPEC.md` is not present in the repo. The spec was delivered in-conversation, not saved as a file. | WP9 | repo tree | The reviewer must be given the spec separately; these docs reference it by name only. |
| **D-12** | **Public push vs D8.** The original D8 said the repo stays local (confidential adjacency). It is now **public** at github.com/wryszka/hb-renewal-workbench, explicitly directed with a sanitised-only push. | D8 / hard rules | `DECISIONS.md` D13–D14 | Accepted. Publication audit passed (`NAME_SCAN.md`): 0 name hits, no confidential files in tree/history, single commit. One PII fix (a personal email) required a history rewrite. Accepted-public: workspace/catalog/warehouse/Genie/dashboard ids. |
| **D-13** | **Smoke checklist divergence.** The spec's WP11 is a ~10-step checklist; the headless `data/smoke_test.py` implements **9** data-layer checks (the app-loop steps are covered by the Phase 2 manual-with-evidence run, not the headless script). | WP11 | `SMOKE_RESULTS.md` + `SMOKE_RESULTS_ADDENDUM.md` | Accepted. Combined coverage = 13/13 (Phase 5). |
| **D-14** | **Seed numbers.** The deployed book is **53 documents / 49 scenarios**, not the spec's "50/43". 50 active + 3 governance-state docs (quarantined/differs/superseded); 49 historical approved decisions. | §3 / WP5 | live counts | Accepted — richer than spec, keeps the governance states visible on the first screen. |
| **D-15** | **`fn_renewal_buildup` addition.** The spec named `fn_renewal_action`; the build adds a second governed function `fn_renewal_buildup` returning the full build-up as JSON, which is the app's actual compute path. | WP3 | `data/build_schema.py:156` | Accepted — additive; both functions run identical arithmetic. |
| **D-16** | **Multi-step deploy vs single-bundle AC.** WP10's AC implies a single `bundle deploy`. The environment actually needs several ordered steps (schema, seed, reviewer, Genie, dashboard, app, bundle). Now wrapped in `deploy.sh` (fail-fast); the orchestrator-Job refactor is V2. | WP10 | `deploy.sh`, `docs/ROADMAP.md` | Accepted. `bundle deploy` alone covers only the Job + (optionally) the app, not the schema/seed/Genie/dashboard. |
| **D-17** | **Genie creation workaround** (was D-6, now contained). Raw SDK/REST/CLI `create_space` fail on `serialized_space`; the working path is genie-rooms builder + `databricks api post`, now wrapped idempotently in `deploy_genie_agent.py`. | WP8 | `data/deploy_genie_agent.py`, `docs/GENIE_SETUP.md` | Resolved as known debt with a retest condition. |

---

## WP-by-WP report

Legend: **MET** / **PARTIAL** / **NOT MET**. Evidence is file paths, object names, live counts, and test output.

### WP1 — Ingestion as a real Databricks Job — **PARTIAL**

**Built.** A single ingestion module `jobs/ingest_pipeline.py` (mirrored to `app/ingest_pipeline.py`) runs identically from three entry points: the local seed (`data/seed_book.py`), the serverless file-arrival Job (`jobs/run_ingest_job.py`), and the in-app upload/scan endpoints. Pipeline stages: `identify()` (filename + `0_carrier_template` fingerprint) → `_rows()` (openpyxl) → two-path extraction `extract_deterministic()` + `extract_ai()` (FMAPI) → `reconcile()` → `archive()` into the UC Volume → append with provenance / quarantine / supersede / reforecast, with audit events at each stage. The DAB (`databricks.yml`) defines job `hb_ingest` = `[hb-renewal] carrier file ingestion`, `file_arrival` trigger on `/Volumes/${catalog}/${schema}/landing/inbox/`, serverless `spark_python_task` = `./jobs/run_ingest_job.py`.

**AC status:**
- Hero file → `active` source_document row, provenance, audit events, archived to `processed/` — **MET** (smoke #2; live: hero `active`, `stored_path` set, `ingested`+`archived` audit events).
- "rows in **all four** source tables" — **MET** (D-3 resolved via D24): all four populated (`1_incurred_claims`, `1_large_claims`, `2_renewal_inputs`, and now `1_detailed_rates` = 24 rows via `parse_detailed`).
- Broken file → quarantine, readable field diff, no rows land — **MET** (smoke #4: 15/17 fields; status `quarantined`).
- v2 → supersession — **MET** (smoke #5).
- month13 → append one month, visible in latest view — **MET** (smoke #6).
- "file moved to `processed/`" — **MET, reinterpreted**: as of the 2026-08-22 change the **pipeline archives** the original into `processed/` (or `quarantine/`) keyed by `doc_id` and records `stored_path`; the Job then deletes the inbox copy (`jobs/run_ingest_job.py`). Net effect (original ends up in `processed/`) matches the AC.

### WP2 — Data model verification & migration — **MET (as drop-and-recreate; see D-8)**

`data/build_schema.py` is idempotent (`CREATE OR REPLACE`). All 9 tables + 8 views + volume + 3 functions verified live (`OBJECT_INVENTORY.md`). Seeded end-to-end chain joins cleanly: `1_source_document` → `1_incurred_claims`/`1_large_claims`/`2_renewal_inputs` (via `source_document_id`) → `5_scenario` (via `source_document_id`) → `5_gov_audit_event` (via `entity_id`). **AC MET**, with the caveat that "migration" is drop-and-recreate.

### WP3 — Governed method (verify only) — **MET, with two fidelity numbers (D-5)**

- Governed function `fn_renewal_action` and the full-buildup `fn_renewal_buildup` exist (verified live). Signature/body in `OBJECT_INVENTORY.md`.
- Deployed synthetic hero reproduces blended action **26.9491%** via `fn_renewal_buildup` (smoke #3). The app's regression assertion (`app/main.py` loads inputs, calls the function) matches the displayed exhibit.
- Local pytest asserts the **reference** exhibit `0.3906` to 4dp and `3888` member-months (`tests/test_regression.py`), **skips** if `data/reference_exhibit.json` absent. **AC "local regression green" MET only where the gitignored fixture exists** (D-5).

### WP4 — Decision layer (verify + wire) — **MET**

`POST /api/scenario` (`app/main.py:147`) inserts a fully-populated `5_scenario` row (baseline_action, scenario_action, value_at_stake_annual, overrides JSON, reason, status `saved`) and writes a `scenario_saved` audit event (`app/main.py:170`). `DESCRIBE HISTORY 5_scenario` shows commits (used by `/api/lineage`, `app/main.py:194`). Requires app SP `MODIFY` on the schema (granted). **AC MET.**

### WP5 — Benchmark seed retune — **MET**

`6_book_trend_benchmark` is a view **derived** from `5_scenario` (not hardcoded; DDL in `OBJECT_INVENTORY.md`). `SELECT * … ORDER BY carrier, group_band` shows the three intended stories — verified live post-seed: Cascade Care ~8.1% (padder), Evergreen Health ~5.4% (fair), visible carrier-vs-negotiated deltas (smoke #7: Cascade 0.0809, Evergreen 0.054). Row lineage: benchmark → `5_scenario.overrides.$.annual_trend` → `source_document_id`. **AC MET.**

### WP6 — Agents — **MET (reviewer precomputed by default)**

- Reviewer: `data/generate_reviewer.py` writes rows to `4_reviewer_finding`. Findings are **precomputed hardcoded strings by default**; a live FMAPI path is behind `LIVE_REVIEWER=true` (D2 in `DECISIONS.md`). Live: **5 findings** on the hero (high:1, medium:2, low:1, ok:1) — **≥3 satisfied**. Shown in the app at `/api/document` → Workspace, and summarised at `/api/agents` → Agents screen.
- Summariser: `POST /api/summary` (`app/main.py:247`) calls FMAPI `databricks-claude-sonnet-4-5` from a saved scenario, with a deterministic fallback if the endpoint is unavailable.
- Flag flip: `LIVE_REVIEWER` env var controls precomputed vs live; surfaced on the Agents screen (`/api/agents` returns `live_flag`).

**AC MET.** Note the default demo path is **precomputed**, not live model output — stated plainly.

### WP7 — App rewire — **MET, with the client-side-math nuance (D-4)**

Full loop verified: open hero → move trend lever (instant preview via **JS** `computeBuildup`, D-4) → **Save** (authoritative number via `fn_renewal_buildup`, writes `5_scenario` + audit) → appears in Compare + Audit + `DESCRIBE HISTORY` → lineage panel resolves number → function → table version → source file (+ **Download original** from the Volume, added 2026-08-22) → benchmark view shows three stories → summariser drafts from the saved scenario → quarantined file visible with diff (Ingestion drill-down) → reforecast banner after month13. "Grep of deployed app bundle contains no real names" — **MET** (see `NAME_SCAN.md`, 0 hits). Screen-by-screen detail and the exact math-source of every displayed number is in `APP_MAP.md`.

### WP8 — Genie: metric views, API-created agent, in-app chat — **MET (with the D-2 naming caveat)**

- "Metric views": `mv_renewal_actions`, `mv_claims_experience` are now **created by `data/build_schema.py`** (D-16), so a clean rebuild reproduces them. They remain **plain SQL views, not UC metric views** (D-2) — a naming/roadmap item, not a function gap.
- "Deploy script creates the agent from scratch on a clean deploy": **works via the single idempotent `data/deploy_genie_agent.py`** — verified re-runnable twice with no duplicate space (Phase 3.2), grants the app SP `CAN_RUN`, and auto-wires `HB_GENIE_SPACE_ID`. The non-working SDK path was removed (D-17).
- "All four seeded questions return correct answers inside the app panel": **verified** — all four return correct SQL + result sets, and a follow-up preserved conversation state (Phase 2.2, `SMOKE_RESULTS_ADDENDUM.md`). `POST /api/genie/ask` (`app/main.py:374`) uses the Conversation API + `execute_message_attachment_query` (needs `databricks-sdk>=0.133`). Native embedded Genie toggle also present (auth-session-only to eyeball).

**AC MET.** Reproducible from committed code; caveat is the plain-view-vs-metric-view naming (D-2, on the roadmap).

### WP9 — Docs — **MET**

`docs/` contains `README.md`, `ARCHITECTURE.md`, `METHOD_SPEC.md`, `ROADMAP.md`, `GENIE_SETUP.md`, `DEMO_RUNSHEET.md`, plus `DECISIONS.md` and `SMOKE_RESULTS.md` at repo root, and this `docs/REVIEW/` set. All sanitised (0 name hits). Note `HB_DEMO_BUILD_SPEC.md` is not committed (D-11).

### WP10 — Repo hygiene & DAB — **MET (deploy is multi-step; see D-16)**

- Hygiene: `.gitignore` excludes all confidential base-data; forbidden-name scan = 0 hits over a **fresh clone of the public remote** and over deployed values (`NAME_SCAN.md`). **MET.**
- DAB: `databricks.yml` defines the ingestion job; `databricks bundle deploy -t dev` succeeds. The `mv_` views are now created by `build_schema.py` (D-16), so a clean rebuild reproduces the full schema. The full environment still needs several ordered steps (schema/seed/Genie/dashboard/app/bundle), now wrapped in **`deploy.sh`** (fail-fast) — the single-`bundle deploy` reading of the AC is an accepted deviation (D-16); the orchestrator-Job refactor is V2. **AC MET** for reproducibility from committed code via `deploy.sh`.

### WP11 — Full smoke — **MET (9/9)**

`data/smoke_test.py` — 9/9 pass on 2026-08-22. Full run in `SMOKE_RESULTS.md` (this folder). Note the smoke script mutates the schema (ingests broken/v2/month13) and then reseeds to a clean state as its final step.

---

## Decision log (from `DECISIONS.md`, referenced inline)

D1 idempotent drop-and-recreate. D2 reviewer precomputed by default, FMAPI behind `LIVE_REVIEWER`. D3 Genie created programmatically + embedded via Conversation API. D4 `reference_exhibit.json` gitignored + sanitised `docs/METHOD_SPEC.md`. D5 hero = Meridian Assurance / Harborview Logistics / 2026H2; synthetic carriers only. D6 app name/URL unchanged. D7 no real names in any committed/deployed asset. D8 repo not pushed to public GitHub unless explicitly directed with a sanitised-only push. D9 file-arrival trigger + in-app run-now fallback. D10 pre-seeded book (49 historical + hero through the pipeline). D11 `field_map` as JSON string, `expected_tabs` as `ARRAY<STRING>`. D12 `mv_*` consumption views + Conversation-API panel; SDK `create_space` fails → resolved via GenieSpaceBuilder + `databricks api post`.

**Cross-check:** D12 calls `mv_renewal_actions`/`mv_claims_experience` "created in-schema" — they are present, but **no committed script creates them** (D-1). This report treats that as the single most material gap for reproducibility.
