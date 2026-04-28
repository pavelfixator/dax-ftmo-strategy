# Lesson Learned — v3.3.2.1

**Datum:** 2026-04-28
**Trigger:** post-extended-ablation analysis → v3.3.1 spec partially based on
statistical noise (F1 mandatory CRASH).

---

## #1 — Sample minimum 100 trades for design decisions

**Context:** v3.3.1 spec marked "F1 mandatory v US-MOM CRASH" based on Iter2b
ablation (1-week sample, drop_F1 = 36 trades, 33% WR, max DD -3 484). Wilson CI
on n=36 = ±42pp wide (true WR 11-55%). Architekt interpreted as "F1 is crash
protection". Red Team (kolo 1/3) explicitly warned about CI width.

**Empirical refutation:** Extended ablation (11 yrs, n=182 in same cell) shows
drop_F1 us_momentum CRASH = WR 0.53, +44.8 exp, FDR sig, OOS pass. **Top winner
of entire 44-cell experiment.**

**Rule:** No specific design decision (filter mandatory/optional, threshold value,
regime gate) on cell sample size <100 trades. Procedural rules ("require 100+ in
ablation") accepted in v3.3.1 process but were not applied to specific decisions.

**Application:** Sample size flag (PRIMARY/WARNING/REJECT) is gating, not advisory.
REJECT cells contribute zero design weight. WARNING cells flagged for re-eval.

---

## #2 — No multi-candidate frameworks without prior evidence

**Context:** F5 framework defined 8 candidates (4 ORB-CRASH + 4 US-CALM) as
"Exp #12" placeholder, assuming at least one would emerge as winner. No priori
mechanistic justification why any specific candidate would beat baseline.

**Empirical refutation:** 0/8 F5 candidates passed FDR + OOS + sample size.
Framework was hypothesis without minimal viable evidence. 8 cells of compute
(~2h within 11h ablation) consumed for null result.

**Rule:** Multi-candidate framework requires at least 1 priori reason per
candidate why it might work (mechanistic, academic, or empirical from prior
test). "We have 4 alternatives, one might win" is wishful thinking.

**Application:** Filter Budget Rule exception accepted: 3-4 filters per regime
maximum. Future F-frameworks must specify candidate hypothesis upfront.

---

## #3 — Empirical primacy (data > intuition)

**Context:** v3.3.1 hypothesized TREND ~40% of CET trading days based on
"general market distribution". Empirical reality from 11-year regime classifier
output: TREND = 26.2 % (756/2 888 days).

**Empirical refutation:** 14pp delta vs hypothesis. Cascading consequence: spec
prioritized TREND as "primary regime" → us_momentum TREND filter set was first
priority in design. Real data shows CRASH and CALM produce stronger edges.

**Rule:** When data contradicts hypothesis, accept data and rewrite hypothesis.
Do NOT rationalize hypothesis to fit data ("market changed", "this period
unusual"). 11 years is sufficient to refute.

**Application:** v3.3.2 prioritized empirically validated cells (us_momentum
CRASH drop_F1 = top winner, orb_dax CALM drop_F3 = #2). TREND retained but
with reduced expectations (stable contributor, not primary edge).

---

## #4 — Multiple comparisons hygiene (FDR / Bonferroni for N > 5)

**Context:** Initial Iter1/Iter2 reports applied no multiple comparisons
correction. With 6 configs × 3 regimes × 2 setups = 36+ cells tested simultaneously,
naive p<0.05 produces ~2 false positives at random.

**Implementation:** v3.3.1 ablation infra mandates Benjamini-Hochberg (FDR) +
Bonferroni secondary check. Acceptance = ≥+10% expectancy boost AND p < FDR-
adjusted alpha.

**Empirical evidence:** 7 cells passed naive p<0.05; only 4 passed FDR; only 3
also passed OOS validation. Without FDR, would have adopted false-positive cells.

**Rule:** FDR mandatory for any analysis with N > 5 simultaneous comparisons.
Bonferroni as secondary stricter check (use sparingly — overly conservative
in correlated tests).

---

## #5 — META: Numerical verification mandatory

**Context:** Spec drafts contained inferred numerical claims ("approximately 40%",
"around 100 trades", "~15% UNDEFINED"). When ablation produced empirical numbers,
some delta vs claims was significant (TREND 26 % vs 40 %, UNDEFINED 65 % vs 15 %).

**Rule:** Every numerical claim in spec must be either:
  (a) explicitly marked as hypothesis pending empirical verification, OR
  (b) backed by referenced source (commit hash, dataset, study)

**Application:** v3.3.2.1 spec contains no inferred numbers — all sample sizes,
WR, expectancy values cite `master_table.csv` rows. Prior rounds' "estimates"
labeled "(TBD)" until empirically verified.

---

## Process improvements applied to v3.3.2.1

1. Extended ablation (11 years, FDR + OOS + bootstrap) ran BEFORE spec drafting.
2. Spec changes are 100% data-driven (filter sets per regime from master_table top cells).
3. 12-round adversarial cycle (3 cycles × 4 rounds avg) before implementation.
4. Asymmetric gate criteria (US-MOM ≥500, ORB-DAX CALM ≥100) based on per-setup sample availability.
5. F5 framework dropped (zero successful candidates), accepted Filter Budget exception.
6. UNDEFINED 65% accepted (not bug, security mechanism); ~525 trades/year still meets gate #1.

---

## Implications for future projects

- **Two-stage spec process:** (a) hypothesis spec + ablation plan, (b) data-driven spec.
  Skip stage (b) only if hypothesis stage already meets sample/significance criteria.
- **No "framework-creep":** if 0/N candidates win, drop framework, do not re-iterate.
- **Adversarial design rounds:** 3 minimum for MAJOR cycles, even with strong consensus.
  Red Team kolo discovered F1 mandatory CRASH error in v3.3.1 — the iteration paid for itself.
