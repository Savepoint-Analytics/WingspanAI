# Ledger audit, 2026-09-25

Two reading errors surfaced in two questions (deck clustering, then the
per-opponent multiplicity surface), so every claim was re-read through the
lenses now known to be unreliable. A third error turned up during the audit.
Nothing here is a new experiment; it is the same games, read correctly.

## Error 3, found by the audit: p-values used a normal approximation

`arm_contrast.paired_test` computed `erfc(|t|/sqrt(2))` — the normal
approximation to the paired t. At n=80 that is harmless (0.073 → 0.076). At
n=5, which is what a 3p arm becomes when read by deck, it is not: it reported
**p=0.001 for what is really p=0.028**. Replaced with an exact two-sided
Student t (incomplete beta, verified against textbook critical values at
df=4, 14 and 79). Every p below is exact.

## Lens 1 — deck clustering, all 3p rows

| contrast | Δ | per-game p | deck p | design effect | change |
|---|---:|---:|---:|---:|---|
| greedy − belief | +2.12 | 0.076 | **0.304** | 2.29 | much weaker |
| oracle − belief | +1.36 | 0.181 | **0.028** | 0.16 | **promoted from null** |
| `belief_apply` − belief | −0.48 | 0.208 | 0.432 | 2.08 | unchanged (null) |
| competent − belief | +0.13 | 0.906 | 0.917 | 1.12 | unchanged (null) |
| placement, 5 decks | +1.12 | 0.131 | 0.343 | 1.98 | weaker |
| placement, 15 decks | +1.12 | 0.189 | 0.216 | 1.04 | unchanged |

**The 3p greedy claim no longer rests on the roster arm.** Recorded as
"+2.12 (p=0.073), suggestive", it is p=0.304 once its five decks are
respected. What carries the conclusion is the *mirror* replication: +1.89 on
30 decks, deck p=**0.038**, design effect 0.69. The finding stands; its
evidence is the self-play arm, and the ledger should say so.

**The oracle row is promoted from null to worth an arm.** Recorded as "+1.36
(p=0.18), null, consistent with the greedy result." Its five per-deck means
are +2.50, +1.78, +0.56, +0.33, +1.61 — all positive, between-deck SD 0.90
against within-deck SD 9.57, so the deck-level test is *more* powerful than
the per-game one (design effect 0.16) and gives p=0.028. Caveats that keep
this from being a finding: five observations, and it is one of six rows
tested here, so it does not survive Bonferroni across the audit itself. It
deserves its own pre-registered arm on 15+ decks.

Self-play rows all hold: A3 denial −5.94 (deck p<0.001), A2 greedy 2p null
both ways, A2 greedy 3p significant by deck.

## Lens 2 — multiplicity

The per-opponent cells are recorded in the ledger's own section. The two
card/pair studies came out better than feared, because both pre-registered a
hypothesis per unit rather than picking cells afterwards:

- **Layer C forced play** tested three pre-registered pairs with a predicted
  band each. P3 (−3.38, p=0.005) survives Bonferroni across the three;
  **P2 (+3.48, p=0.021) does not** (α=0.0167). P2 was followed up on the
  searching pursuer and came back null (−1.67), which the ledger already
  records — so the correct summary is "one of three pairs, and it did not
  transfer", not "+3.48 confirmed".
- **Bonus-card keep** reports pooled *classes*, not cherry-picked cards, and
  ran a replication. Per-bird +3.25 (p=0.009) survives α=0.05/3; tiered
  −1.25 (p=0.043) does not. The doc already says which parts replicated.

## Lens 3 — holdout-set mismatch, and it is bigger than estimated

An arm carrying standing holdouts its baseline lacks is charged for them. I
estimated 0.1–0.4 points. Measured, by re-reading each arm on only the games
where **no** holdout fired on either side (the draw is a deterministic
function of seed, lineup and position, so this conditions on a
pre-determined, outcome-independent subset):

| arm vs `rr_belief_opp` | all 80 games | 64 holdout-free games | shift |
|---|---:|---:|---:|
| **2p placement goal model** | +0.41 (p=0.69) | **+1.44 (p=0.20)** | **+1.03** |
| production config at 5 s | −0.59 (p=0.63) | **+0.00 (p=1.00)** | +0.59 |
| beam pre-ranking | −0.72 (p=0.55) | **−0.16 (p=0.91)** | +0.56 |
| competent opponent model | −0.72 (p=0.48) | −0.66 (p=0.58) | +0.06 |

The bias is **systematically against the arm** and of order half a point to a
point — two to three times my estimate. Three consequences:

1. **The 2p placement arm supports the adoption after all.** Recorded as
   +0.41 and "below the adoption bar"; read like-for-like it is **+1.44**,
   above the +1 bar. With the 15-deck 3p arm at +1.12, both player counts now
   point the same way at about the same size.
2. **The production configuration is free, not −0.6.** On a like-for-like
   comparison it is +0.00. The shipped agent costs nothing in strength for
   its 7× latency reduction.
3. **Beam pre-ranking was dropped as the unbudgeted default on −0.72**, which
   is −0.16 read correctly. That decision should be revisited.

## Net effect on the project's conclusions

| claim | before the audit | after |
|---|---|---|
| placement goal model worth ~+1 | adopted, unconfirmed, 2p looked null | **2p +1.44, 3p +1.12** — better supported, still not individually significant |
| production config costs −0.6 | a small price for 7× latency | **costs 0.00** |
| opponent model worth ~2 at 3p | roster arm p=0.073 | roster arm p=0.304; **carried by the mirror arm** (p=0.038) |
| oracle-type model is null | null | **p=0.028 by deck; needs its own arm** |
| layer C P2 pair +3.48 | "positive" | does not survive its own family; follow-up null |
| pre-ranking costs −0.72 | not adopted as default | −0.16; decision worth revisiting |

Nothing reverses. Two decisions are better supported than recorded, two
findings are weaker, and one dismissed row needs an arm.

## What changed in the tooling

- `arm_contrast.paired_test` uses an exact t distribution.
- `arm_contrast` already reports deck count, deck-clustered p and design
  effect, and flags a design effect above 1.3.
- Standing rules added: match the baseline's holdout set; do not read a
  single per-opponent cell; report the deck-clustered p for any arm whose
  design effect exceeds 1.3.
