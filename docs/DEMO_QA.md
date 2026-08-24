# Demo Q&A — presenter answers

Persona-grouped. Each item: **Q** (as they'd phrase it) / **A** (honest, no hedging; roadmap = "V2" plainly) / **→ show** (the beat that demonstrates it — prefer "click here and show them" over explaining). Run-sheet IF-ASKED lines point to these numbers. Numbers are the real seeded-book figures. All data synthetic.

---

## The actuary / underwriter (hands-on)

**1. Where do the benchmark numbers come from?**
A: Your own retained deals, derived live — not hardcoded, not bought. Each row traces to its scenarios.
→ show: beat 7 (Benchmarks); click a row's lineage.

**2. Can you recreate the carrier's manual rate?**
A: No, and we don't pretend — it's locked as carrier-provided. Everything else is challengeable.
→ show: beat 4/5 (the 🔒 on Manual pool increase).

**3. What if the carrier changes their layout?**
A: The pipeline quarantines it, shows the field diff, a human confirms once. Never silent guessing.
→ show: beat 3 (drop the broken file).

**4. Each carrier's math is different — how many did you build?**
A: One, config-driven. Each new carrier is a template entry, not a rebuild.
→ show: beat 2 (carrier template registry) / Learn node 2.

**5. Self-funded scenarios?**
A: Built and governed — the same experience priced self-funded (carrier premium vs expected cost vs max liability) by a UC function, saved as an FI/SF decision. It's behind a flag, off today, until we set the stop-loss and admin numbers with you.
→ show: Roadmap panel (flag-gated item); can be switched on for a follow-up.

**6. How do we know the extraction is right?**
A: Two independent paths must agree, field by field — **17/17** on this file. Disagreement = quarantine.
→ show: beat 2 (the two-path reconciliation drill-down).

**7. Can I still use Excel?**
A: Yes — download the original any time; uploads come back stamped and audited. Excel becomes an interface, not the system.
→ show: beat 11 (Audit → Download original).

**8. What feeds the trend benchmarks — how many renewals until it's credible?**
A: Every saved deal. Credibility grows with the book; today's demo book is **50** synthetic renewals.
→ show: beat 7 (Benchmarks).

---

## The data / platform person

**9. Is the math in the app?**
A: No — the number of record is one versioned governed function that app, notebook and agent all call. (The live slider preview is client-side, reconciled to the function on save.)
→ show: beat 4 / Learn node 3 (lineage → function).

**10. What happens when someone resubmits a file?**
A: New version supersedes, old retained, every read resolves to latest. Nothing overwritten, ever.
→ show: beat 6 (reforecast) / supersession.

**11. Access control?**
A: Standard Unity Catalog grants on every object — no app-side permissions layer to maintain.
→ show: behind-the-scenes panel (open any object in Catalog Explorer).

**12. What did this take to build?**
A: ~Three weeks, one person, standard platform primitives. It's a pattern, not a product.
→ show: verbal (Learn node captions).

**13. Can agents write?**
A: Advise only. Findings and summaries; humans save decisions. Autonomy would be policy config, server-side.
→ show: beat 8 (Agents advise; Save is human).

**14. What breaks if we lift this to our workspace?**
A: One catalog variable. Serverless + Unity Catalog is the only requirement.
→ show: verbal (databricks.yml catalog var).

---

## The exec / sponsor

**15. Is this a product you sell?**
A: No — a working example on your workflow. You'd own and extend it; we show the pattern.
→ show: beat 0 / 12 (framing + finale).

**16. What's the value?**
A: Negotiation deltas visible per carrier; on the demo book, **$183k/yr** on one deal from one challenged assumption.
→ show: beat 5 (save the trend scenario) / beat 7.

**17. Why can't we do this in our current stack?**
A: You can do pieces. What compounds is one governed spine: same data, method, record — for people and agents.
→ show: beat 12 (finale).

**18. What would production take?**
A: Carrier templates, your benchmarks seeded, access model, an approval workflow. Weeks per increment, not a program.
→ show: roadmap (`ROADMAP.md`).

**19. Where does AI fit — is it deciding?**
A: No. It reads, flags, and drafts; every decision is a named human with a reason on record.
→ show: beat 8 (Agents) + beat 5 (named save with reason).
