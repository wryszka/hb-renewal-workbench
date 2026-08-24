# Roadmap

**V1 (this build) — the loop, end to end, nothing discarded.**
Ingestion as a governed Job (fingerprint · two-path extract · reconcile · quarantine · supersede ·
reforecast) · governed renewal method (UC function, reproduces the exhibit) · retained decisions
with audit + lineage · benchmarks derived from retained decisions · thin app over governed objects ·
Genie over the governed views.

**V2 — depth on the same foundation (each is config/a binding, not a rebuild).**
- **Full Build orchestrator** — one Databricks Job that runs schema → seed → reviewer → Genie → dashboard → app deploy as ordered tasks (today: `deploy.sh` runs the steps sequentially; the Job refactor gives retries, lineage, and a single run id).
- **Closed synthetic loop (`advance_period`)** — a routine that rolls the book forward a period (new experience months, a fresh carrier exhibit per group) so the demo can run indefinitely without hand-seeding.
- **Fully-insured → self-funded UI** with a stop-loss basis (engine exists: `app/selffunded.py`, currently unwired — see IMPLEMENTATION_REPORT D-7).
- **New-carrier onboarding UI** (confirm a template from a first file → writes a `0_carrier_template` row).
- **More carrier layouts** as template registry rows (`0_carrier_template`) — no new code.
- **Pharmacy-rebate document family** through the same pipeline (a second parser + binding).
- **MCP tool surface over the stages** — expose ingest / recompute / save-scenario / benchmark as MCP tools so an agent can drive the governed method directly.
- **How-it-works deep-link layer** — every displayed number links to its method version, table version, and source file (extends the current lineage panel).
- **Real benchmarks** from the firm's own book once volume accumulates.
- **Genie**: promote the `mv_*` consumption views to formal UC **metric views** (they are plain SQL views today); retest raw-API/SDK space creation on the next platform release (the `serialized_space` double-encoding bug — see `docs/GENIE_SETUP.md`); broaden the agent.

**V3 — intelligence and reach.**
- **ML risk scoring** — is a deal above or below the mark, given the book.
- **Agentic**: an account executive pings an agent; the governed method answers under human-in-the-loop.
- **Sharing pilots** — cross-line and cross-entity, governed via Unity Catalog / Delta Sharing.

**Close:** *the distance between a discarded spreadsheet and a compounding system of record was — drop the file.*
