# Reroll Chance Node: Making Feeder Rolls Unknown Before They Happen

Status: complete, 2026-09-06
Code: `b33a5e1` (clean tree; recorded in every manifest)
Artifacts: `artifacts/rr_reroll_fix/`, mirrored to object storage
Baseline: `artifacts/rr_det_d3_f8_k4/` from
[determinized_search_test.md](determinized_search_test.md)

## The defect

Until this change the legal-action generator rolled the birdfeeder *while
enumerating* gain-food actions. When a reroll was allowed, every "reroll, then
take X" action carried the dice that the reroll would produce, because the
roll is a deterministic function of `random_seed` and the turn number. Every
agent in the roster therefore chose "reroll" already knowing the outcome, and
the determinized search could not resample the seed without making the true
state's actions illegal on the sample
([determinized_search_test.md](determinized_search_test.md), "Residual leak").

In the determinized depth-3 baseline a reroll was on offer on 29% of turns and
`potential_points` took one on 5.9% of its turns (123 of 2080); the archetypes
took one on 8–11%. Each of those choices was made with the result in hand.

## The fix

Rolls now happen when the action is applied, not when it is listed.

- A gain-food action names its foods exactly when the feeder shows enough dice
  to serve it. When a reroll or a mid-action refill would intervene, the
  action instead names a *preference*: one ordered multiset of base foods
  (5 / 15 / 35 / 70 preference actions for 1–4 food). `apply_action` rolls the
  feeder, takes the first obtainable preferred food, and falls back to the
  hand's food needs when nothing preferred came up. Rerolls that happen because
  the feeder ran dry mid-action are recorded the same way.
- Roll salts are unchanged (`legal_{n}`, `gain_food_action_{food}`), so every
  archived game still replays to its recorded state hashes.
- `determinize_state` now resamples `random_seed` as well as the hidden cards.
  Feeder rolls, predator hunts and pink-power reactions all derive from it, so
  the search sees a reroll as a chance node whose outcome differs across the
  four samples.
- `expected_gain_food` gives the non-searching agents the expected value of a
  preference action: on-table foods count in full, rolled foods at the
  probability that at least the needed number of five dice show them.

Rules detail is in [../rules/birdfeeder_dice.md](../rules/birdfeeder_dice.md),
"When the dice are rolled".

## Design

Same 200-game counterbalanced design, same roster, same seeds, same
`potential_points` configuration as the baseline (depth 3, every turn,
K=4). This is a rules-engine change, so **every agent's games can differ**
from the baseline, not only `potential_points`' 80: the greedy and archetype
agents now pick rerolls on expected value, and any turn on which a reroll was
offered can diverge. The contrast is therefore engine-vs-engine on paired
seeds, not an agent ablation. Games in which no agent ever chose a reroll are
expected to be identical.

## Results

Paired by lineup, rotation and seed, n = 80 games per agent. 19 of the 200
games were bit-identical to the baseline; the other 181 diverged at some
reroll decision.

| Agent | Score base → arm | Δ score | p | Win base → arm | Δ win | p |
|---|---:|---:|---:|---:|---:|---:|
| `potential_points` | 79.40 → 79.09 | −0.31 | 0.689 | 0.900 → 0.906 | +0.006 | 0.870 |
| `archetype_bonus_card_focus` | 63.33 → 63.55 | +0.23 | 0.741 | 0.537 → 0.519 | −0.019 | 0.624 |
| `archetype_engine_builder` | 62.19 → 61.33 | −0.86 | 0.410 | 0.537 → 0.475 | −0.062 | 0.146 |
| `greedy_immediate` | 48.48 → 49.10 | +0.62 | 0.508 | 0.212 → 0.206 | −0.006 | 0.783 |
| `net_value_response` | 55.89 → 55.99 | +0.10 | 0.922 | 0.312 → 0.394 | +0.081 | 0.024 |

No agent's score moved. `net_value_response`'s win share rose 8 points at
p=0.024 with its score unchanged; with ten tests in the table and no matching
score movement, that is treated as noise until it reappears. Per opponent, no
`potential_points` cell moved by more than 0.9 points (all p > 0.5).

### Knowing the roll was worth nothing

The determinized search now averages the reroll over four sampled outcomes
instead of reading one, and it scored −0.31 (p=0.69) for it. The leak was
real but the decisions it touched were cheap: a reroll is usually taken when
the feeder holds nothing useful, and in that spot most outcomes are an
improvement. Combined with
[determinized_search_test.md](determinized_search_test.md), every known
hidden-information leak in the search agent is now closed and its
**+10.4-point, 0.90-win-rate result stands on a leak-free engine.**

### Rerolls fell by roughly half

| Agent | Reroll chosen, per turn (base → arm) | Turns with a reroll on offer |
|---|---:|---:|
| `potential_points` | 5.9% → 3.7% | 28.9% → 26.9% |
| `archetype_engine_builder` | 10.9% → 5.0% | 30.6% → 25.6% |
| `archetype_bonus_card_focus` | 8.3% → 3.3% | 30.1% → 23.2% |
| `greedy_immediate` | 7.8% → 5.8% | 29.3% → 27.3% |
| `net_value_response` | 3.5% → 1.4% | 30.1% → 25.4% |

Every agent rerolls less once it cannot see the result, the archetypes most of
all: their old rate was inflated by rerolls that were only chosen because the
outcome was known to be good. Fewer rerolls also leave fewer dice on the
table, so the reroll is offered less often. Gain-food frequency is unchanged
(`potential_points` 20.6% → 20.3%).

### Composition and action mix

`potential_points`, per game: bird 35.67 → 35.94, bonus 5.75 → 5.71, round
goal 15.70 → 16.04, egg 13.07 → 13.11, cached food 3.66 → 3.38, tucked
5.54 → 4.91. Action mix: draw 24.3% → 23.8%, food 20.6% → 20.3%, eggs
26.7% → 27.5%, bird 28.4% → 28.4%. Nothing here is outside seed noise.

## What changes

- The rules engine resolves feeder rolls at apply time; every future batch
  runs on this engine, and `artifacts/rr_reroll_fix` is the new baseline for
  `potential_points` at the default configuration (79.09, win 0.906).
- Archived runs before `b33a5e1` were played with reroll outcomes visible.
  Their conclusions are unaffected — this test shows the knowledge was worth
  nothing measurable — but their action logs overstate reroll frequency by
  about 2×.
- `determinize_state` resamples the seed, so any future search or rollout
  agent built on it sees predator hunts and pink reactions as chance nodes
  too.

## Caveats

- Non-searching agents still evaluate candidate actions by applying them to
  the true state, which resolves the roll from the true seed. Their one-ply
  feeder peek is a smaller version of the old leak; `expected_gain_food` is
  used for their food-need scoring but not for the apply-and-score path.
- Preference actions enlarge the action set: a player with four forest birds
  and a dry feeder sees 70 gain-food actions plus rerolls, and in one probe
  game a single `potential_points` decision over 107 legal actions took over
  five minutes. Collapsing near-duplicate preferences inside the search is the
  obvious follow-up.
- One roster, two players, as with every result in this series.
