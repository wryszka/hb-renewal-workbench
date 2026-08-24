"""Fully insured -> self-funded transition scenario.

A common broker ask: take the same experience and enrolment, but price
the group as self-funded — expected claims retained by the employer up to an
individual stop-loss point, with ISL premium bought from the stop-loss market
instead of the carrier's fully-insured pooling charge, plus ASO/admin fees.

The worked example uses a $115,000 individual stop-loss level, and an input
assumption for the ISL premium is fine for a first version — so that is exactly
how this is built: an assumption, clearly labelled.

The comparison is deliberately like-for-like: both sides start from the same
projected claim cost that the fully-insured build-up produces.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict

from renewal_engine import RenewalResult


@dataclass
class SelfFundedInputs:
    # Individual stop-loss (ISL)
    isl_point: float = 115_000.0        # example level
    isl_premium_pmpm: float = 82.50     # assumption — quote from the SL market
    # Aggregate stop-loss (ASL)
    asl_corridor: float = 1.25          # attachment as a multiple of expected
    asl_premium_pmpm: float = 9.00      # assumption
    # Administration
    aso_fee_pmpm: float = 48.00         # carrier/TPA admin (ASO)
    network_access_pmpm: float = 6.50
    # Other
    advisor_fee_pmpm: float = 0.0       # set from the FI advisor fee if desired
    expected_claims_credit: float = 0.0  # manual adjustment to expected claims
    # What the employer keeps rather than pays as premium
    margin_release: float = 0.0          # risk/profit margin no longer paid


@dataclass
class SelfFundedResult:
    expected_retained_claims_pmpm: float
    isl_premium_pmpm: float
    asl_premium_pmpm: float
    fixed_costs_pmpm: float
    total_self_funded_pmpm: float
    fully_insured_pmpm: float
    saving_pmpm: float
    saving_pct: float
    annual_saving: float
    total_self_funded_annual: float
    fully_insured_annual: float
    asl_attachment_pmpm: float
    max_liability_pmpm: float
    max_liability_annual: float
    worst_case_vs_fi_pct: float

    def as_dict(self):
        return asdict(self)


def compute_self_funded(
    fi: RenewalResult,
    sf: SelfFundedInputs,
    current_members: int,
    fi_pooled_credit_pmpm: float,
    fi_excess_pmpm: float,
) -> SelfFundedResult:
    """Price the group self-funded against the fully-insured quote.

    Expected retained claims start from the fully-insured *projected* claim
    cost, then add back the pooled/excess elements the FI rate removed and
    charged for separately — because under self-funding the employer retains
    claims below the ISL point and buys ISL cover for the rest.
    """
    # Projected claims under FI already exclude claims above the pooling point
    # (they were removed, then charged back as projected excess + add-back).
    # Self-funded expected claims = projected cost less the excess element,
    # since that layer is now covered by ISL premium instead.
    expected_retained = (
        fi.projected_medical_pmpm - fi_excess_pmpm - sf.expected_claims_credit
    )
    expected_retained = max(expected_retained, 0.0)

    fixed_costs = (
        sf.aso_fee_pmpm + sf.network_access_pmpm + sf.advisor_fee_pmpm
    )

    total_sf = (
        expected_retained + sf.isl_premium_pmpm + sf.asl_premium_pmpm + fixed_costs
    )

    # Fully insured cost of risk = the quoted premium & fees
    fi_pmpm = fi.projected_billed_premium_pmpm

    saving = fi_pmpm - total_sf
    saving_pct = saving / fi_pmpm if fi_pmpm else 0.0

    # Worst case: aggregate stop-loss caps retained claims at the corridor
    asl_attachment = expected_retained * sf.asl_corridor
    max_liability = (
        asl_attachment + sf.isl_premium_pmpm + sf.asl_premium_pmpm + fixed_costs
    )

    return SelfFundedResult(
        expected_retained_claims_pmpm=expected_retained,
        isl_premium_pmpm=sf.isl_premium_pmpm,
        asl_premium_pmpm=sf.asl_premium_pmpm,
        fixed_costs_pmpm=fixed_costs,
        total_self_funded_pmpm=total_sf,
        fully_insured_pmpm=fi_pmpm,
        saving_pmpm=saving,
        saving_pct=saving_pct,
        annual_saving=saving * current_members * 12,
        total_self_funded_annual=total_sf * current_members * 12,
        fully_insured_annual=fi_pmpm * current_members * 12,
        asl_attachment_pmpm=asl_attachment,
        max_liability_pmpm=max_liability,
        max_liability_annual=max_liability * current_members * 12,
        worst_case_vs_fi_pct=(max_liability / fi_pmpm - 1) if fi_pmpm else 0.0,
    )


SF_LEVERS = [
    "isl_point", "isl_premium_pmpm", "asl_corridor", "asl_premium_pmpm",
    "aso_fee_pmpm", "network_access_pmpm", "advisor_fee_pmpm",
    "expected_claims_credit",
]
