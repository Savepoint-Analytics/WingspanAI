# Resource-Spending Ablation: the Third Null

Status: complete, 2026-09-04. **Correctness fixes retained; no measurable effect
on play.**

## Design

`VALUE_RESOURCE_SPENDING` on versus off. Five-agent roster, seeds 1-10,
`control` setup, full seat counterbalancing, five 2-seed chunks, **200 games per
arm**. Arms ran sequentially. Zero chunk failures.

The switch covers three changes:

- Wild and choice food costs paid by replacement cost (need over die
  probability) instead of `BASE_FOOD_TYPES` declaration order.
- Eggs taken from positions feeding the fewest active scoring conditions instead
  of `Habitat` enum order.
- Discards ranked on bonus fit, habitat room, affordability and then points
  instead of printed points alone — shared by four call sites.

The teal-trigger fix shipped alongside but is **not** in this contrast: the core
set has zero teal birds, so it cannot affect base-game play either way.

## Result

| Agent | Win on | Win off | Delta | p | Score delta | p |
|---|---:|---:|---:|---:|---:|---:|
| `archetype_bonus_card_focus` | 0.575 | 0.500 | +0.075 | 0.343 | +1.27 | 0.629 |
| `archetype_engine_builder` | 0.600 | 0.588 | +0.012 | 0.873 | +0.20 | 0.915 |
| `greedy_immediate` | 0.237 | 0.287 | -0.050 | 0.474 | +0.67 | 0.810 |
| `net_value_response` | 0.362 | 0.463 | -0.100 | 0.199 | -1.31 | 0.584 |
| `potential_points` | 0.750 | 0.713 | +0.037 | 0.595 | -0.01 | 0.995 |

Pooled average score: **59.39 on vs 59.22 off, delta +0.17 (p=0.886)**.

### A pre-registered check that held

`net_value_response` read 0.356 in the on-arm against 0.463 in the previous run,
and that gap was flagged **before** the off-arm finished as probably noise. The
paired contrast puts it at -0.100 with p=0.199 — not significant. Recording the
prediction ahead of the data is what makes that readable as noise rather than as
a result.

## The pattern is now the finding

Three faithful modelling improvements, three nulls:

| Change | Real gap closed? | Effect on play |
|---|---|---|
| Mat-scaling habitat valuation | yes | null |
| Feeder odds and six-face die | yes | null (p=0.993) |
| Resource-spending selection | yes, incl. a scoring bug | null (p=0.886) |

Each closed a genuine gap between simulator and game. None made the agents
stronger. One of them fixed an outright scoring defect — eggs spent in enum order
could take the very egg a round goal was counting — and even that did not move
the result.

At one null this was a weak signal; at three it is the most substantive strategic
result the project has. **These heuristic agents are not limited by the fidelity
of their resource valuation.** Adding domain knowledge to the evaluation function
has stopped being a defensible default, and further fidelity work should be
justified on correctness grounds alone.

The alternative hypothesis has not been tested: that strength lives in **search
depth, opponent modelling, or the structure of action selection** rather than in
what the agent knows about a resource. That is now the highest-value experiment.

## Caveats

- Detection limit at 200 paired units per arm is roughly 1.9 points
  (`seat_effect_power_analysis.md`). An effect below that would not be visible
  here. The pooled delta is +0.17, well inside noise, so this bounds the effect
  as small rather than proving it zero.
- All three ablations used the same five-agent roster at two players. A term that
  matters only at higher player counts, or against different opponents, would not
  show up.
- The switches stay `True`. The changes are more faithful than what they replaced
  and cost nothing; they are retained on correctness grounds and should not be
  described anywhere as improvements to play.
