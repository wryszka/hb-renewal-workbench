#!/usr/bin/env python3
"""Idempotent deploy of the 'HB Renewal Book' Genie agent over the governed views.

Single entry point (supersedes the earlier create-only script). Re-runnable:
  * finds an existing space by title -> UPDATES it if present, CREATES it if absent
    (so running twice never produces duplicate spaces);
  * grants the app service principal CAN_RUN;
  * writes the space id to data/genie_space_id.txt AND updates HB_GENIE_SPACE_ID in
    app/app.yaml automatically (no hand-wiring).

Uses the genie-rooms GenieSpaceBuilder + `databricks api` (POST to create, PATCH to
update). This is the working path. KNOWN DEBT: the raw SDK `w.genie.create_space`,
raw REST, and `databricks genie create-space` all double-encode `serialized_space`
and fail ("Expected START_OBJECT not VALUE_STRING"); retest on the next platform
release (see docs/GENIE_SETUP.md).

Usage: python3 data/deploy_genie_agent.py [profile] [warehouse] [catalog] [schema]
"""
import json, pathlib, re, subprocess, sys

prof = sys.argv[1] if len(sys.argv) > 1 else "DEV"
wh = sys.argv[2] if len(sys.argv) > 2 else "a3b61648ea4809e3"
cat = sys.argv[3] if len(sys.argv) > 3 else "lr_dev_aws_us_catalog"
sch = sys.argv[4] if len(sys.argv) > 4 else "hb_renewal"
APP_SP = "b417c702-dd1f-4ba7-a81c-2459b48fb325"  # hb-renewal-workbench service principal
TITLE = "HB Renewal Book"
ROOT = pathlib.Path(__file__).resolve().parent.parent

BUILDER = pathlib.Path.home() / ".vibe/marketplace/plugins/fe-internal-tools/skills/genie-rooms/resources"
sys.path.insert(0, str(BUILDER))
from genie_space_builder import GenieSpaceBuilder  # noqa: E402

fqn = f"{cat}.{sch}"


def api(method, path, payload=None):
    cmd = ["databricks", "api", method, path, "--profile", prof]
    if payload is not None:
        pathlib.Path("/tmp/genie_deploy_payload.json").write_text(json.dumps(payload))
        cmd += ["--json", "@/tmp/genie_deploy_payload.json"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    return out.stdout, out.stderr


# ---- build the space definition -------------------------------------------
space = GenieSpaceBuilder(
    title=TITLE,
    description="Natural-language analytics over a governed US health & benefits medical renewal book "
                "(synthetic): carrier-proposed vs negotiated renewal actions, the firm's own trend benchmark "
                "by carrier and group size, monthly claims experience, and the value negotiated.",
    warehouse_id=wh,
)
space.set_instructions(
    "You answer questions about a US health & benefits (H&B) medical renewal book (synthetic data; USD). "
    "A renewal 'action' is the percentage change in billed premium. In 6_book_trend_benchmark and "
    "mv_renewal_actions: avg_carrier_action = the carrier's proposed action; avg_negotiated_action = the "
    "position the broker negotiated; avg_negotiation_delta = carrier minus negotiated (what challenging was "
    "worth, in points); book_trend_median = the firm's OWN trend benchmark derived from retained decisions "
    "(NOT a licensed feed); total_value_negotiated = annual $ saved. group_band buckets covered members "
    "(<100, 100-499, 500-1999, 2000+). mv_claims_experience has monthly total_incurred and med_members with "
    "a derived pmpm by carrier and employer_group. v_source_document_latest lists renewals (carrier, "
    "employer_group, policy_period, status). A carrier 'runs rich' or is a 'padder' when avg_carrier_action "
    "sits well above book_trend_median. When asked which carrier is richest or where the biggest gap is, "
    "answer directly with the top row; report money in USD and percentages to one decimal."
)
for t in ["v_source_document_latest", "v_2_renewal_inputs_latest", "v_1_incurred_claims_latest",
          "6_book_trend_benchmark", "mv_renewal_actions", "mv_claims_experience"]:
    space.add_table(f"{fqn}.{t}")
space.add_example_sql(
    "Average carrier-proposed action for groups over 500 lives",
    f"SELECT round(avg(avg_carrier_action),4) AS avg_carrier_action FROM {fqn}.`6_book_trend_benchmark` "
    f"WHERE group_band IN ('500-1999','2000+')", item_id="00000000000000000000000000000001")
space.add_example_sql(
    "Which carrier runs richest versus our book trend",
    f"SELECT carrier, round(avg(avg_carrier_action - book_trend_median),4) AS gap_vs_book "
    f"FROM {fqn}.`6_book_trend_benchmark` GROUP BY carrier ORDER BY gap_vs_book DESC", item_id="00000000000000000000000000000002")
space.add_example_sql(
    "Which months drove claims for Harborview Logistics",
    f"SELECT month, total_incurred FROM {fqn}.`mv_claims_experience` "
    f"WHERE employer_group='Harborview Logistics' ORDER BY total_incurred DESC", item_id="00000000000000000000000000000003")
space.add_example_sql(
    "Where is the biggest gap between the carrier ask and our negotiated position",
    f"SELECT carrier, group_band, avg_negotiation_delta, total_value_negotiated "
    f"FROM {fqn}.`6_book_trend_benchmark` ORDER BY avg_negotiation_delta DESC LIMIT 10", item_id="00000000000000000000000000000004")
try:
    space.validate()
except Exception as e:  # noqa: BLE001
    print("validate warning:", e)

# parent path from the current user at runtime (no identifying path committed)
me_out, _ = api("get", "/api/2.0/preview/scim/v2/Me")
try:
    _user = json.loads(me_out).get("userName")
except Exception:  # noqa: BLE001
    _user = None
parent_path = f"/Workspace/Users/{_user}" if _user else "/Workspace/Shared"

# ---- find existing space by title (idempotency guard) ----------------------
existing_id = None
list_out, list_err = api("get", "/api/2.0/genie/spaces")
try:
    for s in json.loads(list_out).get("spaces", []):
        if (s.get("title") or "").strip() == TITLE:
            existing_id = s.get("space_id")
            break
except Exception:  # noqa: BLE001
    print("list warning:", list_err[:200])

body = {"title": TITLE,
        "description": "Governed H&B medical renewal book (synthetic): carrier vs negotiated actions, book trend benchmark, claims experience.",
        "parent_path": parent_path, "warehouse_id": wh,
        "serialized_space": space.to_json()}

if existing_id:
    print(f"space '{TITLE}' exists ({existing_id}) -> updating in place")
    out, err = api("patch", f"/api/2.0/genie/spaces/{existing_id}", body)
    if err and "serialized_space" not in out:
        print(f"  (update returned: {err[:200]} — keeping existing space, no duplicate created)")
    space_id = existing_id
else:
    print(f"space '{TITLE}' not found -> creating")
    out, err = api("post", "/api/2.0/genie/spaces", body)
    try:
        space_id = json.loads(out)["space_id"]
    except Exception:  # noqa: BLE001
        print("CREATE FAILED:", (out or err)[:400]); sys.exit(1)

print("SPACE_ID:", space_id)

# ---- grant the app SP CAN_RUN ---------------------------------------------
out, err = api("patch", f"/api/2.0/permissions/genie/{space_id}",
               {"access_control_list": [{"service_principal_name": APP_SP, "permission_level": "CAN_RUN"}]})
print("grant CAN_RUN:", "ok" if not err else err[:200])

# ---- write id to file + app.yaml (auto-wire) -------------------------------
(ROOT / "data" / "genie_space_id.txt").write_text(space_id)
appyaml = ROOT / "app" / "app.yaml"
txt = appyaml.read_text()
new = re.sub(r'(name:[ \t]*HB_GENIE_SPACE_ID[ \t]*\n[ \t]*value:[ \t]*)[^\n]*', rf'\g<1>{space_id}', txt)
if new != txt:
    appyaml.write_text(new); print(f"app.yaml HB_GENIE_SPACE_ID -> {space_id}")
else:
    print("app.yaml unchanged (HB_GENIE_SPACE_ID pattern not found — check manually)")
print("done.")
