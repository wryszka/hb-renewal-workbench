# Method spec — fully-insured medical renewal build-up

Generic specification of the renewal method reproduced by `fn_renewal_buildup` /
`fn_renewal_action`. Derived from a **reference carrier exhibit** (a fully-insured medical
renewal illustration). All figures used in the demo are synthetic.

A carrier exhibit typically carries 4–5 tabs — a cover, monthly **claims experience**, **high-cost
claimants**, and the **rate development** build-up — flowing:
**claims experience + large claims + rates → rate development → blended renewal action.**

## Rate development (PMPM basis, annualised at the end)

| Line | Formula |
|---|---|
| Member months | experience total member-months |
| Incurred claims PMPM | total incurred claims / member months |
| Adjusted incurred PMPM | incurred PMPM × demographic adjustment |
| Experience claim cost | adjusted − less pooled claims (claims above the pooling point removed) |
| Effective trend | (1 + annual trend) ^ (months of trend / 12) − 1 |
| Projected medical PMPM | experience claim cost × benefit change × (1 + effective trend) + projected excess + large-claim add-back |
| Experience-based premium | projected medical / target loss ratio × (1 + advisor fee) |
| Current premium PMPM | current total premium / current members |
| Experience-based increase | experience premium / current premium − 1 |
| Manual pool increase | carrier-provided manual/book rate (opaque, treated as an input) |

## Blend (credibility-weighted)
`blended action = experience_weight × experience_increase + manual_weight × manual_increase`
(weights sum to 1, credibility Z by group size). `quoted change = blended + broker adjustment`.
Projected billed premium = current premium × (1 + quoted change).

## Negotiation levers
demographic adjustment · pooled-claims credit · benefit change · **annual trend** · months of trend ·
pooling point · projected excess / add-back · target loss ratio · **credibility weights** ·
broker adjustment. **Manual pool increase is carrier-provided and rendered locked.**

## Fidelity
`fn_renewal_buildup` reproduces the reference exhibit's stated blended action **to 8 decimal places**;
the local regression test (`tests/test_regression.py`) asserts reproduction to 4 dp against the
(local, gitignored) reference. The method is illustrative — the intent is to show a governed,
reproducible workflow, not to certify a rate selection.
