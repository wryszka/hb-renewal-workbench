"""Local regression: the governed method must reproduce the reference carrier
exhibit's blended renewal action to 4 decimal places.

Runs offline against data/reference_exhibit.json (gitignored, local only — the
sanitised reference used purely to prove the math is faithful). Skips cleanly if
the reference is absent (e.g. a fresh clone), so it never blocks a deploy.

    uv run --native-tls --with pytest pytest -q
"""
from __future__ import annotations
import json, sys, pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
from renewal_engine import RenewalInputs, compute_renewal  # noqa: E402

REF = ROOT / "data" / "reference_exhibit.json"
EXPECTED_BLENDED = 0.3906  # the reference exhibit's blended renewal action


def _inputs_from_reference():
    d = json.loads(REF.read_text())
    ri = d["renewal_inputs"]
    member_months = sum(m["med_members"] for m in d["incurred_claims"])
    total_incurred = sum(m["total_incurred"] for m in d["incurred_claims"])
    current_premium_monthly = sum(r["rate"] * r["subs"] for r in d["detailed_rates"] if r["kind"] == "current")
    return RenewalInputs(
        member_months=member_months, total_incurred_claims=total_incurred,
        months_experience=ri["months_experience"], current_members=ri["current_members"],
        current_total_premium_monthly=current_premium_monthly,
        demographic_adjustment=ri["demographic_adjustment"], less_pooled_claims_pmpm=ri["less_pooled_claims_pmpm"],
        benefit_change=ri["benefit_change"], annual_trend=ri["annual_trend"], months_of_trend=ri["months_of_trend"],
        individual_pooling_point=ri["individual_pooling_point"], projected_excess_claims_pmpm=ri["projected_excess_claims_pmpm"],
        large_claim_add_back_pmpm=ri["large_claim_add_back_pmpm"], target_loss_ratio=ri["target_loss_ratio"],
        benefit_advisor_fee=ri["benefit_advisor_fee"], manual_rating_pool_increase=ri["manual_rating_pool_increase"],
        credibility_experience_weight=ri["credibility_experience_weight"],
        credibility_manual_weight=ri["credibility_manual_weight"], adjustment=ri["adjustment"])


@pytest.mark.skipif(not REF.exists(), reason="reference exhibit not present (local-only)")
def test_reproduces_reference_exhibit_to_4dp():
    res = compute_renewal(_inputs_from_reference())
    assert round(res.blended_rate_action, 4) == round(EXPECTED_BLENDED, 4), \
        f"blended {res.blended_rate_action:.6f} != reference {EXPECTED_BLENDED}"


@pytest.mark.skipif(not REF.exists(), reason="reference exhibit not present (local-only)")
def test_member_months_and_total_tie_out():
    d = json.loads(REF.read_text())
    assert sum(m["med_members"] for m in d["incurred_claims"]) == 3888
