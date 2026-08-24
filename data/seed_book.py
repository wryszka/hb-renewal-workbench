"""Master seeder — builds the whole book so the app is never empty.

1. Reset schema (build_schema).
2. Ingest the hero exhibit THROUGH the ingestion module (same path as the live Job)
   so the seed itself proves the pipeline.
3. Seed ~49 historical renewal decisions (summary: source_document + 5_scenario)
   retuned so the benchmark view tells three stories:
     - the padder  (Cascade Care ~8% book trend, proposals ~2x book, rising with band)
     - the fair carrier (Evergreen Health ~5.5%, proposals close to book)
     - a visible negotiation delta (carrier action above negotiated by 2-7 pts)
   Meridian Assurance gets a row in the hero's band so the reviewer agent can cite it.

All synthetic. Run: uv run --native-tls --with databricks-sdk --with openpyxl --with openai seed_book.py
"""
from __future__ import annotations
import os, sys, json, random, subprocess, pathlib
from databricks.sdk import WorkspaceClient

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "jobs"))
from renewal_engine import RenewalInputs, compute_renewal, scenario  # noqa: E402

WAREHOUSE, CAT, SCH = "a3b61648ea4809e3", "lr_dev_aws_us_catalog", "hb_renewal"
FQ = f"{CAT}.{SCH}"
w = WorkspaceClient(profile=os.getenv("HB_PROFILE") or None)
rng = random.Random(20260821)


def run(sql, label=""):
    r = w.statement_execution.execute_statement(warehouse_id=WAREHOUSE, statement=sql, wait_timeout="50s")
    if not r.status or r.status.state.value != "SUCCEEDED":
        raise SystemExit(f"FAILED [{label}]: {r.status.error.message if r.status and r.status.error else '?'}")
    return r


def sv(x):
    if x is None:
        return "NULL"
    if isinstance(x, str):
        return "'" + x.replace("'", "''") + "'"
    return repr(x)


# carrier "true" book trend + how rich they quote (richness added to carrier trend)
CARRIERS = {
    "Cascade Care":       {"book": 0.080, "rich": 0.052},  # the padder
    "Evergreen Health":   {"book": 0.055, "rich": 0.012},  # the fair carrier
    "Summit Health":      {"book": 0.068, "rich": 0.034},
    "Ridgeline Mutual":   {"book": 0.064, "rich": 0.028},
    "Meridian Assurance": {"book": 0.072, "rich": 0.040},  # hero carrier
}
GROUPS = ["Alderman Freight", "Brightwater Foods", "Copperfield Retail", "Dunmore Logistics",
          "Elmwood Systems", "Fairhaven Health", "Granite Peak Mfg", "Hollow Creek Energy",
          "Ironbridge Robotics", "Juniper Hospitality", "Kestrel Property", "Lantern Bay Media",
          "Maple Ridge Foods", "Northgate Freight", "Oakhurst Systems", "Pinecrest Retail",
          "Quarry Lane Mfg", "Redwood Logistics", "Sterling Health", "Thornwood Energy",
          "Underhill Robotics", "Vantage Hospitality", "Westfield Property", "Yarrow Media"]
PERIODS = ["2025H1", "2025H2", "2026H1", "2026H2"]
BANDS = [(80, 99, "<100"), (150, 480, "100-499"), (560, 1900, "500-1999"), (2200, 4200, "2000+")]


def band_of(m):
    return "<100" if m < 100 else "100-499" if m < 500 else "500-1999" if m < 2000 else "2000+"


def make_case(carrier, prof, members):
    months_exp, member_months = 12, int(members * 12 * rng.uniform(0.95, 1.0))
    incurred_pmpm, cur_prem_pmpm = rng.uniform(560, 880), rng.uniform(660, 800)
    carrier_trend = round(prof["book"] + prof["rich"] + rng.uniform(-0.008, 0.015), 4)
    z = min(0.9, max(0.25, (members / 2000) ** 0.5))
    inp = RenewalInputs(
        member_months=member_months, total_incurred_claims=incurred_pmpm * member_months,
        months_experience=months_exp, current_members=members,
        current_total_premium_monthly=cur_prem_pmpm * members,
        demographic_adjustment=round(rng.uniform(0.96, 1.03), 4),
        less_pooled_claims_pmpm=round(rng.uniform(120, 220), 2), benefit_change=round(rng.uniform(0.95, 1.0), 4),
        annual_trend=carrier_trend, months_of_trend=rng.choice([12, 15, 18]),
        individual_pooling_point=rng.choice([100000.0, 125000.0]),
        projected_excess_claims_pmpm=round(rng.uniform(120, 170), 2),
        large_claim_add_back_pmpm=round(rng.uniform(105, 140), 2),
        target_loss_ratio=round(rng.uniform(0.90, 0.94), 4), benefit_advisor_fee=rng.choice([0.04, 0.045, 0.05]),
        manual_rating_pool_increase=round(rng.uniform(0.10, 0.18), 4),
        credibility_experience_weight=round(z, 3), credibility_manual_weight=round(1 - z, 3))
    negotiated_trend = round(min(prof["book"] + rng.uniform(-0.006, 0.006), carrier_trend - 0.005), 4)
    base = compute_renewal(inp)
    cands = [{"annual_trend": negotiated_trend}]
    if members < 500:
        cands.append({"annual_trend": negotiated_trend, "credibility_experience_weight": 0.5, "credibility_manual_weight": 0.5})
    ov, scn = min(((o, scenario(inp, **o)) for o in cands), key=lambda t: t[1].blended_rate_action)
    vas = base.projected_billed_premium_annual - scn.projected_billed_premium_annual
    return base, scn, ov, negotiated_trend, vas


# ---- 1. reset schema + 2. ingest hero via the pipeline module ----
# demo-file dir: HB_DEMO_DIR (writable /tmp on a Job) else this data/ dir
DEMODIR = pathlib.Path(os.getenv("HB_DEMO_DIR") or HERE)
print("resetting schema…")
import runpy  # noqa: E402
runpy.run_path(str(HERE / "build_schema.py"), run_name="__main__")  # in-process (serverless-safe; no subprocess)
print("ingesting hero through the ingestion module…")
import ingest_pipeline  # noqa: E402
import make_carrier_file as _mcf  # noqa: E402
# Seed a real version chain: the carrier's FIRST (richer) submission, ingested first so the
# hero file supersedes it — leaving v0 (superseded) -> hero (active) for the version-diff beat,
# demoable without a live drop. The live …_v2 drop then extends the chain.
_v0 = "/tmp/meridian_harborview_2026H2_v0.xlsx"
_mcf.build(_v0, dict(_mcf.BASE, annual_trend=0.1385))
r0 = ingest_pipeline.process_file(_v0, actor="seed@local")
print(f"  v0 predecessor -> {r0['status']} {r0.get('doc_id')}")
res = ingest_pipeline.process_file(str(DEMODIR / "meridian_harborview_2026H2.xlsx"), actor="seed@local")
print(f"  hero -> {res['status']} {res.get('doc_id')} ({res.get('found')}/{res.get('expected')})")

# ---- 3. historical decisions ----
docs, scns, evs, i = [], [], [], 0
plan = [("Cascade Care", 11), ("Evergreen Health", 10), ("Summit Health", 10),
        ("Ridgeline Mutual", 9), ("Meridian Assurance", 9)]
for carrier, n in plan:
    prof = CARRIERS[carrier]
    for _ in range(n):
        i += 1
        lo, hi, _b = rng.choice(BANDS)
        # ensure Meridian has a hero-band (100-499) presence
        if carrier == "Meridian Assurance" and i % 3 == 0:
            lo, hi = 150, 480
        members = rng.randint(lo, hi)
        base, scn, ov, ntrend, vas = make_case(carrier, prof, members)
        grp = f"{rng.choice(GROUPS)}"
        period = rng.choice(PERIODS)
        doc_id, scn_id = f"DOC-H{i:03d}", f"SCN-H{i:03d}"
        docs.append((doc_id, carrier, grp, period))
        ovj = json.dumps({"annual_trend": ntrend, "members": members, "group_band": band_of(members), **{k: v for k, v in ov.items() if k != "annual_trend"}})
        scns.append((scn_id, doc_id, carrier, grp, base.blended_rate_action, scn.blended_rate_action, vas, ovj,
                     f"Held carrier trend to book ~{ntrend:.1%}" + ("; credibility 50/50" if members < 500 else "")))
        if i % 7 == 0:
            evs.append((scn_id, carrier, ntrend, vas))

print(f"seeding {len(docs)} historical documents + decisions…")
doc_vals = ",".join(
    f"({sv(d)},{sv(c)},{sv(g)},{sv(p)},{sv(c.split()[0].lower()+'_'+g.split()[0].lower()+'_'+p.lower()+'.xlsx')},"
    f"'renewal_exhibit',current_timestamp() - INTERVAL {n+1} DAYS,17,17,'{{\"found\":17,\"expected\":17}}','active',"
    f"'analyst@broker.example',current_timestamp() - INTERVAL {n+1} DAYS,NULL)"
    for n, (d, c, g, p) in enumerate(docs))
run(f"INSERT INTO {FQ}.`1_source_document` VALUES {doc_vals}", "hist docs")

scn_vals = ",".join(
    f"({sv(sid)},{sv(did)},{sv(car)},{sv(grp)},'Negotiated renewal','analyst@broker.example',"
    f"current_timestamp() - INTERVAL {n+1} DAYS,'carrier_proposal',{sv(ovj)},{ba},{sa},{vas},{sv(rsn)},'approved',NULL,'FI')"
    for n, (sid, did, car, grp, ba, sa, vas, ovj, rsn) in enumerate(scns))
run(f"INSERT INTO {FQ}.`5_scenario` VALUES {scn_vals}", "hist scenarios")

ev_vals = ",".join(
    f"('AE-H{k:03d}','scenario_approved','scenario',{sv(sid)},{sv(f'trend held to {nt:.1%}; ${vas:,.0f} at stake')},'analyst@broker.example',current_timestamp() - INTERVAL {k+1} DAYS)"
    for k, (sid, car, nt, vas) in enumerate(evs))
run(f"INSERT INTO {FQ}.`5_gov_audit_event` VALUES {ev_vals}", "hist events")

# governance states visible in the book from the first screen: a quarantined file,
# a differs (pending human confirm), and a superseded prior version.
# DOC-Q900 is a RESOLVABLE (moved/renamed-label) quarantine — archived file + a proposed
# re-map — so the accept-remap → re-process → active loop works without a live drop.
_qpath = "/tmp/cascade_fernbrook_2026h2.xlsx"
_mcf.build(_qpath, dict(_mcf.BASE), broken=True)
q900_stored = ingest_pipeline.archive(open(_qpath, "rb").read(), "DOC-Q900", "cascade_fernbrook_2026h2.xlsx", quarantined=True)
qdiff = json.dumps({"missing_tabs": [], "found": 15, "expected": 17, "disagreements": 0,
                    "fields": [{"field": "member_months", "status": "ai-only", "det": None, "ai": 5412, "det_label": None, "ai_label": "Covered Life-Months"},
                               {"field": "annual_trend", "status": "ai-only", "det": None, "ai": 0.122, "det_label": None, "ai_label": "Trend Rate (annual)"}],
                    "proposed_remap": [{"field": "member_months", "expected_label": "Member Months", "found_label": "Covered Life-Months"},
                                       {"field": "annual_trend", "expected_label": "Annual Trend", "found_label": "Trend Rate (annual)"}]})
ddiff = json.dumps({"found": 16, "expected": 17, "disagreements": 1,
                    "fields": [{"field": "less_pooled_claims_pmpm", "status": "differs"}]})
run(f"""INSERT INTO {FQ}.`1_source_document` VALUES
  ('DOC-Q900','Cascade Care','Fernbrook Retail','2026H2','cascade_fernbrook_2026h2.xlsx','renewal_exhibit',
   current_timestamp() - INTERVAL 1 DAYS,17,15,{sv(qdiff)},'quarantined',NULL,NULL,{sv(q900_stored)}),
  ('DOC-D901','Summit Health','Oakmont Freight','2026H1','summit_oakmont_2026h1.xlsx','renewal_exhibit',
   current_timestamp() - INTERVAL 2 DAYS,17,16,{sv(ddiff)},'differs',NULL,NULL,NULL),
  ('DOC-S902','Meridian Assurance','Harborview Logistics','2025H2','meridian_harborview_2025h2.xlsx','renewal_exhibit',
   current_timestamp() - INTERVAL 190 DAYS,17,17,'{{\"found\":17,\"expected\":17}}','superseded','analyst@broker.example',current_timestamp() - INTERVAL 190 DAYS,NULL)""", "governance states")
run(f"""INSERT INTO {FQ}.`5_gov_audit_event` VALUES
  ('AE-Q900','quarantined','source_document','DOC-Q900','15/17 fields; two core labels renamed (Covered Life-Months, Trend Rate (annual)) — held for a re-map','system',current_timestamp() - INTERVAL 1 DAYS),
  ('AE-D901','extraction_differs','source_document','DOC-D901','two paths disagree on pooled-claims credit — pending human confirm','system',current_timestamp() - INTERVAL 2 DAYS),
  ('AE-S902','superseded','source_document','DOC-S902','replaced by the 2026H2 renewal','system',current_timestamp() - INTERVAL 190 DAYS)""", "governance events")

# ---- verify the three stories ----
print("\nBOOK TREND BENCHMARK (derived):")
r = run(f"SELECT carrier, group_band, renewals_negotiated, book_trend_median, avg_carrier_action, avg_negotiated_action, avg_negotiation_delta FROM {FQ}.`6_book_trend_benchmark` ORDER BY carrier, group_band", "bench")
print(f"  {'carrier':<20}{'band':<10}{'n':>3}{'book':>8}{'carrier':>9}{'negot':>8}{'delta':>8}")
for row in r.result.data_array:
    c, b, n, bt, ca, na, dl = row
    print(f"  {c:<20}{b:<10}{n:>3}{float(bt):>7.1%}{float(ca):>9.1%}{float(na):>8.1%}{float(dl):>8.1%}")
for t in ("1_source_document", "5_scenario", "v_2_renewal_inputs_latest"):
    print(f"  {t}: {run(f'SELECT count(*) FROM {FQ}.`{t}`','c').result.data_array[0][0]} rows")
print("seed complete.")
