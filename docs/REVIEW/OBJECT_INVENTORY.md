# Object Inventory — HB Renewal Workbench

Every deployed object in `lr_dev_aws_us_catalog.hb_renewal`, verified live 2026-08-22 (post `seed_book.py` + `generate_reviewer.py`). Row counts are the clean demo state.

**Naming note:** numeric prefixes encode the layer — `0_` registry, `1_` source, `2_` assumptions, `4_` reviewer, `5_` decision/audit, `6_` benchmark, `v_*_latest` active-only views, `mv_*` consumption views, `fn_*` governed functions.

---

## Tables (all MANAGED Delta)

| Object | Rows | Purpose | Created by |
|--------|-----:|---------|------------|
| `0_carrier_template` | 2 | Carrier layout registry: expected tabs + field map per carrier/doc-family. A new carrier is a row, not new code. | `data/build_schema.py:73` (+ seed rows `:111`) |
| `1_incurred_claims` | 12 | Monthly incurred-claims experience (one row per document per month). | `data/build_schema.py:35`; loaded by `jobs/ingest_pipeline.py` `parse_monthly` |
| `1_large_claims` | 12 | Large/pooled claimants above the pooling point. | `data/build_schema.py:41`; loaded by `parse_large` |
| `1_detailed_rates` | 24 | Current-vs-renewal premium rates by plan×tier (12 current + 12 renewal), populated by `parse_detailed` from the demo file's Detailed Rates sheet (D-3 resolved). | `data/build_schema.py:46`; loaded by `parse_detailed` |
| `2_renewal_inputs` | 1 | The renewal assumption set / levers extracted from an exhibit (one active row = the hero). | `data/build_schema.py:51`; loaded by `ingest_pipeline.process_file:327` |
| `1_source_document` | 53 | Intake + assurance provenance: one row per ingested file, its reconciliation result, status, sign-off, and archived-original Volume path (`stored_path`). | `data/build_schema.py:64`; rows from pipeline + `seed_book.py` |
| `4_reviewer_finding` | 5 | Reviewer-agent findings challenging carrier assumptions vs book/method. | `data/build_schema.py:94`; rows from `data/generate_reviewer.py` |
| `5_scenario` | 49 | Retained negotiation decisions (who/when/what-changed/why/value-at-stake). | `data/build_schema.py:80`; rows from `seed_book.py` + `POST /api/scenario` |
| `5_gov_audit_event` | 12 | Append-only governance audit trail. | `data/build_schema.py:89`; rows from pipeline + app |

**`1_source_document` state breakdown (53):** active 50, differs 1 (`DOC-D901`), quarantined 1 (`DOC-Q900`), superseded 1 (`DOC-S902`).
**`5_scenario` status breakdown:** approved 49 (0 `saved`/`draft` in clean state — live demo saves create `saved` rows).
**`5_gov_audit_event` types:** ingested 1, archived 1, extraction_differs 1, quarantined 1, superseded 1, scenario_approved 7 (the seed emits one approval event per 7 historical scenarios — the trail is intentionally sparse for history).
**`4_reviewer_finding` severities:** high 1, medium 2, low 1, ok 1 (all on the hero document).

### Column schemas

**`1_source_document`** — `doc_id STRING, carrier STRING, employer_group STRING, policy_period STRING, file_name STRING, doc_family STRING, ingested_at TIMESTAMP, fields_expected INT, fields_found INT, reconciliation_detail STRING, status STRING, signed_off_by STRING, signed_off_at TIMESTAMP, stored_path STRING` (`stored_path` added 2026-08-22).

**`2_renewal_inputs`** — `source_document_id STRING, carrier STRING, employer_group STRING, experience_start STRING, experience_end STRING, months_experience INT, funding_type STRING, individual_pooling_point DOUBLE, renewal_effective STRING, demographic_adjustment DOUBLE, less_pooled_claims_pmpm DOUBLE, benefit_change DOUBLE, annual_trend DOUBLE, months_of_trend DOUBLE, projected_excess_claims_pmpm DOUBLE, large_claim_add_back_pmpm DOUBLE, current_members INT, current_total_premium_monthly DOUBLE, target_loss_ratio DOUBLE, benefit_advisor_fee DOUBLE, manual_rating_pool_increase DOUBLE, credibility_experience_weight DOUBLE, credibility_manual_weight DOUBLE, adjustment DOUBLE, member_months DOUBLE, total_incurred_claims DOUBLE`.

**`5_scenario`** — `scenario_id STRING, source_document_id STRING, carrier STRING, employer_group STRING, scenario_name STRING, created_by STRING, created_at TIMESTAMP, base_source STRING, overrides STRING, baseline_action DOUBLE, scenario_action DOUBLE, value_at_stake_annual DOUBLE, reason STRING, status STRING, parent_scenario_id STRING`.

**`5_gov_audit_event`** — `event_id STRING, event_type STRING, entity_type STRING, entity_id STRING, detail STRING, actor STRING, created_at TIMESTAMP`.

**`4_reviewer_finding`** — `source_document_id STRING, finding_type STRING, severity STRING, lever STRING, carrier_value DOUBLE, book_value DOUBLE, narrative STRING, created_at TIMESTAMP, generated_by STRING` (`generated_by` ∈ {precomputed, fmapi}).

**`0_carrier_template`** — `carrier STRING, template_version STRING, doc_family STRING, expected_tabs ARRAY<STRING>, field_map STRING (JSON), field_count INT, status STRING`.

**`1_incurred_claims`** — `source_document_id STRING, carrier STRING, employer_group STRING, month STRING, billed_premium DOUBLE, ffs_medical DOUBLE, pharmacy DOUBLE, fixed_charges DOUBLE, out_of_network DOUBLE, total_incurred DOUBLE, med_ees INT, med_members INT`.

**`1_large_claims`** — `source_document_id STRING, carrier STRING, employer_group STRING, status STRING, ee_dep STRING, diagnosis STRING, amount DOUBLE`.

**`1_detailed_rates`** — `source_document_id STRING, carrier STRING, employer_group STRING, kind STRING, plan STRING, tier STRING, subs INT, rate DOUBLE`.

---

## Views

| Object | Type | Purpose | Created by |
|--------|------|---------|------------|
| `v_1_incurred_claims_latest` | VIEW | `1_incurred_claims` restricted to rows from `status='active'` documents. | `data/build_schema.py:199` (loop) |
| `v_1_large_claims_latest` | VIEW | active-only large claims | `data/build_schema.py:199` |
| `v_1_detailed_rates_latest` | VIEW | active-only detailed rates (0 rows, since base is empty) | `data/build_schema.py:199` |
| `v_2_renewal_inputs_latest` | VIEW | active-only renewal inputs | `data/build_schema.py:199` |
| `v_source_document_latest` | VIEW | `1_source_document` excluding `superseded` | `data/build_schema.py:206` |
| `6_book_trend_benchmark` | VIEW | Book trend benchmark **derived from `5_scenario`** by carrier/band. | `data/build_schema.py:211` |
| `mv_renewal_actions` | VIEW (plain SQL; **not** a UC metric view) | Carrier vs negotiated action + value-at-stake by carrier/band/period, for Genie & the dashboard. | `data/build_schema.py` (added in the post-review pass — was previously ad-hoc; D-16) |
| `mv_claims_experience` | VIEW (plain SQL) | Monthly PMPM + members by carrier/group, for Genie & the dashboard. | `data/build_schema.py` (D-16) |

**`6_book_trend_benchmark` DDL (verbatim, key columns):**
```sql
CREATE VIEW hb_renewal.`6_book_trend_benchmark` (...) WITH SCHEMA COMPENSATION AS
SELECT carrier, get_json_object(overrides,'$.group_band') AS group_band,
  count(*) AS renewals_negotiated,
  round(avg(cast(get_json_object(overrides,'$.annual_trend') AS DOUBLE)),4) AS book_trend_avg,
  round(percentile_approx(cast(get_json_object(overrides,'$.annual_trend') AS DOUBLE),0.5),4) AS book_trend_median,
  round(avg(baseline_action),4) AS avg_carrier_action,
  round(avg(scenario_action),4) AS avg_negotiated_action,
  round(avg(baseline_action)-avg(scenario_action),4) AS avg_negotiation_delta,
  round(sum(value_at_stake_annual),0) AS total_value_negotiated
FROM 5_scenario WHERE status IN ('saved','approved')
GROUP BY carrier, get_json_object(overrides,'$.group_band');
```

**`mv_renewal_actions` DDL (verbatim):**
```sql
CREATE VIEW hb_renewal.mv_renewal_actions (...) WITH SCHEMA COMPENSATION AS
SELECT s.carrier, get_json_object(s.overrides,'$.group_band') AS group_band, d.policy_period,
  count(*) AS renewals, round(avg(s.baseline_action),4) AS avg_carrier_action,
  round(avg(s.scenario_action),4) AS avg_negotiated_action, round(sum(s.value_at_stake_annual),0) AS total_value_at_stake
FROM 5_scenario s JOIN 1_source_document d ON d.doc_id=s.source_document_id
GROUP BY s.carrier, get_json_object(s.overrides,'$.group_band'), d.policy_period;
```

**`mv_claims_experience` DDL (verbatim):**
```sql
CREATE VIEW hb_renewal.mv_claims_experience (...) WITH SCHEMA COMPENSATION AS
SELECT c.carrier, c.employer_group, c.month, c.total_incurred, c.med_members,
  round(c.total_incurred/nullif(c.med_members,0),2) AS pmpm
FROM v_1_incurred_claims_latest c;
```

---

## Volume

| Object | Purpose | Created by |
|--------|---------|------------|
| `landing` | File ingestion landing zone with `inbox/`, `processed/`, `quarantine/`, and `demo_files/` prefixes. Originals are archived to `processed/{doc_id}__{file}.xlsx` or `quarantine/…` (referenced by `1_source_document.stored_path`). `demo_files/` holds the four synthetic demo exhibits for download by anyone running the demo (no repo needed), staged by `data/stage_demo_files.py` and restaged by the reset Job. | `data/build_schema.py:32` |

Live: `processed/` holds one file (the current hero, ~8.9 KB); `quarantine/` empty in clean state.

---

## UC Functions

| Object | Purpose | Created by |
|--------|---------|------------|
| `fn_renewal_action(...18 args...) → DOUBLE` | Governed renewal method: returns the quoted change in billed premium. | `data/build_schema.py:122` |
| `fn_effective_trend(annual_trend, months) → DOUBLE` | Compounded trend over the projection period. | `data/build_schema.py:147` |
| `fn_renewal_buildup(...18 args...) → STRING (JSON)` | Full build-up (every exhibit line) as JSON — the single governed compute path the app calls. | `data/build_schema.py:156` |

### `fn_renewal_action` — signature & body

**Signature (18 DOUBLE args):** `member_months, total_incurred_claims, months_experience, current_members, current_total_premium_monthly, demographic_adjustment, less_pooled_claims_pmpm, benefit_change, annual_trend, months_of_trend, projected_excess_claims_pmpm, large_claim_add_back_pmpm, target_loss_ratio, benefit_advisor_fee, manual_rating_pool_increase, credibility_experience_weight, credibility_manual_weight, adjustment` → `RETURNS DOUBLE LANGUAGE PYTHON`.

**Body (verbatim logic):**
```python
incurred_pmpm = total_incurred_claims / member_months
adjusted = incurred_pmpm * demographic_adjustment
experience_claim_cost = adjusted - less_pooled_claims_pmpm
effective_trend = (1 + annual_trend) ** (months_of_trend / 12.0) - 1
projected_medical = (experience_claim_cost * benefit_change * (1 + effective_trend)
                     + projected_excess_claims_pmpm + large_claim_add_back_pmpm)
experience_premium = projected_medical / target_loss_ratio * (1 + benefit_advisor_fee)
current_premium_pmpm = current_total_premium_monthly / current_members
experience_increase = experience_premium / current_premium_pmpm - 1
blended = (credibility_experience_weight * experience_increase
           + credibility_manual_weight * manual_rating_pool_increase)
return blended + adjustment
```
`fn_renewal_buildup` runs the identical arithmetic and returns every intermediate line as a JSON object (adds `blended_rate_action`, `quoted_change`, `projected_billed_premium_annual`, etc.). See `docs/METHOD_SPEC.md` for the line-by-line map. `fn_effective_trend` is a standalone helper duplicating the `effective_trend` line.

---

## Jobs (DAB)

| Object | Config | Defined in |
|--------|--------|-----------|
| `hb_ingest` — `[hb-renewal] carrier file ingestion` | `file_arrival` trigger on `/Volumes/${var.catalog}/${var.schema}/landing/inbox/`; serverless `spark_python_task` = `./jobs/run_ingest_job.py` (env: openpyxl, openai). | `databricks.yml` |
| `hb_reseed` — `[hb-renewal] demo reset (reseed)` | serverless `spark_python_task` = `./jobs/run_reseed_job.py` (regenerate demo files → `seed_book` → `generate_reviewer`); triggered by the app's `POST /api/reset`. App SP granted `CAN_MANAGE_RUN`. Runs as the bundle deployer (has schema CREATE). | `databricks.yml` |

Bundle name `hb-renewal-workbench`; target `dev` (host `fevm-lr-dev-aws-us`, root `/Workspace/Shared/.bundle/hb-renewal-workbench`); vars `catalog`/`schema`/`warehouse_id`.

---

## Genie agent

| Attribute | Value |
|-----------|-------|
| Space name / id | "HB Renewal Book" / `01f19d63fe03198a95c55b64a81ea535` |
| Tables exposed | `v_source_document_latest`, `v_2_renewal_inputs_latest`, `v_1_incurred_claims_latest`, `6_book_trend_benchmark`, `mv_renewal_actions`, `mv_claims_experience` |
| Created by | `data/deploy_genie_agent.py` — single **idempotent** script (GenieSpaceBuilder + `databricks api post`/`patch`): find-by-title → update-or-create → grant SP `CAN_RUN` → auto-wire `HB_GENIE_SPACE_ID`. Re-runnable with no duplicates (verified). The old create-only `create_genie_space.py` was removed. |
| Payload | `data/genie_space.json` (version 2; the 6 tables above; instructions defining action/trend terms) |
| App wiring | in-app panel `POST /api/genie/ask` (Conversation API) + embedded `embed/genie/rooms/{id}`; app SP granted `CAN_RUN`; `HB_GENIE_SPACE_ID` in `app/app.yaml` |

---

## App

| Attribute | Value |
|-----------|-------|
| Name / URL | `hb-renewal-workbench` / `https://hb-renewal-workbench-7474656169654171.aws.databricksapps.com` |
| Service principal | `b417c702-dd1f-4ba7-a81c-2459b48fb325` (granted `USE`/`SELECT`/`EXECUTE`/`MODIFY` on the schema, `CAN_USE` on the warehouse, `CAN_RUN` on the Genie space, `CAN_READ` on the dashboard) |
| Backend | FastAPI `app/main.py` (uvicorn `main:app` port 8000); flat modules `ingest_pipeline.py`, `renewal_engine.py`, `selffunded.py` (unwired), `frontend/` static SPA |
| Deps | `app/requirements.txt`: fastapi, uvicorn[standard], databricks-sdk>=0.133.0, openai, openpyxl, python-multipart |
| Env (`app/app.yaml`) | `HB_CATALOG=lr_dev_aws_us_catalog`, `HB_SCHEMA=hb_renewal`, `HB_WAREHOUSE=a3b61648ea4809e3`, `HB_LLM_ENDPOINT=databricks-claude-sonnet-4-5`, `DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/a3b61648ea4809e3`, `HB_GENIE_SPACE_ID=01f19d63fe03198a95c55b64a81ea535`, `HB_DASHBOARD_ID=01f19d737ef41c468039d889d47d91a9` |

---

## Lakeview dashboard

| Attribute | Value |
|-----------|-------|
| Id | `01f19d737ef41c468039d889d47d91a9` (published `embed_credentials=True`) |
| Created by | `data/create_dashboard.py`; definition `data/hb_renewal_board.lvdash.json` |
| Datasets | `ds_bench` (from `6_book_trend_benchmark`), `ds_band` (from `6_book_trend_benchmark`), `ds_claims` (from `mv_claims_experience`) |
| Widgets | `w_carrier`, `w_booktrend`, `w_value`, `w_band` (bar), `w_claims` (line) |

**Reproducibility note:** `ds_claims` reads `mv_claims_experience`, now created by `build_schema.py` (D-16), so a from-scratch deploy (`deploy.sh` step 1) creates it before the dashboard step.
