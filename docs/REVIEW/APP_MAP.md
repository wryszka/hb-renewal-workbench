# App Map — HB Renewal Workbench

Every screen and panel in the deployed app: what it shows, which API/SQL feeds it, which governed object it reads/writes, what actions exist and what each writes, and — for every displayed number — **where the math happens**.

**Shell.** Single-page app, `app/frontend/index.html`. Left sidebar nav (`NAME:function` in `RENDER`, `:141`): Overview (Daily view · Dashboard) · Pipeline (Ingestion · Book) · Renewal (Renewal Workspace · Benchmarks) · Intelligence (Agents · Ask the Book · Audit). Backend `app/main.py` (FastAPI). All SQL runs on warehouse `a3b61648ea4809e3` via `statement_execution` (`query()`, `:45`). Auth: OAuth service-principal via `Config().authenticate()` (no `DATABRICKS_TOKEN` in Apps).

**Compute-source legend for displayed numbers:**
- **[UC]** — computed by the governed function `fn_renewal_buildup` on the warehouse (`buildup()`, `app/main.py:58`).
- **[STORED]** — a value read from a table/view (originally produced by [UC] on save, or by the seed's Python engine for history).
- **[SQL]** — an aggregate computed by a SQL view/query over stored values.
- **[JS]** — computed client-side in the browser by `computeBuildup` (`index.html:143`), a hand-maintained mirror of the UC function. **This is the one place app-side math drives a displayed number** — flagged per the spec.

---

## 1. Daily view (`renderHome`, `index.html:183`)
- **Feed:** `GET /api/overview` (`main.py:276`).
- **Reads:** `1_source_document` (status counts), `5_scenario` (KPIs: `count`, `avg(baseline_action)`, `avg(scenario_action)`, `sum(value_at_stake_annual)` WHERE status IN saved/approved), `1_source_document` (attention = quarantined/differs), `5_gov_audit_event` (recent 7), hero lookup.
- **Numbers:** book counts, avg carrier action, avg negotiated, value negotiated → **[SQL]** over stored rows. Attention list and recent activity → **[STORED]**.
- **Actions:** **↺ Reset demo** (top-right) → `resetDemo()` → `POST /api/reset` triggers the serverless `hb_reseed` Job and polls `GET /api/reset/status` (~1–2 min, spinner), then refreshes. **Writes:** a `demo_reset` audit event + (via the Job) a full reseed of the schema data.

## 2. Dashboard (`renderDashboard`, `index.html:221`)
- **Feed:** `GET /api/config` (`main.py:310`) → `dashboard_url = {host}/embed/dashboardsv3/{HB_DASHBOARD_ID}`.
- **Shows:** the Lakeview dashboard `01f19d737ef41c468039d889d47d91a9` in an `<iframe>`. Widgets read `6_book_trend_benchmark` and `mv_claims_experience`.
- **Numbers:** computed by Lakeview/DBSQL → **[SQL]**. **Writes:** none.
- **Caveat:** the iframe renders only on an authenticated browser session; on localhost it shows a login wall (see `DEMO_READINESS.md`).

## 3. Ingestion (`renderIngestion`, `index.html:262`)
- **Feed:** `GET /api/ingestion` (`main.py:323`) → `0_carrier_template` (registry), `1_source_document` (recent 16), Volume `inbox/` listing.
- **Panels:** pipeline-stage explainer; landing zone / inbox; template registry; **Upload & ingest** card; **Recent ingestions** feed (`renderRecent`, `:297`).
- **Actions & writes:**
  - **Upload a file** → `POST /api/ingest/upload` (`main.py:339`) → writes `/tmp`, calls `ingest_pipeline.process_file`. **Writes:** source rows + `1_source_document` + audit events + archives the original to the Volume (full flow in `DATA_FLOW.md`). Live end-to-end ≈ **18.7 s** active / **11.3 s** quarantine (includes the FMAPI call).
  - **Scan inbox (run-now)** → `POST /api/ingest/scan` (`main.py:353`) → processes any `.xlsx` in `inbox/`.
  - **Row click** → `openIngestDetail(id)` (`:322`) → `GET /api/document/{id}` → renders the **two-path reconciliation table** from `reconciliation_detail`, **Download original submission** (`dlOriginal`, `:174` → `GET /api/document/{id}/file`), and **Show lineage & governance** → `GET /api/lineage/{id}`.
- **Numbers:** field counts, per-field agree/differ → **[STORED]** (from `reconciliation_detail`). Download streams the archived `.xlsx` from `stored_path` and writes a `file_retrieved` audit event (`main.py:242` in `document_file`).

## 4. Book (`renderBook`, `index.html:349`)
- **Feed:** `GET /api/book` (`main.py:69`) → `1_source_document` (all statuses, active first), joined to `5_scenario` aggregates (`max(scenario_action)`, `count`, `max(baseline_action)`).
- **Shows:** every renewal with status chip, fields, carrier action, #scenarios; search + status-filter chips.
- **Numbers:** `carrier_action` is **[STORED]** (`max(baseline_action)` from `5_scenario`) for docs with saved scenarios; for a **freshly-ingested active exhibit with no scenario yet**, it is computed live via `buildup()` → **[UC]** (`main.py:88`).
- **Actions:** row click → `openDoc(id)` (`:388`, loads `/api/document` into `STATE`, goes to Workspace) or `openQuarantine(id)` for held files. **Writes:** none.

## 5. Renewal Workspace (`renderWorkspace`, `index.html:405`) — the negotiation screen
- **Feed:** `STATE.doc` from `GET /api/document/{id}` (`main.py:102`), which returns `baseline` = `fn_renewal_buildup(inputs)` **[UC]**, plus `findings`, `scenarios`, `monthly`, `book_trend`.
- **Left "Carrier build-up" table** (`recompute`, `:441`): the **Carrier column** = `STATE.doc.baseline` → **[UC]**. The **Scenario column** = `computeBuildup(inputs, overrides)` → **[JS]**.
- **Right "Negotiation levers":** each lever `oninput` sets `STATE.overrides[k]` and calls `recompute()` (`:423`). Manual pool increase rendered **locked** 🔒.
- **Result strip** (`:447`): **Carrier quoted** = `baseline.quoted_change` **[UC]**; **Your position** = `scenario.quoted_change` **[JS]**; **Value at stake / yr** = `baseline.projected_billed_premium_annual − scenario…` **[JS]**. The strip prints the label "governed by fn_renewal_buildup".
  - **⚠ Honest flag (spec "no math in the app container"):** the container runs no math, but the **live preview** of "Your position" and "Value at stake" while dragging a lever is **[JS]**, computed in the browser by a mirror of the UC function. The baseline is [UC]; the saved value is recomputed [UC] (below). The strip's "governed by" label is accurate for the baseline and the saved record, **not** for the live-preview scenario figure.
- **Actions & writes:**
  - **💾 Save scenario** → modal → `doSave` (`:463`) → `POST /api/scenario` (`main.py:147`). Server **recomputes** baseline and scenario via `fn_renewal_buildup` **[UC]**, computes value-at-stake, and **INSERTs a `5_scenario` row** (status `saved`) + a `scenario_saved` **audit event**. Requires name + reason (400 otherwise). Authoritative numbers are [UC]/[STORED]; the JS preview is discarded.
  - **✎ Draft exec summary** → `doSummary` (`:467`) → `POST /api/summary` (`main.py:247`) → FMAPI `databricks-claude-sonnet-4-5`, deterministic fallback if unavailable. Read-only (LLM text).
  - **🔗 Lineage** → `doLineage` (`:471`) → `GET /api/lineage/{id}` → chain "the number → fn_renewal_buildup → 2_renewal_inputs v{n} → file:{name}" + **Download original** (`dlOriginal`).
- **Compare panel** (`renderCompare`, `:452`): `GET /api/document` → "Carrier proposal" = `baseline.quoted_change` **[UC]**; each saved scenario's action + value-at-stake → **[STORED]**.
- **Reforecast banner** (`:414`): shows when `reforecast_months>12` (a month13 drop appended a month).

## 6. Benchmarks (`renderBench`, `index.html:480`)
- **Feed:** `GET /api/benchmarks` (`main.py:175`) → `6_book_trend_benchmark`.
- **Numbers:** book trend median, avg carrier/negotiated action, delta, value negotiated → **[SQL]** (view derived from `5_scenario`). Padder/fair flags computed in JS from those thresholds (presentation only).
- **Row click → lineage:** `openBenchmark(carrier,band)` → `GET /api/benchmark/scenarios` lists the retained decisions behind that cell + a chain `6_book_trend_benchmark ← 5_scenario ← 1_source_document`. **Writes:** none.

## 7. Agents (`renderAgents`, `index.html:231`)
- **Feed:** `GET /api/agents` (`main.py:293`).
- **Shows:** Reviewer (target doc + findings from `4_reviewer_finding`, with `generated_by` and `LIVE_REVIEWER` flag), Deal Summariser (endpoint name), Ask-the-Book/Genie (configured + space id).
- **Numbers/text:** reviewer narratives are **[STORED]** — **precomputed hardcoded strings by default** (`data/generate_reviewer.py`), or FMAPI output when `LIVE_REVIEWER=true`. Stated plainly: the default demo path is precomputed, not live model output.
- **Actions (all three cards are actionable, not display-only):** Reviewer → **"Open the flagged renewal →"** (`openDoc(target)`); Deal Summariser → **"Draft a summary now"** inline (`POST /api/summary`, FMAPI); Genie → an **inline ask box** (`genieQuery` → `POST /api/genie/ask`) plus "Open full Ask the Book →". **Writes:** none (Summariser/Genie are read/LLM).

## 8. Ask the Book (`renderAsk`) — Genie
- **Two surfaces via a toggle:** **Workbench panel** (in-app Q&A + generated SQL + result table) and **Native Genie** (embedded `<iframe>`, `genie_url = {host}/embed/genie/rooms/{HB_GENIE_SPACE_ID}`, auth-session only). `askFromDashboard(q)` sets `GENIE.mode='panel'` + `GENIE_PENDING` and navigates here to auto-run a question from the Dashboard screen.
- **Workbench panel:** `askGenie` → `genieQuery` → `POST /api/genie/ask` (also reused by the Agents inline ask box).
  - **Agent id source:** `HB_GENIE_SPACE_ID` env (`app.yaml` = `01f19d63…`). If unset → returns `{error}` (HTTP 200) and the panel shows a banner.
  - **Conversation flow:** first question → `W.genie.start_conversation_and_wait(space, q)`; follow-ups → `W.genie.create_message_and_wait(space, conv, q)` (statefulness via `GENIE.conv` kept client-side). Attachments are scanned for `text` and a `query`; the SQL is executed via `execute_message_attachment_query` (or `get_message_attachment_query_result`, resolved by lazy `getattr` for older SDKs — needs `databricks-sdk>=0.133`), first 50 rows returned.
  - **Returns** `{conversation_id, text, sql, rows}`. Panel shows the NL answer, a collapsible "Show generated SQL", and the result table.
  - **Error handling:** any exception is caught and returned as `{error}` with HTTP 200 (never a 500 to the UI); the panel renders "Genie not available: …". **Writes:** none (read-only queries over the governed views).

## 9. Audit (`renderAudit`, `index.html:523`)
- **Feed:** `GET /api/audit` (`main.py:182`) → `5_gov_audit_event` (last 40).
- **Shows:** append-only event table (when · event · entity · detail · actor).
- **Actions:** entity ids starting `SCN`/`DOC` are clickable → `openProvenance(eid)` (`:542`): `SCN` → `GET /api/deal/{sid}` (`main.py:208`, joins `5_scenario` → `1_source_document`); `DOC` → `GET /api/document/{id}`. Renders the chain **deal → 1_source_document → file** and **Download original** (`dlOriginal`).
- **Numbers:** value-at-stake shown in provenance = **[STORED]**. Download writes a `file_retrieved` audit event (so retrieval is itself governed).

---

## Endpoint ↔ object matrix

| Endpoint | Method | Reads | Writes | Math |
|----------|--------|-------|--------|------|
| `/api/overview` | GET | `1_source_document`, `5_scenario`, `5_gov_audit_event` | — | [SQL] |
| `/api/book` | GET | `1_source_document`, `5_scenario`, `2_renewal_inputs` | — | [STORED]+[UC] for fresh |
| `/api/document/{id}` | GET | `1_source_document`, `2_renewal_inputs`, `4_reviewer_finding`, `5_scenario`, `1_incurred_claims`, `6_book_trend_benchmark` | — | [UC] baseline |
| `/api/recompute` | POST | `2_renewal_inputs` | — | [UC] — **defined but not called by the UI** (the UI uses [JS] `computeBuildup` for the live preview) |
| `/api/scenario` | POST | `2_renewal_inputs`, `1_source_document` | `5_scenario` + `5_gov_audit_event` | [UC] |
| `/api/benchmarks` | GET | `6_book_trend_benchmark` | — | [SQL] |
| `/api/audit` | GET | `5_gov_audit_event` | — | — |
| `/api/lineage/{id}` | GET | `1_source_document`, `information_schema.routines`, `DESCRIBE HISTORY` | — | — |
| `/api/deal/{sid}` | GET | `5_scenario`, `1_source_document` | — | — |
| `/api/document/{id}/file` | GET | `1_source_document`, Volume | `5_gov_audit_event` (`file_retrieved`) | — |
| `/api/summary` | POST | `2_renewal_inputs`, `1_source_document`, `4_reviewer_finding` | — | FMAPI (LLM) |
| `/api/overview`,`/api/agents`,`/api/config`,`/api/ingestion` | GET | see above | — | [SQL]/env |
| `/api/ingest/upload`,`/api/ingest/scan` | POST | Volume | source tables + `1_source_document` + `5_gov_audit_event` (via pipeline) | — |
| `/api/genie/ask` | POST | Genie space → governed views | — | Genie-generated SQL |
| `/api/reset` | POST | — | triggers the `hb_reseed` Job (`jobs.run_now`) + writes a `demo_reset` audit event | — |
| `/api/reset/status` | GET | Jobs run state | — | — |
| `/api/health` | GET | — | — | — |

**Unwired code shipped in the app dir:** `app/selffunded.py` (self-funded engine) is not imported anywhere (grep clean). `POST /api/recompute` is defined but not called by the frontend.
