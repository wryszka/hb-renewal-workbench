"""H&B fully-insured renewal engine.

Reproduces a fully-insured medical renewal build-up exactly, exposed as a pure
function so the app can recompute live as a broker overwrites assumptions
(the negotiation "what-if" levers). See docs/METHOD_SPEC.md for the line-by-line map.

Everything is computed on a PMPM basis and annualized at the end.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, replace


@dataclass
class RenewalInputs:
    # --- experience (from Incurred/Large Claims) ---
    member_months: float            # Incurred Claims total member-months
    total_incurred_claims: float    # Incurred Claims total $ (all months)
    months_experience: int
    current_members: int
    # --- current premium (from Detailed Rates) ---
    current_total_premium_monthly: float  # sum of current tier premiums / month
    # --- levers a broker overwrites ---
    demographic_adjustment: float   # age/sex factor
    less_pooled_claims_pmpm: float  # claims above pooling point removed
    benefit_change: float           # plan-design change factor
    annual_trend: float             # medical+rx trend, annual
    months_of_trend: float          # midpoint-to-midpoint months
    individual_pooling_point: float
    projected_excess_claims_pmpm: float  # projected claims > pooling point
    large_claim_add_back_pmpm: float
    target_loss_ratio: float
    benefit_advisor_fee: float
    manual_rating_pool_increase: float   # carrier manual/book increase
    credibility_experience_weight: float
    credibility_manual_weight: float
    adjustment: float = 0.0              # broker override on final action


@dataclass
class RenewalResult:
    incurred_pmpm: float
    adjusted_incurred_pmpm: float
    experience_claim_cost_pmpm: float
    effective_trend: float
    projected_medical_pmpm: float
    avg_members_experience: float
    annualized_projected_cost: float
    experience_based_premium_pmpm: float
    current_premium_pmpm: float
    experience_based_increase: float
    manual_increase: float
    blended_rate_action: float
    quoted_change: float
    projected_billed_premium_pmpm: float
    projected_billed_premium_annual: float

    def as_dict(self):
        return asdict(self)


def compute_renewal(i: RenewalInputs) -> RenewalResult:
    incurred_pmpm = i.total_incurred_claims / i.member_months
    adjusted_incurred_pmpm = incurred_pmpm * i.demographic_adjustment
    experience_claim_cost = adjusted_incurred_pmpm - i.less_pooled_claims_pmpm

    effective_trend = (1 + i.annual_trend) ** (i.months_of_trend / 12) - 1
    projected_medical_pmpm = (
        experience_claim_cost * i.benefit_change * (1 + effective_trend)
        + i.projected_excess_claims_pmpm
        + i.large_claim_add_back_pmpm
    )

    avg_members = i.member_months / i.months_experience
    annualized_projected_cost = projected_medical_pmpm * i.current_members * 12

    experience_based_premium = (
        projected_medical_pmpm / i.target_loss_ratio * (1 + i.benefit_advisor_fee)
    )
    current_premium_pmpm = i.current_total_premium_monthly / i.current_members
    experience_based_increase = experience_based_premium / current_premium_pmpm - 1

    blended = (
        i.credibility_experience_weight * experience_based_increase
        + i.credibility_manual_weight * i.manual_rating_pool_increase
    )
    quoted_change = blended + i.adjustment
    projected_billed_pmpm = current_premium_pmpm * (1 + quoted_change)

    return RenewalResult(
        incurred_pmpm=incurred_pmpm,
        adjusted_incurred_pmpm=adjusted_incurred_pmpm,
        experience_claim_cost_pmpm=experience_claim_cost,
        effective_trend=effective_trend,
        projected_medical_pmpm=projected_medical_pmpm,
        avg_members_experience=avg_members,
        annualized_projected_cost=annualized_projected_cost,
        experience_based_premium_pmpm=experience_based_premium,
        current_premium_pmpm=current_premium_pmpm,
        experience_based_increase=experience_based_increase,
        manual_increase=i.manual_rating_pool_increase,
        blended_rate_action=blended,
        quoted_change=quoted_change,
        projected_billed_premium_pmpm=projected_billed_pmpm,
        projected_billed_premium_annual=projected_billed_pmpm * i.current_members * 12,
    )


def scenario(base: RenewalInputs, **overrides) -> RenewalResult:
    """Recompute with one or more levers overwritten (the what-if action)."""
    return compute_renewal(replace(base, **overrides))
