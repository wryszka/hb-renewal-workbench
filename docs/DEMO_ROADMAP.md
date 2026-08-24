# Roadmap — lined up for delivery

Everything in the workbench today is built and live. The items below are **specced or planned — not yet built** — shown for direction (this is the "what's next" a sponsor/actuary asks for). All data in the demo is synthetic; timelines are per-increment (weeks), not a program.

## Next up — specced, not yet built

- **Self-funded scenario path.** Model the fully-insured → self-funded transition on the same experience base — individual stop-loss level, stop-loss premium, admin fees — showing the carrier's renewal premium vs expected self-funded cost vs maximum liability, side by side. Same governed method, same decision record.
- **Quarantine → resolution ("confirm once").** When a carrier changes their layout: review the field diff, accept the proposed re-map, and the carrier template learns a new version so the same file re-processes clean — or reject with a reason. Both audited. The control story, end to end.
- **Changed-file version diff.** When a carrier resubmits: see v1 → v2 field-by-field and the money impact (the ask moves e.g. 26.9% → 24.1%). Decisions built on the old version get a "data has moved" flag with one-click recompute — and reforecast gets its explicit old-vs-new.

## Also on the roadmap

- **V2** — Pharmacy-rebate document family: a second exhibit type through the same pipeline (a parser + a binding, not a rebuild).
- **V2** — New-carrier onboarding UI: confirm a template from a first file, no code.
- **V2** — Real book benchmarks as volume accumulates; promote the consumption views to formal governed metric views.
- **V2** — One-command full-build orchestrator Job; a closed synthetic loop to roll the book forward a period.
- **V3** — ML risk scoring: is a deal above or below the mark, given the book.
- **V3** — Agentic distribution: an account exec pings an agent; the governed method answers, human-in-the-loop.
- **V3** — Cross-line / cross-entity sharing, governed via Unity Catalog / Delta Sharing.

_Shown in-app under the **Roadmap** tab (bottom of the sidebar)._
