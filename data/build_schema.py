"""Authoritative idempotent schema build for the HB Renewal Workbench.

Drop-and-recreate every governed object (names preserved). Loads NO business
data — the book is seeded by seed_book.py through the ingestion module, and the
hero exhibit is loaded by the same ingestion code path the live Job uses.

All synthetic. No real carrier/client/broker names anywhere.

Run: uv run --native-tls --with databricks-sdk build_schema.py
"""
from __future__ import annotations
import os
from databricks.sdk import WorkspaceClient

WAREHOUSE = os.getenv("HB_WAREHOUSE", "a3b61648ea4809e3")
CAT = os.getenv("HB_CATALOG", "lr_dev_aws_us_catalog")
SCH = os.getenv("HB_SCHEMA", "hb_renewal")
FQ = f"{CAT}.{SCH}"
# profile locally (HB_PROFILE=DEV); ambient auth on a Job (no profile)
w = WorkspaceClient(profile=os.getenv("HB_PROFILE") or None)


def run(sql: str, label: str):
    r = w.statement_execution.execute_statement(warehouse_id=WAREHOUSE, statement=sql, wait_timeout="50s")
    st = r.status.state.value if r.status else "?"
    if st != "SUCCEEDED":
        raise SystemExit(f"FAILED [{label}]: {st} :: {r.status.error.message if r.status and r.status.error else ''}")
    print(f"  ok  {label}")
    return r


run(f"CREATE SCHEMA IF NOT EXISTS {FQ} COMMENT '[hb-renewal] Governed H&B medical renewal workbench — synthetic demo data only.'", "schema")

# UC Volume for file ingestion (inbox / processed / quarantine).
run(f"CREATE VOLUME IF NOT EXISTS {FQ}.landing COMMENT '[hb-renewal] Carrier file landing zone: inbox/ processed/ quarantine/'", "volume")

# ---------------------------------------------------------------- source tables
run(f"""CREATE OR REPLACE TABLE {FQ}.`1_incurred_claims` (
  source_document_id STRING, carrier STRING, employer_group STRING, month STRING,
  billed_premium DOUBLE, ffs_medical DOUBLE, pharmacy DOUBLE, fixed_charges DOUBLE,
  out_of_network DOUBLE, total_incurred DOUBLE, med_ees INT, med_members INT)
COMMENT '[hb-renewal] Monthly incurred claims experience (source layer). One row per document per month.'""", "1_incurred_claims")

run(f"""CREATE OR REPLACE TABLE {FQ}.`1_large_claims` (
  source_document_id STRING, carrier STRING, employer_group STRING,
  status STRING, ee_dep STRING, diagnosis STRING, amount DOUBLE)
COMMENT '[hb-renewal] Large / pooled claimants above the pooling point (source layer).'""", "1_large_claims")

run(f"""CREATE OR REPLACE TABLE {FQ}.`1_detailed_rates` (
  source_document_id STRING, carrier STRING, employer_group STRING,
  kind STRING, plan STRING, tier STRING, subs INT, rate DOUBLE)
COMMENT '[hb-renewal] Current vs renewal premium rates by plan x tier (source layer).'""", "1_detailed_rates")

run(f"""CREATE OR REPLACE TABLE {FQ}.`2_renewal_inputs` (
  source_document_id STRING, carrier STRING, employer_group STRING,
  experience_start STRING, experience_end STRING, months_experience INT,
  funding_type STRING, individual_pooling_point DOUBLE, renewal_effective STRING,
  demographic_adjustment DOUBLE, less_pooled_claims_pmpm DOUBLE, benefit_change DOUBLE,
  annual_trend DOUBLE, months_of_trend DOUBLE, projected_excess_claims_pmpm DOUBLE,
  large_claim_add_back_pmpm DOUBLE, current_members INT, current_total_premium_monthly DOUBLE,
  target_loss_ratio DOUBLE, benefit_advisor_fee DOUBLE, manual_rating_pool_increase DOUBLE,
  credibility_experience_weight DOUBLE, credibility_manual_weight DOUBLE, adjustment DOUBLE,
  member_months DOUBLE, total_incurred_claims DOUBLE)
COMMENT '[hb-renewal] The renewal assumption set / levers extracted from a carrier exhibit (source layer). member_months + total_incurred_claims are the exhibit-stated experience totals used for faithful reproduction.'""", "2_renewal_inputs")

# --------------------------------------------------------- intake + assurance
run(f"""CREATE OR REPLACE TABLE {FQ}.`1_source_document` (
  doc_id STRING, carrier STRING, employer_group STRING, policy_period STRING,
  file_name STRING, doc_family STRING, ingested_at TIMESTAMP,
  fields_expected INT, fields_found INT, reconciliation_detail STRING,
  status STRING COMMENT 'active | superseded | quarantined | differs',
  signed_off_by STRING, signed_off_at TIMESTAMP,
  stored_path STRING COMMENT 'governed UC Volume path of the archived original file — retrievable from any decision that traces back to this document')
COMMENT '[hb-renewal] Intake+assurance provenance: one row per ingested carrier file, its reconciliation result, supersession status, human sign-off, and the governed Volume path of the archived original.'""", "1_source_document")

# --------------------------------------------------- carrier template registry
run(f"""CREATE OR REPLACE TABLE {FQ}.`0_carrier_template` (
  carrier STRING, template_version STRING, doc_family STRING,
  expected_tabs ARRAY<STRING>, field_map STRING COMMENT 'JSON logical-field -> tab/label anchor',
  field_count INT, status STRING)
COMMENT '[hb-renewal] Carrier layout registry: the tabs and labels the ingestion job expects per carrier document family. A new carrier is a row here, not new code.'""", "0_carrier_template")

# --------------------------------------------------------------- decision layer
run(f"""CREATE OR REPLACE TABLE {FQ}.`5_scenario` (
  scenario_id STRING, source_document_id STRING, carrier STRING, employer_group STRING,
  scenario_name STRING, created_by STRING, created_at TIMESTAMP, base_source STRING,
  overrides STRING COMMENT 'JSON lever -> value that the analyst changed',
  baseline_action DOUBLE, scenario_action DOUBLE, value_at_stake_annual DOUBLE,
  reason STRING COMMENT 'required rationale', status STRING COMMENT 'draft | saved | approved',
  parent_scenario_id STRING)
COMMENT '[hb-renewal] Retained negotiation decisions: every what-if saved with who/when/what-changed/why/what-it-was-worth. The unit of retained evidence.'""", "5_scenario")

run(f"""CREATE OR REPLACE TABLE {FQ}.`5_gov_audit_event` (
  event_id STRING, event_type STRING, entity_type STRING, entity_id STRING,
  detail STRING, actor STRING, created_at TIMESTAMP)
COMMENT '[hb-renewal] Append-only governance audit trail across ingestion, sign-off, scenario save and approval.'""", "5_gov_audit_event")

run(f"""CREATE OR REPLACE TABLE {FQ}.`4_reviewer_finding` (
  source_document_id STRING, finding_type STRING, severity STRING, lever STRING,
  carrier_value DOUBLE, book_value DOUBLE, narrative STRING,
  created_at TIMESTAMP, generated_by STRING COMMENT 'precomputed | fmapi')
COMMENT '[hb-renewal] Reviewer agent findings: carrier assumptions challenged against the book benchmark and method, per document.'""", "4_reviewer_finding")

# --------------------------------------------- carrier template registry seeds
FIELD_MAP = ('{"member_months":"Rate Development/Member Months",'
             '"total_incurred_claims":"Rate Development/Total Incurred Claims",'
             '"demographic_adjustment":"Rate Development/Demographic Adjustment",'
             '"less_pooled_claims_pmpm":"Rate Development/Less Pooled Claims",'
             '"benefit_change":"Rate Development/Benefit Change",'
             '"annual_trend":"Rate Development/Annual Trend",'
             '"months_of_trend":"Rate Development/Months of Trend",'
             '"target_loss_ratio":"Rate Development/Target Loss Ratio",'
             '"manual_rating_pool_increase":"Rate Development/Manual Rating Pool Increase",'
             '"credibility_experience_weight":"Rate Development/blend block"}')
run(f"""INSERT INTO {FQ}.`0_carrier_template` VALUES
  ('Meridian Assurance','v1','renewal_exhibit',
   array('Renewal Summary','Claims Experience','High Cost Claimants','Rate Development','Benefits Overview','Detailed Rates'),
   '{FIELD_MAP}', 17, 'active'),
  ('Meridian Assurance','v1','monthly_claims',
   array('Claims Experience'),
   '{{"month":"Claims Experience/Month","total_incurred":"Claims Experience/Total Incurred","med_members":"Claims Experience/Covered Members"}}',
   3, 'active')""", "seed templates")

# ------------------------------------------------------------ governed method
FN = f"{FQ}.fn_renewal_action"
run(f"""CREATE OR REPLACE FUNCTION {FN}(
  member_months DOUBLE, total_incurred_claims DOUBLE, months_experience DOUBLE,
  current_members DOUBLE, current_total_premium_monthly DOUBLE,
  demographic_adjustment DOUBLE, less_pooled_claims_pmpm DOUBLE, benefit_change DOUBLE,
  annual_trend DOUBLE, months_of_trend DOUBLE, projected_excess_claims_pmpm DOUBLE,
  large_claim_add_back_pmpm DOUBLE, target_loss_ratio DOUBLE, benefit_advisor_fee DOUBLE,
  manual_rating_pool_increase DOUBLE, credibility_experience_weight DOUBLE,
  credibility_manual_weight DOUBLE, adjustment DOUBLE)
RETURNS DOUBLE LANGUAGE PYTHON
COMMENT '[hb-renewal] The fully-insured medical renewal build-up as a governed, versioned method. Returns the quoted change in billed premium (credibility-weighted blended action + broker adjustment). Reproduces a reference carrier exhibit to 8dp. Same inputs + same version = same answer, in an audit.'
AS $$
  incurred_pmpm = total_incurred_claims / member_months
  adjusted = incurred_pmpm * demographic_adjustment
  experience_claim_cost = adjusted - less_pooled_claims_pmpm
  effective_trend = (1 + annual_trend) ** (months_of_trend / 12.0) - 1
  projected_medical = (experience_claim_cost * benefit_change * (1 + effective_trend)
                       + projected_excess_claims_pmpm + large_claim_add_back_pmpm)
  experience_premium = projected_medical / target_loss_ratio * (1 + benefit_advisor_fee)
  current_premium_pmpm = current_total_premium_monthly / current_members
  experience_increase = experience_premium / current_premium_pmpm - 1
  blended = (credibility_experience_weight * experience_increase
             + credibility_manual_weight * manual_rating_pool_increase)
  return blended + adjustment
$$""", "fn_renewal_action")

run(f"""CREATE OR REPLACE FUNCTION {FQ}.fn_effective_trend(annual_trend DOUBLE, months DOUBLE)
RETURNS DOUBLE LANGUAGE PYTHON
COMMENT '[hb-renewal] Effective (compounded) trend over the projection period.'
AS $$
  return (1 + annual_trend) ** (months / 12.0) - 1
$$""", "fn_effective_trend")

# Full build-up as a governed function returning every exhibit line as JSON — so
# the app renders the exhibit and recomputes levers with NO math in the container.
run(("""CREATE OR REPLACE FUNCTION __FQ__.fn_renewal_buildup(
  member_months DOUBLE, total_incurred_claims DOUBLE, months_experience DOUBLE,
  current_members DOUBLE, current_total_premium_monthly DOUBLE,
  demographic_adjustment DOUBLE, less_pooled_claims_pmpm DOUBLE, benefit_change DOUBLE,
  annual_trend DOUBLE, months_of_trend DOUBLE, projected_excess_claims_pmpm DOUBLE,
  large_claim_add_back_pmpm DOUBLE, target_loss_ratio DOUBLE, benefit_advisor_fee DOUBLE,
  manual_rating_pool_increase DOUBLE, credibility_experience_weight DOUBLE,
  credibility_manual_weight DOUBLE, adjustment DOUBLE)
RETURNS STRING LANGUAGE PYTHON
COMMENT '[hb-renewal] The full renewal build-up (every exhibit line) as a JSON object. Single governed compute path for the app exhibit and lever recompute — no renewal math runs in the app container.'
AS $$
  import json
  incurred_pmpm = total_incurred_claims / member_months
  adjusted = incurred_pmpm * demographic_adjustment
  experience_claim_cost = adjusted - less_pooled_claims_pmpm
  effective_trend = (1 + annual_trend) ** (months_of_trend / 12.0) - 1
  projected_medical = (experience_claim_cost * benefit_change * (1 + effective_trend)
                       + projected_excess_claims_pmpm + large_claim_add_back_pmpm)
  experience_premium = projected_medical / target_loss_ratio * (1 + benefit_advisor_fee)
  current_premium_pmpm = current_total_premium_monthly / current_members
  experience_increase = experience_premium / current_premium_pmpm - 1
  blended = (credibility_experience_weight * experience_increase
             + credibility_manual_weight * manual_rating_pool_increase)
  quoted = blended + adjustment
  return json.dumps({
    "member_months": member_months, "incurred_pmpm": incurred_pmpm,
    "demographic_adjustment": demographic_adjustment, "adjusted_incurred_pmpm": adjusted,
    "less_pooled_claims_pmpm": less_pooled_claims_pmpm, "experience_claim_cost_pmpm": experience_claim_cost,
    "benefit_change": benefit_change, "annual_trend": annual_trend, "months_of_trend": months_of_trend,
    "effective_trend": effective_trend, "projected_excess_claims_pmpm": projected_excess_claims_pmpm,
    "large_claim_add_back_pmpm": large_claim_add_back_pmpm, "projected_medical_pmpm": projected_medical,
    "target_loss_ratio": target_loss_ratio, "benefit_advisor_fee": benefit_advisor_fee,
    "experience_based_premium_pmpm": experience_premium, "current_premium_pmpm": current_premium_pmpm,
    "experience_based_increase": experience_increase, "manual_rating_pool_increase": manual_rating_pool_increase,
    "credibility_experience_weight": credibility_experience_weight, "credibility_manual_weight": credibility_manual_weight,
    "blended_rate_action": blended, "adjustment": adjustment, "quoted_change": quoted,
    "current_members": current_members,
    "projected_billed_premium_annual": current_premium_pmpm * (1 + quoted) * current_members * 12,
    "current_billed_premium_annual": current_premium_pmpm * current_members * 12,
  })
$$""").replace("__FQ__", FQ), "fn_renewal_buildup")

# --------------------------------------------------------- latest-only views
for t in ("1_incurred_claims", "1_large_claims", "1_detailed_rates", "2_renewal_inputs"):
    run(f"""CREATE OR REPLACE VIEW {FQ}.`v_{t}_latest`
COMMENT '[hb-renewal] {t} restricted to rows from currently ACTIVE source documents. All downstream reads use the *_latest views.'
AS SELECT t.* FROM {FQ}.`{t}` t
   JOIN {FQ}.`1_source_document` d ON d.doc_id = t.source_document_id
   WHERE d.status = 'active'""", f"v_{t}_latest")

run(f"""CREATE OR REPLACE VIEW {FQ}.`v_source_document_latest`
COMMENT '[hb-renewal] Source documents excluding superseded ones (active, quarantined, differs).'
AS SELECT * FROM {FQ}.`1_source_document` WHERE status <> 'superseded'""", "v_source_document_latest")

# ------------------------------------------------ accumulation benchmark view
run(f"""CREATE OR REPLACE VIEW {FQ}.`6_book_trend_benchmark`
COMMENT '[hb-renewal] Book trend benchmark DERIVED from retained renewal decisions (5_scenario) — what our own book says trend is, by carrier and group-size band. Not a licensed input. Lineage: view -> 5_scenario -> 1_source_document -> the carrier file.'
AS
SELECT carrier,
       get_json_object(overrides,'$.group_band')                                          AS group_band,
       count(*)                                                                           AS renewals_negotiated,
       round(avg(cast(get_json_object(overrides,'$.annual_trend') AS DOUBLE)),4)          AS book_trend_avg,
       round(percentile_approx(cast(get_json_object(overrides,'$.annual_trend') AS DOUBLE),0.5),4) AS book_trend_median,
       round(avg(baseline_action),4)                                                      AS avg_carrier_action,
       round(avg(scenario_action),4)                                                      AS avg_negotiated_action,
       round(avg(baseline_action) - avg(scenario_action),4)                               AS avg_negotiation_delta,
       round(sum(value_at_stake_annual),0)                                                AS total_value_negotiated
FROM {FQ}.`5_scenario`
WHERE status IN ('saved','approved')
GROUP BY carrier, get_json_object(overrides,'$.group_band')""", "6_book_trend_benchmark")

# ------------------------------------------ consumption views (Genie + AI/BI)
# Plain SQL views over the governed layer, consumed by the Genie space and the
# Lakeview dashboard. Named mv_* for "model/consumption view"; NOT UC metric
# views (promotion to formal metric views is on the roadmap). Created here so a
# clean rebuild reproduces the full deployed schema (was previously ad-hoc).
run(f"""CREATE OR REPLACE VIEW {FQ}.mv_renewal_actions
COMMENT '[hb-renewal] Renewal actions by carrier / band / period, for Genie & analytics. Carrier vs negotiated action and value at stake, from retained decisions.'
AS SELECT s.carrier, get_json_object(s.overrides,'$.group_band') AS group_band, d.policy_period,
     count(*) AS renewals, round(avg(s.baseline_action),4) AS avg_carrier_action,
     round(avg(s.scenario_action),4) AS avg_negotiated_action,
     round(sum(s.value_at_stake_annual),0) AS total_value_at_stake
   FROM {FQ}.`5_scenario` s JOIN {FQ}.`1_source_document` d ON d.doc_id = s.source_document_id
   GROUP BY s.carrier, get_json_object(s.overrides,'$.group_band'), d.policy_period""", "mv_renewal_actions")

run(f"""CREATE OR REPLACE VIEW {FQ}.mv_claims_experience
COMMENT '[hb-renewal] Monthly claims experience (PMPM, members) by carrier/group, for Genie & analytics.'
AS SELECT c.carrier, c.employer_group, c.month, c.total_incurred, c.med_members,
     round(c.total_incurred / nullif(c.med_members,0),2) AS pmpm
   FROM {FQ}.`v_1_incurred_claims_latest` c""", "mv_claims_experience")

print("schema build complete.")
