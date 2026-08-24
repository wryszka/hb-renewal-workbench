# Learn panel — how-it-works layer

The **Learn** panel maps the nine things a broker does in a renewal to how this workbench does
each, with deep links into the live governed objects. Behind-the-scenes is a click, never a
hand-wave. This file is the **single source of truth** for the panel copy — the backend
(`LEARN_CARDS` in `app/main.py`) mirrors it. Do not fork variants.

## The nine activities

| # | Activity (what needs doing) | How it's done here | Deep links |
|---|------------------------------|---------------------|------------|
| 1 | Get the data in — receive the carrier file, prove it was read correctly | File drop on a Volume; two extraction paths (deterministic + AI) run and must agree | Volume `landing/inbox`, ingestion Job, `1_source_document` |
| 2 | Verify and trust it — known format? catch what's wrong, sign off exceptions | Fingerprint vs carrier template; disagreement or drift → quarantine, never silent guessing | `0_carrier_template`, quarantined docs filter in Book view |
| 3 | Reproduce the carrier's math — how they got to their number | The build-up is a versioned Unity Catalog function; the app cannot compute its own answer | `fn_renewal_action` (Catalog Explorer function page), exhibit panel |
| 4 | Challenge it — find where to push, test what-ifs | Levers with book context beside each; reviewer findings flag challenge candidates | Renewal Workspace levers, `4_reviewer_finding` |
| 5 | Decide and record — commit to a position, keep the why | Save requires a name and a reason; every save is a versioned commit with author | `5_scenario`, `5_gov_audit_event`, Delta history |
| 6 | Present and negotiate — the summary that goes to client and carrier | Exec summary drafted from the saved scenario; compare shows the ask, the position, the $ at stake | Compare panel, summariser |
| 7 | Reforecast — fresh data arrives, update without rebuilding | New months append through the same pipeline; recompute is one click, old position retained | Reforecast banner, `v_incurred_claims_latest` |
| 8 | Learn across the book — accumulate what every negotiation taught you | Benchmarks are a view derived from retained decisions, never hardcoded | `6_book_trend_benchmark`, Benchmarks panel |
| 9 | Answer questions about the book — anyone, anytime, no spreadsheet | Central metric definitions + natural language over the governed book | `mv_renewal_actions`, "Ask the book" panel |

**Implementation note:** the reforecast latest view is deployed as `v_1_incurred_claims_latest`
(numeric-prefix convention); the row above keeps the spec's `v_incurred_claims_latest` label.

## Three layers per card

1. **The activity** (broker voice, one line) — column 2 above.
2. **How it's done here** (plain language) — column 3 above.
3. **See it live** (deep links) — column 4 above.

**Readability rule (enforced):** layers 1–2 carry **no** Databricks object names — object names
live only in the "See it live" links. A broker reads the first two layers; the technical reader
follows the third.

## Journey grouping

Numbered nodes 1→9 in one flow, in three light group bands:
- **Trust the data** — 1, 2
- **Work the renewal** — 3, 4, 5, 6
- **Compound the book** — 7, 8, 9

One card open at a time. Each card carries a small inline-SVG schematic (no chart libraries).

## Anchor param convention

Opening Learn from another panel pre-expands the matching node. The frontend sets a module
variable `LEARN_ANCHOR = <node #>` then navigates (`go("learn")`); `renderLearn` reads it once
and clears it. The "❓ how does this work?" glyph on each panel maps to:

| Panel | Opens Learn node |
|-------|------------------|
| Book | 2 (verify & trust) |
| Renewal Workspace | 3 (reproduce the math) |
| Benchmarks | 8 (learn across the book) |
| Ask the Book | 9 (answer questions) |

## Deep-link building (env-driven — no hardcoded hosts)

`GET /api/learn` returns the nine cards as data; links are built server-side by
`_workspace_links()` in `app/main.py` from:
- **host** — resolved from the ambient Databricks config / `HB_PROFILE` (`Config().host`); never hardcoded.
- **catalog / schema** — `HB_CATALOG` / `HB_SCHEMA`.
- **dashboard / genie ids** — `HB_DASHBOARD_ID` / `HB_GENIE_SPACE_ID`.
- **job ids** — resolved at runtime by job name (`[hb-renewal] carrier file ingestion`).

URL shapes: tables/views → `{host}/explore/data/{catalog}/{schema}/{name}`; function →
`{host}/explore/data/functions/{catalog}/{schema}/{fn}`; Volume →
`{host}/explore/data/volumes/{catalog}/{schema}/landing`; Job → `{host}/jobs/{id}`. External
links open in a new tab; in-app targets (levers, compare, benchmarks, Ask-the-book) are in-app
anchors (`go(view)`), not external URLs.
