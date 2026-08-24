# Genie — "Ask the book" (working, in-app)

The app embeds a Genie agent via the Conversation API (`/api/genie/ask` in `app/main.py`) over the
governed views. The space is created **programmatically** — this is the working pattern (raw SDK
`create_space`, raw REST, and `databricks genie create-space` all fail on the `serialized_space`
encoding).

## Create / refresh the space — one idempotent script
```
python3 data/deploy_genie_agent.py DEV       # DEV, wh a3b61648ea4809e3, schema hb_renewal
```
Single entry point. Re-runnable: **finds the space by title → updates if present, creates if absent**
(verified twice-in-a-row with no duplicate), **grants the app SP `CAN_RUN`**, and **auto-writes** the
space id to `data/genie_space_id.txt` and `HB_GENIE_SPACE_ID` in `app/app.yaml` (no hand-wiring).
Uses the genie-rooms `GenieSpaceBuilder` + `databricks api post`/`patch`. Current space:
**HB Renewal Book · 01f19d63fe03198a95c55b64a81ea535**.

Tables: `v_source_document_latest`, `v_2_renewal_inputs_latest`, `v_1_incurred_claims_latest`,
`6_book_trend_benchmark`, `mv_renewal_actions`, `mv_claims_experience` (the `mv_*` views are created
by `data/build_schema.py`).

## Known debt — programmatic creation
The raw SDK `w.genie.create_space`, raw REST, and `databricks genie create-space` all **double-encode
`serialized_space`** and fail with *"Expected START_OBJECT not VALUE_STRING"*. The working path is the
genie-rooms builder + `databricks api post` (above), wrapped idempotently in `deploy_genie_agent.py`.
**Retest condition:** re-try the raw `create_space` API on the next Databricks platform release; if it
accepts a nested `serialized_space` object, the builder+CLI shim can be dropped.

## App wiring (handled by the script)
1. App SP `CAN_RUN` granted via `PATCH /api/2.0/permissions/genie/{space_id}`.
2. `HB_GENIE_SPACE_ID` written to `app/app.yaml`; redeploy the app to pick it up.
3. App needs `databricks-sdk>=0.133.0` (pinned) for `execute_message_attachment_query`; falls back to
   `get_message_attachment_query_result` via lazy getattr for older SDKs.

## Sample questions (tuned to the seeded example SQL)
- What's the average carrier-proposed action for groups over 500 lives?
- Which carrier runs richest versus our book trend?
- Which months drove claims for Harborview Logistics?
- Where is the biggest gap between the carrier ask and our negotiated position?

The panel renders the NL answer + the generated SQL (collapsible) + the result table, stateful within
a session. Verified live: text + SQL + rows all return.
