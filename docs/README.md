# HB Renewal Workbench

A governed alternative to negotiating US Health & Benefits medical renewals inside carrier
spreadsheets. A carrier renewal exhibit is ingested, verified, and governed on Databricks; the
renewal method is a versioned Unity Catalog function; every negotiation is retained with audit
and lineage; and benchmarks emerge from the retained decisions.

> **The thesis:** the app is thin — everything of substance is a governed object. Same governed
> data and method behind a notebook, Genie, or an agent.

## The seven-step arc
`drop file → verify → govern → explore → advise → decide → accumulate → compare`

| # | Beat | Object |
|---|------|--------|
| ① | Ingestion (file → reconcile → quarantine/append) | Job + `jobs/ingest_pipeline.py`, `0_carrier_template`, `1_source_document` |
| ② | Governed method | `fn_renewal_buildup`, `fn_renewal_action` (UC functions) |
| ③ | Decision layer | `5_scenario`, `5_gov_audit_event` |
| ④ | Lineage | `DESCRIBE HISTORY` + `information_schema` (surfaced in app) |
| ⑤ | Accumulation | `6_book_trend_benchmark` (derived view) + `mv_renewal_actions`/`mv_claims_experience` (consumption views) |
| ⑥ | Second document family (pharmacy-rebate) | **cut to roadmap (V2)** — not built; see `ROADMAP.md` |
| ⑦ | Thin app | `app/` (FastAPI + single-page UI) |

**App surface (left sidebar):** Overview (Daily view · Dashboard) · Pipeline (Ingestion · Book) · Renewal (Renewal Workspace · Benchmarks) · Intelligence (Agents · Ask the Book · Audit) · **Learn** (pinned at the bottom). **Learn** is the how-it-works layer — a plain-language map of the nine renewal activities to how the workbench does each, with deep links into the live governed objects (`docs/LEARN_PANEL.md`). The presenter run-sheet + persona Q&A live in `docs/DEMO_RUNSHEET.md` + `docs/DEMO_QA.md`, published as a Google Doc linked from the actuarial-workbench hub next to the app (not an in-app tab).

## Architecture diagram (ASCII)
```
 carrier .xlsx ─▶ [Volume inbox] ─▶ Ingestion Job (jobs/ingest_pipeline.py)
                                      │  fingerprint · 2-path extract · reconcile
                                      ├─ quarantine ─▶ 1_source_document (status)
                                      └─ append ─▶ 1_incurred/large/rates + 2_renewal_inputs (+ source_document_id)
                                                     │
   v_*_latest (active only) ◀────────────────────────┘
        │
        ├─▶ fn_renewal_buildup / fn_renewal_action  (governed method)
        ├─▶ 5_scenario + 5_gov_audit_event          (retained decisions)
        ├─▶ 6_book_trend_benchmark                  (derived from 5_scenario)
        └─▶ mv_renewal_actions / mv_claims_experience ─▶ Genie "Ask the book"
                                                     │
        app/ (thin) ── reads/writes the above ───────┘
```

## Deploy
Environment: workspace `fevm-lr-dev-aws-us` (profile `DEV`), catalog `lr_dev_aws_us_catalog`,
schema `hb_renewal`, warehouse `a3b61648ea4809e3` (serverless). One workspace edit point: the
catalog variable in `databricks.yml`.

**One command** (fail-fast, runs the eight steps below in order):
```bash
./deploy.sh DEV
```

Or the steps individually:
```bash
# schema + method + views incl. mv_ consumption views (idempotent)
uv run --native-tls --with databricks-sdk data/build_schema.py
# seed the book (ingests hero through the pipeline + 49 historical decisions)
uv run --native-tls --with databricks-sdk --with openpyxl --with openai data/seed_book.py
uv run --native-tls --with databricks-sdk data/generate_reviewer.py
# demo files
uv run --native-tls --with openpyxl data/make_carrier_file.py
# Genie agent (idempotent: update-or-create, grant SP, wire app.yaml) + dashboard
uv run --native-tls --with databricks-sdk data/deploy_genie_agent.py DEV
uv run --native-tls --with databricks-sdk data/create_dashboard.py
# app
databricks sync app/ /Workspace/Shared/hb-renewal-workbench --profile DEV
databricks apps deploy hb-renewal-workbench --source-code-path /Workspace/Shared/hb-renewal-workbench --profile DEV
# DAB (file-arrival ingestion job)
databricks bundle deploy -t dev
```

## Local dev / test
```bash
export HB_PROFILE=DEV
uv run --native-tls --with pytest --with openpyxl pytest tests/ -q        # method regression (4dp)
cd app && HB_PROFILE=DEV uv run --native-tls --with fastapi --with 'uvicorn[standard]' \
  --with databricks-sdk --with openai --with openpyxl uvicorn main:app --port 8770
```

See `ARCHITECTURE.md`, `METHOD_SPEC.md`, `DEMO_RUNSHEET.md`, `DEMO_QA.md`, `ROADMAP.md`, `GENIE_SETUP.md`,
`../DECISIONS.md`, `../SMOKE_RESULTS.md`.

**Reviewer documentation set** (`docs/REVIEW/`) — verify what was built against the spec without
codebase access: `IMPLEMENTATION_REPORT.md` (WP1–WP11 + deviations), `OBJECT_INVENTORY.md`,
`DATA_FLOW.md`, `APP_MAP.md`, `DEMO_READINESS.md`, `SMOKE_RESULTS_ADDENDUM.md`, `NAME_SCAN.md`, `PERSONA_REVIEW_PACK.md` (full app+demo description for external persona review — surface census, click-flows, state machine, persona interrogation, numbers appendix, weaknesses register).

All data is synthetic; the method is illustrative.
