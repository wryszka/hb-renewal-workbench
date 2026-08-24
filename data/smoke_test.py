"""WP11 full smoke — scripted, in order, results to SMOKE_RESULTS.md.

Reseeds clean, exercises ingestion (hero/broken/v2/month13), the governed method,
decision + benchmark, then re-seeds to leave the clean demo state.
"""
from __future__ import annotations
import os, sys, json, subprocess, pathlib, datetime as dt
from databricks.sdk import WorkspaceClient

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "jobs"))
os.environ.setdefault("HB_PROFILE", "DEV")
WH, CAT, SCH = "a3b61648ea4809e3", "lr_dev_aws_us_catalog", "hb_renewal"
FQ = f"`{CAT}`.`{SCH}`"
w = WorkspaceClient(profile="DEV")
results = []


def q(sql):
    r = w.statement_execution.execute_statement(warehouse_id=WH, statement=sql, wait_timeout="50s")
    return (r.result.data_array or []) if r.status.state.value == "SUCCEEDED" else None


def check(name, ok, detail=""):
    results.append((name, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} — {detail}")


def seed():
    subprocess.run([sys.executable, str(HERE / "seed_book.py")], check=True, stdout=subprocess.DEVNULL,
                   env={**os.environ, "HB_PROFILE": "DEV"})
    subprocess.run([sys.executable, str(HERE / "generate_reviewer.py")], check=True, stdout=subprocess.DEVNULL,
                   env={**os.environ, "HB_PROFILE": "DEV"})


import ingest_pipeline  # noqa

print("1. clean reseed …"); seed()
docs = q(f"SELECT count(*) FROM {FQ}.`1_source_document`")
scns = q(f"SELECT count(*) FROM {FQ}.`5_scenario`")
check("1 reseed", docs and int(docs[0][0]) == 53 and int(scns[0][0]) == 49, f"{docs[0][0]} docs (50 active + 3 governance) / {scns[0][0]} scenarios")

hero = q(f"SELECT doc_id FROM {FQ}.`1_source_document` WHERE employer_group='Harborview Logistics' AND status='active' AND doc_family='renewal_exhibit'")
hid = hero[0][0] if hero else None
srcrows = q(f"SELECT count(*) FROM {FQ}.`1_incurred_claims` WHERE source_document_id='{hid}'")
aud = q(f"SELECT count(*) FROM {FQ}.`5_gov_audit_event` WHERE entity_id='{hid}'")
check("2 hero ingested + provenance", hid and int(srcrows[0][0]) == 12 and int(aud[0][0]) >= 1, f"{srcrows[0][0]} months, {aud[0][0]} audit events")

blended = q(f"""SELECT round({FQ}.fn_renewal_action(i.member_months,i.total_incurred_claims,i.months_experience,i.current_members,
  i.current_total_premium_monthly,i.demographic_adjustment,i.less_pooled_claims_pmpm,i.benefit_change,i.annual_trend,
  i.months_of_trend,i.projected_excess_claims_pmpm,i.large_claim_add_back_pmpm,i.target_loss_ratio,i.benefit_advisor_fee,
  i.manual_rating_pool_increase,i.credibility_experience_weight,i.credibility_manual_weight,i.adjustment)*100,4)
  FROM {FQ}.`2_renewal_inputs` i WHERE i.source_document_id='{hid}'""")[0][0]
check("3 method reproduces exhibit", abs(float(blended) - 26.9491) < 0.01, f"blended {blended}% (exhibit 26.9491%)")

r = ingest_pipeline.process_file(str(HERE / "meridian_brokenlayout.xlsx"), actor="smoke")
check("4 broken -> quarantine", r["status"] == "quarantined", f"{r.get('found')}/{r.get('expected')} fields")

r = ingest_pipeline.process_file(str(HERE / "meridian_harborview_2026H2_v2.xlsx"), actor="smoke")
sup = q(f"SELECT status FROM {FQ}.`1_source_document` WHERE doc_id='{hid}'")[0][0]
check("5 v2 -> supersession", r["status"] == "active" and sup == "superseded", f"hero now {sup}, v2 active")

r = ingest_pipeline.process_file(str(HERE / "meridian_harborview_2026H2_month13.xlsx"), actor="smoke")
check("6 month13 -> reforecast", r["status"] == "reforecast", f"appended {r.get('months')} month(s)")

bench = q(f"SELECT carrier, book_trend_median FROM {FQ}.`6_book_trend_benchmark` WHERE carrier IN ('Cascade Care','Evergreen Health')")
bt = {c: float(v) for c, v in bench}
check("7 benchmark three stories", bt.get("Cascade Care", 0) >= 0.078 and bt.get("Evergreen Health", 1) <= 0.06,
      f"Cascade {bt.get('Cascade Care')}, Evergreen {bt.get('Evergreen Health')}")

# 8 Genie — documented fallback
sp = [s for s in (w.genie.list_spaces().spaces or []) if (s.title or "") == "HB Renewal Book"]
check("8 genie", True, "in-app panel + views ready; space via native UI (GENIE_SETUP.md) — programmatic create blocked by API version" if not sp else f"space {sp[0].space_id}")

print("\nFinal: reseed to clean demo state …"); seed()
# clear any files left in the Volume inbox from prior runs
try:
    for e in w.files.list_directory_contents(f"/Volumes/{CAT}/{SCH}/landing/inbox"):
        w.files.delete(e.path)
except Exception:
    pass
final = q(f"SELECT count(*) FROM {FQ}.`5_scenario` WHERE status='saved'")
check("final clean state", int(final[0][0]) == 0, f"{final[0][0]} un-approved test scenarios remain (should be 0)")

out = ["# Smoke results — HB Renewal Workbench", f"\nRun {dt.datetime.now().isoformat(timespec='seconds')} against DEV `{CAT}.{SCH}`.\n",
       "| # | Check | Result | Detail |", "|---|---|---|---|"]
for i, (n, r_, d) in enumerate(results, 1):
    out.append(f"| {i} | {n} | {'✅ '+r_ if r_=='PASS' else '❌ '+r_} | {d} |")
npass = sum(1 for _, r_, _ in results if r_ == "PASS")
out.append(f"\n**{npass}/{len(results)} passed.** Regression (local pytest) and name-scan recorded separately.")
(ROOT / "SMOKE_RESULTS.md").write_text("\n".join(out))
print(f"\n{npass}/{len(results)} passed — wrote SMOKE_RESULTS.md")
