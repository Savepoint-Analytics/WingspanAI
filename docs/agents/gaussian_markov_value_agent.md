# Gaussian-Markov Value Agent

Status: assessed 2026-09-28, **not built**. One blocker, named below.

## The question

Asked whether a "Gaussian Markov chain agent" is worth building for Wingspan.
Three readings are possible; two are dead on this project's own evidence.

| Reading | Verdict |
|---|---|
| **Kalman filter tracking opponents' hidden state** | **Dead.** Perfect opponent-type knowledge measures **+0.00 (p=1.000)** over 90 paired 3p games, and +0.24 at 2p. A filter cannot beat the oracle it approximates, and the oracle is worth nothing. |
| **A Gaussian Markov random field over bird/board synergies** | **Discouraging.** The nearest prior attempt, the engine-potential mechanic-pair term, measured **−4.51 (p=0.001)**, and a board-only variant +1.31 (p=0.17), not adopted. |
| **A round-indexed linear-Gaussian forecast of final score, used as a distributional leaf evaluator** | **The live one.** Specified below. |

## Why the third one is interesting: score gains do not convert to wins

The argument is not theoretical. It is a pattern already in the ledger:

| arm | Δ score | Δ win |
|---|---:|---:|
| oracle opponent model, 3p | +0.00 | +0.011 |
| greedy opponent model, 3p mirror | **+1.89** | **−0.011** |
| greedy opponent model, 2p mirror | +0.46 | −0.006 |
| placement goal model, 3p | +1.12 | +0.037 |
| denial term | −5.94 | −0.156 |

`evaluate_state_potential` returns a **scalar**. The agent therefore cannot
express the most basic piece of real Wingspan strategy: when ahead, take the
low-variance line; when behind, take the gamble. A distributional evaluator can,
and it optimises the objective that actually decides games.

## And the regime where it would matter

| regime | mean winning margin | games within 5 points |
|---|---:|---:|
| vs the weak roster (2p) | 24.8 | 13.8% |
| **champion vs champion (2p)** | **12.4** | **30.3%** |

Outcome noise from an *identical* state is SD 4.88 (measured over 2,045 near-tie
rollouts). So against a peer the noise is the same order as the deciding margin
in about a third of games, while roster games are mostly blowouts. **The upside
is capped by that ~30%**, and is worth approximately nothing against the roster —
which is also a caution against reading roster win rates as skill.

## Specification

Per player, a continuous summary state at each round boundary — not the full
game state:

    x_r = [score_so_far, birds_in_play, egg_capacity_left,
           food_rate, egg_rate, card_rate, tuck_rate, cache_rate,
           bonus_progress, goal_progress]

Transition, **round-indexed**:

    x_{r+1} = A_r x_r + b_r + eps,    eps ~ N(0, Q_r)

Then:

    own final ~ N(mu_me, s2_me);  opponent ~ N(mu_opp, s2_opp)
    P(win) = Phi( (mu_me - mu_opp) / sqrt(s2_me + s2_opp - 2*cov) )

**Decision rule: maximise P(win), not expected score.**

Fit `A_r, b_r, Q_r` by least squares or EM on archived round transitions.

## Design constraints that are not optional

1. **`A_r` must be round-indexed.** Four rounds of 8/7/6/5 turns is
   non-stationary by construction; a single stationary `A` is wrong.
2. **The covariance term is mandatory.** The tray, birdfeeder and round goals are
   shared, so outcomes are correlated; dropping `cov` makes P(win) overconfident.
3. **Round goals stay out of the Gaussian.** Placement is a rank/max statistic on
   counts — violently non-Gaussian. Keep the existing Poisson placement model
   (`round_goal_placement_model.md`) and feed its expected points in as a term.
4. **Scoring is end-loaded.** Bonus cards and goals settle at the end, so final
   score is not smooth accumulation. Model engine state with the chain and use a
   separate terminal emission for bonus/goal points.
5. **The model must never select actions, only evaluate leaves.** Hard
   constraints — "cannot play this bird without two fish", egg capacity, habitat
   slots — are inexpressible in linear dynamics. The rules engine enumerates
   legality; this replaces the scalar at the leaf.
6. Integer, non-negative, bounded scores make the tails wrong. Acceptable:
   decisions turn on the middle of the distribution.

## The blocker

**Per-round score snapshots are not emitted.** `kpi_taxonomy_findings.md` already
flags this: "cumulative score by round and per-round delta need a score snapshot
at each round end, which is not emitted." A Markov chain over rounds cannot be
fit without round states.

Fix: emit a feature-vector snapshot at each round boundary. Small emitter; makes
every future game yield four transitions. It applies to future games only — the
archive could be partially reconstructed by replay, which is more work.

## How to test it, if it is built

**Pre-test the premise first, at near-zero cost.** The near-tie rows
(`artifacts/near_ties/placement_default.jsonl`) carry `chosen_final` and
`runner_up_final` from identical states, so they already measure outcome variance.
If realized deltas at near-ties do not correlate with a variance proxy over ~2,000
natural experiments, the distributional objective probably will not pay.

**Register the win-rate band, not the score band.** The whole mechanism is
converting score into wins, so a score-band registration would declare it null by
construction. Win rates need far more games than score deltas for the same power,
so compute that limit before launching — rule 1 of the standing registration rules
in `results_ledger.md`.

## Honest prior

≈0 on score, small positive on win rate, concentrated in the close-margin third of
peer games. Ranked below the human-trace study and the European expansion as of
2026-10-02.
