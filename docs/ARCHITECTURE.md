# Architecture

## The thesis
The app is deliberately thin — a last-mile interface. Everything of substance is a **governed
Unity Catalog object**: the method is a versioned function, the data is managed Delta with history
and lineage, the decisions are governed rows, the benchmark is a derived view. Swap the app for a
notebook, Genie, or an agent and nothing underneath changes.

## The seven layers → objects

| Layer | Requirement | Object(s) |
|---|---|---|
| ① Ingestion | file → validated structured data, layout-agnostic, at scale | `jobs/ingest_pipeline.py` (two-path extract + reconcile), `0_carrier_template`, Volume `landing/{inbox,processed,quarantine}` |
| ② Method | versioned, reproducible, attributable calculation | `fn_renewal_buildup` (all lines), `fn_renewal_action` (scalar), `fn_effective_trend` — UC Python functions |
| ③ Decision | every scenario retained: who/when/what/why/worth | `5_scenario`, `5_gov_audit_event` |
| ④ Lineage | number ← scenario ← function version ← table version ← file | Delta `DESCRIBE HISTORY`, `system.information_schema.routines`, surfaced in the app |
| ⑤ Accumulation | benchmarks derived from retained decisions | `6_book_trend_benchmark` (view over `5_scenario`) |
| — Semantics/Genie | governed metrics + NL access | `mv_renewal_actions`, `mv_claims_experience`, Genie agent over the `v_*_latest` + views |
| ⑦ Surface | thin UI over governed objects | `app/main.py` (FastAPI) + `app/frontend/index.html` |

## Principles

**Append-only + provenance.** Every source row carries `source_document_id`; every ingested file
is one `1_source_document` row with its reconciliation result and sign-off. Nothing is edited in
place; supersession writes a new document and marks the old `superseded`.

**Latest-only reads.** All downstream compute reads the `v_*_latest` views, which resolve to rows
from `status='active'` documents — so superseded files silently drop out of every calculation,
benchmark and Genie answer without deleting history.

**Supersession model.** A new file for the same `employer_group` + `policy_period` supersedes the
prior active document (audited). A `monthly_claims` document appends fresh months to the active
chain (reforecast). A file that fails the fingerprint/reconciliation is quarantined and lands **no**
source rows.

**One compute path.** No renewal math runs in the app container. The exhibit and every lever
recompute call `fn_renewal_buildup` through the SQL warehouse — the same function a notebook or
job would call, versioned in the catalog.

**Governance by construction.** Managed Delta gives version history and lineage for free; the
reconciliation control and human sign-off gate are recorded, not transient; the decision record
and audit trail make a renewal position defensible to a client or an auditor.
