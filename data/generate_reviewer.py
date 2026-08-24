"""Reviewer agent — challenge the active hero document's assumptions against the
book benchmark and method. Pre-computed by default; FMAPI path behind LIVE_REVIEWER.

Writes 4_reviewer_finding rows (incl. at least one green/OK, so it reads as a
reviewer not an attack dog). Run: uv run --native-tls --with databricks-sdk generate_reviewer.py
"""
from __future__ import annotations
import os, json, datetime as dt
from databricks.sdk import WorkspaceClient

WAREHOUSE = os.getenv("HB_WAREHOUSE", "a3b61648ea4809e3")
CAT = os.getenv("HB_CATALOG", "lr_dev_aws_us_catalog")
SCH = os.getenv("HB_SCHEMA", "hb_renewal")
FQ = f"{CAT}.{SCH}"
_PROF = os.getenv("HB_PROFILE") or None
w = WorkspaceClient(profile=_PROF)
LIVE = os.getenv("LIVE_REVIEWER", "false").lower() == "true"


def run(sql, label=""):
    r = w.statement_execution.execute_statement(warehouse_id=WAREHOUSE, statement=sql, wait_timeout="50s")
    if not r.status or r.status.state.value != "SUCCEEDED":
        raise SystemExit(f"FAILED [{label}]: {r.status.error.message if r.status and r.status.error else '?'}")
    return r


def sv(x):
    if x is None:
        return "NULL"
    return "'" + x.replace("'", "''") + "'" if isinstance(x, str) else repr(x)


# active hero document + its inputs
doc = run(f"SELECT doc_id, carrier, employer_group FROM {FQ}.`v_source_document_latest` "
          f"WHERE status='active' AND doc_family='renewal_exhibit' ORDER BY ingested_at DESC LIMIT 1", "doc").result.data_array
doc_id, carrier, group = doc[0]
inp = run(f"SELECT annual_trend, months_of_trend, current_members, target_loss_ratio, "
          f"manual_rating_pool_increase, credibility_experience_weight FROM {FQ}.`v_2_renewal_inputs_latest` "
          f"WHERE source_document_id={sv(doc_id)}", "inp").result.data_array[0]
trend, months_trend, members, target_lr, manual, cred = (float(x) if x is not None else None for x in inp)
band = "<100" if members < 100 else "100-499" if members < 500 else "500-1999" if members < 2000 else "2000+"
bench = run(f"SELECT book_trend_median FROM {FQ}.`6_book_trend_benchmark` "
            f"WHERE carrier={sv(carrier)} AND group_band='{band}'", "bench").result.data_array
book_trend = float(bench[0][0]) if bench else 0.07

run(f"DELETE FROM {FQ}.`4_reviewer_finding` WHERE source_document_id={sv(doc_id)}", "clear")

findings = [
    ("trend_challenge", "high", "annual_trend", trend, book_trend,
     f"Carrier annual trend {trend:.1%} vs book median {book_trend:.1%} for {carrier} at {band} lives — "
     f"{ (trend-book_trend)*100:.1f} points rich. Strongest challenge candidate."),
    ("trend_period", "medium", "months_of_trend", months_trend, None,
     f"{months_trend:.0f} months of trend applied — verify midpoint-to-midpoint alignment with the renewal effective date; "
     f"an over-stated trend period compounds the rate."),
    ("manual_rate", "medium", "manual_rating_pool_increase", manual, None,
     f"Manual rating pool increase {manual:.1%} is carrier-provided and opaque — request the supporting book-rate basis before accepting."),
    ("target_lr", "low", "target_loss_ratio", target_lr, 0.94,
     f"Target loss ratio {target_lr:.1%} implies retention ~{(1-target_lr)*100:.1f}% — modestly above a 6% book benchmark; a minor challenge."),
    ("credibility_ok", "ok", "credibility_experience_weight", cred, None,
     f"Experience credibility weight {cred:.2f} is consistent with ~{members:.0f} covered members — no challenge, leave as is."),
]

if LIVE:
    from openai import OpenAI
    from databricks.sdk.core import Config
    cfg = Config(profile=_PROF)
    bearer = cfg.authenticate().get("Authorization", "").removeprefix("Bearer ")
    client = OpenAI(api_key=bearer, base_url=f"{cfg.host.rstrip('/')}/serving-endpoints")
    prompt = (f"You are a senior H&B underwriting reviewer. Given carrier assumptions: annual_trend={trend}, "
              f"months_of_trend={months_trend}, manual_rating_pool_increase={manual}, target_loss_ratio={target_lr}, "
              f"credibility_experience_weight={cred}, members={members}; and book median trend={book_trend}. "
              f"Return JSON list of findings [{{finding_type, severity(high|medium|low|ok), lever, carrier_value, book_value, narrative}}]. "
              f"Include at least one 'ok' finding. Broker voice, concise.")
    import re
    resp = client.chat.completions.create(model=os.getenv("HB_LLM_ENDPOINT", "databricks-claude-sonnet-4-5"),
                                          messages=[{"role": "user", "content": prompt}], max_tokens=1200)
    m = re.search(r"\[.*\]", resp.choices[0].message.content or "", re.S)
    if m:
        findings = [(f["finding_type"], f["severity"], f["lever"], f.get("carrier_value"), f.get("book_value"), f["narrative"])
                    for f in json.loads(m.group(0))]

gen = "fmapi" if LIVE else "precomputed"
vals = ",".join(f"({sv(doc_id)},{sv(ft)},{sv(sev)},{sv(lev)},{sv(cv)},{sv(bv)},{sv(narr)},current_timestamp(),{sv(gen)})"
                for ft, sev, lev, cv, bv, narr in findings)
run(f"INSERT INTO {FQ}.`4_reviewer_finding` VALUES {vals}", "insert findings")
print(f"wrote {len(findings)} reviewer findings for {doc_id} ({carrier}/{group}), generated_by={gen}")
for ft, sev, lev, cv, bv, narr in findings:
    print(f"  [{sev:>6}] {narr}")
