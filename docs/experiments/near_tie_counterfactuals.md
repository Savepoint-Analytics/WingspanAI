# Near-tie counterfactuals: design and pre-registration

Registered **2026-09-29, before the first collection was read.** Written this way
deliberately: the last two "findings" this project produced by re-slicing
existing data both evaporated under a pre-registered arm, and this instrument
can generate dozens of testable claims an hour. The registration below is what
makes any of them quotable.

## The idea

At every decision the searching agent records its own ranked valuation of the
candidates (`agent_decision_summary.search_ranking.top`, up to 8 entries with
values). When the top two are within a hair, the agent is **indifferent**, and
which one won was settled by noise in its own estimate. Those decisions are
naturally occurring randomised trials.

Measured over 400 archived games before designing this: **33% of ranked champion
decisions have a top-two margin within 0.2 points**, and the median margin over
all ranked decisions is 0.47. The most common tied pairs are same-type choices —
which card to draw, which food to take, which bird to lay on — which is exactly
the "could have gone either way" case this is meant to study.

For each near-tie: rebuild the state, verify it against the logged
`state_hash_before`, then roll the chosen action and the runner-up to the end of
the game under **identical continuation policies and identical determinized
worlds**, and record `realized_delta = chosen − runner_up`.

## What the sign means

| | reading |
|---|---|
| **> 0** | the agent's preference among options it calls a tie still carries real signal; its tie-breaking beats a coin flip and its reported margin understates what it knows |
| **= 0** | genuine indifference; nothing is on the table at this margin |
| **< 0** | the tie-breaking is actively harmful — among near-ties it takes the worse branch |

## Registration

**Primary hypothesis.** Overall `realized_delta` across all near-ties is zero:
the agent is genuinely indifferent where it says it is.

**Band: −0.3 to +0.3 confirms indifference.** Outside that, the tie-breaking is
informative (positive) or harmful (negative).

**Power, stated up front** — required by the standing rule earned on
2026-09-25, after three arms in a row registered bands their samples could not
resolve. At an assumed per-decision SD of 4.0 and an expected n of ~2,000
near-ties from 230 games, the standard error is 0.089 and the **detection limit
at 80% power is 0.25 points**. The ±0.3 band clears that limit, so this
registration is answerable. If the delivered n is below ~1,400 or the SD above
5.5, the limit exceeds the band and the primary read must be reported as
underpowered rather than quoted.

**Secondary, by tied action-type pair.** This is where an actionable finding
would live: a non-zero delta for one pair (say `play_bird` chosen over
`lay_eggs`) while others sit at zero means the evaluator mis-prices that
tradeoff at the margin, which is tunable.

This table is a **multiplicity surface** and is registered as such, because the
2026-09-25 audit's ~95 unadjusted per-cell reads produced two findings that both
died. Expect ~10 pairs with n ≥ 20. **Bonferroni at 10 tests: a pair is a
finding only at p < 0.005.** Anything between 0.005 and 0.05 is a nomination for
its own arm, never a result. Per-cell detection limits at that threshold:

| pair n | limit at p<0.05 | limit at p<0.005 |
|---:|---:|---:|
| 400 | 0.56 | 0.70 |
| 200 | 0.79 | 0.98 |
| 100 | 1.12 | 1.39 |
| 50 | 1.58 | 1.97 |

So a pair cell with 50 decisions cannot detect anything under ~2 points, and
small cells must not be quoted at all.

**Config restriction.** The first collection uses only roots running the current
placement-default evaluator (`rr_goal_placement`, `rr3p_goal_place15`,
`rr3p_goal_place25`; 230 games). Mixing roots from different arms would mix
evaluator versions, and "the evaluator's tie-breaking" is not a single object
across them.

## Three limits that belong on every claim from this instrument

1. **The continuation defines the value.** Both branches are played out by the
   same cheap one-ply policy, so a number here means "worth this much to a
   competent non-searching continuation", not "under optimal play". A deeper
   continuation can reverse a small effect. This is the same caveat
   `play_counterfactuals.py` carries and it is not a formality — the project has
   already measured that *deeper* search is worth −10.4 points at two plies, so
   continuation strength is not a monotone dial.
2. **Selection on the state distribution.** The decisions available are the ones
   this agent reached through its own earlier choices. Near-tie filtering removes
   the agent's *preference* from which branch was taken; it does not make the
   states representative of Wingspan. A conclusion is about "this agent's
   trajectory", not the game.
3. **Indifference is measured with the evaluator under test.** If the evaluator
   is blind to a feature it will also be blind to it when judging two options
   close, so near-ties are not a uniform sample of genuinely close decisions.
   This biases toward finding **less** than the true error, which makes a
   positive result more trustworthy than a null.

## Instrument

    python analysis/near_tie_counterfactuals.py artifacts/rr_goal_placement \
        --epsilon 0.2 --continuation-samples 2 \
        --out artifacts/near_ties/placement_default.jsonl
    python analysis/near_tie_counterfactuals.py \
        artifacts/near_ties/placement_default.jsonl --report

Cost measured on this hardware: ~11 s a game undeterminized, ~20 s at two
samples, ~46 s at four. Precision is driven by the number of near-ties rather
than by per-observation noise, so more games at two samples beats fewer at four.

`tests/test_near_tie_counterfactuals.py` pins the selection logic. The case
worth knowing about: **the chosen entry is flagged, not assumed to be first.**
The agent breaks ties on a secondary key and an action priority, so the
top-valued candidate is not always the one taken, and reading `top[0]` as
"chosen" would silently flip the sign of `realized_delta` on exactly the
decisions this instrument exists to study.

## Results

_Pending the first collection. Fill in against the registration above, and state
the delivered n and SD so the power claim can be checked rather than trusted._
