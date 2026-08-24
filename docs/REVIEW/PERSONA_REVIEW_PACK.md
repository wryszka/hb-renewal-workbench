# Persona Review Pack — HB Renewal Workbench

Self-contained description of the app + demo for an external reviewer who cannot run the app or read the code, written to be inspected through three personas (H&B actuary/underwriter, data-platform lead, exec sponsor). Facts only; verified against a fresh Reset of DEV (`lr_dev_aws_us_catalog.hb_renewal`, warehouse `a3b61648ea4809e3`) on 2026-08-24. Where something is stubbed / precomputed / seeded / synthetic / half-wired, it is flagged in place. All data synthetic (carrier "Meridian Assurance", employer "Harborview Logistics", etc.). Live app: `https://hb-renewal-workbench-7474656169654171.aws.databricksapps.com`.

Compute-source tags on numbers: **[UC]** governed function `fn_renewal_buildup`; **[STORED]** table value; **[VIEW]** SQL view; **[JS]** frontend arithmetic (flagged loudly — this is the only app-side math).

---

## 1. Surface census — every screen

Left sidebar: Overview (Daily view · Dashboard) · Pipeline (Ingestion · Book) · Renewal (Renewal Workspace · Benchmarks) · Intelligence (Agents · Ask the Book · Audit) · **Learn** (pinned bottom). No Presenter tab (removed; presenter content is a Google Doc linked from the hub).

### Daily view (`/api/overview`)
- **Purpose:** the renewal desk today.
- **KPI tiles [VIEW/STORED]:** In the book **53** · Active **50** · Needs attention **2** (quarantined 1 + differs 1) · Avg carrier action **25.4%** (avg of `5_scenario.baseline_action`) · Value negotiated **$12,975,304** (sum of `5_scenario.value_at_stake_annual`, status saved/approved).
- **Interactive:** **↺ Reset demo** (top-right) → confirm dialog → `POST /api/reset` triggers the serverless `hb_reseed` Job → polls `GET /api/reset/status` every 5 s (spinner "reseeding… Ns") → on success refreshes Daily view. **Open workspace →** (on the hero card) → `openDoc(hero_doc_id)` → loading spinner → Renewal Workspace. **"Needs your attention" rows** → click → quarantined row opens the quarantine view, active row opens the workspace. **Recent activity** rows: display only.
- **States:** loading = none (renders after `/api/overview`); empty attention = "Nothing in quarantine — the book is clean."; reset failure = "reset <state> (Ns)", button re-enabled.
- **Dead ends:** recent-activity rows are not clickable (display only) — not a stuck state (sidebar always available).

### Dashboard (`/api/config` → embedded Lakeview iframe)
- **Purpose:** board view over the same governed views.
- **Content [VIEW]:** KPI counters (renewals, avg carrier ask, avg negotiated, value negotiated), ask-vs-negotiated grouped bars (amber ask / green negotiated), value-negotiated by carrier, book-trend by carrier with padder coloring (Cascade red, Evergreen green), renewals-by-band pie, monthly claims line (Oct-2025 → Sep-2026). Dashboard `01f19d737ef41c468039d889d47d91a9`; also carries a native **Ask Genie** button (`uiSettings.genieSpace`).
- **Interactive:** the iframe (Lakeview's own controls + Ask Genie); **example follow-up chips** below → `askFromDashboard(q)` → navigates to Ask the Book (panel) and auto-runs the question.
- **VERIFY-MANUALLY:** the embedded dashboard iframe renders only on an authenticated Databricks browser session. Steps: log into the workspace, open the app, click Dashboard, confirm the tiles/charts render inline (on localhost/unauthenticated it shows a login wall).

### Ingestion (`/api/ingestion` + `/api/config`)
- **Purpose:** carrier file → governed rows.
- **Pipeline stage blocks** (① File lands in Volume → ② Fingerprint vs template → ③ Two-path extract → ④ Reconcile → ⑤ Quarantine/append): each is a **link to the real asset** (Volume, `0_carrier_template`, Claude endpoint, `1_source_document`) opening Catalog Explorer / serving-endpoint in a new tab.
- **"Behind the scenes — real assets"** panel: links to Volume, ingestion Job, tables, `fn_renewal_buildup`, Claude endpoint, `5_scenario`, `5_gov_audit_event`, `6_book_trend_benchmark`, Genie space, dashboard, reset Job.
- **Drop card:** file picker + **↥ Upload & ingest** → `POST /api/ingest/upload` (runs the pipeline live, ~10 s) → shows the two-path reconciliation result; **⟳ Scan inbox** → `POST /api/ingest/scan`. A note points to the `demo_files/` Volume folder + a Catalog Explorer link.
- **Carrier template registry [STORED]:** 2 rows (Meridian renewal_exhibit 6 tabs / monthly_claims).
- **Recent ingestions:** rows → `openIngestDetail(doc_id)` → drill-down: two-path reconciliation table (17/17 AGREE on the hero), **⬇ Download original submission** (`/api/document/{id}/file`, streams the archived `.xlsx` from the Volume, writes a `file_retrieved` audit), **🔗 Show lineage & governance**, **Open renewal workspace →**, **← Back**.
- **Dead ends:** the lineage **chain nodes** (`governed tables ← fn_renewal_buildup ← 2_renewal_inputs vN ← 1_source_document ← file`) are display-only spans — they look structured but are not clickable onward; only **Download original** and **Open workspace** act. (Cosmetic; §6.)

### Book (`/api/book`)
- **Purpose:** every renewal, all statuses.
- **Content [STORED/UC]:** 53 rows; carrier action per row is `max(5_scenario.baseline_action)` **[STORED]**, or for a fresh active exhibit with no scenario, computed live via `fn_renewal_buildup` **[UC]**.
- **Interactive:** search box + status-filter chips (active/differs/quarantined/superseded, with counts); row click → active → `openDoc` (workspace); quarantined/differs → quarantine view (with **← Back**).
- **States:** filter chips reflect counts; no empty state in seeded data.

### Renewal Workspace (`/api/document/{id}`)
- **Purpose:** reproduce + negotiate one renewal.
- **Carrier build-up table:** **Carrier column [UC]** (from `/api/document` baseline via `fn_renewal_buildup`); **Scenario column [JS]** (`computeBuildup`, frontend arithmetic). Lines + seeded hero values in §5.
- **Levers (right) [JS on drag]:** Annual trend, Months of trend, Demographic adj, Pooled claims credit, Benefit change, Target loss ratio, **Credibility (experience)**, Broker adjustment. Each `oninput` → `recompute()` → JS `computeBuildup`. Manual pool increase is shown in the build-up with 🔒 and is **not** a lever.
- **Result strip:** Carrier quoted **[UC]** = 26.9491%; **Your position [JS]**; **Value at stake / yr [JS]** (= baseline−scenario projected annual premium). Strip label reads "governed by fn_renewal_buildup" — accurate for the baseline and the saved record, **not** for the live JS preview.
- **Actions:** **💾 Save scenario** → modal (name + reason required, else HTTP 400) → `POST /api/scenario` recomputes via `fn_renewal_buildup` **[UC]**, inserts a `5_scenario` row (`status='saved'`) + a `scenario_saved` audit event. **✎ Draft exec summary** → `POST /api/summary` (FMAPI). **🔗 Lineage** → `/api/lineage` chain + **Download original**.
- **Compare panel [UC/STORED]:** Carrier proposal (baseline quoted **[UC]**) vs each saved scenario (`scenario_action`, `value_at_stake_annual` **[STORED]**).
- **Reforecast banner:** appears when `reforecast_months>12` (after a month13 drop). It is a **cue only** — no side-by-side recompute (V2).
- **Dead ends / no-approve:** a saved scenario cannot be **edited, deleted, or approved** in-app (`save_scenario` is insert-only, `main.py:147`; the only `approved` rows are seeded). §4 actuary.

### Benchmarks (`/api/benchmarks`)
- **Purpose:** book trend derived from retained decisions.
- **Table [VIEW]:** 19 rows (carrier × band) from `6_book_trend_benchmark`; padder/fair flags are **[JS]** thresholds (`book_trend_median>=0.078` padder, `<=0.058` fair). Full values in §5.
- **Interactive (fixed 2026-08-24):** row click → `openBenchmark(carrier,band)` → `GET /api/benchmark/scenarios` → inline lineage: the retained deals behind that cell + chain `6_book_trend_benchmark ← N retained decisions ← 5_scenario ← 1_source_document`.

### Agents (`/api/agents`)
- **Reviewer card [STORED, precomputed]:** 5 findings on the hero (narratives are **precomputed hardcoded strings** by default, `data/generate_reviewer.py`; live FMAPI only under `LIVE_REVIEWER=true`). Action: **Open the flagged renewal →** (`openDoc`).
- **Deal Summariser card:** **Draft a summary now** → `POST /api/summary` with the hero + `annual_trend:0.07` override (FMAPI) → renders an editable summary inline.
- **Genie card:** an **inline ask box** (`genieQuery` → `/api/genie/ask`) + **Open full Ask the Book →**.

### Ask the Book (`/api/genie/ask`, `/api/config`)
- **Two surfaces via toggle:** **Workbench panel** (example chips + input → `genieQuery` → NL answer + collapsible generated SQL + result table) and **Native Genie** (embedded iframe).
- **Genie behaviour:** returns text + SQL + rows; for "richest carrier" / "biggest gap" it may phrase the narrative as a clarifying question while still returning the correct rows (Cascade Care). Error handling: any failure returns `{error}` (HTTP 200) → banner "Genie not available".
- **VERIFY-MANUALLY:** the Native Genie iframe (auth-gated). Steps: authenticated session → Ask the Book → Native Genie → confirm the embed renders.

### Audit (`/api/audit`)
- **Table [STORED]:** last 40 `5_gov_audit_event` rows. Clean-state total 12 (ingested 1, archived 1, extraction_differs 1, quarantined 1, superseded 1, scenario_approved 7).
- **Interactive:** entity ids starting `SCN`/`DOC` → `openProvenance` → `/api/deal` or `/api/document` → provenance chain (deal → source_document → file) + **⬇ Download original submission**. Historical seeded deals show "not archived" (no `stored_path`); the hero + live uploads download.

### Learn (`/api/learn`)
- Nine-activity journey (3 group bands), one card open at a time, inline-SVG schematics. Each card: activity → how → "See it live" links (external Catalog-Explorer/Job/Genie/dashboard, or in-app view anchors). "❓ how does this work?" glyphs on Book/Workspace/Benchmarks/Ask open Learn at nodes 2/3/8/9.

---

## 2. Click-flow walkthroughs (freshly reset state, per reordered runsheet beat)

**0 Problem** — verbal, no screen.
**1 Daily view** — Overview→Daily view. Screen: hero card "Harborview Logistics — Meridian Assurance · 2026H2", tiles 53/50/2/25.4%/$12,975,304, attention list (Cascade Fernbrook quarantined, Summit Oakmont differs), recent activity.
**2 Ingest** — Ingestion→Upload→drop `meridian_harborview_2026H2.xlsx`. **During ~10 s:** button shows "Extracting (two paths)… ⟳". After: result card "active · 17/17"; open drill-down → 17-row reconciliation, all AGREE. **On failure:** result shows `{error}`; fallback = the hero is already active (book non-empty). File-arrival Job path instead: ~57 s (drop into `landing/inbox`), nothing on screen until the row appears in Recent ingestions.
**3 Quarantine** — drop `meridian_brokenlayout.xlsx`. **During ~11 s:** spinner. After: "quarantined 15/17", field diff (annual_trend, member_months missing). Fallback: seeded `DOC-Q900`.
**4 Matches** — Book→Harborview row→Workspace (spinner while `/api/document` runs the function). Build-up left column = the exhibit line-by-line; blended action **26.9491%**.
**5 Negotiate** — Levers→Annual Trend→7.0% (Scenario column + strip update instantly **[JS]**): Your position **22.97%**, Value at stake **$183,525**. Save (name "Trend to book", reason "Carrier trend 5.2pts above our book median") → alert "Saved SCN-… — $183,525/yr". Then ✎ Draft exec summary → summary text. **On save failure:** modal alert; nothing persisted.
**6 Reforecast** — drop `..._month13.xlsx` (~10 s) → Workspace banner "Fresh data available — 13 claims months loaded". **On failure:** skip, mention verbally.
**7 Benchmarks** — Renewal→Benchmarks. 19 rows; Cascade highlighted padder (amber), Evergreen fair (green). Click a row → inline retained-deals lineage.
**8 Agents** — Intelligence→Agents. Reviewer 5 findings; Draft-a-summary inline; Genie inline ask.
**9 Ask the book** — toggle Workbench panel; chip "Which carrier runs richest…" → answer names Cascade + SQL + 1 row.
**10 Dashboard** — Overview→Dashboard (auth-gated iframe — see VERIFY-MANUALLY).
**11 Audit** — Intelligence→Audit→click a `SCN`/`DOC` → provenance + download.
**11b Learn** — bottom→Learn→nodes 1/5/8.

**Presenter vs projection:** the embedded **Dashboard** and **Native Genie** iframes need the presenter's authenticated session; on a shared projection of an unauthenticated browser they show a login wall. Everything else (workbench Genie panel, drill-downs, build-up, benchmarks) renders without the iframe.

---

## 3. State machine — what the demo mutates

**Starting state (post-Reset, deterministic):** `1_source_document` 53 (active 50, differs 1 `DOC-D901`, quarantined 1 `DOC-Q900`, superseded 1 `DOC-S902`); `5_scenario` 49 (all `approved`); `4_reviewer_finding` 5; `5_gov_audit_event` 12; `1_incurred_claims` 12; `1_large_claims` 12; `1_detailed_rates` 24 (12 current/12 renewal); `2_renewal_inputs` 1; `0_carrier_template` 2. Volume `demo_files/` has the 4 synthetic files; `processed/` has the hero archive.

| Live action | Mutates | Reversible in-app? | Repeat (idempotency) |
|-------------|---------|--------------------|----------------------|
| Hero drop (upload/scan) | new `1_source_document` (active) + supersedes prior active same group+period + 12 incurred + 12 large + 24 detailed + 1 renewal_inputs + `ingested`/`archived` audit + Volume `processed/` file | No (Reset only) | Each run supersedes the previous hero; book stays 1 active hero but `doc_id` changes; numbers identical |
| Broken drop | new `1_source_document` (quarantined) + `quarantined`/`archived` audit; **no source rows** | No | Each run adds another quarantined doc → **attention count grows** (2→3→…) |
| v2 drop | supersedes the active hero, new active (annual_trend **0.105**, so blended ≠ 26.9491%) | No | Supersedes again |
| month13 drop | appends 1 row to `1_incurred_claims` on the active hero + `reforecast_data` audit | No | **Keeps appending** (13→14→… months) |
| Lever move | none (client-side preview only) | Yes (reset lever) | n/a |
| Scenario save | +1 `5_scenario` (`saved`) + `scenario_saved` audit + Delta version on `5_scenario` | No (no delete in-app) | Each save adds another row; benchmark for that carrier×band shifts |
| Summary run | none | — | Re-runs FMAPI; text varies |
| Genie ask | none (read) | — | Stateful within the conversation |

**Ordering constraints:**
- **Drop v2 before beat 4/5 and you poison the trust beat:** the active hero becomes the v2 exhibit (trend 0.105), so "matches your sheet 26.9491%" no longer holds. Keep v2 out of the main flow (it is not a numbered beat).
- **Save the hero scenario (beat 5) before Benchmarks (beat 7)** and the **Meridian Assurance / 100-499** benchmark row shifts (count 3→4; the view includes `status IN (saved,approved)`). Cascade/Evergreen rows are unaffected (different carrier) — so the padder/fair story still reads, but don't quote the Meridian 100-499 figures after saving.
- **Broken/v2/month13 are additive and not auto-undone** — only Reset returns to the exact starting counts.

---

## 4. Persona interrogation

### Actuary / underwriter — checks the math by hand
Opens the hero build-up and reproduces each line against the method (seeded values; all PMPM unless noted). Verified vs `fn_renewal_buildup`:
- incurred PMPM = 4,186,930.44 / 5,412 = **773.638** ✓
- adjusted = 773.638 × 1.0142 = **784.624** ✓
- experience claim cost = 784.624 − 158.75 = **625.874** ✓
- effective trend = 1.122^(15/12) − 1 = **0.154758** ✓ (⚠ **misread risk:** this is 15 **months** of a 12.2% **annual** trend compounded → 15.48%, not 12.2%; the build-up shows both — read the "Effective trend" line, not "Annual trend").
- projected medical = 625.874 × 0.984 × 1.154758 + 133.40 + 111.25 = **955.819** ✓
- experience premium = 955.819 / 0.918 × 1.045 = **1088.051** ✓
- experience-based increase = 1088.051 / 831.40 − 1 = **0.308698** ✓
- blended = 0.71 × 0.308698 + 0.29 × 0.1735 = **0.2694905** = **26.9491%** ✓ ; quoted = blended + 0 = 26.9491% ✓
- **PMPM vs annual (misread risk):** the headline is a % change; the $ figures (`projected_billed_premium_annual` 5,851,439 vs current 4,609,282) are annual and members×12 — don't compare a PMPM line to an annual line.
- **Lever edge cases:** `member_months` is **not** a lever (no div-by-zero reachable via UI). Extreme trend (e.g. 100%) → preview shows a very large %, no guard. **Credibility (experience) lever — real defect:** the JS preview auto-sets manual weight = 1 − experience so it sums to 1 (`computeBuildup`), but **`save_scenario` sends only the changed experience weight to the UC function**, leaving manual weight at the original 0.29 → the **saved** blended action ≠ the preview and the weights **don't sum to 1**. Verdict: **breaks** → *"Leave the credibility lever alone in the demo — trend is the lever that tells the story."*
- **Scenario lifecycle:** a saved scenario **cannot be edited, deleted, or approved** in the app (insert-only, `main.py:147`); seeded history is `approved`, live saves are `saved`. Verdict: holds-with-caveat → *"Decisions are append-only and audited; approval workflow is roadmap."*
- **Self-funded:** searches every screen — **finds nothing** (no self-funded control; `app/selffunded.py` exists but is unwired). Verdict: holds-with-caveat → *"Engine exists, wiring is V2 — same levers, different funding math."*
- **Manual rate:** locked 🔒, correctly not challengeable. Holds.

### Platform lead — hostile infra inspection
- **Deep links:** every link is `{host}/explore/data/…`, `/jobs/{id}`, `/genie/rooms/{id}`, `/dashboardsv3/{id}` built from `Config().host` + catalog/schema (no hardcoded host). They land in Catalog Explorer / Jobs / Genie / Lakeview. **A non-admin needs UC grants on the objects** to see them. Verdict: holds-with-caveat. **VERIFY-MANUALLY:** open each as a non-admin principal and confirm visibility.
- **App SP grants:** `b417c702-…` has `USE`/`SELECT`/`EXECUTE`/`MODIFY` on the schema, `CAN_USE` warehouse, `CAN_RUN` Genie, `CAN_READ` dashboard, `CAN_MANAGE_RUN` on the reseed Job. **The app can write:** `5_scenario`, `5_gov_audit_event`, the source tables (via upload/scan/reset), and the Volume archive — all under `MODIFY`. No delete path exposed.
- **SQL from user input:** the app builds SQL by **string interpolation with `sq()`** (single-quote doubling for strings, `repr()` for numbers) — not parameter binding. User-supplied strings that reach SQL: scenario name/reason, `doc_id`, benchmark carrier/band, Genie question (Genie question goes to the Genie API, not app SQL). Verdict: holds-with-caveat → *"Inputs are escaped, not parameterised; a demo risk only if someone types a quote-heavy string."*
- **FMAPI / data egress:** `extract_ai`, the Deal Summariser, and the live Reviewer POST sheet text + numbers to `{host}/serving-endpoints` (Databricks Foundation Model API, model `databricks-claude-sonnet-4-5`) — **stays within the Databricks workspace/account boundary**; nothing leaves to a third-party endpoint. Bearer is the SP's own OAuth token (`main.py:275-276`).
- **Lineage table-version claim — important:** the lineage panel's `table_versions` come from `DESCRIBE HISTORY … LIMIT 1` (`main.py:209`) → the **current/latest** version, **not the version pinned at the moment the number was computed**. Verdict: holds-with-caveat → *"It shows the current governed version of the table, not a compute-time snapshot — Delta history is the audit, this panel is the pointer."*

### Exec sponsor — does the money reconcile
- **Value negotiated reconciles across surfaces:** Daily view KPI, Benchmarks `total_value_negotiated` sum, `mv_renewal_actions`, and the sum of `5_scenario.value_at_stake_annual` all equal **≈ $12,975,304** (agree to <$3 rounding). Verdict: holds.
- **$183k vs $12.97M — do not conflate:** the **$183,525** in beat 5 is **one live deal** (hero at 7% trend); the **$12.97M** is the **whole seeded book** (49 approved deals). Two different things on two screens. Verdict: holds-with-caveat → *"$183k is one renewal we just challenged; $12.97M is the book we've already negotiated."*
- **Superlatives in copy:** app copy avoids "seamless/powerful/robust"; benchmark explainer says "not a licensed data feed … computed live" — true (derived view). "One governed source, many surfaces" — true (all screens read the same UC objects). No superlative contradicts what's underneath.

---

## 5. Numbers appendix

| Number | Source | Deterministic? |
|--------|--------|----------------|
| 26.9491% (blended/quoted) | `fn_renewal_buildup` on the seeded hero inputs **[UC]** | Yes |
| 12.2% carrier trend / 7.02% book / 5.2 pts | `2_renewal_inputs.annual_trend` vs `4_reviewer_finding.book_value` | Yes |
| 7.0% negotiated → 22.97% quoted | `fn_renewal_buildup` with `annual_trend=0.07` | Yes |
| $183,525 ("~$183k") | base − scenario `projected_billed_premium_annual` at 7% **[UC]** | Yes |
| $12,975,304 (value negotiated) | sum `5_scenario.value_at_stake_annual` (saved/approved) | Yes (unless you save a live scenario → grows) |
| 17/17 fields | `1_source_document.fields_found/expected` on hero | Yes |
| 53 / 50 active / 49 scenarios / 5 findings / 12 audit / 24 detailed | seed counts | Yes |
| Cascade 8.09% (100-499), 8.2% (2000+) padder; Evergreen 5.4% fair | `6_book_trend_benchmark` **[VIEW]** | Yes (seed rng fixed) |
| Cascade 2000+ value $3,851,104 | `6_book_trend_benchmark.total_value_negotiated` | Yes |
| Claims Oct-2025 $339,141 → Sep-2026 $347,515 (12 mo) | `mv_claims_experience` | Yes |
| Live-drop timings ~10 s upload / ~57 s Job | measured, environment-dependent | **VARIES — never promise verbatim** |
| hero `doc_id` (e.g. `DOC-MER-5bbd3d`), scenario ids | uuid at seed time | **VARIES per Reset — don't read aloud as fixed** |
| Reviewer narratives | precomputed strings (or FMAPI if `LIVE_REVIEWER`) | Yes by default |

---

## 6. Known weaknesses register (ranked by embarrassment-in-the-room; one-liners ≤20 words)

**(a) Breaks under one click**
1. **Credibility (experience) lever:** preview auto-balances weights; the saved value doesn't → saved ≠ preview, weights ≠ 1. *"Don't touch the credibility lever — trend is the lever that tells the story."*
2. **Embedded Dashboard / Native Genie on an unauthenticated projection:** login wall. *"These embed in my session; here's the same data in the workbench panel."*

**(b) Holds only if the presenter avoids X**
3. **Live lever numbers are client-side:** Your position / Value at stake are JS until Save. *"The saved number is the governed one; the slider is a live preview."*
4. **Dropping v2 before the trust beat** replaces the hero with a different number. *"v2 isn't in the flow — it's the supersession example, shown separately."*
5. **Saving the hero scenario before Benchmarks** shifts the Meridian 100-499 row. *"That row just moved because we saved a decision — that's the point."*
6. **Repeating a live drop** keeps adding docs/months (broken → attention grows; month13 → 14 months). *"Each drop is a real event; Reset returns to a clean book."*
7. **$183k vs $12.97M** confusion. *"$183k is this one deal; $12.97M is the book we've already negotiated."*
8. **Genie phrasing:** "richest carrier" may come back as a clarifying question. *"It's asking to refine — the rows already show Cascade on top."*
9. **Reforecast banner** has no side-by-side recompute. *"It flags the data moved; side-by-side recompute is next."*
10. **No edit/delete/approve of a saved scenario.** *"Decisions are append-only and audited; an approval step is roadmap."*
11. **Self-funded** has no control. *"Engine's there, wiring is V2 — same levers, different funding math."*

**(c) Cosmetic**
12. **Lineage chain nodes look clickable but aren't** (only Download/Open act). *"The chain's the map; the file's the click."*
13. **Lineage shows current table version, not compute-time.** *"That's the current governed version; Delta history is the full audit."*
14. **Inputs escaped, not parameterised** (`sq()`). *"Inputs are escaped; parameter binding is a hardening item."*
15. **`1_detailed_rates` / benefits are illustrative** (per-contract, not reconciled to the PMPM build-up). *"Rate detail is illustrative; the build-up is the governed number."*
