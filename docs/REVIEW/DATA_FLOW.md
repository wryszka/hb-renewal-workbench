# Data Flow — four end-to-end traces

Traces one file each through the pipeline, naming the exact code path (`file:function:line`) and the exact rows/columns written at every step. All four run through the **same** `jobs/ingest_pipeline.py` (byte-identical copy at `app/ingest_pipeline.py`), whether invoked by the seed, the serverless Job (`jobs/run_ingest_job.py`), or the app endpoints (`POST /api/ingest/upload`, `POST /api/ingest/scan`).

**Shared front matter (every file):**
1. **Entry.** `run_ingest_job.main()` lists `/Volumes/.../landing/inbox`, downloads each `.xlsx` to `/tmp`, calls `ingest_pipeline.process_file(local, actor)`. (In-app: `POST /api/ingest/upload` writes the upload to `/tmp` and calls the same function — `app/main.py:339`.)
2. **`process_file`** — `jobs/ingest_pipeline.py:251`. Reads bytes, `file_name = basename`, `meta = identify(file_name)` (`:230`), `sheets = _rows(data)` (openpyxl, `:88`), `doc_id = "DOC-<CAR>-<hex6>"`.
3. **`identify`** (`:230`) parses `carrier_key`/`group`/`period` from the filename, matches a `0_carrier_template` row (`LIKE '<carrier_key>%'`), sets `doc_family = "monthly_claims"` if the stem contains "month" else `"renewal_exhibit"`, and returns `expected_tabs` + `field_count`.

The `doc_family` decides the branch. Then:

---

## Trace 1 — hero file (happy path → `active`)

**File:** `meridian_harborview_2026H2.xlsx` → carrier Meridian Assurance, group Harborview Logistics, period 2026H2, family `renewal_exhibit`. Measured end-to-end: **18.7 s** (includes the FMAPI extraction call).

1. **Fingerprint.** `present = set(sheets)`; `missing_tabs = expected_tabs − present` (`:262`). Hero has all four tabs → `missing_tabs = []`.
2. **Two-path extraction.**
   - `extract_deterministic(sheets)` (`:99`) — walks every row, matches labels in `FIELD_LABELS` (17 fields incl. `member_months`, `annual_trend`, `target_loss_ratio`, credibility weight from the blend block). Returns `{field: {value,label,sheet}}`.
   - `extract_ai(sheets)` (`:131`) — flattens the sheets to text, prompts FMAPI `databricks-claude-sonnet-4-5` for the same fields as JSON. On failure it is caught and the run proceeds deterministic-only (`:267` try/except).
3. **Reconcile.** `reconcile(det, ai)` (`:162`) compares field-by-field: `agree` if within 2 % (or 1e-6), else `differs`; `det-only`/`ai-only`/`missing`. Returns `(recon rows, found, expected, disagreements)`. Hero: 17 found / 17 expected / 0 disagreements.
4. **Gate.** `core_ok = all CORE_FIELDS present`; branch condition `if missing_tabs or not core_ok or disagreements>0` is **False** → active path.
5. **Supersede prior active** (`:305`). `SELECT doc_id FROM 1_source_document WHERE employer_group=… AND policy_period=… AND status='active'`; for each, `UPDATE … SET status='superseded'` (`:307`) + `audit('superseded', …)`. (On a clean first ingest: none.)
6. **Load source rows.**
   - `parse_monthly(sheets)` → `INSERT INTO 1_incurred_claims` (`:318`) — **12 rows**, columns `(source_document_id=doc_id, carrier, employer_group, month, billed_premium, ffs_medical, pharmacy, fixed_charges, out_of_network=NULL, total_incurred, med_ees, med_members)`.
   - `parse_large(sheets)` → `INSERT INTO 1_large_claims` (`:323`) — **12 rows**, `(source_document_id, carrier, employer_group, status, ee_dep, diagnosis=NULL, amount)`.
   - `1_detailed_rates`: **no insert** (no `parse_detailed`; table stays empty — D-3).
   - `INSERT INTO 2_renewal_inputs` (`:327`) — **1 row**, all 26 columns; `current_total_premium_monthly = current_premium_pmpm × members`, `credibility_experience_weight` from extraction (default 0.652), `credibility_manual_weight = 1 − exp_w`.
7. **Archive original.** `archive(data, doc_id, file_name, quarantined=False)` (`:73`) uploads bytes (via `io.BytesIO`) to `/Volumes/lr_dev_aws_us_catalog/hb_renewal/landing/processed/{doc_id}__meridian_harborview_2026H2.xlsx`; returns the path.
8. **Provenance row.** `INSERT INTO 1_source_document` (`:340`) — **1 row**: `status='active'`, `fields_found=17`, `fields_expected=17`, `reconciliation_detail = {found, expected, reconciliation:[…]}` (full two-path table), `stored_path=<Volume path>`, `signed_off_* = NULL`.
9. **Audit.** `audit('ingested', 'source_document', doc_id, "17/17 fields, both paths agree; 12 months, 12 large claims")` (`:344`) then `audit('archived', …, stored_path)` — **2 events**.
10. **Return** `{status:'active', doc_id, found:17, expected:17, recon, stored_path}`.

**Downstream visibility.** `v_2_renewal_inputs_latest` / `v_1_incurred_claims_latest` now resolve to this doc (status active). App `/api/document` calls `fn_renewal_buildup(...)` on the row → blended action **26.9491%**. Lineage (`/api/lineage`) resolves number → function → `2_renewal_inputs` version → `1_source_document` → `stored_path` file.

---

## Trace 2 — broken file (quarantine path)

**File:** `meridian_brokenlayout.xlsx` — a Rate Development sheet with a renamed trend label and a dropped "Member Months" row. Family `renewal_exhibit`. Measured end-to-end: **11.3 s**.

1. Steps 1–3 as above. Deterministic extraction misses `member_months` (row absent) and `annual_trend` (label "Trend Rate (annual)" not in `FIELD_LABELS`). `reconcile` → found ≈ 15/17.
2. **Gate** (`:290`). `core_ok = all(CORE_FIELDS present)` is **False** (`member_months`, `annual_trend` ∈ `CORE_FIELDS`) → `status = 'quarantined'`.
3. **No source rows land.** The quarantine branch does **not** call `parse_monthly`/`parse_large` or insert into `1_incurred_claims`/`1_large_claims`/`2_renewal_inputs`.
4. **Archive to quarantine.** `archive(data, doc_id, file_name, quarantined=True)` → `/Volumes/.../landing/quarantine/{doc_id}__meridian_brokenlayout.xlsx`.
5. **Provenance row.** `INSERT INTO 1_source_document` (`:293`) — **1 row**: `status='quarantined'`, `fields_found≈15`, `fields_expected=17`, `reconciliation_detail = {missing_tabs, found, expected, disagreements, fields:[{field,status} for non-agree]}`, `stored_path=<quarantine path>`.
6. **Audit.** `audit('quarantined', 'source_document', doc_id, "15/17 fields; missing tabs []; 0 disagreements")` (`:298`) + `audit('archived', …)` if archived.
7. **Return** `{status:'quarantined', doc_id, found, expected, missing_tabs, recon, stored_path}`.

**Note on `differs`:** if tabs and core fields are present but the two paths disagree on a non-core field (`disagreements>0`), the same branch sets `status='differs'` instead of `quarantined` (rows still do not land). This is the state of the seeded `DOC-D901`.

---

## Trace 3 — v2 file (supersession)

**File:** `meridian_harborview_2026H2_v2.xlsx` — same carrier/group/period as the hero, `annual_trend` changed to 0.1050. Family `renewal_exhibit`.

1. Steps 1–4 as Trace 1 → active path (all tabs, core ok, 0 disagreements).
2. **Supersede** (`:305`). `SELECT … WHERE employer_group='Harborview Logistics' AND policy_period='2026H2' AND status='active'` returns the hero `doc_id`. `UPDATE 1_source_document SET status='superseded' WHERE doc_id=<hero>` (`:307`) + `audit('superseded', 'source_document', <hero_id>, "replaced by <v2_id>")`.
3. Loads source rows tagged with the **v2** `doc_id` (12 incurred, 12 large, 1 renewal_inputs), archives to `processed/`, inserts a new `active` `1_source_document` row, `audit('ingested')` + `audit('archived')`.
4. **Return** `{status:'active', doc_id:<v2>, …}`.

**Downstream.** `v_*_latest` now resolve to the v2 doc (the hero's rows are excluded because its status is `superseded`). Smoke #5 asserts `hero → superseded, v2 → active`.

---

## Trace 4 — month-13 file (reforecast)

**File:** `meridian_harborview_2026H2_month13.xlsx` — a single fresh claims month ("Oct-2026"), only a Claims Experience sheet. `identify` sets family `monthly_claims` (stem contains "month").

1. **Reforecast branch** (`:262`, `if meta["doc_family"]=="monthly_claims"`).
2. **Find active chain.** `SELECT doc_id FROM 1_source_document WHERE employer_group='Harborview Logistics' AND status='active' ORDER BY ingested_at DESC LIMIT 1` (`:267`). If none → returns `{status:'orphan'}` and stops.
3. **Append months.** `parse_monthly(sheets)` → `INSERT INTO 1_incurred_claims` (`:271`) with `source_document_id = <target active doc_id>` — **1 row** (the new month), columns as Trace 1 step 6.
4. **No new `1_source_document` row, no supersession.** The month is attached to the existing active document.
5. **Audit.** `audit('reforecast_data', 'source_document', <target>, "appended 1 fresh claims month(s)")`.
6. **Return** `{status:'reforecast', doc_id:<target>, months:1}`.

**Downstream.** `v_1_incurred_claims_latest` gains the extra month for the active document; the app Workspace shows a "fresh data available" affordance. Smoke #6 asserts `appended 1 month`.

---

## Cross-cutting facts

- **Provenance key.** Every source row carries `source_document_id = doc_id`; `v_*_latest` join back to `1_source_document` and keep only `status='active'`. Supersession and quarantine are therefore purely status-driven — no row deletion.
- **Audit coverage.** Ingest emits `ingested`+`archived`; quarantine emits `quarantined`(+`archived`); differs emits `extraction_differs`; supersede emits `superseded`; reforecast emits `reforecast_data`; the app emits `scenario_saved` and `file_retrieved`.
- **`stored_path`** (added 2026-08-22) is written by the pipeline for `active`/`differs`/`quarantined` renewal-exhibit docs; reforecast (no new doc row) does not set one. Seeded historical/governance rows have `stored_path=NULL` and honestly show "not archived" in the app.
