"""Local offline test for the self-funded projection (WP1).

Proves compute_self_funded prices the group self-funded consistently against the
fully-insured build-up, and locks the payoff arithmetic. The governed UC function
fn_selffunded_projection embeds the identical formula (see data/build_schema.py);
this test guards the reference logic without needing a live warehouse.

    uv run --native-tls --with pytest pytest -q
"""
from __future__ import annotations
import sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "data"))
from renewal_engine import RenewalInputs, compute_renewal  # noqa: E402
from selffunded import SelfFundedInputs, compute_self_funded  # noqa: E402
import make_carrier_file as mcf  # noqa: E402


def _fi():
    b = mcf.BASE
    inp = RenewalInputs(
        member_months=b["member_months"], total_incurred_claims=b["total_incurred_annual"],
        months_experience=b["months_experience"], current_members=b["current_members"],
        current_total_premium_monthly=b["current_premium_pmpm"] * b["current_members"],
        demographic_adjustment=b["demographic_adj"], less_pooled_claims_pmpm=b["pooled_credit_pmpm"],
        benefit_change=b["benefit_change"], annual_trend=b["annual_trend"], months_of_trend=b["months_of_trend"],
        individual_pooling_point=b["pooling_point"], projected_excess_claims_pmpm=b["excess_pmpm"],
        large_claim_add_back_pmpm=b["add_back_pmpm"], target_loss_ratio=b["target_lr"],
        benefit_advisor_fee=b["advisor_fee"], manual_rating_pool_increase=b["manual_increase"],
        credibility_experience_weight=b["experience_weight"],
        credibility_manual_weight=round(1 - b["experience_weight"], 4))
    return inp, compute_renewal(inp)


def _sf(inp, fi, sf):
    return compute_self_funded(fi, sf, current_members=int(inp.current_members),
                               fi_pooled_credit_pmpm=inp.less_pooled_claims_pmpm,
                               fi_excess_pmpm=inp.projected_excess_claims_pmpm)


def test_payoff_identities():
    inp, fi = _fi()
    r = _sf(inp, fi, SelfFundedInputs())
    # total self-funded = expected retained claims + ISL + ASL + fixed
    assert round(r.total_self_funded_pmpm, 6) == round(
        r.expected_retained_claims_pmpm + r.isl_premium_pmpm + r.asl_premium_pmpm + r.fixed_costs_pmpm, 6)
    # saving = fully-insured - self-funded; annualisation is members * 12
    assert round(r.saving_pmpm, 6) == round(r.fully_insured_pmpm - r.total_self_funded_pmpm, 6)
    assert round(r.annual_saving, 4) == round(r.saving_pmpm * inp.current_members * 12, 4)
    # max liability (aggregate stop-loss cap) is strictly worse than the expected cost
    assert r.max_liability_pmpm > r.total_self_funded_pmpm
    # the fully-insured side ties to the FI build-up's billed premium PMPM
    assert round(r.fully_insured_pmpm, 6) == round(fi.projected_billed_premium_pmpm, 6)


def test_uc_formula_matches_python():
    # re-implement the fn_selffunded_projection body inline; it must equal compute_self_funded
    inp, fi = _fi()
    sf = SelfFundedInputs()
    expected_retained = max(fi.projected_medical_pmpm - inp.projected_excess_claims_pmpm - sf.expected_claims_credit, 0.0)
    fixed = sf.aso_fee_pmpm + sf.network_access_pmpm + sf.advisor_fee_pmpm
    total_sf = expected_retained + sf.isl_premium_pmpm + sf.asl_premium_pmpm + fixed
    r = _sf(inp, fi, sf)
    assert round(expected_retained, 8) == round(r.expected_retained_claims_pmpm, 8)
    assert round(total_sf, 8) == round(r.total_self_funded_pmpm, 8)


def test_credit_reduces_retained_claims():
    inp, fi = _fi()
    base = _sf(inp, fi, SelfFundedInputs())
    with_credit = _sf(inp, fi, SelfFundedInputs(expected_claims_credit=25.0))
    assert with_credit.expected_retained_claims_pmpm == base.expected_retained_claims_pmpm - 25.0
    assert with_credit.total_self_funded_pmpm < base.total_self_funded_pmpm
