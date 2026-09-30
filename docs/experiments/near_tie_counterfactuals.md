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

## Results, first collection (2026-09-29)

230 games from the placement-default roots, epsilon 0.2, two determinized
samples. **2,045 near-tie decisions across 90 games** (only 90 of the 230 games
carried a champion seat with ranked decisions).

**The registration was answerable as committed.** Delivered n = 2,045 (floor was
1,400) and SD = 4.88 (ceiling was 5.5), so the power claim holds rather than
needing to be trusted. The realized detection limit is **0.302** against the
0.25 predicted, because the SD came in at 4.88 rather than the assumed 4.0 —
which sits a hair *outside* the band's 0.3 half-width, so the power margin is
thinner than registered and the confirmation below rests on the confidence
interval rather than on the limit.

### Primary: indifference confirmed

| | value |
|---|---|
| mean realized delta | **+0.062** |
| p | 0.565 |
| 95% CI | **[−0.149, +0.273]** |
| registered band | −0.3 to +0.3 |

The whole interval sits inside the registered band, which is the strong form of
the result: this is not a failure to reject, it is a positive finding of
indifference. **Where the searching agent says two options are within a hair, it
is right — its tie-breaking carries no recoverable signal.**

A third of near-ties (688 of 2,045, **33.6%**) end with *exactly* zero realized
difference: both branches converge to the same final score. Those decisions do
not merely look close, they are genuinely inert.

### Secondary: no per-pair finding, two nominations

Sixteen pairs reached n ≥ 20, not the ~10 the registration anticipated, so the
true Bonferroni threshold is **0.0031** rather than the registered 0.005. Under
either, **nothing qualifies as a finding.** The two smallest p-values, recorded
as nominations for their own arms and not as results:

| pair | n | realized Δ | p | note |
|---|---:|---:|---:|---|
| `play_bird` chosen over `draw_cards` | 63 | **−1.508** | 0.024 | mechanistically plausible: over-eagerness to play a bird when drawing is equally valued. n=63 cannot detect anything under ~1.4, so this is at the edge of what the cell could ever show |
| `gain_food` vs `gain_food` | 393 | +0.434 | 0.051 | which food to take; the largest cell to show any signal |

Neither is quotable. The first is the more interesting one and the cheaper to
test: a registered arm that biases the evaluator's `play_bird` versus
`draw_cards` tradeoff at the margin.

### What this does and does not settle

**Settles:** there is no free ≥0.3 points sitting in the evaluator's
tie-breaking, so tie-break tuning is not a productive direction. That closes a
line of work cheaply, which is the main value here.

**Does not settle:** effects smaller than ~0.3 points; effects confined to
contexts too rare to power in 2,045 decisions; and anything about the
*continuation* policy, since both branches were rolled out by the same cheap
one-ply agent. A stronger continuation could surface differences this design
averages away — the project has already measured that two-ply search is worth
−10.4 points, so continuation strength is not a monotone dial and a re-run at
greater depth is not obviously more truthful.

**Available but not run:** the collected rows carry `chosen_final` and
`runner_up_final` from identical states, so the spread of realized outcomes is a
direct measure of outcome variance. That makes this dataset a cheap pre-test for
a distributional/risk-aware evaluator — the question being whether realized
deltas at near-ties correlate with a variance proxy. Unregistered, so it would
be exploratory and nomination-only.
