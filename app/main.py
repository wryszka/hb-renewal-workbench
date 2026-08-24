"""HB Renewal Workbench — thin FastAPI shell over governed Unity Catalog objects.

No renewal math runs in this container. The only compute path is the governed UC
function fn_renewal_buildup, called through the SQL warehouse. Every read is a
governed table/view; every save writes a governed row + an audit event.
"""
from __future__ import annotations
import os, json, uuid, sys, pathlib
from fastapi import FastAPI, Body, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from databricks.sdk import WorkspaceClient

CAT = os.getenv("HB_CATALOG", "lr_dev_aws_us_catalog")
SCH = os.getenv("HB_SCHEMA", "hb_renewal")
FQ = f"`{CAT}`.`{SCH}`"
LLM = os.getenv("HB_LLM_ENDPOINT", "databricks-claude-sonnet-4-5")
_http = os.getenv("DATABRICKS_HTTP_PATH", "")
WAREHOUSE = os.getenv("HB_WAREHOUSE") or (_http.rstrip("/").split("/")[-1] if _http else "a3b61648ea4809e3")
_prof = os.getenv("HB_PROFILE")
W = WorkspaceClient(profile=_prof) if _prof else WorkspaceClient()

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "jobs"))

app = FastAPI(title="HB Renewal Workbench")

INPUT_COLS = ["member_months", "total_incurred_claims", "months_experience", "current_members",
              "current_total_premium_monthly", "demographic_adjustment", "less_pooled_claims_pmpm",
              "benefit_change", "annual_trend", "months_of_trend", "projected_excess_claims_pmpm",
              "large_claim_add_back_pmpm", "target_loss_ratio", "benefit_advisor_fee",
              "manual_rating_pool_increase", "credibility_experience_weight",
              "credibility_manual_weight", "adjustment"]


def sq(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def query(sql: str):
    r = W.statement_execution.execute_statement(warehouse_id=WAREHOUSE, statement=sql, wait_timeout="50s")
    if not r.status or r.status.state.value != "SUCCEEDED":
        raise HTTPException(500, f"SQL error: {r.status.error.message if r.status and r.status.error else '?'}")
    cols = [c.name for c in r.manifest.schema.columns] if r.manifest and r.manifest.schema else []
    return [dict(zip(cols, row)) for row in (r.result.data_array or [])]


def audit(event_type, entity_type, entity_id, detail, actor):
    query(f"INSERT INTO {FQ}.`5_gov_audit_event` VALUES ('AE-{uuid.uuid4().hex[:10]}',{sq(event_type)},"
          f"{sq(entity_type)},{sq(entity_id)},{sq(detail)},{sq(actor)},current_timestamp())")


def buildup(inputs: dict, overrides: dict | None = None) -> dict:
    args = dict(inputs)
    if overrides:
        args.update({k: v for k, v in overrides.items() if k in INPUT_COLS})
    call = ",".join(sq(args.get(c)) for c in INPUT_COLS)
    rows = query(f"SELECT {FQ}.fn_renewal_buildup({call}) AS j")
    return json.loads(rows[0]["j"])


# ------------------------------------------------------------------- API
@app.get("/api/book")
def book():
    # all statuses (active, differs, quarantined, superseded) so governance is visible;
    # active first, superseded last.
    docs = query(f"""SELECT doc_id, carrier, employer_group, policy_period, file_name, doc_family,
        status, fields_found, fields_expected, cast(ingested_at AS STRING) ingested_at, signed_off_by
        FROM {FQ}.`1_source_document`
        ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'differs' THEN 1 WHEN 'quarantined' THEN 2 ELSE 3 END,
                 ingested_at DESC""")
    scn = query(f"""SELECT source_document_id, max(scenario_action) latest_scenario, count(*) n_scenarios,
        max(baseline_action) carrier_action FROM {FQ}.`5_scenario` GROUP BY source_document_id""")
    smap = {s["source_document_id"]: s for s in scn}
    have_inputs = {r["source_document_id"] for r in query(f"SELECT DISTINCT source_document_id FROM {FQ}.`2_renewal_inputs`")}
    for d in docs:
        s = smap.get(d["doc_id"], {})
        d["latest_scenario_action"] = float(s["latest_scenario"]) if s.get("latest_scenario") is not None else None
        d["carrier_action"] = float(s["carrier_action"]) if s.get("carrier_action") is not None else None
        d["n_scenarios"] = int(s.get("n_scenarios") or 0)
        # freshly-ingested active exhibit with no saved scenario yet: compute its action live
        if d["carrier_action"] is None and d["status"] == "active" and d["doc_id"] in have_inputs:
            inp = _hero_inputs(d["doc_id"])
            if inp:
                d["carrier_action"] = buildup(inp)["quoted_change"]
    return docs


def _hero_inputs(doc_id: str) -> dict | None:
    rows = query(f"SELECT {', '.join(INPUT_COLS)} FROM {FQ}.`2_renewal_inputs` WHERE source_document_id={sq(doc_id)}")
    if not rows:
        return None
    return {k: (float(v) if v is not None else None) for k, v in rows[0].items()}


@app.get("/api/document/{doc_id}")
def document(doc_id: str):
    docs = query(f"SELECT doc_id, carrier, employer_group, policy_period, file_name, status, doc_family, "
                 f"fields_found, fields_expected, reconciliation_detail, cast(ingested_at AS STRING) ingested_at, "
                 f"signed_off_by, stored_path FROM {FQ}.`1_source_document` WHERE doc_id={sq(doc_id)}")
    if not docs:
        raise HTTPException(404, "document not found")
    doc = docs[0]
    inputs = _hero_inputs(doc_id)
    result = {"document": doc, "inputs": inputs}
    if inputs:
        base = buildup(inputs)
        result["baseline"] = base
        # benchmark for this carrier + band
        members = inputs.get("current_members") or 0
        band = "<100" if members < 100 else "100-499" if members < 500 else "500-1999" if members < 2000 else "2000+"
        bench = query(f"SELECT book_trend_median, avg_negotiation_delta FROM {FQ}.`6_book_trend_benchmark` "
                      f"WHERE carrier={sq(doc['carrier'])} AND group_band='{band}'")
        result["benchmark_band"] = band
        result["book_trend"] = float(bench[0]["book_trend_median"]) if bench else None
    result["findings"] = query(f"SELECT finding_type, severity, lever, carrier_value, book_value, narrative "
                               f"FROM {FQ}.`4_reviewer_finding` WHERE source_document_id={sq(doc_id)} "
                               f"ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END")
    result["scenarios"] = query(f"SELECT scenario_id, scenario_name, created_by, cast(created_at AS STRING) created_at, "
                                f"overrides, baseline_action, scenario_action, value_at_stake_annual, reason, status "
                                f"FROM {FQ}.`5_scenario` WHERE source_document_id={sq(doc_id)} ORDER BY created_at DESC")
    result["monthly"] = query(f"SELECT month, total_incurred, med_members FROM {FQ}.`1_incurred_claims` "
                              f"WHERE source_document_id={sq(doc_id)} ORDER BY month")
    # reforecast: is there a newer claims month than the input experience end?
    result["reforecast_months"] = len(result["monthly"])
    return result


@app.post("/api/recompute")
def recompute(payload: dict = Body(...)):
    doc_id = payload["doc_id"]
    inputs = _hero_inputs(doc_id)
    if not inputs:
        raise HTTPException(404, "no inputs")
    base = buildup(inputs)
    scn = buildup(inputs, payload.get("overrides") or {})
    vas = base["projected_billed_premium_annual"] - scn["projected_billed_premium_annual"]
    return {"baseline": base, "scenario": scn, "value_at_stake_annual": vas}


@app.post("/api/scenario")
def save_scenario(payload: dict = Body(...)):
    doc_id = payload["doc_id"]
    name = (payload.get("scenario_name") or "").strip()
    reason = (payload.get("reason") or "").strip()
    if not name or not reason:
        raise HTTPException(400, "scenario_name and reason are required")
    inputs = _hero_inputs(doc_id)
    if not inputs:
        raise HTTPException(404, "no inputs")
    overrides = payload.get("overrides") or {}
    base = buildup(inputs)
    scn = buildup(inputs, overrides)
    vas = base["projected_billed_premium_annual"] - scn["projected_billed_premium_annual"]
    doc = query(f"SELECT carrier, employer_group FROM {FQ}.`1_source_document` WHERE doc_id={sq(doc_id)}")[0]
    sid = f"SCN-{uuid.uuid4().hex[:8]}"
    actor = payload.get("actor") or "workbench-user"
    members = inputs.get("current_members") or 0
    band = "<100" if members < 100 else "100-499" if members < 500 else "500-1999" if members < 2000 else "2000+"
    stored = {**overrides, "members": members, "group_band": band}
    query(f"""INSERT INTO {FQ}.`5_scenario` VALUES ({sq(sid)},{sq(doc_id)},{sq(doc['carrier'])},
        {sq(doc['employer_group'])},{sq(name)},{sq(actor)},current_timestamp(),'carrier_proposal',
        {sq(json.dumps(stored))},{sq(base['blended_rate_action'])},{sq(scn['quoted_change'])},
        {sq(vas)},{sq(reason)},'saved',NULL)""")
    audit("scenario_saved", "scenario", sid, f"{name}: {json.dumps(overrides)}; ${vas:,.0f} at stake", actor)
    return {"scenario_id": sid, "value_at_stake_annual": vas, "scenario_action": scn["quoted_change"]}


@app.get("/api/benchmarks")
def benchmarks():
    return query(f"SELECT carrier, group_band, renewals_negotiated, book_trend_median, avg_carrier_action, "
                 f"avg_negotiated_action, avg_negotiation_delta, total_value_negotiated "
                 f"FROM {FQ}.`6_book_trend_benchmark` ORDER BY carrier, group_band")


@app.get("/api/benchmark/scenarios")
def benchmark_scenarios(carrier: str, band: str):
    """The retained decisions behind one benchmark cell (carrier × group band) — the row's lineage."""
    return query(f"""SELECT scenario_id, employer_group, cast(created_at AS STRING) created_at,
        baseline_action, scenario_action, value_at_stake_annual, reason, status, source_document_id
        FROM {FQ}.`5_scenario`
        WHERE carrier={sq(carrier)} AND get_json_object(overrides,'$.group_band')={sq(band)}
          AND status IN ('saved','approved')
        ORDER BY created_at DESC""")


@app.get("/api/audit")
def audit_feed(doc_id: str = ""):
    where = f"WHERE entity_id={sq(doc_id)}" if doc_id else ""
    return query(f"SELECT cast(created_at AS STRING) created_at, event_type, entity_type, entity_id, detail, actor "
                 f"FROM {FQ}.`5_gov_audit_event` {where} ORDER BY created_at DESC LIMIT 40")


@app.get("/api/lineage/{doc_id}")
def lineage(doc_id: str):
    doc = query(f"SELECT doc_id, file_name, cast(ingested_at AS STRING) ingested_at, fields_found, fields_expected, "
                f"status, stored_path FROM {FQ}.`1_source_document` WHERE doc_id={sq(doc_id)}")
    fn = query(f"SELECT routine_name FROM system.information_schema.routines WHERE routine_schema={sq(SCH)} "
               f"AND routine_name='fn_renewal_buildup'")
    hist = query(f"DESCRIBE HISTORY {FQ}.`5_scenario`")
    tbl_versions = {}
    for t in ("2_renewal_inputs", "5_scenario"):
        try:
            h = query(f"DESCRIBE HISTORY {FQ}.`{t}` LIMIT 1")
            tbl_versions[t] = h[0].get("version") if h else None
        except Exception:
            tbl_versions[t] = None
    return {"source_document": doc[0] if doc else None,
            "function": {"name": "fn_renewal_buildup", "governed": bool(fn), "catalog": f"{CAT}.{SCH}"},
            "table_versions": tbl_versions}


@app.get("/api/deal/{scenario_id}")
def deal(scenario_id: str):
    """Resolve a saved/approved decision back to the exact carrier file it came from.
    The bridge from 'here is the deal we agreed' to 'here is the spreadsheet it was built on'."""
    s = query(f"""SELECT scenario_id, source_document_id, carrier, employer_group, scenario_name,
        baseline_action, scenario_action, value_at_stake_annual, reason, status,
        cast(created_at AS STRING) created_at, created_by
        FROM {FQ}.`5_scenario` WHERE scenario_id={sq(scenario_id)}""")
    if not s:
        raise HTTPException(404, "deal not found")
    s = s[0]
    doc = query(f"""SELECT doc_id, carrier, employer_group, policy_period, file_name, status,
        fields_found, fields_expected, cast(ingested_at AS STRING) ingested_at, stored_path
        FROM {FQ}.`1_source_document` WHERE doc_id={sq(s['source_document_id'])}""")
    return {"scenario": s, "document": doc[0] if doc else None}


@app.get("/api/document/{doc_id}/file")
def document_file(doc_id: str):
    """Pull the exact original carrier file for a document straight out of the governed
    UC Volume — the physical evidence behind every number that traces to it."""
    rows = query(f"SELECT file_name, stored_path FROM {FQ}.`1_source_document` WHERE doc_id={sq(doc_id)}")
    if not rows:
        raise HTTPException(404, "document not found")
    stored_path, file_name = rows[0].get("stored_path"), rows[0].get("file_name") or "submission.xlsx"
    if not stored_path:
        raise HTTPException(404, "no archived original for this document — only files ingested through the "
                                 "pipeline are stored in the governed Volume and retrievable here.")
    try:
        data = W.files.download(stored_path).contents.read()
    except Exception as e:
        raise HTTPException(404, f"original not found in Volume ({stored_path}): {e}")
    # retrieving the source is itself a governed act — record it.
    audit("file_retrieved", "source_document", doc_id, f"original pulled from governed Volume: {stored_path}", "workbench-user")
    return Response(content=data,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{file_name}"'})


@app.post("/api/summary")
def summary(payload: dict = Body(...)):
    doc_id = payload["doc_id"]
    inputs = _hero_inputs(doc_id)
    doc = query(f"SELECT carrier, employer_group FROM {FQ}.`1_source_document` WHERE doc_id={sq(doc_id)}")[0]
    overrides = payload.get("overrides") or {}
    base = buildup(inputs)
    scn = buildup(inputs, overrides)
    findings = query(f"SELECT narrative FROM {FQ}.`4_reviewer_finding` WHERE source_document_id={sq(doc_id)} AND severity<>'ok'")
    prompt = (f"You are a senior H&B underwriting consultant writing a short broker-facing renewal summary for "
              f"{doc['employer_group']} ({doc['carrier']}, fully insured). 3-5 crisp bullets + a target range. "
              f"Carrier blended action {base['blended_rate_action']*100:.1f}%; negotiated position "
              f"{scn['quoted_change']*100:.1f}%. Reviewer flags: {[f['narrative'] for f in findings]}. "
              f"Explain why the increase is what it is and the top negotiation levers. Broker voice, concrete.")
    try:
        from openai import OpenAI
        from databricks.sdk.core import Config
        cfg = Config(profile=_prof) if _prof else Config()
        bearer = cfg.authenticate().get("Authorization", "").removeprefix("Bearer ")
        client = OpenAI(api_key=bearer, base_url=f"{cfg.host.rstrip('/')}/serving-endpoints")
        resp = client.chat.completions.create(model=LLM, messages=[{"role": "user", "content": prompt}], max_tokens=650)
        return {"summary": resp.choices[0].message.content}
    except Exception as e:
        return {"summary": f"**{doc['employer_group']} — {doc['carrier']} renewal**\n\n"
                f"- Carrier blended action: {base['blended_rate_action']*100:.1f}%\n"
                f"- Negotiated position: {scn['quoted_change']*100:.1f}%\n"
                f"- Primary lever: medical trend, above book benchmark\n\n_(LLM unavailable: {e})_"}


@app.get("/api/overview")
def overview():
    counts = {r["status"]: int(r["n"]) for r in query(f"SELECT status, count(*) n FROM {FQ}.`1_source_document` GROUP BY status")}
    kpi = query(f"""SELECT count(*) renewals, round(avg(baseline_action),4) avg_carrier, round(avg(scenario_action),4) avg_negotiated,
        round(sum(value_at_stake_annual),0) value_negotiated FROM {FQ}.`5_scenario` WHERE status IN ('saved','approved')""")[0]
    attention = query(f"""SELECT doc_id, carrier, employer_group, policy_period, status, fields_found, fields_expected
        FROM {FQ}.`1_source_document` WHERE status IN ('quarantined','differs') ORDER BY ingested_at DESC""")
    recent = query(f"""SELECT cast(created_at AS STRING) created_at, event_type, entity_id, detail
        FROM {FQ}.`5_gov_audit_event` ORDER BY created_at DESC LIMIT 7""")
    hero = query(f"""SELECT doc_id, carrier, employer_group, policy_period FROM {FQ}.`1_source_document`
        WHERE status='active' AND doc_family='renewal_exhibit'
          AND doc_id IN (SELECT source_document_id FROM {FQ}.`2_renewal_inputs`) ORDER BY ingested_at DESC LIMIT 1""")
    return {"counts": counts, "kpi": {k: (float(v) if v is not None else None) for k, v in kpi.items()},
            "attention": attention, "recent": recent, "hero": hero[0] if hero else None,
            "book_total": sum(counts.values())}


@app.get("/api/agents")
def agents():
    fdoc = query(f"""SELECT r.source_document_id, d.carrier, d.employer_group, max(r.generated_by) generated_by, count(*) n
        FROM {FQ}.`4_reviewer_finding` r JOIN {FQ}.`1_source_document` d ON d.doc_id=r.source_document_id
        GROUP BY r.source_document_id, d.carrier, d.employer_group ORDER BY n DESC LIMIT 1""")
    findings = []
    if fdoc:
        findings = query(f"""SELECT severity, lever, narrative FROM {FQ}.`4_reviewer_finding`
            WHERE source_document_id={sq(fdoc[0]['source_document_id'])}
            ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END""")
    return {"reviewer": {"target": fdoc[0] if fdoc else None, "findings": findings,
                         "generated_by": (fdoc[0]["generated_by"] if fdoc else "precomputed"),
                         "live_flag": os.getenv("LIVE_REVIEWER", "false")},
            "summariser": {"endpoint": LLM},
            "genie": {"configured": bool(os.getenv("HB_GENIE_SPACE_ID")), "space_id": os.getenv("HB_GENIE_SPACE_ID", "")}}


def _job_id_by_name(name):
    try:
        for j in W.jobs.list(name=name):
            return j.job_id
    except Exception:
        pass
    return None


def _workspace_links():
    """Build deep-links to the real workspace assets from the configured host +
    catalog/schema (never hardcoded). Shared by /api/config and /api/learn."""
    host = ""
    try:
        from databricks.sdk.core import Config
        host = (Config(profile=_prof) if _prof else Config()).host.rstrip("/")
    except Exception:
        pass
    did, gid = os.getenv("HB_DASHBOARD_ID", ""), os.getenv("HB_GENIE_SPACE_ID", "")

    def tbl(t):
        return f"{host}/explore/data/{CAT}/{SCH}/{t}" if host else ""

    def fn(f):
        return f"{host}/explore/data/functions/{CAT}/{SCH}/{f}" if host else ""

    ingest_job = _job_id_by_name("[hb-renewal] carrier file ingestion")
    reseed_job = _job_id_by_name("[hb-renewal] demo reset (reseed)")
    links = {
        "schema": f"{host}/explore/data/{CAT}/{SCH}" if host else "",
        "volume": f"{host}/explore/data/volumes/{CAT}/{SCH}/landing" if host else "",
        "carrier_template": tbl("0_carrier_template"),
        "source_document": tbl("1_source_document"),
        "renewal_inputs": tbl("2_renewal_inputs"),
        "incurred_claims": tbl("1_incurred_claims"),
        "incurred_latest": tbl("v_1_incurred_claims_latest"),
        "reviewer_finding": tbl("4_reviewer_finding"),
        "scenario": tbl("5_scenario"),
        "audit": tbl("5_gov_audit_event"),
        "benchmark": tbl("6_book_trend_benchmark"),
        "mv_renewal_actions": tbl("mv_renewal_actions"),
        "fn_buildup": fn("fn_renewal_buildup"),
        "fn_action": fn("fn_renewal_action"),
        "llm_endpoint": f"{host}/ml/endpoints/{LLM}" if host else "",
        "ingest_job": f"{host}/jobs/{ingest_job}" if (host and ingest_job) else "",
        "reseed_job": f"{host}/jobs/{reseed_job}" if (host and reseed_job) else "",
        "genie": f"{host}/genie/rooms/{gid}" if (host and gid) else "",
        "dashboard": f"{host}/dashboardsv3/{did}" if (host and did) else "",
    }
    return host, links, did, gid


@app.get("/api/config")
def config():
    host, links, did, gid = _workspace_links()
    return {"dashboard_url": f"{host}/embed/dashboardsv3/{did}" if (did and host) else "",
            "genie_url": f"{host}/embed/genie/rooms/{gid}" if (host and gid) else "",
            "links": links}


# The nine renewal activities — the single source of the Learn-panel copy.
# Layers 1-2 (activity, how) are broker-readable and carry NO object names;
# object names live only in the "See it live" links. See docs/LEARN_PANEL.md.
LEARN_CARDS = [
    {"n": 1, "group": "Trust the data",
     "activity": "Get the data in — receive the carrier's file and prove it was read correctly.",
     "how": "You drop the file in; two independent readers pull the numbers and must agree before anything is trusted.",
     "links": [{"label": "Volume landing/inbox", "key": "volume"},
               {"label": "Ingestion Job", "key": "ingest_job"},
               {"label": "1_source_document", "key": "source_document"}]},
    {"n": 2, "group": "Trust the data",
     "activity": "Verify and trust it — is this a format we know? Catch what's wrong and sign off the exceptions.",
     "how": "The file is checked against the carrier's known layout; anything unexpected or drifting is held back for a human rather than guessed.",
     "links": [{"label": "0_carrier_template", "key": "carrier_template"},
               {"label": "Quarantined docs — Book view", "view": "book"}]},
    {"n": 3, "group": "Work the renewal",
     "activity": "Reproduce the carrier's math — rebuild exactly how they reached their number.",
     "how": "The build-up is one shared, versioned calculation; the app can't invent its own answer — it can only call it.",
     "links": [{"label": "fn_renewal_action (function)", "key": "fn_action"},
               {"label": "Exhibit — Renewal Workspace", "view": "workspace"}]},
    {"n": 4, "group": "Work the renewal",
     "activity": "Challenge it — find where to push back and test what-ifs.",
     "how": "Each lever shows the carrier's value beside your book's, and a reviewer flags the assumptions most worth challenging.",
     "links": [{"label": "Levers — Renewal Workspace", "view": "workspace"},
               {"label": "4_reviewer_finding", "key": "reviewer_finding"}]},
    {"n": 5, "group": "Work the renewal",
     "activity": "Decide and record — commit to a position and keep the reasoning.",
     "how": "Saving needs a name and a reason; every save is kept as a dated version with its author, nothing overwritten.",
     "links": [{"label": "5_scenario (+ version history)", "key": "scenario"},
               {"label": "5_gov_audit_event", "key": "audit"}]},
    {"n": 6, "group": "Work the renewal",
     "activity": "Present and negotiate — the summary that goes to the client and the carrier.",
     "how": "A short summary is drafted from your saved position, and a compare view shows the ask, your position, and the money at stake.",
     "links": [{"label": "Compare — Renewal Workspace", "view": "workspace"},
               {"label": "Summariser — Agents", "view": "agents"}]},
    {"n": 7, "group": "Compound the book",
     "activity": "Reforecast — fresh data arrives, update without rebuilding.",
     "how": "New months come in through the same intake; the position recomputes on one click and your earlier decision is kept.",
     "links": [{"label": "Reforecast — Renewal Workspace", "view": "workspace"},
               {"label": "v_1_incurred_claims_latest", "key": "incurred_latest"}]},
    {"n": 8, "group": "Compound the book",
     "activity": "Learn across the book — accumulate what every negotiation taught you.",
     "how": "The book's own trend benchmark is built from the decisions you've retained — it isn't a bought-in number.",
     "links": [{"label": "6_book_trend_benchmark", "key": "benchmark"},
               {"label": "Benchmarks panel", "view": "benchmarks"}]},
    {"n": 9, "group": "Compound the book",
     "activity": "Answer questions about the book — anyone, anytime, without a spreadsheet.",
     "how": "Shared metric definitions plus natural-language questions over the governed book; the generated query is shown so answers can be checked.",
     "links": [{"label": "mv_renewal_actions", "key": "mv_renewal_actions"},
               {"label": "Ask the book panel", "view": "ask"}]},
]


@app.get("/api/learn")
def learn():
    _, links, _, _ = _workspace_links()
    cards = []
    for c in LEARN_CARDS:
        out = []
        for lk in c["links"]:
            if lk.get("key"):
                url = links.get(lk["key"], "")
                if url:
                    out.append({"label": lk["label"], "url": url, "external": True})
            else:
                out.append({"label": lk["label"], "view": lk["view"], "external": False})
        cards.append({"n": c["n"], "group": c["group"], "activity": c["activity"], "how": c["how"], "links": out})
    return {"cards": cards}


@app.get("/api/ingestion")
def ingestion():
    templates = query(f"""SELECT carrier, doc_family, field_count, expected_tabs, status
        FROM {FQ}.`0_carrier_template` ORDER BY carrier, doc_family""")
    recent = query(f"""SELECT carrier, employer_group, file_name, doc_family, status,
        fields_found, fields_expected, cast(ingested_at AS STRING) ingested_at, reconciliation_detail, doc_id
        FROM {FQ}.`1_source_document` ORDER BY ingested_at DESC LIMIT 16""")
    inbox = []
    try:
        inbox = [os.path.basename(f.path) for f in W.files.list_directory_contents(f"/Volumes/{CAT}/{SCH}/landing/inbox")
                 if f.path.endswith(".xlsx")]
    except Exception:
        pass
    return {"templates": templates, "recent": recent, "inbox": inbox,
            "volume": f"/Volumes/{CAT}/{SCH}/landing"}


@app.post("/api/ingest/upload")
async def ingest_upload(file: UploadFile = File(...)):
    """Drop a carrier file from the app itself: run it through the ingestion pipeline
    and return the two-path reconciliation + outcome."""
    import ingest_pipeline
    data = await file.read()
    local = f"/tmp/{os.path.basename(file.filename)}"
    with open(local, "wb") as fh:
        fh.write(data)
    res = ingest_pipeline.process_file(local, actor="workbench-upload")
    return res


@app.post("/api/ingest/scan")
def ingest_scan(payload: dict = Body(default={})):
    """Run-now fallback: process any files sitting in the Volume inbox/."""
    import ingest_pipeline
    base = f"/Volumes/{CAT}/{SCH}/landing/inbox"
    processed = []
    try:
        files = [f.path for f in W.files.list_directory_contents(base)]
    except Exception as e:
        return {"processed": [], "note": f"inbox empty or unavailable: {e}"}
    for path in files:
        if not path.endswith(".xlsx"):
            continue
        local = f"/tmp/{os.path.basename(path)}"
        with open(local, "wb") as fh:
            fh.write(W.files.download(path).contents.read())
        res = ingest_pipeline.process_file(local, actor="workbench-scan")
        processed.append({"file": os.path.basename(path), "status": res.get("status"), "doc_id": res.get("doc_id")})
    return {"processed": processed}


RESEED_JOB_NAME = "[hb-renewal] demo reset (reseed)"


def _reseed_job_id():
    try:
        for j in W.jobs.list(name=RESEED_JOB_NAME):
            return j.job_id
    except Exception:
        pass
    return None


@app.post("/api/reset")
def reset_demo():
    """Trigger the serverless reseed Job — restores the pristine demo state (~1-2 min)."""
    job_id = _reseed_job_id()
    if not job_id:
        raise HTTPException(404, f"reseed job not found — deploy the bundle ('{RESEED_JOB_NAME}').")
    w = W.jobs.run_now(job_id=job_id)
    run_id = getattr(w, "run_id", None) or getattr(getattr(w, "response", None), "run_id", None)
    audit("demo_reset", "job", str(job_id), f"reseed run {run_id} triggered", "workbench-user")
    return {"run_id": run_id, "job_id": job_id}


@app.get("/api/reset/status")
def reset_status(run_id: int):
    r = W.jobs.get_run(run_id=run_id)
    st = r.state
    life = st.life_cycle_state.value if st and st.life_cycle_state else None
    result = st.result_state.value if st and st.result_state else None
    done = life in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR")
    return {"life_cycle_state": life, "result_state": result, "done": done, "success": result == "SUCCESS"}


@app.post("/api/genie/ask")
def genie_ask(payload: dict = Body(...)):
    space_id = os.getenv("HB_GENIE_SPACE_ID")
    if not space_id:
        return JSONResponse({"error": "HB_GENIE_SPACE_ID not configured — see GENIE_SETUP.md (native Genie UI works over the same views)."}, status_code=200)
    q = payload["question"]
    conv = payload.get("conversation_id")
    try:
        if conv:
            msg = W.genie.create_message_and_wait(space_id, conv, q)
        else:
            msg = W.genie.start_conversation_and_wait(space_id, q)
        conv_id = getattr(msg, "conversation_id", None)
        text, sql, rows = None, None, []
        for att in (getattr(msg, "attachments", None) or []):
            if getattr(att, "text", None):
                text = att.text.content
            qy = getattr(att, "query", None)
            if qy:
                sql = getattr(qy, "query", None) or getattr(qy, "description", None)
                for name in ("execute_message_attachment_query", "get_message_attachment_query_result"):
                    fn = getattr(W.genie, name, None)
                    if not fn:
                        continue
                    try:
                        res = fn(space_id, conv_id, msg.id, att.attachment_id)
                        sr = getattr(res, "statement_response", None)
                        if not sr or not getattr(sr, "manifest", None) or not sr.manifest.schema:
                            continue  # this method returned no result set; try the next
                        cols = [c.name for c in sr.manifest.schema.columns]
                        rows = [dict(zip(cols, r)) for r in (sr.result.data_array or [])][:50]
                        if rows:
                            break
                    except Exception:
                        pass
        return {"conversation_id": conv_id, "text": text, "sql": sql, "rows": rows}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=200)


@app.get("/api/health")
def health():
    return {"ok": True, "catalog": CAT, "schema": SCH, "warehouse": WAREHOUSE,
            "genie": bool(os.getenv("HB_GENIE_SPACE_ID"))}


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "frontend"), html=True), name="static")
