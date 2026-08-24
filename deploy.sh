#!/usr/bin/env bash
# One-command deploy of the HB Renewal Workbench to a Databricks workspace.
# Fail-fast: any step's failure aborts the run. Equivalent to the numbered steps
# in docs/README.md. The full orchestrator-Job refactor is V2 (see docs/ROADMAP.md).
#
#   ./deploy.sh [PROFILE]        # PROFILE defaults to DEV
set -euo pipefail
PROFILE="${1:-DEV}"
export HB_PROFILE="$PROFILE"   # seed scripts read this; a Job uses ambient auth (no HB_PROFILE)
UV="uv run --native-tls"
echo "== 1/8 schema (idempotent: tables, views, mv_ consumption views, UC functions) =="
$UV --with databricks-sdk data/build_schema.py
echo "== 2/8 seed the book (hero through the pipeline + historical decisions) =="
HB_PROFILE="$PROFILE" $UV --with databricks-sdk --with openpyxl --with openai data/seed_book.py
echo "== 3/8 reviewer findings =="
HB_PROFILE="$PROFILE" $UV --with databricks-sdk data/generate_reviewer.py
echo "== 4/8 synthetic demo carrier files (local + staged into the Volume for download) =="
$UV --with openpyxl data/make_carrier_file.py
HB_PROFILE="$PROFILE" $UV --with databricks-sdk --with openpyxl data/stage_demo_files.py
echo "== 5/8 Genie agent (idempotent: update-or-create, grant SP, wire app.yaml) =="
HB_PROFILE="$PROFILE" $UV --with databricks-sdk data/deploy_genie_agent.py "$PROFILE"
echo "== 6/8 AI/BI dashboard =="
HB_PROFILE="$PROFILE" $UV --with databricks-sdk data/create_dashboard.py
echo "== 7/8 app (sync + deploy) =="
databricks sync app/ /Workspace/Shared/hb-renewal-workbench --profile "$PROFILE"
databricks apps deploy hb-renewal-workbench --source-code-path /Workspace/Shared/hb-renewal-workbench --profile "$PROFILE"
echo "== 8/8 DAB (file-arrival ingestion Job) =="
databricks bundle deploy -t dev --profile "$PROFILE"
echo "== deploy complete =="
