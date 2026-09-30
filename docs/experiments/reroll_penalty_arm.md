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

**Caveat on what the switch actually does.** Probed on 17 archived
reroll-eligible decisions, the penalty changed 4 of them. One was the intended
case (`Gain rodent if rolled, after rerolling` -> `Gain rodent`), but two pushed
food-gaining below a different action type entirely (`-> Draw tray cards 2`, and
`-> Gain seed and fish by discarding a card`). So a flat penalty is broader than
"decline the reroll": it can demote food-gaining altogether. That is a fair
consequence of the intervention, but it means a positive result would not
localise cleanly to the near-tie finding, and a negative result could be a
penalty that is simply too blunt rather than a refutation of the nomination.

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

## Results (2026-09-30)

### The delivered design is not the registered one, and that is my error

Registered: 160 games over 20 decks. **Delivered: 80 games over 10 decks.**
`analysis/launch_arm.py --seeds 1-20` was silently ignored because, as its own
help text says, *"2p roster arms always use seeds 1-10"*. I registered a design
the launcher cannot produce for this arm type and did not check the dry-run's
game count before committing the registration -- the dry run was verified only
to the extent that it wrote its scripts.

The consequence matters: the realized detection limit is **1.82**, which is
*above* the registered +1.5 adopt threshold. So the delivered arm could not
reliably detect its own adoption criterion. That is the fourth registration this
month to outrun its sample, and the first where the cause was a tooling
assumption rather than an optimistic variance estimate. **Standing addition to
the 2026-09-25 rule: verify a dry run's game count against the registered n
before launching, not just that it wrote its scripts.**

### Reads

| read | n | Δ | p | SD | limit | 95% CI |
|---|---:|---:|---:|---:|---:|---|
| **primary, all games** | 80 | **−0.388** | 0.553 | 5.81 | 1.82 | [−1.66, +0.89] |
| by deck | 10 decks | −0.388 | 0.501 | — | — | — |
| secondary, differing games only | 41 | −0.756 | 0.556 | 8.15 | 3.56 | [−3.25, +1.74] |

**Verdict by the registered rule: the middle zone. Not adopted, not refuted --
"untested at this budget".** The point estimate is mildly *negative*, the
opposite sign to the nomination's prediction.

The power model held up well, which is worth recording because the last three
arms' did not: predicted 47% identical games against **49%** delivered, and
predicted SD 6.5 against **5.81**.

### What the arm does and does not settle

**It refutes the strong form of the nomination.** The CI's upper bound is +0.89,
which excludes both the registered +1.5 threshold and the +1.44 the nomination
predicted if the measured +2.40 a flip transferred. So **the +2.40 per near-tie
decision does not transfer to whole-game score.** That is a real, if narrow,
conclusion.

**It does not resolve** anything between −1.66 and +0.89, so a small positive
effect remains possible, as does a small harm. The point estimate leans harm.

**Why the near-tie effect probably did not transfer.** Two candidates, neither
tested: the flat penalty is too blunt -- probed beforehand, 2 of 4 flipped
decisions demoted food-gaining below a different action type entirely rather
than just declining the reroll, so the switch buys the near-tie gain and pays an
unrelated cost; or the near-tie +2.40 was itself a small-sample artifact, which
29 decisions cannot exclude.

### What would settle it, and whether it is worth it

At the realized SD of 5.81, resolving ±0.7 needs **540 games** and ±1.0 needs
265. A 2p roster arm caps at 80 (seeds 1-10 × 4 opponents × 2 rotations), so
this needs mirror mode, which does accept `--seeds`: 540 games is 270 seeds × 2
rotations.

**Recommendation: do not spend it.** The prior was 29 post-hoc decisions, the
mechanism I proposed is falsified, the nearest prior work is null three times
over, the point estimate is negative, and the strong form is now excluded. A
540-game arm to chase a possible sub-point effect of the wrong sign is a poor
trade against the human games or the expansion work. Recorded as closed on cost
grounds, with the nomination noted as untested below ±0.9 rather than refuted.

If it is ever reopened, the better intervention is not a flat penalty but
pricing the post-reroll feeder state for the player's own later turns -- the
horizon mechanism -- which would test the actual hypothesis instead of a blunt
proxy.
