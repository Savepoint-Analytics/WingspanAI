# Registered arm: `reroll_penalty` — 2026-09-30

Registered **before launch**, with the power stated up front as the 2026-09-25
rule requires.

## Where this came from, and how weak the prior is

A near-tie sub-slice. Among 2,045 archived near-tie decisions, 29 had the
champion valuing "take this food" and "reroll the feeder, then take" within 0.2
points of each other. Declining the reroll realized **+2.397** (23/29 positive,
SD 3.30, CI [+1.20, +3.60], exact-t p=0.00053).

Three things make this a weak prior, and they are recorded here so the arm is
not over-read whichever way it lands:

1. **It is an unregistered post-hoc slice.** The near-tie registration covered
   the by-pair table at `action_type` granularity. Splitting `gain_food` vs
   `gain_food` into sub-decisions afterwards is the move that produced two
   findings that died this week, which is why this needs its own arm rather
   than a ledger row.
2. **n = 29**, with a cell detection limit of 1.71 points.
3. **The mechanism I first proposed is falsified.** I expected "the evaluator
   prices an uncertain outcome by its mean and overrates it". It does not: the
   reroll resolves deterministically inside `apply_action` from
   `random_seed : global_turn : salt`, and applying the same reroll action five
   times from the same reconstructed state gives one outcome, verified on six
   real archived decisions. **The search already sees the roll it will get**, so
   this is not a risk-discount and the switch is not a distributional fix.

The surviving candidate mechanism is **horizon**: a reroll re-randomises the
feeder for the player's own later turns and for every opponent, and a
short-horizon evaluator books the immediate food without that downstream cost.
That is consistent with the established finding that the round is the unit of
planning. It is a hypothesis, not a measurement, and this arm does not test it —
the arm tests the *effect*, agnostic about why.

Also relevant and not encouraging: **feeder-odds valuation has already measured
null three times** (+0.5, −0.1, +0.2). Pricing the birdfeeder better has a track
record of not paying here, even though discounting the reroll *option* is a
different intervention from pricing the odds.

## The switch

`reroll_penalty: float = 0.0` on `PotentialPointsSearchConfig` and the agent.
Subtracts a flat penalty from any root action with `reroll_birdfeeder=True`,
**only when a non-reroll action is also legal** — with no alternative the penalty
shifts every candidate equally and changes nothing, and the feeder is rerolled
anyway when empty. Applied through the same per-action adjustment vector as the
denial term, so it affects both the search and one-ply paths.

**Arm value: 2.0**, chosen close to the measured +2.4 margin bias. One value
only; a sweep follows if and only if this arm is positive.

## Design

- 2p, **seeds 1–20 × 4 opponents × 2 rotations = 160 games per side**, both
  sides fresh at the same commit. Not paired against the existing
  `rr_goal_placement`, which covers only **10 decks** — too few for a
  deck-clustered read after the 2026-09-25 audit.
- 20 decks, 8 games a deck.

## Power, measured rather than assumed

The flip rate was measured on the 80 archived baseline games before registering:
of 2,080 ranked champion decisions, 77 (3.7%) had a reroll as the best option,
and **48 of those had a non-reroll alternative within 2.0** — so a 2.0 penalty
flips about **0.60 decisions a game**, and only **38 of 80 games** contained any
flip at all. Roughly **47% of games will be bit-identical**, which cuts the
paired variance well below the usual 10.5 per-game SD; the estimate below uses
SD 6.5, anchored on `rr_opener_v2`, an arm with a comparable identical-game
share.

| | expected effect | detection limit at 80% power |
|---|---:|---:|
| all 160 games | **+1.44** (if the full +2.4 a flip transfers) | **1.44** |
| all 160 games | +0.72 (if half transfers) | 1.44 |
| differing games only (~84) | +2.74 | 1.99 |

The arm is therefore **marginal by construction**, and the registration says so
rather than pretending otherwise: it can resolve the optimistic effect and
cannot resolve the pessimistic one.

## Decision rule

**Primary — all 160 games, paired, deck-clustered p reported alongside:**

- **Δ ≥ +1.5 at p < 0.1 → adopt**, and run a penalty sweep.
- **Δ ≤ −1.5 → drop**, and record the nomination as refuted.
- **−1.5 < Δ < +1.5 → the arm cannot resolve it.** The nomination is recorded as
  *untested at this budget*, **not** refuted. Resolving ±0.7 would need ~640
  games, which is the decision to take at that point.

The threshold is set at the detection limit deliberately. Three arms this month
registered bands narrower than their samples could resolve; setting +1.5 against
a 1.44 limit keeps this one answerable.

**Secondary, pre-specified — differing games only.** Membership is determined by
the switch (whether it flipped a decision), not by the outcome, so this is a
legitimate subset on the same logic as the holdout-free reads. Expected +2.74
against a limit of 1.99. Report both; if the primary is inconclusive and this is
positive at p < 0.05, that is a **nomination for a 640-game arm**, not an
adoption.

**Holdout.** If adopted, `Holdout("reroll_penalty", 0.0)` enters
`DEFAULT_HOLDOUTS` so the losing side survives in 5% of future games.

## Honest prior

I expect this to land inconclusive. The effect is capped near the detection
limit, the prior comes from 29 decisions, the mechanism I proposed is falsified,
and the nearest prior work is null three times over. The reason to run it anyway
is that it is cheap (~1 hour) and the alternative is leaving a p=0.0005 slice
unexamined in the ledger, which is how the audit's two ghosts got in.

## Results

_Pending. Report the realized n, the identical-game share, the realized paired
SD and detection limit, and the deck-clustered p, so the power claim above can
be checked rather than trusted._
